__author__ = 'belens'
"""
Program seeks to enable ViPR Admin to create hosts in bulk based on a hypothetical
CSV export of an Excel spreadsheet or another report type (maybe ViPR SRM)

Example CLI:
    -f [file name located in same path as the script] -m 1 -full_debug
    -f [file name located in same path as the script] -m 1 -full_debug -register_hosts

Assumptions:
    all hosts will be loaded to the same tenant as username provided (and it must be Tenant Admin)

High level steps:
    1) read in external input data
    2) for each row - issue API call to create a host
    3) for the tenant at hand, report on how discovery of hosts is ongoing
    4) when number of successfully discovered hosts doesn't change, offer to quit.

Executing script AGAIN on same arguments (or when some clusters/hosts/initiators are already in ViPR)
- for discovered hosts the script will update all provided fields (except for Human Host Name - it searches by that, so update would provide the same value back)
- for registered hosts it will use the cluster/hosts it found, and will not register WWNs 2nd time
"""

import argparse
import os
import sys
from vseLib.vseCmn import VseExceptions, vseCmn
from vseLib.VseViprApi import VseViprApi

DEFAULT_ENV_CFG_FILE = r'./env_cfg.ini'
DEFAULT_LOCAL_PATH = os.path.dirname(os.path.realpath(__file__))

#
# required arguments (hosts that get discovered)
#
IDX_H_H_N = 0
IDX_H_N_N = 1
IDX_H_T   = 2
IDX_D_SSL = 3
IDX_D_P_N = 4
IDX_H_U_N = 5
IDX_H_PWD = 6
discover_hosts_headers = 'Host Human Name,Host FQDN or IP,Host Type,SSL,Port,Username,Password'

REG_CLUSTER = 0
REG_H_H_N   = 1
REG_H_N_N   = 2
REG_H_T     = 3
REG_H_WWNS  = 4

REG_WWN_NAME = 0
REG_WWN_PROT = 1
REG_WWN_PWWN = 2
register_hosts_headers = 'Cluster Name,Host Human Name,Host FQDN or IP,Host Type,' \
                         'WWNs Semicolon Separated Keys (Name/Protocol(FC|iSCSI)/WWN;Name/Protocol(FC|iSCSI)/WWN;)'

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="%(prog)s will attempt to either discover or register all hosts from a supplied CSV file. "
                    "There must be separate files for discovery and registration as they require different headers."
                    ">>>>Discovered hosts CSV Headers are: {0}.\n "
                    ">>>>Registered hosts CSV Headers are: {1}\n".format(discover_hosts_headers, register_hosts_headers))

    r_args = parser.add_argument_group('Required Arguments')

    # file
    r_args.add_argument('-file', '-f',
                        required=True,
                        help='Specify name of data file on hosts to be discovered')

    o_args = parser.add_argument_group('Optional Arguments')
    o_args.add_argument('-msg_level', '-m',
                        required=False,
                        default=vseCmn.MSG_LVL_INFO,
                        help='Specify output level: 0-DEBUG, 1-INFO, '
                             '2-WARNING, 3-ERROR.\n INFO is default.')
    o_args.add_argument('-full_debug',
                        action='store_true',
                        required=False,
                        help='Full Debug will cause full output of '
                             'API calls and other extra large objects')
    o_args.add_argument('-register_hosts',
                        action='store_true',
                        required=False,
                        help='If hosts are not discovered but only registered instead,'
                             'the input headers and each line body must change. See description '
                             'of script or error message for how exactly. The script will now load hosts '
                             'but not discover them, as well as follow up with WWN load')

    parser.set_defaults(
        env_settings=DEFAULT_ENV_CFG_FILE,
        default_local_path=DEFAULT_LOCAL_PATH,
        msg_level=vseCmn.MSG_LVL_INFO,
        full_debug=False,
        register_hosts=False)

    return parser.parse_args()


