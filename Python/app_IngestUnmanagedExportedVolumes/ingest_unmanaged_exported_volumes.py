__author__ = 'belens'

"""
Program seeks to enable ViPR Admin to ingest unmanaged exported volume

Example CLI:
    -tp "Ingest" -st exclusive -so slb-fake.lss.emc.com -m 1 -full_debug -prevent_umv_replicas

Assumptions:
    Tenant is Provider Tenant
    UnManaged Array discovery (including VPLEX if required) must be completed ahead of time
    Only 1 VA and VP possible per candidate volume (else - invalid)
    - Exported volumes only
    - FC protocol only
    - not replicated, no replicas (actually there is a flag that allows to ignore all replicas)

High level steps:
    1) identify all volumes eligible for ingestion
    2) reject ambiguous VA/VP placements
    3) if -prevent_umv_replicas - program will cleanse REPLICA indicators from UnManagedVolume table in ViPR DB.
    4) using Service Catalog API calls: ingest unmanaged exported volumes

"""
import argparse
import os
import sys
from vseLib.vseCmn import VseExceptions, vseCmn
from vseLib.VseViprApi import VseViprApi
from vseLib.VseRemoteExecution import VseRemoteExecution

try:
    import xml.etree.cElementTree as eTree
#    from xml.etree.cElementTree import ParseError as pE
except ImportError:
    import xml.etree.ElementTree as eTree
#    from xml.etree.ElementTree import ParseError as pE


DEFAULT_ENV_CFG_FILE = r'./env_cfg.ini'
DEFAULT_LOCAL_PATH = os.path.dirname(os.path.realpath(__file__))


# path to DBCLI file on ViPR VM
# this is the script that will dump XML structure and load it back
PATH_VIPRC_DBCLI = r'/opt/storageos/bin/dbcli'
# path to remove dump location of the file
PATH_VIPRC_FILE_DUMP = r'/tmp/{0}'
# /opt/storageos/bin/dbcli dump -i "id1,id2,..." -f <file name> <column family>
CMD_DBCLI_DUMP = "{0} dump -i {1} -f {2} {3}"
# /opt/storageos/bin/dbcli load -f <file name>
CMD_DBCLI_LOAD = "{0} load -f {1}"



def parse_arguments():
    parser = argparse.ArgumentParser(
        description="%(prog)s ingests UnManaged Exported Volumes visible to a specific host/cluster")

    r_args = parser.add_argument_group('Required Arguments')

    # target project
    r_args.add_argument('-target_project', '-tp',
                        required=True,
                        help='Specify name of target project to ingest '
                             'volumes into.')
    # storage type - shared or exclusive
    r_args.add_argument('-storage_type', '-st',
                        required=True,
                        choices=[VseViprApi.STORAGE_TYPE_SHARED,
                                 VseViprApi.STORAGE_TYPE_EXCLUSIVE],
                        help='Specify type of storage, either shared or '
                             'exclusive')
    # owner - name of host or cluster
    r_args.add_argument('-storage_owner', '-so',
                        required=True,
                        help='Specify name of storage owner (host or '
                             'cluster).')

    o_args = parser.add_argument_group('Optional Arguments')
    o_args.add_argument('-prevent_umv_replicas',
                        required=False,
                        action='store_true',
                        help='If UnManagedVolume record contains any local '
                             'replica references (e.g. snapshots), '
                             'the script will update target vipr database '
                             'UnManagedVolume table directly to remove such. '
                             'This can be used in an attempt to prevent '
                             'ingestion failures when we don\'t care for '
                             'replicas')
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

    sc_args = parser.add_argument_group('Optional Service Catalog Arguments')
    sc_args.add_argument('-catalog_ingest_exported_volume',
                         required=False,
                         default=VseViprApi.SC_BSS_INGEST_EXPORTED_UMNGD,
                         help='Specify name of service catalog service '
                              'inside the catalog folder that is used to '
                              'ingest exported unmanaged block volume. '
                              'Default value is [{0}].'.format(
                             VseViprApi.SC_BSS_INGEST_EXPORTED_UMNGD))

    parser.set_defaults(
        env_settings=DEFAULT_ENV_CFG_FILE,
        default_local_path=DEFAULT_LOCAL_PATH,
        msg_level=vseCmn.MSG_LVL_INFO,
        full_debug=False)

    return parser.parse_args()


