__author__ = 'belens'

"""
Program seeks to enable ViPR Admin to change project of an exported volume

Program will delete targeted volume/s from ViPR DB and use ingestion services
to bring it back.

High level steps:
    1) identify target volume/s and new project
    2) collect information on target volume/s
    3) using Service Catalog API calls: delete volume/s from database
    4) using Service Catalog API calls: discover unmanaged storage systems
    5) using Service Catalog API calls: ingest unmanaged volumes

Assumptions:
    - Exported volumes only
    - FC protocol only
    - Not VPLEX, not replicated, not replicas

Version History
    v1.0 + work for a single volume
         + dump submitted arguments into a log file
         + lookup service catalog URNs by name
         + offer to input SC names instead of hard-code assume them, default to
            previously hardcoded names though...
         + work from input: src project, owner_type, owner_name,
            exact_vol_name, tgt project
         + safety
            + block inactive, CG, VPLEX, RPA, SRDF, Locally protected devices
         + carry over volume's tags

    v2.0 + enable multi-volume operation
         + enable input for multiple volumes by vol_name_mask
            + multiple volumes must be in same project, owner, va, vp

Future:
    v3.0 - enable partial operation attempt from prior session dump file
         - improve safety measures
            - offer backup of vipr database
            - dump candidate volumes' required info into a text file
"""
import argparse
import os
import sys
from vseLib.vseCmn import VseExceptions, vseCmn
from vseLib.VseViprApi import VseViprApi