def main():
    # deal with cmd line and init file arguments
    # initialize cmn module for logging and else.
    args = parse_arguments()

    # Initialize environment, if any errors - quit gruesomely
    try:
        cmn = vseCmn(
            "ViPR Load Hosts from {0}".format(args.file),
            int(args.msg_level),
            args,
            logging_mode=vseCmn.SESSION_BASED,
            logging_value=None,
            full_debug=args.full_debug)

    except VseExceptions.VSEInitExc as e:
        print "Basic environment initialization error: " + e.value
        sys.exit(1)

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Printing command line arguments:",
                 args)

    # Main logic
    exit_code = cmn.SUCCESS
    exit_msg = None
    try:
        # read/parse/validate input data, stuff it into a data structure I find useful
        l_of_host_info_lists = parse_input_file(
            cmn,
            os.path.join(DEFAULT_LOCAL_PATH, args.file),
            args.register_hosts)

        # instantiate VseViprApi and login to ViPR
        from vseLib.VseViprApi import VseViprApi
        cmn.printMsg(cmn.MSG_LVL_INFO, "Logging into ViPR Controller...")
        vipr_api = VseViprApi(cmn)
        vipr_api.login()

        # we need Tenant of current user
        about_me = vipr_api.get_who_am_i()
        tenant_uri = about_me.get('tenant')

        # prepare for summary output
        discovery_accepted_count = 0
        discovery_failed_count = 0
        discovery_host_existing_pwd_update_success_count = 0
        discovery_host_existing_pwd_update_failure_count = 0
        register_cluster_existing_count = 0
        register_cluster_new_count = 0
        register_cluster_fail_count = 0
        register_host_existing_count = 0
        register_host_new_count = 0
        register_host_fail_count = 0
        register_wwn_existing_count = 0
        register_wwn_new_count = 0
        register_wwn_fail_count = 0
        status_chain = {}
        # for each host - send in API call, and output appropriate message whether task was accepted or rejected. Keep tally of totals to print out.
        for host_info_list in l_of_host_info_lists:
            #
            # discovering hosts
            #
            if not args.register_hosts:
                # does host exist? update password! else discover anew
                host_ids = vipr_api.search_by_name(
                    vipr_api.IDX_SEARCH_TYPE_HOST,
                    host_info_list[IDX_H_H_N].strip(),
                    exact_match=True
                )
                # host exists, we update all we have but the name of it
                if len(host_ids) == 1:
                    host_uri = host_ids[0]
                    (ret_code, details) = vipr_api.update_host(
                        host_uri,
                        fqdn=host_info_list[IDX_H_N_N].strip(),
                        h_type=host_info_list[IDX_H_T].strip(),
                        use_ssl=host_info_list[IDX_D_SSL].strip(),
                        port=host_info_list[IDX_D_P_N].strip(),
                        uname=host_info_list[IDX_H_U_N].strip(),
                        pwd=host_info_list[IDX_H_PWD].strip()
                    )

                    if ret_code not in [200, 202]:
                        discovery_host_existing_pwd_update_failure_count += 1
                        status_chain[host_info_list[IDX_H_N_N]] = details
                    else:
                        discovery_host_existing_pwd_update_success_count += 1
                # host doesn't exist, we attempt to create it
                else:
                    (ret_code, details) = vipr_api.discover_host(
                        tenant_uri,
                        host_info_list[IDX_H_H_N].strip(),
                        host_info_list[IDX_H_N_N].strip(),
                        host_info_list[IDX_H_T].strip(),
                        host_info_list[IDX_D_SSL].strip(),
                        host_info_list[IDX_D_P_N].strip(),
                        host_info_list[IDX_H_U_N].strip(),
                        host_info_list[IDX_H_PWD].strip(),
                    )

                    if ret_code not in [200, 202]:
                        discovery_failed_count += 1
                        status_chain[host_info_list[IDX_H_N_N]] = details
                    else:
                        discovery_accepted_count += 1

            #
            # registering clusters/hosts/initiators
            #
            if args.register_hosts:
                # is cluster required? does cluster exist? if yes, get its ID. if not, create.
                # On failure can exit handling
                cluster_uri = ''
                if len(host_info_list[REG_CLUSTER]) > 0:
                    cluster_ids = vipr_api.search_by_name(
                        vipr_api.IDX_SEARCH_TYPE_CLUSTER,
                        host_info_list[REG_CLUSTER].strip(),
                        exact_match=True
                    )
                    if len(cluster_ids) == 1:
                        register_cluster_existing_count += 1
                        cluster_uri = cluster_ids[0]
                    else:
                        (ret_code, details) = vipr_api.create_cluster(tenant_uri,
                                                                      host_info_list[REG_CLUSTER])
                        if ret_code not in [200, 202]:
                            status_chain["{0}/{1}".format(host_info_list[REG_CLUSTER],
                                                          host_info_list[REG_H_N_N])] = details
                            register_cluster_fail_count += 1
                            register_host_fail_count += 1
                            register_wwn_fail_count += len(host_info_list[REG_H_WWNS])
                            continue
                        else:
                            register_cluster_new_count += 1
                            cluster_uri = details.get('id')

                # does host exist? if yes, get its ID. if not, create.
                # On failure can exit handling.
                host_uri = ''
                host_ids = vipr_api.search_by_name(
                    vipr_api.IDX_SEARCH_TYPE_HOST,
                    host_info_list[REG_H_H_N].strip(),
                    exact_match=True
                )
                if len(host_ids) == 1:
                    register_host_existing_count += 1
                    host_uri = host_ids[0]
                else:
                    (ret_code, details) = vipr_api.register_host(
                        tenant_uri,
                        host_info_list[REG_H_H_N].strip(),
                        host_info_list[REG_H_N_N].strip(),
                        host_info_list[REG_H_T].strip(),
                        cluster_urn=cluster_uri
                    )
                    if ret_code not in [200, 202]:
                        status_chain[host_info_list[REG_H_N_N]] = details
                        register_host_fail_count += 1
                        register_wwn_fail_count += len(host_info_list[REG_H_WWNS])
                        continue
                    else:
                        register_host_new_count += 1
                        host_uri = details.get('resource').get('id')


                # does host already have initiator? if yes, do nothing; else - register attempt
                # for each WWN: api.register_initiator
                vc_host_inits_info_lists = vipr_api.get_host_initiators(host_info_list[REG_H_N_N],
                                                                        host_uri)
                vc_host_init_wwn_list = list(
                    init_dict.get('initiator_port').lower() for init_dict in vc_host_inits_info_lists)

                host_wwns_info_lists = host_info_list[REG_H_WWNS]
                for host_wwn_info_list in host_wwns_info_lists:
                    if host_wwn_info_list[REG_WWN_PWWN].strip().lower() in vc_host_init_wwn_list:
                        # we are done, initiator is already in the host
                        register_wwn_existing_count += 1
                        continue;

                    # we only make user submit 1 wwn (the wwn of HBA card)
                    # but the API takes init_node and init_port that can be same wwn...
                    # so whatever. I don't mind submitting it twice to keep flexibility in ViPRAPI lib.
                    (ret_code, details) = vipr_api.register_initiator(
                        host_uri,
                        host_wwn_info_list[REG_WWN_NAME].strip(),
                        host_wwn_info_list[REG_WWN_PROT].strip(),
                        host_wwn_info_list[REG_WWN_PWWN].strip(),
                        host_wwn_info_list[REG_WWN_PWWN].strip(),
                    )

                    if ret_code not in [200, 202]:
                        status_chain["{0}/{1}".format(host_info_list[REG_H_N_N],
                                                      host_wwn_info_list[REG_WWN_PWWN])] = details
                        register_wwn_fail_count += 1
                        continue

                    register_wwn_new_count += 1


        cmn.printMsg(cmn.MSG_LVL_INFO, '\n'
                     'Total host loads attempted: {0}\n'
                     'Total host discoveries accepted : {1}\n'
                     'Total host discoveries rejected : {2}\n'
                     'Total host update succeeded/failed: {12},{13}\n'
                     'Total cluster registrations existed/succeeded/failed: {3},{4},{5}\n'
                     'Total host registrations existed/succeeded/failed: {6},{7},{8}\n'
                     'Total initiator registrations existed/succeeded/failed: {9},{10},{11}\n'
                     'Listing failed Cluster/Host/Initiator loads:'.format(
                         len(l_of_host_info_lists),
                         discovery_accepted_count,
                         discovery_failed_count,
                         register_cluster_existing_count,
                         register_cluster_new_count,
                         register_cluster_fail_count,
                         register_host_existing_count,
                         register_host_new_count,
                         register_host_fail_count,
                         register_wwn_existing_count,
                         register_wwn_new_count,
                         register_wwn_fail_count,
                         discovery_host_existing_pwd_update_success_count,
                         discovery_host_existing_pwd_update_failure_count,
                     ),
                     status_chain)

        vipr_api.logout()

    except Exception as e:
        VseExceptions.announce_exception(cmn, e)
        exit_code = cmn.ERROR_GENERIC
        exit_msg = str(e)


    cmn.exit(exit_code, exit_msg)