def main():
    # deal with cmd line and init file arguments
    # initialize cmn module for logging and else.
    args = parse_arguments()

    # Initialize environment, if any errors - quit gruesomely
    try:
        cmn = vseCmn(
            "ViPR Ingest Volumes for .".format(args.storage_owner),
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
        # instantiate VseViprApi and login to ViPR
        from vseLib.VseViprApi import VseViprApi

        cmn.printMsg(cmn.MSG_LVL_INFO, "Logging into ViPR Controller...")
        vipr_api = VseViprApi(cmn)
        vipr_api.login()

        #
        # find required Service Catalog URNs
        #
        cmn.printMsg(cmn.MSG_LVL_INFO, "Finding Service Catalog services...")
        # sc_ingest_unmanaged_exported_urn = gather_service_catalog_service_urns(
        # cmn,
        # vipr_api,
        #     args.catalog_ingest_exported_volume
        # )
        cmn.printMsg(cmn.MSG_LVL_WARNING, "Overriding with VSE Lab Value "
                                          "from .211 instance...")
        sc_ingest_unmanaged_exported_urn = \
            'urn:storageos:CatalogService:542526b2-67b6-4f5d-8932-b638a0bacb72:vdc1'


        cmn.printMsg(cmn.MSG_LVL_INFO, "Scanning available unmanaged exported "
                                       "volumes...")
        (
            tenant_urn,
            project_info,
            storage_owner_info,
            candidate_map,
            eligible_map,
            invalid_map
        ) = gather_and_bless_initial_data(cmn, vipr_api,
                                          args.target_project,
                                          args.storage_type,
                                          args.storage_owner)

        if len(invalid_map.keys()) > 0:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "{0} out of {1} identified unmanaged exported devices are NOT "
                         "eligible for ingestion [owner_name/device_name: "
                         "project_name/va_name/vp_name/dev_urn/reasons"
                         "]:".format(
                             len(invalid_map.keys()),
                             len(candidate_map.keys())
                         ),
                         pretty_print_invalid_map(vipr_api,
                                                  project_info,
                                                  storage_owner_info,
                                                  invalid_map,
                                                  candidate_map)
            )

        #
        # devices that ARE eligible, they need to get sanitized in the database
        # specifically - we need to remove their local replica,
        # else ingestion will fail with demand to ingest a replica, that E.
        # (customer) requires to be left out.
        #
        if args.prevent_umv_replicas:
            forget_unmanaged_devices_replicas(cmn, vipr_api, eligible_map)

        # service catalog API call to ingest. sync.
        #   - 'storageType' could be 'exclusive' and 'shared'
        #   - 'host' could be URN of a Host or a Cluster
        #   - 'volumes' is a list of UnManagedVolume URN
        cmn.printMsg(cmn.MSG_LVL_INFO,
            "Ingesting devices [owner_name/device_name: "
            "project_name/va_name/vp_name/dev_urn]:",
            pretty_print_eligible_map(vipr_api,
                                      project_info,
                                      storage_owner_info,
                                      eligible_map)
        )

        for va_urn in eligible_map.keys():
            va_map = eligible_map[va_urn]
            for vp_urn in va_map.keys():
                vp_map = va_map[vp_urn]
                umv_urn_list = vp_map.keys()

                cmn.printMsg(cmn.MSG_LVL_DEBUG,
                             "Ingesting UnManaged Export Volumes for VA [{"
                             "0}], VP [{1}], Volumes:".format(
                                 vipr_api.get_va_info_by_uri(va_urn).get(
                                     'name') + '/' + va_urn,
                                 vipr_api.get_vp_info_by_uri(vp_urn).get(
                                     'name') + '/' + vp_urn),
                             umv_urn_list)

                (is_ingestion_success, state, work_order_dict) = \
                    vipr_api.catalog_execute(
                    "Ingest Exported Unmanaged Volumes",
                    sc_ingest_unmanaged_exported_urn,
                    tenant_urn,
                    {'storageType': args.storage_type,
                     'host': storage_owner_info.get('id'),
                     'virtualArray': va_urn,
                     'virtualPool': vp_urn,
                     'project': project_info.get('id'),
                     'volumeFilter': '-1',
                     'ingestionMethod': 'Full',
                     'volumes': umv_urn_list
                     }
                )
                if not is_ingestion_success:
                    cmn.printMsg(cmn.MSG_LVL_WARNING,
                                 'Ingestion of below volumes reported '
                                 'errors: {0} '.format(work_order_dict.get('message')),
                                 umv_urn_list)
                else:
                    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                                 'Ingestion of below volumes succeeded: ',
                                 umv_urn_list)

        vipr_api.logout()

    except Exception as e:
        VseExceptions.announce_exception(cmn, e)
        exit_code = cmn.ERROR_GENERIC
        exit_msg = str(e)


    cmn.exit(exit_code, exit_msg)