DEFAULT_ENV_CFG_FILE = r'./env_cfg.ini'
DEFAULT_LOCAL_PATH = os.path.dirname(os.path.realpath(__file__))

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="%(prog)s deletes a volume from database and ingests it "
                    "back under a new project")

    r_args = parser.add_argument_group('Required Arguments')
    # source project
    r_args.add_argument('-source_project', '-sp',
                        required=True,
                        help='Specify name of source project.')
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
    # virtual_array - to pickup multiple devices
    r_args.add_argument('-virtual_array', '-va',
                        required=True,
                        help='Specify name of virtual array')
    # virtual_pool - to pickup multiple devices
    r_args.add_argument('-virtual_pool', '-vp',
                        required=True,
                        help='Specify name of virtual pool')

    o_args = parser.add_argument_group('Optional Arguments')
    o_args.add_argument('-volume_name', '-vn',
                        required=False,
                        help='Optionally filter volumes by name (startswith).')
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
    sc_args.add_argument('-catalog_uxp_rmv_volume',
                         required=False,
                         default=VseViprApi.SC_BSS_UXP_RMV_VOLUME,
                         help='Specify name of service catalog service '
                              'inside the catalog folder that is used to '
                              'unexport and remove block volume. Default '
                              'value is [{0}].'.format(
                              VseViprApi.SC_BSS_UXP_RMV_VOLUME))
    sc_args.add_argument('-catalog_discover_unmanaged_volumes',
                         required=False,
                         default=VseViprApi.SC_BSS_DISCOVER_UMNGD,
                         help='Specify name of service catalog service '
                              'inside the catalog folder that is used to '
                              'discover unmanaged block volumes. Default '
                              'value is [{0}].'.format(
                              VseViprApi.SC_BSS_DISCOVER_UMNGD))
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

    # Initialize environment, if any errors - quite gruesomely
    try:
        cmn = vseCmn(
            "ViPR change project to [{0}].".format(args.target_project),
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
        (
            sc_uxp_rmv_urn,
            sc_discover_unmanaged_urn,
            sc_ingest_unmanaged_exported_urn
        ) = gather_service_catalog_service_urns(
            cmn,
            vipr_api,
            args.catalog_uxp_rmv_volume,
            args.catalog_discover_unmanaged_volumes,
            args.catalog_ingest_exported_volume
        )

        #
        # match inputs to ViPR entities
        #
        cmn.printMsg(cmn.MSG_LVL_INFO, "Finding eligible target devices...")
        (
            tenant_urn,
            va_urn,
            vp_urn,
            ss_urn_list,
            source_project_info,
            target_project_info,
            storage_type,
            storage_owner_info,
            source_volumes_map
        ) = gather_and_bless_initial_data(cmn, vipr_api,
                                          args.source_project,
                                          args.target_project,
                                          args.storage_type,
                                          args.storage_owner,
                                          args.virtual_array,
                                          args.virtual_pool,
                                          args.volume_name)

        cmn.printMsg(
            cmn.MSG_LVL_INFO,
            "Qualified below devices for drop/ingest "
            "from project [{0}] to project [{1}]:".format(
                args.source_project, args.target_project
            ),
            sorted(
                list(
                    v.get('name') for v in source_volumes_map.values()
                )
            )
        )
        if not cmn.confirm(
                prompt="Review qualified devices above. Shall we proceed?",
                resp=True):
            cmn.printMsg(cmn.MSG_LVL_INFO, "stopping execution...")
            raise VseExceptions.VSEViPRAPIExc("operator refused to proceed")

        #
        # service catalog API call to delete device from DB. sync.
        #
        cmn.printMsg(cmn.MSG_LVL_INFO, "Deleting devices from ViPR DB")
        is_deletion_from_db_success = vipr_api.catalog_execute(
            vipr_api.SC_BSS_UXP_RMV_VOLUME,
            sc_uxp_rmv_urn,
            tenant_urn,
            {'deletionType':'VIPR_ONLY',
             'project':source_project_info.get('id'),
             'volumes': list(v.get('id') for v in source_volumes_map.values())}
        )
        if not is_deletion_from_db_success:
            msg = "Problem deleting devices from database:\n"
            for d_info in source_volumes_map.values():
                msg += "\t[{0}]=>[{1}]\n".format(d_info.get('label').
                                                 d_info.get('id'))
            cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
            raise VseExceptions.VSEViPRAPIExc(msg)

        #
        # service catalog API call to discover storage array. sync.
        #
        cmn.printMsg(cmn.MSG_LVL_INFO, "Discovering unmanaged storage "
                                       "on storage arrays")
        is_unmanaged_volume_discovery_success = vipr_api.catalog_execute(
            vipr_api.SC_BSS_DISCOVER_UMNGD,
            sc_discover_unmanaged_urn,
            tenant_urn,
            {'storageSystems': ss_urn_list}
        )
        if not is_unmanaged_volume_discovery_success:
            msg = "Problem discovering storage systems [{0}]".format(
                ss_urn_list)
            cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
            raise VseExceptions.VSEViPRAPIExc(msg)

        #
        # find newly discovered unmanaged device URN that matches
        # device we have just deleted
        #
        cmn.printMsg(cmn.MSG_LVL_INFO, "Matching source device URNs to "
                                       "discovered unmanaged target device "
                                       "URNs")
        d_unmanaged_urns = list()
        missing_unmanaged_msgs = list()
        for d_info in source_volumes_map.values():
            d_unmanaged_urn = match_unmanaged_urn(cmn,
                                                  vipr_api,
                                                  storage_type,
                                                  storage_owner_info.get('id'),
                                                  d_info)
            if d_unmanaged_urn is None:
                msg = "Problem finding UnManagedVolume record for " \
                      "[{0}]=>[{1}]. - WATCH " \
                      "OUT - device has been removed " \
                      "from ViPR database by this " \
                      "point in execution!" \
                      "".format(
                      d_info.get('name'),
                      d_info.get('id')
                )
                cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
                missing_unmanaged_msgs.append(msg)
                continue

            d_unmanaged_urns.append(d_unmanaged_urn)

        if len(missing_unmanaged_msgs) > 0:
            msg = ""
            for v_msg in missing_unmanaged_msgs:
                msg += v_msg + "\n"
            raise VseExceptions.VSEViPRAPIExc(msg)


        # service catalog API call to ingest. sync.
        #   - 'storageType' could be 'exclusive' and 'shared'
        #   - 'host' could be URN of a Host or a Cluster
        #   - 'volumes' is a list of UnManagedVolume URN
        cmn.printMsg(cmn.MSG_LVL_INFO, "Ingesting matched unmanaged URNs")
        is_ingestion_success = vipr_api.catalog_execute(
            "Ingest Exported Unmanaged Volumes",
            sc_ingest_unmanaged_exported_urn,
            tenant_urn,
            {'storageType': storage_type,
             'host': storage_owner_info.get('id'),
             'virtualArray': va_urn,
             'virtualPool': vp_urn,
             'project': target_project_info.get('id'),
             'volumeFilter': '-1',
             'ingestionMethod': 'Full',
             'volumes': d_unmanaged_urns
             }
        )
        if not is_ingestion_success:
            msg = "Problem ingestion devices:\n"
            for d_info in source_volumes_map.values():
                msg += "\t[{0}]=>[{1}]\n".format(d_info.get('label').
                                                 d_info.get('id'))
            cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
            raise VseExceptions.VSEViPRAPIExc(msg)

        #
        # carryover volume tag as well - that is a very important
        # piece of info when dealing with volumes created for VMWare, Linux,
        # Windows, etc. ViPR uses tags to let catalogs know down the line
        # whether they can operate on a volume.
        #
        cmn.printMsg(cmn.MSG_LVL_INFO, "Carrying over device tags, if any")
        tagging_errors = list()
        for v in source_volumes_map.values():
            is_tag_carried_over = carry_tag_to_ingested_volume(
                cmn,
                vipr_api,
                v,
                target_project_info
            )
            if not is_tag_carried_over:
                msg = "Problem carrying tag over for" \
                      " device [{0}]=>[{1}]".format(
                    v.get('name'),
                    "legacy source volume id is no longer active")
                cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
                tagging_errors.append(msg)

        if len(tagging_errors) > 0:
            msg = ""
            for v_msg in tagging_errors:
                msg += v_msg + "\n"
            raise VseExceptions.VSEViPRAPIExc(msg)

        # TODO: could be that EG on source project is empty now and should
        # TODO: be deleted.

    except Exception as e:
        VseExceptions.announce_exception(cmn, e)
        exit_code = cmn.ERROR_GENERIC
        exit_msg = str(e)

    cmn.exit(exit_code, exit_msg)


#
# carry over source volume tag onto newly ingested device
#
def carry_tag_to_ingested_volume(cmn,
                                 vipr_api,
                                 source_volume_info,
                                 target_project_info):

    # Tags look like this in volume_info
      # "tags": [
      #   "vipr:vmfsDatastore-urn:storageos:Host:3626c903-4e92-4799-b110-40d35d07e4cf:vdc1=slb-t-ds-name"
      # ]

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if source volume [{0}] had any associated "
                 "tags...".format(source_volume_info.get('name')))

    source_volume_tags = list()

    #
    # if source volume has no tags - msg and return.
    #
    if len(source_volume_info.get('tags')) == 0:
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Source volume [{0}] has no associated tags.".format(
                         source_volume_info.get('id')))
        return True
    else:
        source_volume_tags = source_volume_info.get('tags')
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Source volume [{0}] has associated tags:".format(
                         source_volume_info.get('id')),
                     source_volume_tags)

    #
    # get target project's devices
    #
    target_project_volumes = vipr_api.get_volumes_per_project(
        target_project_info.get('name'),
        target_project_info.get('id')
    )

    #
    # match source volume's parameters to target project's volume,
    # find a match
    #
    target_managed_device_urn = match_searched_volume_to_candidates(
        cmn,
        source_volume_info,
        target_project_volumes
    )

    if target_managed_device_urn is None:
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Unable to identify source volume [{0}] amongst target "
                     "project [{1}]'s volumes".format(
                         source_volume_info.get('name'),
                         target_project_info.get('name')
                     ))
        return False

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Matched source volume [{0}] to new URN [{1}]".format(
                     source_volume_info.get('name'),
                     target_managed_device_urn
                 ))

    #
    # assign tag and verify assignment
    #
    vipr_api.manage_resource_tags(vipr_api.IDX_TAG_BLOCK_VOLUME,
                                  vipr_api.IDX_TAG_ACTION_ADD,
                                  target_managed_device_urn,
                                  source_volume_tags)

    target_volume_tags = vipr_api.manage_resource_tags(
        vipr_api.IDX_TAG_BLOCK_VOLUME,
        vipr_api.IDX_TAG_ACTION_GET,
        target_managed_device_urn)

    if source_volume_tags.sort() != target_volume_tags.sort():
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Tags on source volume [{0}] failed a comparison with "
                     "tags on target volume [{1}]=>[{2}]. Reporting "
                     "failure.".format(
                         source_volume_info.get('name'),
                         source_volume_info.get('name'), # this is not a
                         # typo. name is the same of source and target devices
                         target_managed_device_urn
                     ))
        return False

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Tags on source volume [{0}] have been carried over to "
                 "target volume [{1}]=>[{2}]:".format(
                     source_volume_info.get('name'),
                     source_volume_info.get('name'), # this is not a
                     # typo. name is the same of source and target devices
                     target_managed_device_urn
                 ),
                 target_volume_tags)

    return True