def parse_input_file(cmn, file_path, register_hosts):
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 'Reading file [{0}]...'.format(file_path))

    if not os.path.isfile(file_path):
        msg = 'File [{0}] does not exist'.format(file_path)
        cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)

    l_of_host_info_lists = []

    with open(file_path, 'r') as contents:
        #
        # qualify headers
        # check that headers are in the right order and the right names
        # whether each entry is 'required' will be checking contents.
        #
        headers = contents.readline().strip()
        if not register_hosts and headers != discover_hosts_headers:
            msg = 'Expected headers are: {0}'.format(discover_hosts_headers)
            cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
            raise VseExceptions.VSEViPRAPIExc(msg)
        elif register_hosts and headers != register_hosts_headers:
            msg = 'Expected headers are: {0}'.format(register_hosts_headers)
            cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
            raise VseExceptions.VSEViPRAPIExc(msg)

        # remember how many data elements in each data line are required
        data_element_count = len(discover_hosts_headers.split(',')) if not register_hosts \
            else len(register_hosts_headers.split(','))
        offending_data_rows = []

        for line in contents:
            # this is nice and clean, but what if the password has a comma in it?
            # we are hosed... would need to change password on 1,000s of hosts.
            #

            # http://stackoverflow.com/questions/18092354/python-split-string-without-splitting-escaped-character
            #   There is a much easier way using a regex with a negative lookbehind assertion:
            # solution: re.split(r'(?<!\\):', str)
            values = line.strip().split(',')

            # protect against wrong element count, jump to next row
            if len(values) != data_element_count:
                offending_data_rows.append(line)
                continue

            invalid_wwns_format = False
            if register_hosts:
                wwns_element = values[REG_H_WWNS]
                wwn_keys = wwns_element.strip().split(';')
                wwns_info = []
                for wwn_key in wwn_keys:
                    # just skip over it if it is an empty string - probably last semicolon
                    if len(wwn_key) == 0:
                        continue
                    wwn_data = wwn_key.strip().split('/')
                    # remember there was a parsing failure if not exactly 3 elements
                    if len(wwn_data) != 3:
                        invalid_wwns_format = True
                        continue
                    wwns_info.append(wwn_data)

                # in-place sub user provided string with list of lists on host WWNs.
                values[REG_H_WWNS] = wwns_info

            # but if there was a problem with 1 of user provided wwn strings, kill the whole thing
            if invalid_wwns_format:
                offending_data_rows.append(line)
                continue

            # save data to be returned
            l_of_host_info_lists.append(values)

        if len(offending_data_rows) > 0:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Below data lines are dirty - they didn't pass the filters:",
                         offending_data_rows)
            raise VseExceptions.VSEViPRAPIExc('Invalid data submitted, not running any load until data is cleaned up')

    return l_of_host_info_lists


if __name__ == '__main__':
    main()