def analyze_device(cmn, vipr_api, device_info, eligible_map, invalid_map):
    device_urn = device_info.get('id')
    reasons = list()

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Starting eligibility analysis for device [{0}].".format(
                     device_info.get('name')
                 ))

    # volumeCharacterstics =>  (check for)
    #   IS_SNAP_SHOT=false
    #   IS_RECOVERPOINT_ENABLED=false
    #   REMOTE_MIRRORING=false
    #   IS_FULL_COPY=false
    #   HAS_REPLICAS=false (check disabled)

    vChars_list = device_info.get('unmanaged_volumes_characterstics')
    for vChar_map in vChars_list:
        name = vChar_map.get('name')
        value = vChar_map.get('value')
        if name == 'IS_SNAP_SHOT' and value == 'true':
            msg = "Device [{0}] is a snapshot".format(device_info.get('name'))
            reasons.append(msg)
        if name == 'IS_RECOVERPOINT_ENABLED' and value == 'true':
            msg = "Device [{0}] is RPA enabled".format(device_info.get('name'))
            reasons.append(msg)
        if name == 'IS_FULL_COPY' and value == 'true':
            msg = "Device [{0}] is a clone".format(device_info.get('name'))
            reasons.append(msg)
        if name == 'REMOTE_MIRRORING' and value == 'true':
            msg = "Device [{0}] is in SRDF relationship".format(device_info.get('name'))
            reasons.append(msg)
        #
        # disabling this check because we are introducing a 'forget
        # replicas' cli flag
        #
        # if name == 'HAS_REPLICAS' and value == 'true':
        #     msg = "Device [{0}] has replicas".format(device_info.get('name'))
        #     reasons.append(msg)


    # volumeCharacterstics=>
    #           HAS_REPLICAS=true   delete or set to false? can set to false
    #  then sessions come in still. so need to delete from vI.
    # volumeInformation=>
    #           SNAPSHOT_SESSIONS=[slb-t-ing-ss-2-snapsession:SYMMETRIX-+-000196701186-+-002EB-+-slb-t-ing-ss-2-snapsession-+-0]
    #           SNAPSHOTS=[SYMMETRIX+000196701186+UNMANAGEDVOLUME+002F9]

    #
    # is there 0 or more than 1 VP?
    #
    vp_urn = None
    vp_urn_list = device_info.get('supported_virtual_pools')

    if len(vp_urn_list) == 0:
        msg = "Device [{0}] was not mapped to any VPs".format(
            device_info.get('name')
        )
        reasons.append(msg)

    if len(vp_urn_list) >= 2:
        msg = "Device [{0}] is mapped to 2 or more VPs".format(
            device_info.get('name')
        )
        reasons.append(msg)

    #
    # does VP have more than a single VA listed?
    # check only if VP is determined
    #
    va_urn = None

    if len(vp_urn_list) == 1:
        vp_urn = vp_urn_list[0]
        vp_info = vipr_api.get_vp_info_by_uri(vp_urn)
        va_id_list = vp_info.get('varrays')
        # can't have 0 VAs in a VP - it won't let you save
        if len(va_id_list) >= 2:
            msg = "Device [{0}] (through mapped VP) is mapped to 2 or more " \
                  "VAs".format(
                device_info.get('name')
            )
            reasons.append(msg)
        else:
            va_urn = va_id_list[0].get('id')

    #
    # final: device is valid if length of reasons list is 0
    #

    #
    # goal: return valid hashmap
    #   VA=>VP=>URN=>DevInfo
    #
    # goal: return invalid hashmap
    #   URN=>Reasons
    #
    if len(reasons) == 0:
        cmn.printMsg(cmn.MSG_LVL_INFO,
                     "Device [{0}] is eligible for ingestion".format(
                         device_info.get('name'))
        )
        if va_urn not in eligible_map.keys():
            eligible_map[va_urn] = {}
        va_map = eligible_map[va_urn]

        if vp_urn not in va_map.keys():
            va_map[vp_urn] = {}
        vp_map = va_map[vp_urn]

        vp_map[device_urn] = device_info

    else:
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Device [{0}] is NOT eligible for ingestion "
                     "because: ".format(device_info.get('name')),
                     reasons
        )
        invalid_map[device_urn] = reasons

    # this is for testing - forcing all devices to fail with BS reason
    # keep this commented out
    #
    # reasons.append('just testing - remove this section from analyze_device')
    # invalid_map[device_urn] = reasons

    return