#
# out of all unmanaged devices identified for the owner, pick the URN of the
# device that we just deleted from ViPR DB
#
def match_unmanaged_urn(cmn, api, storage_type, owner_urn, device_info):

    unmanaged_devs_urn_list = api.get_list_of_unmanaged_volume_urns_by_owner(
        storage_type, owner_urn)

    unmanaged_devs_info = api.get_list_unmanaged_volumes_info(
        unmanaged_devs_urn_list)

    # find the right device, return its URN
    unmanaged_device_urn = match_searched_volume_to_candidates(
        cmn,
        device_info,
        unmanaged_devs_info)

    return unmanaged_device_urn


def match_searched_volume_to_candidates(
        cmn,
        source_info,
        candidates_info_list):
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Amongst all possible volume candidacies, looking "
                 "for a match of StorageSystem, NativeID, and WWN properties")

    for candidate_info in candidates_info_list:
        if match_storage_system_urn(source_info, candidate_info) and \
            match_volume_native_id(source_info, candidate_info) and \
            match_volume_wwn(source_info, candidate_info):

            cand_urn = candidate_info.get('id')
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Match is found - {0}".format(cand_urn))
            return cand_urn

    return None


def match_storage_system_urn(source_info, candidate_info):
    #
    # if candidate is a managed volume, the ID is under
    # storage_controller=>URN,
    # if unmanaged, then the ID is under storage_system=>id=>URN
    #
    candidate_ss_urn = candidate_info.get('storage_controller') \
        if 'storage_controller' in candidate_info.keys() \
        else candidate_info.get('storage_system').get('id')

    return source_info.get('storage_controller') == candidate_ss_urn