def gather_and_bless_initial_data(cmn, vipr_api,
                                  target_project_name,
                                  storage_type,
                                  storage_owner_name):
    #
    # get information on target project
    #
    target_project_info = vipr_api.get_project_info_by_name(
        target_project_name
    )
    if target_project_info is None:
        msg = "Problem querying target project [{0}]".format(
            target_project_name)
        cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)

    #
    # figure out storage owner
    #
    search_for_urns_type = vipr_api.IDX_SEARCH_TYPE_HOST \
        if storage_type == vipr_api.STORAGE_TYPE_EXCLUSIVE \
        else vipr_api.IDX_SEARCH_TYPE_CLUSTER

    matched_owners_urns_list = vipr_api.search_by_name(
        search_for_urns_type, storage_owner_name)

    query_for_info_bulk_api_call = vipr_api.API_PST_HOST_BULK_INFO \
        if storage_type == vipr_api.STORAGE_TYPE_EXCLUSIVE \
        else vipr_api.API_PST_CLUSTER_BULK_INFO

    matched_owners_info_list = vipr_api.get_bulk_info_by_list_of_ids(
        query_for_info_bulk_api_call, matched_owners_urns_list
    )

    owner_info = None
    for owner_candidate in matched_owners_info_list:
        if owner_candidate.get('name') == storage_owner_name:
            if owner_info is not None:
                raise VseExceptions.VSEViPRAPIExc(
                    "more than one storage owner candidate identified, "
                    "cannot proceed. URN of 1st identified candidate is [{"
                    "0}] and now a conflicting candidate [{1}] came "
                    "up.".format(
                        owner_info.get('id'),
                        owner_candidate.get('id'))
                )
            owner_info = owner_candidate
    if owner_info is None:
        raise VseExceptions.VSEViPRAPIExc(
            "Storage owner candidate [{0}] was not found, "
            "cannot proceed.".format(storage_owner_name))

    #
    # find tenant of storage owner
    #
    tenant_urn = owner_info.get('tenant').get('id')

    #
    # -------------------- DEVICES ------------------------------------
    #

    #
    # goal: return hashmap
    #   VA=>VP=>URN=>DevInfo
    #

    #
    # get all unmanaged for the storage owner
    # assumption: whatever appropriate storage systems have been discovered
    # already
    #
    # question: what does unmanaged VPLEX volume look like in this API call?
    #  a: just comes, can't tell except by name and VP. Internal VMAX
    #     volumes don't come in at all
    # question: what does VMAX volume with a snapshot look like
    #  a: ?
    #
    unmanaged_devs_urn_list = vipr_api.get_list_of_unmanaged_volume_urns_by_owner(
        storage_type, owner_info.get('id'))
    unmanaged_devs_info = vipr_api.get_list_unmanaged_volumes_info(
        unmanaged_devs_urn_list)

    eligible_map = {}
    invalid_map = {}
    for device_info in unmanaged_devs_info:
        analyze_device(cmn, vipr_api, device_info, eligible_map, invalid_map)

    return tenant_urn, \
           target_project_info, \
           owner_info, \
           cmn.convert_list_of_dict_objects_into_dict_by_id(unmanaged_devs_info),\
           eligible_map, \
           invalid_map


def gather_service_catalog_service_urns(cmn, vipr_api,
                                        catalog_ingest_exported_volume):
    sc_ingest_unmanaged_exported_urn = vipr_api.fetch_sc_urn(
        catalog_ingest_exported_volume)

    if sc_ingest_unmanaged_exported_urn is None:
        msg = "One of SC services required cannot be found, " \
              "unable to continue"
        cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)

    return sc_ingest_unmanaged_exported_urn


# format eligible_map to something more consumable by printMsg
def pretty_print_eligible_map(vipr_api,
                              project_info,
                              storage_owner_info,
                              eligible_map):
    pretty_map = {}
    for va_uri in eligible_map.keys():
        vp_map = eligible_map[va_uri]
        for vp_uri in vp_map.keys():
            devs_map = vp_map[vp_uri]
            for dev_uri in devs_map.keys():
                dev_map = devs_map[dev_uri]
                pretty_map_key = storage_owner_info.get('name') + '/' + \
                            dev_map.get('name')
                pretty_map_value = project_info.get('name') + '/' + \
                              vipr_api.get_va_info_by_uri(va_uri).get('name') + '/' + \
                              vipr_api.get_vp_info_by_uri(vp_uri).get('name') + '/' + \
                              dev_uri
                pretty_map[pretty_map_key] = pretty_map_value

    return pretty_map


# format invalid_map to something more consumable by printMsg
def pretty_print_invalid_map(vipr_api,
                             project_info,
                             storage_owner_info,
                             invalid_map,
                             candidate_map):
    pretty_map = {}
    for dev_uri in invalid_map.keys():
        reasons = invalid_map[dev_uri]
        dev_map = candidate_map[dev_uri]
        vp_info = vipr_api.get_vp_info_by_uri(dev_map.get('supported_virtual_pools')[0])
        va_info = vipr_api.get_va_info_by_uri(vp_info.get('varrays')[0].get('id'))
        pretty_map_key = storage_owner_info.get('name') + '/' + dev_map.get('name')
        pretty_map_value = project_info.get('name') + '/' + \
                           va_info.get('name') + '/' + \
                           vp_info.get('name') + '/' + \
                           dev_uri + '/' + "Because: {0}".format(reasons)
        pretty_map[pretty_map_key] = pretty_map_value

    return pretty_map


def forget_unmanaged_devices_replicas(cmn, vipr_api, eligible_map):
    #
    # identify devices that have replicas
    # announce
    # trigger database data modification
    #
    for va_urn in eligible_map.keys():
        va_map = eligible_map[va_urn]
        for vp_urn in va_map.keys():
            vp_map = va_map[vp_urn]
            for dev_urn in vp_map.keys():
                dev_map = vp_map[dev_urn]
                dev_vChars_list = dev_map['unmanaged_volumes_characterstics']

                has_replicas = False
                for dev_vChar_map in dev_vChars_list:
                    name = dev_vChar_map.get('name')
                    value = dev_vChar_map.get('value')
                    if name == 'HAS_REPLICAS' and value == 'true':
                        has_replicas = True
                        continue

                if has_replicas:
                    forget_unmanaged_device_replicas(cmn, vipr_api, dev_map)