def match_volume_native_id(source_info, candidate_info):
    source_native_id = source_info.get('native_id')

    #
    # if candidate is a managed volume, use regular comparison
    #
    if 'unmanaged_volumes_info' not in candidate_info.keys():
        return source_native_id == candidate_info.get('native_id')

    candidate_native_id = None
    for cand_info_fragment in candidate_info.get('unmanaged_volumes_info'):
        if cand_info_fragment.get('name') == 'NATIVE_ID':
            candidate_native_id = cand_info_fragment.get('value')
            break
    return source_native_id == candidate_native_id


def match_volume_wwn(source_info, candidate_info):
    return source_info.get('wwn') == candidate_info.get('wwn')


def is_device_eligible_for_this_algorithm(cmn, vipr_api, device_info):
    eligible = True

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Starting eligibility analysis for device [{0}].".format(
                     device_info.get('name')
                 ))

    #
    # catch: devices that are inactive
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if device is inactive...")
    if device_info.get('inactive') is True:
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is inactive.".format(
                         device_info.get('name')
                     ))
        eligible = False

    #
    # catch: a device is in a Consistency Group
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if device is in a CG...")
    if 'consistency_group' in device_info.keys():
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is in a consistency group, algorithm "
                     "doesn't support consistency groups yet:".format(
                         device_info.get('name')
                     ),
                     device_info.get('consistency_group'))
        eligible = False

    #
    # catch: VPLEX devices
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if device is a VPLEX device...")
    if device_info.get('system_type') == 'vplex' or \
        ('high_availability_backing_volumes' in device_info.keys() and \
         len(device_info.get('high_availability_backing_volumes')) > 0):
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is a VPLEX [{1}] device, algorithm "
                     "doesn't support VPLEX devices yet. Below are "
                     "'high_availability_backing_volumes':".format(
                         device_info.get('name'),
                         "local" if len(device_info.get(
                             'high_availability_backing_volumes')) == 1
                         else "distributed"
                     ),
                     device_info.get('high_availability_backing_volumes'))
        eligible = False

    #
    # catch: RPA
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if device is a RPA protected device...")
    if 'protection' in device_info.keys() and \
        device_info.get('protection') is not None and \
        'recoverpoint' in device_info.get('protection').keys():
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is protected by [recoverpoint], "
                     "algorithm doesn't "
                     "support recoverpoint protected devices yet.".format(
                         device_info.get('name')
                     ),
                     device_info.get('protection').get('recoverpoint'))
        eligible = False

    #
    # catch: SRDF
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if device is a SRDF protected device...")
    if 'protection' in device_info.keys() and \
        device_info.get('protection') is not None and \
        'srdf' in device_info.get('protection').keys():
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is protected by [SRDF], "
                     "algorithm doesn't "
                     "support SRDF protected devices yet.".format(
                         device_info.get('name')
                     ),
                     device_info.get('protection').get('srdf'))
        eligible = False

    #
    # catch: devices that have snapshots, snapshot_sessions, continuous
    # copies and full copies.
    #
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Checking if device is protected locally...")
    if len(vipr_api.get_block_volume_protection(
            vipr_api.IDX_BLOCK_PROTECTION_S, device_info)) > 0:
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is protected with [{1}]. Algorithm does "
                     "not support protected devices yet.".format(
                         device_info.get('name'),
                         vipr_api.IDX_BLOCK_PROTECTION_S))
        eligible = False

    if len(vipr_api.get_block_volume_protection(
            vipr_api.IDX_BLOCK_PROTECTION_SS, device_info)) > 0:
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is protected with [{1}]. Algorithm does "
                     "not support protected devices yet.".format(
                         device_info.get('name'),
                         vipr_api.IDX_BLOCK_PROTECTION_SS))
        eligible = False

    if len(vipr_api.get_block_volume_protection(
            vipr_api.IDX_BLOCK_PROTECTION_CC, device_info)) > 0:
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is protected with [{1}]. Algorithm does "
                     "not support protected devices yet.".format(
                         device_info.get('name'),
                         vipr_api.IDX_BLOCK_PROTECTION_CC))
        eligible = False

    if len(vipr_api.get_block_volume_protection(
            vipr_api.IDX_BLOCK_PROTECTION_FC, device_info)) > 0:
        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "Device [{0}] is protected with [{1}]. Algorithm does "
                     "not support protected devices yet.".format(
                         device_info.get('name'),
                         vipr_api.IDX_BLOCK_PROTECTION_FC))
        eligible = False

    #
    # stating final status for the logs
    #
    msg_level = cmn.MSG_LVL_DEBUG if eligible else cmn.MSG_LVL_WARNING
    cmn.printMsg(msg_level,
                 "Device [{0}] is [{1}] to be worked on.".format(
                     device_info.get('name'),
                     "eligible" if eligible else "not eligible"
                 ))

    return eligible