def forget_unmanaged_device_replicas(cmn, vipr_api, dev_map):

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 'Device [{0}] has replicas, removing '
                 'mentions of them...'.format(
                     dev_map.get('name')
                 ))

    # this makes name too long for windows dev_map.get('id'))
    umv_dmp_file_name = "{0}---{1}".format(dev_map.get('name'),'urn')
    umv_tgt_file_name = umv_dmp_file_name+'_tgt'

    # dump XML on ViPR instance
    # bring XML locally
    umv_dmp_file_path = obtain_xml_dump_file(cmn,
                                             umv_dmp_file_name,
                                             'UnManagedVolume',
                                             dev_map.get('id'))

    # parse & modify XML
    try:
        doc_tree = eTree.parse(umv_dmp_file_path)

        # cache reference to 'record'  - this is parent of all fields
        record = doc_tree.getroot().find('./data_object_schema/record')

        # I need to find entries where there are certain 'key' and delete entries

        #
        #  EXAMPLE
        #
        #  <field name="label" type="java.lang.String" value="slb-t-ingestion-w-ss-1"/>
        #  example for a simple attrib. Responds to things like
        #  leaf_label.attrib['name']
        #  leaf_label.attrib['type']
        #  leaf_label.attrib['value']
        #
        leaf_label = get_xml_leaves_by_name_from_root(cmn,
                                                      doc_tree,
                                                      'field',
                                                      filter_name='label')[0]


        # find volumeCharacterstics data structure in the XML
        # descend, bypassing 'wrapper' to its 'stringMap' list of 'elements'
        # get the list itself, so we can get through each element and find what we have to remove
        # find and remove
        leaf_vChars = get_xml_leaves_by_name_from_root(cmn,
                                                       doc_tree,
                                                       'field',
                                                       filter_name='volumeCharacterstics')[0]
        leaf_vChars_stringMap = get_xml_leaves_by_name_from_root(cmn,
                                                                 leaf_vChars,
                                                                 'stringMap')[0]
        leaves_individual_chars = get_xml_leaves_by_name_from_root(cmn,
                                                                   leaf_vChars,
                                                                   'entry')
        for leaf_vChar in leaves_individual_chars:
            key = leaf_vChar.find('key').text
            value = leaf_vChar.find('value').text

            if key == 'HAS_REPLICAS' and value == 'true':
                leaf_vChars_stringMap.remove(leaf_vChar)

        # find volumeCharacterstics data structure in the XML
        # descend, bypassing 'wrapper' to its 'stringMap' list of 'elements'
        # get the list itself, so we can get through each element and find what we have to remove
        # find and remove
        leaf_vIs = get_xml_leaves_by_name_from_root(cmn,
                                                       doc_tree,
                                                       'field',
                                                       filter_name='volumeInformation')[0]
        leaf_vIs_stringMap = get_xml_leaves_by_name_from_root(cmn,
                                                                 leaf_vIs,
                                                                 'stringSetMap')[0]
        leaves_individual_infos = get_xml_leaves_by_name_from_root(cmn,
                                                                   leaf_vIs,
                                                                   'entry')
        for leaf_vI in leaves_individual_infos:
            key = leaf_vI.find('key').text

            if key in ['SNAPSHOTS','SNAPSHOT_SESSIONS']:
                leaf_vIs_stringMap.remove(leaf_vI)

        # write out resulting XML file
        out_path = os.path.join(cmn.get_session_path(), umv_tgt_file_name)
        doc_tree.write(out_path, xml_declaration=True)

    except:
        cmn.printMsg(cmn.MSG_LVL_ERROR,
                     "XML parsing error on file [{0}], execution failed"
                     "".format(umv_dmp_file_path))

    # apply XML update remotely
    apply_xml_update_file(cmn, umv_tgt_file_name)

    pass


#
# lookup and return a LIST of xml tree leaves by field_name
#
def get_xml_leaves_by_name_from_root(cmn, doc_tree,
                                     search_for, filter_name=None):
    #
    # find all leaves that are 'search_for' (e.g. fields or keys)
    # if filter_name is given, then match the name attribute
    #
    leaves = []
    for element in doc_tree.iter(search_for):
        if filter_name is None:
            leaves.append(element)

        if filter_name is not None and element.attrib['name'] == filter_name:
            leaves.append(element)

    # this is too chatty
    #
    # for leaf in leaves:
    #     msg = "FOUND Element for update: \n" \
    #           "\tTag       : " + str(leaf.tag) + "\n" \
    #           "\tAttributes: " + str(leaf.attrib) + "\n" \
    #           "\tValue     : " + str(leaf) + "\n"
    #     try:
    #         if leaf.text is not None:
    #             msg += "\tText      : " + leaf.text + "\n"
    #         if leaf.find('key').text is not None:
    #             msg += "\tKey       : " + leaf.find('key').text + "\n"
    #         if leaf.find('value').text is not None:
    #             msg += "\tValue     : " + leaf.find('value').text + "\n"
    #     except:
    #         cmn.printMsg(cmn.MSG_LVL_DEBUG,
    #                      "Exception trying to obtain some of leaf's properties")
    #    cmn.printMsg(cmn.MSG_LVL_DEBUG, msg)

    return leaves




#
# if all is OK, returns full path to where XML file has been DL'd to.
#
def obtain_xml_dump_file(cmn, filename, cfname, uri):
    vse_rx = VseRemoteExecution(cmn)

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Dumping {0}/{1} record remotely to {2}..."
                 "".format(
                     cfname,
                     uri,
                     PATH_VIPRC_FILE_DUMP.format(filename)
                 )
    )

    #
    # create file dump on remote system
    # TODO: check output for indications of some sort of error
    # should throw some "record doesn't exist exception" in case of 'Deleted'
    #
    """
    Example of problematic output (record doesn't exist):
        DEBUG: Command exited with code [0], and output:

        Initializing db client ...
        id: fake [ Deleted ]
        Dump into file: /tmp/0001_ExportGroup_fake successfully
    """
    (exit_code, output) = vse_rx.rx_cmd_simple(
        cmn.get_vipr_host_name(),
        cmn.get_vipr_user(),
        cmn.get_vipr_password(),
        CMD_DBCLI_DUMP.format(
            PATH_VIPRC_DBCLI,
            uri,
            PATH_VIPRC_FILE_DUMP.format(filename),
            cfname
            ),
        sleepTimerSeconds=5
    )

    #
    # copy file from remote system, locally
    # TODO: this can throw Exception if md5 checksum is bad or sftp fails
    #
    delivery_path = os.path.join(cmn.get_session_path(), filename)
    vse_rx.xfer_file_sftp(
        vse_rx.XFER_OP_DL,
        cmn.get_vipr_host_name(),
        cmn.get_vipr_user(),
        cmn.get_vipr_password(),
        delivery_path,
        PATH_VIPRC_FILE_DUMP.format(filename)
    )

    return delivery_path


# upload local file to remote ViPR instance
# update database by loading remote file
def apply_xml_update_file(cmn, filename):
    vse_rx = VseRemoteExecution(cmn)

    tgt_xml_file_path_lcl = os.path.join(
        cmn.get_session_path(), filename
    )
    tgt_xml_file_path_rmt = PATH_VIPRC_FILE_DUMP.format(filename)

    #
    # upload xml update file
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Uploading [{0}] file to remote location [{1}]..."
                 "".format(
                     tgt_xml_file_path_lcl,
                     tgt_xml_file_path_rmt
                 )
    )

    #
    # copy file to remote system, locally
    # warning: this can throw Exception if md5 checksum is bad or sftp fails
    #
    vse_rx.xfer_file_sftp(
        vse_rx.XFER_OP_UP,
        cmn.get_vipr_host_name(),
        cmn.get_vipr_user(),
        cmn.get_vipr_password(),
        tgt_xml_file_path_lcl,
        tgt_xml_file_path_rmt
    )

    #
    # load xml file on remote system
    # maybe: check output for indications of some sort of error
    #
    (exit_code, output) = vse_rx.rx_cmd_simple(
        cmn.get_vipr_host_name(),
        cmn.get_vipr_user(),
        cmn.get_vipr_password(),
        CMD_DBCLI_LOAD.format(
            PATH_VIPRC_DBCLI,
            tgt_xml_file_path_rmt),
        sleepTimerSeconds=5
    )

    # WARNING: not the best way to return db load errors...
    return tgt_xml_file_path_rmt


if __name__ == '__main__':
    main()