def gather_and_bless_initial_data(cmn, vipr_api,
                                  source_project_name,
                                  target_project_name,
                                  storage_type,
                                  storage_owner_name,
                                  va_name,
                                  vp_name,
                                  volume_name=None
                                  ):
    #
    # get information on source project
    #
    source_project_info = vipr_api.get_project_info_by_name(
        source_project_name
    )
    if source_project_info is None:
        msg = "Problem querying source project [{0}]".format(
            source_project_name)
        cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)

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
    # get va_urn
    #
    va_match_urns = vipr_api.search_by_name(
        vipr_api.IDX_SEARCH_TYPE_VA, va_name, True)
    if len(va_match_urns) != 1:
        msg = "Matched [{0}] VAs to name [{1}], unable to make " \
              "determination".format(
            va_match_urns, va_name)
        cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)
    va_urn = va_match_urns[0]

    #
    # get vp_urn
    #
    vp_match_urns = vipr_api.search_by_name(
        vipr_api.IDX_SEARCH_TYPE_VP, vp_name, True)
    if len(vp_match_urns) != 1:
        msg = "Matched [{0}] VPs to name [{1}], unable to make " \
              "determination".format(
            vp_match_urns, vp_name)
        cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)
    vp_urn = vp_match_urns[0]

    #
    # -------------------- DEVICES ------------------------------------
    #

    # for each device, need to obtain .../exports and trace each Initiator
    # to owner. Do not execute on devices owned by extra owner. For
    # exclusive devices ensure no path leads to a different host. For shared
    # devices ensure no path leads to a different cluster.

    # get a list of device URNs in a project
    all_project_device_urns = []
    source_project_resources_list = vipr_api.get_project_resources_list(
        source_project_info.get('id')
    )
    for source_project_resource in source_project_resources_list:
        # filter out non-volumes
        if source_project_resource.get('resource_type') != 'volume':
            continue
        # if volume name is provided - filter by volume name
        if volume_name is not None and \
            not source_project_resource.get('name').startswith(volume_name):
            continue
        # record all others for further analysis
        all_project_device_urns.append(source_project_resource.get('id'))

    # get info for all devices in the project, and filter out by VA/VP
    # assume that it is cheaper to do that, rather than get exports for
    # absolutely everything
    #
    # once we filter out by ownership, we can use the list to return it
    va_vp_filtered_project_devices_info_map = {}
    all_project_devices_info_list = vipr_api.get_bulk_info_by_list_of_ids(
        vipr_api.API_PST_ALL_VOLUME_DETAILS,
        all_project_device_urns
    )
    for device_info in all_project_devices_info_list:
        id = device_info.get('id')
        this_va_urn = device_info.get('varray').get('id')
        this_vp_urn = device_info.get('vpool').get('id')
        # skip device if it doesn't match VA/VP
        if this_va_urn != va_urn or this_vp_urn != vp_urn:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Device [{0}]=>[{1}] doesn't match VA/VP filter, "
                         "skipping...".format(
                             device_info.get('device_label'),
                             id)
            )
            continue
        va_vp_filtered_project_devices_info_map[id] = device_info

    # get export paths for all devices identified
    # each export path will have initiator, need to trace and cache initiator
    # if at any point we find a path leading to unexpected owner - that
    # device cannot be considered.
    device_export_paths = vipr_api.get_bulk_info_by_list_of_ids(
        vipr_api.API_PST_ALL_VOLUME_EXPORT_PATHS,
        va_vp_filtered_project_devices_info_map.keys()
    )

    # reshape export paths for a clearer picture of where each device is
    # mapped.
    device_to_wwn_paths = dict()
    for export_path in device_export_paths:
        d_urn = export_path.get('device').get('id')
        i_urn = export_path.get('initiator').get('id')
        if d_urn not in device_to_wwn_paths.keys():
            device_to_wwn_paths[d_urn] = list()
        device_to_wwn_paths[d_urn].append(i_urn)

    # now need to figure out what to do...

    # dict to store devices that do not meet eligibility based on paths
    devices_excluded_and_reason = dict()

    # so need to get that list of owner's WWN
    owner_initiators = vipr_api.get_initiators_for_compute(
        storage_type, storage_owner_name, owner_info.get('id'), 'FC'
    )
    owner_to_init_urns_list = list(init_info.get('id')
                                   for init_info in owner_initiators)

    # now compare equivalence of all of owner's initiator URNs with each
    # device's path initiator URNs.
    for device_urn in device_to_wwn_paths.keys():
        device_to_init_urns_list = device_to_wwn_paths[device_urn]

        # perform comparison of unique entries using sets
        if set(device_to_init_urns_list) != set(owner_to_init_urns_list):
            devices_excluded_and_reason[device_urn] = \
                "Owner name mismatch - device is exposed to a different set " \
                "of WWNs than storage owner in argument"

    # announce devices exclusions
    msgs = "{0} devices excluded from consideration:\n".format(
        len(devices_excluded_and_reason.keys()))
    for device_urn in devices_excluded_and_reason.keys():
        dev_info = va_vp_filtered_project_devices_info_map[device_urn]
        dev_name = dev_info.get('device_label')
        dev_reason = devices_excluded_and_reason[device_urn]
        msg = "Device [{0}]=>[{1}] is not considered because: [{2}]".format(
            dev_name, device_urn, dev_reason
        )
        msgs += msg + "\n"
    cmn.printMsg(cmn.MSG_LVL_DEBUG, msgs)

    # devices that we will work on, pre-last filter of device availability
    devices_urn_remaining_list = list(
        set(va_vp_filtered_project_devices_info_map.keys()) -
        set(devices_excluded_and_reason.keys())
    )

    # last eligibility check - this is what our algorithm can work with
    # dbl duty - assemble list of StorageSystems to be discovered also
    final_devices_dict = dict()
    ss_urn_set = set()
    for device_urn in devices_urn_remaining_list:
        device_info = va_vp_filtered_project_devices_info_map[device_urn]
        if not is_device_eligible_for_this_algorithm(cmn,
                                                     vipr_api,
                                                     device_info):
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                'device [{0}]=>[{1}] is not eligible, skipping'.format(
                    device_info.get('device_label'), device_info.get('id'))
            )
        else:
            final_devices_dict[device_urn] = device_info
            ss_urn_set.add(device_info.get('storage_controller'))

    return tenant_urn, \
           va_urn, \
           vp_urn, \
           list(ss_urn_set), \
           source_project_info, \
           target_project_info, \
           storage_type, \
           owner_info, \
           final_devices_dict


def gather_service_catalog_service_urns(cmn, vipr_api,
                                        catalog_uxp_rmv_volume,
                                        catalog_discover_unmanaged_volumes,
                                        catalog_ingest_exported_volume):
    sc_uxp_rmv_urn = vipr_api.fetch_sc_urn(
        catalog_uxp_rmv_volume)
    sc_discover_unmanaged_urn = vipr_api.fetch_sc_urn(
        catalog_discover_unmanaged_volumes)
    sc_ingest_unmanaged_exported_urn = vipr_api.fetch_sc_urn(
        catalog_ingest_exported_volume)

    if sc_uxp_rmv_urn is None or \
        sc_discover_unmanaged_urn is None or \
        sc_ingest_unmanaged_exported_urn is None:
        msg = "One of SC services required cannot be found, " \
              "unable to continue"
        cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
        raise VseExceptions.VSEViPRAPIExc(msg)

    return sc_uxp_rmv_urn, \
           sc_discover_unmanaged_urn, \
           sc_ingest_unmanaged_exported_urn


if __name__ == '__main__':
    main()