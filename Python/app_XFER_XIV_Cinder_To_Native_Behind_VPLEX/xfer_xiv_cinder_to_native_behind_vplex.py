__author__ = 'belens'

"""
v1:
    arguments
        URI of target export group
    outputs
        download XML files from ViPR instance
        output list of field names to be upgraded
    inputs
        target export group uri
        natively-discovered storage system uri
        cinder's targeted pool name (inside cinder driver)

"""

"""
instantiate internal object that deals with data
- that makes it easy to separate fake data from the algorithm
- when i get good data i will deal with instantiating this object properly
"""

import os, argparse, sys
from vseLib.vseCmn import vseCmn, VseExceptions
from vseLib.VseRemoteExecution import VseRemoteExecution

try:
    import xml.etree.cElementTree as eTree
    from xml.etree.cElementTree import ParseError as pE
except ImportError:
    import xml.etree.ElementTree as eTree
    from xml.etree.ElementTree import ParseError as pE

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
        description="%(prog)s provides recommendations for field upgrades "
                    "in XML dumps of records from ViPR DB")

    r_args = parser.add_argument_group('Required Arguments')
    r_args.add_argument('-target_export_group_uri', '-teguri',
                        required=True,
                        help='Specify target export group URI.')
    r_args.add_argument('-target_storage_system_uri', '-tssuri',
                        required=True,
                        help='Specify target storage system URI.')
    r_args.add_argument('-target_virtual_array_uri', '-tvauri',
                        required=True,
                        help='Specify target virtual array URI.')
    r_args.add_argument('-target_virtual_pool_uri', '-tvpuri',
                        required=True,
                        help='Specify target virtual pool URI.')
    r_args.add_argument('-target_storage_pool_name', '-tspname',
                        required=True,
                        help='Specify target storage pool name (from Cinder '
                             'instance driver config file).')
    r_args.add_argument('-export_mask_name_xiv', '-emnamexiv',
                        required=True,
                        help='Specify export mask name on XIV system')
    r_args.add_argument('-export_mask_native_id_xiv', '-emnativeidxiv',
                        required=True,
                        help='Specify export mask native id on XIV system')

    o_args = parser.add_argument_group('Optional Arguments')
    o_args.add_argument('-volume_limit', '-vl',
                        required=False,
                        default=None,
                        help='Specify a limit of how many volumes will get '
                             'processed. Useful for development only')
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

    parser.set_defaults(
        env_settings=DEFAULT_ENV_CFG_FILE,
        default_local_path=DEFAULT_LOCAL_PATH,
        msg_level=vseCmn.MSG_LVL_INFO,
        full_debug=False)

    return parser.parse_args()


def main():
    args = parse_arguments()

    # Initialize environment, if any errors - quite gruesomely
    try:
        cmn = vseCmn(
            "ViPR Remove Cinder for Export Group [{0}].".format(
                args.target_export_group_uri),
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
        vipr_api = VseViprApi(cmn)
        vipr_api.login()

        data_repo = DataRepo(cmn, vipr_api, args)

        #
        # acquire Export Group file, process it, and while processing
        # generate next steps for Export Masks and ?Virtual Volumes? and
        # ?Backing Volumes?
        #
        # for now - produce and save recommendations into data_repo,
        # in order to print them altogether later on
        #
        # processing each VVOL triggers processing of underlying Backing Volume
        #
        process_export_group(cmn, data_repo, args.target_export_group_uri)

        process_export_mask(cmn, data_repo, args.target_export_group_uri)

        process_volumes(cmn, vipr_api, data_repo,
                        args.target_export_group_uri,
                        args.volume_limit)

        data_repo.print_updates(cmn)

        vipr_api.logout()

        pass

    except Exception as e:
        VseExceptions.announce_exception(cmn, e)
        exit_code = cmn.ERROR_GENERIC
        exit_msg = str(e)

    cmn.exit(exit_code, exit_msg)


#
#  processing of volumes
# this is also tricky - because we start from Export Group that is internal
# (it is VPLEX-level export group), the volumes listed are actually XIV's
# volumes, and not VVOLs presented up to the hosts. But we do need to find
# those VVOLs in order to change their VA and VP settings.
#
# we've gotta search in really sneaky ways. typically internal volume's
# label (search by name) will get -# appended to it. So if we shave 2
# characters off the end we should end up with a VVOL name. Then the search
# will return 2 or more volumes. We find the right VVOL by checking that its
# high_availability_backing_volumes refers back to our volume
#
# volumes can start from different VPs, but cust0004 has no
# distributed volumes and always a single VP. so that makes things easier.
#
def process_volumes(cmn, vipr_api, data_repo, eg_uri, limit):
    # if limit is given, convert it to int, else treat as 99999
    limit = 99999 if limit is None else int(limit)

    #
    # get backing volumes URI from prior Export Group work
    #
    backing_volumes_uri = data_repo.get_set_obj(
        data_repo.IDX_EG, eg_uri, data_repo.IDX_EG_BACKING_VOLS)

    volume_counter = 1000
    for backing_volume_uri in backing_volumes_uri:
        if volume_counter >= 1000 + limit:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Reached {1} backing volume records, quitting loop, "
                         "there is {0} records total to process".format(
                             len(backing_volumes_uri), limit))
            break
        process_volume(
            cmn, vipr_api, data_repo, volume_counter, backing_volume_uri)
        volume_counter += 1


def process_volume(cmn, vipr_api, data_repo, volume_counter,
                   backing_volume_uri):
    #
    # deal with Backing Volumes
    # must be done first, process_vvol depends on data_repo contents
    # generated by processing of backing volume
    #
    process_backing_volume(cmn, data_repo, volume_counter, backing_volume_uri)

    #
    # deal with VVOLs
    #
    process_vvol(cmn, vipr_api, data_repo, volume_counter, backing_volume_uri)


def process_vvol(cmn, vipr_api, data_repo, volume_counter, backing_volume_uri):
    #
    # we only have backing_volume_uri, so need to find VVOL first.
    #
    # in database there is a field on VVOLs "associatedVolumes" that is a
    # StringSet of backing volume URIs
    #
    # but there is zilch in the backing volumes themselves. So need to
    # reverse lookup this thing. Going to use search function.
    #

    # process backing volume first.
    # get BV's label, cut it back 2 positions
    # do a lookup for VVOL
    # verify associatedVolumes
    # operate on VVOL
    be_volume_name = data_repo.get_set_obj(data_repo.IDX_BE,
                                           backing_volume_uri,
                                           data_repo.IDX_BE_LABEL)

    match_uris = vipr_api.search_by_name(vipr_api.IDX_SEARCH_TYPE_VOLUME,
                                         be_volume_name[:-2])

    vvol_uri = None
    for match_uri in match_uris:
        if match_uri == backing_volume_uri:
            # found itself, skip
            continue
        # obtain full info on what we found
        volume_info = vipr_api.get_list_of_vipr_volume_details([match_uri])[0]

        # isn't a vplex volume, skip
        if 'high_availability_backing_volumes' not in volume_info.keys():
            continue

        # look into vplex protections
        habvs = volume_info.get('high_availability_backing_volumes')
        for habv in habvs:
            # found our guy!
            if habv.get('id') == backing_volume_uri:
                vvol_uri = match_uri

    if vvol_uri is None:
        cmn.printMsg(cmn.MSG_LVL_ERROR,
                     "Unable to find VVOL for Backing Volume [{0}]".format(
                         backing_volume_uri))


    #
    # finally process VVOL!
    #

    #
    # get XML dump file for the VVOL
    #
    vvol_dmp_file_name = generate_xml_dump_file_name(
        cmn,
        volume_counter,
        "VolumeVirtual",
        vvol_uri)

    vvol_dmp_file_path = obtain_xml_dump_file(
        cmn,
        vvol_dmp_file_name,
        'Volume',
        vvol_uri)

    #
    # parse XML file and load source, next steps, and changes required into
    # data_repo
    #
    try:
        doc_tree = eTree.parse(vvol_dmp_file_path)

        # cache reference to 'record'  - this is parent of all fields
        record = doc_tree.getroot().find('./data_object_schema/record')

        #
        # simple attributes, updating them would be
        # leaf.set('attr_name', 'value')
        #
        leaf_varray = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='varray')[0]
        leaf_virtualPool = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='virtualPool')[0]

        #
        # BV: record data in the data_repo
        #
        data_repo.get_set_obj(data_repo.IDX_VVOL,
                              vvol_uri,
                              data_repo.IDX_ASSOCIATED_FILE_NAME,
                              vvol_dmp_file_name)
        data_repo.get_set_obj(data_repo.IDX_VVOL,
                              vvol_uri,
                              data_repo.IDX_VVOL_VA,
                              leaf_varray.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_VVOL,
                              vvol_uri,
                              data_repo.IDX_VVOL_VP,
                              leaf_virtualPool.attrib['value'])

        #
        # BV: recommend updates (not the same as making updates in XML)
        #
        data_repo.request_update(data_repo.IDX_VVOL,
                                 vvol_uri,
                                 data_repo.IDX_VVOL_VA,
                                 data_repo.get_vvol_new_varray())
        data_repo.request_update(data_repo.IDX_VVOL,
                                 vvol_uri,
                                 data_repo.IDX_VVOL_VP,
                                 data_repo.get_vvol_new_vpool())

    except pE as parse_exc:
        cmn.printMsg(cmn.MSG_LVL_ERROR,
                     "XML parsing error on file [{0}], execution failed: "
                     "".format(vvol_dmp_file_path) + parse_exc.message)
        raise parse_exc


def process_backing_volume(cmn, data_repo, volume_counter, backing_volume_uri):
    #
    # get XML dump file for the Backing Volume
    #
    bv_dmp_file_name = generate_xml_dump_file_name(
        cmn,
        volume_counter,
        "VolumeBacking",
        backing_volume_uri)

    bv_dmp_file_path = obtain_xml_dump_file(
        cmn,
        bv_dmp_file_name,
        'Volume',
        backing_volume_uri)


    #
    # parse XML file and load source, next steps, and changes required into
    # data_repo
    #
    try:
        doc_tree = eTree.parse(bv_dmp_file_path)

        # cache reference to 'record'  - this is parent of all fields
        record = doc_tree.getroot().find('./data_object_schema/record')

        #
        # simple attributes, updating them would be
        # leaf.set('attr_name', 'value')
        #
        leaf_label = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='label')[0]
        leaf_wwn = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='wwn')[0]
        leaf_nativeId = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='nativeId')[0]
        leaf_nativeGuid = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='nativeGuid')[0]
        leaf_storageDevice = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='storageDevice')[0]
        leaf_pool = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='pool')[0]
        leaf_varray = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='varray')[0]
        leaf_virtualPool = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='virtualPool')[0]

        #
        # complex attributes, stringMap or stringSet
        # updating them requires lookup of individual members
        #
        leaf_extensions = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='extensions')[0]

        #
        # BV: record data in the data_repo
        #
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_ASSOCIATED_FILE_NAME,
                              bv_dmp_file_name)
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_LABEL,
                              leaf_label.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_WWN,
                              leaf_wwn.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_NATIVE_ID,
                              leaf_nativeId.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_NATIVE_GUID,
                              leaf_nativeGuid.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_STORAGE_DEVICE,
                              leaf_storageDevice.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_EXTENSIONS,
                              "Don't matter, we will be removing them")
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_STORAGE_POOL,
                              leaf_pool.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_VARRAY,
                              leaf_varray.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_BE,
                              backing_volume_uri,
                              data_repo.IDX_BE_VPOOL,
                              leaf_virtualPool.attrib['value'])

        #
        # BV: recommend updates (not the same as making updates in XML)
        #
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_WWN,
                                 data_repo.get_xiv_volume_wwn(
                                     backing_volume_uri
                                 ))
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_NATIVE_ID,
                                 data_repo.get_be_new_native_id(
                                     backing_volume_uri))
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_NATIVE_GUID,
                                 data_repo.get_be_new_native_guid(
                                     backing_volume_uri))
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_STORAGE_DEVICE,
                                 data_repo.get_be_new_storage_device())
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_EXTENSIONS,
                                 "Remove all ITL related entries")
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_STORAGE_POOL,
                                 data_repo.get_be_new_storage_pool())
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_VARRAY,
                                 data_repo.get_be_new_varray())
        data_repo.request_update(data_repo.IDX_BE,
                                 backing_volume_uri,
                                 data_repo.IDX_BE_VPOOL,
                                 data_repo.get_be_new_vpool())

    except pE as parse_exc:
        cmn.printMsg(cmn.MSG_LVL_ERROR,
                     "XML parsing error on file [{0}], execution failed: "
                     "".format(bv_dmp_file_path) + parse_exc.message)
        raise parse_exc

#
# processing of EG actually depends on this, so maybe need to cut it into EG
#  processing... need to think about that.
#
def process_export_mask(cmn, data_repo, eg_uri):
    #
    # get Export Mask URI from prior Export Group work
    #
    em_uri = data_repo.get_set_obj(
        data_repo.IDX_EG, eg_uri, data_repo.IDX_EG_EMS)[0]

    #
    # get XML dump file for Export Group
    #
    em_dmp_file_name = generate_xml_dump_file_name(
        cmn,
        2,
        "ExportMask",
        em_uri)

    em_dmp_file_path = obtain_xml_dump_file(
        cmn,
        em_dmp_file_name,
        'ExportMask',
        em_uri)

    #
    # parse XML file and load source, next steps, and changes required into
    # data_repo
    #
    try:
        doc_tree = eTree.parse(em_dmp_file_path)

        # cache reference to 'record'  - this is parent of all fields
        record = doc_tree.getroot().find('./data_object_schema/record')

        #
        # simple attributes, updating them would be
        # leaf.set('attr_name', 'value')
        #
        leaf_createdBySystem = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='createdBySystem')[0]
        leaf_maskName = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='maskName')[0]
        leaf_storageDevice = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='storageDevice')[0]

        #
        # complex attributes, stringMap or stringSet
        # updating them requires lookup of individual members
        #
        leaf_root_initiators = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='initiators')[0]
        leaf_root_userAddedInitiators = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='userAddedInitiators')[0]
        leaf_root_storagePorts = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='storagePorts')[0]
        leaf_root_userAddedVolumes = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='userAddedVolumes')[0]
        leaf_root_deviceDataMap = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='deviceDataMap')[0]
        leaf_root_zoningMap = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='zoningMap')[0]

        #
        # element.text         - accesses URI of initiator
        # element.text = value - changes text to value
        #
        leaves_initiators = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_initiators, 'stringSet')

        initiator_uris = []
        for leaf in leaves_initiators:
            initiator_uris.append(leaf.text)

        #
        # userAddedInitiators also has Initiator URIs as 'value'. For now
        # just want to pull list of initiator WWNs.
        #
        # <field name="userAddedInitiators" type="com.emc.storageos.db.client.model.StringMap">
        #     <wrapper>
        #         <stringMap>
        #             <entry>
        #                 <key>50001442804E4910</key>
        #                 <value>urn:storageos:Initiator:436fa9e3-cb79-4d9f-bdda-19ebf13d2eec:vdc1</value>
        #             </entry>
        #             ...
        #         </stringMap>
        #     </wrapper>
        # </field>

        leaves_userAddedInitiators = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_userAddedInitiators, 'entry')

        userAddedInitiators_uri_wwn = []
        for leaf in leaves_userAddedInitiators:
            userAddedInitiators_uri_wwn.append("{0}={1}".format(
                leaf.find('value').text, leaf.find('key').text
            ))

        #
        # storage ports
        #
        leaves_storagePorts = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_storagePorts, 'stringSet')

        storage_ports_uris = []
        for leaf in leaves_storagePorts:
            storage_ports_uris.append(leaf.text)

        #
        # userAddedVolumes are tricky.
        #
        #     <field name="userAddedVolumes" type="com.emc.storageos.db.client.model.StringMap">
        #         <wrapper>
        #             <stringMap>
        #                 <entry>
        #                     <key>34470E3B1BE24A9CB8B81CAD23A7F911</key>
        #                     <value>urn:storageos:Volume:48227a59-bc88-4516-a2a3-ade6a5a1302b:vdc1</value>
        #                 </entry>
        #                 ...
        #             </stringMap>
        #         </wrapper>
        #     </field>
        #
        leaves_userAddedVolumes = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_userAddedVolumes, 'entry')

        userAddedVolumes_uri_cinderID = []
        for leaf in leaves_userAddedVolumes:
            userAddedVolumes_uri_cinderID.append("{0}={1}".format(
                leaf.find('value').text, leaf.find('key').text
            ))

        #
        # deviceDataMap is similar to userAddedVolumes
        #
        # <field name="deviceDataMap" type="com.emc.storageos.db.client.model.StringSetMap">
        #     <wrapper>
        #         <stringSetMap>
        #             <entry>
        #                 <key>ImmutableZoningMap</key>
        #                 <value>true</value>
        #             </entry>
        #         </stringSetMap>
        #     </wrapper>
        # </field>
        leaves_deviceDataMap = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_deviceDataMap, 'entry')

        deviceDataMap_key_value = []
        for leaf in leaves_deviceDataMap:
            deviceDataMap_key_value.append("{0}={1}".format(
                leaf.find('key').text, leaf.find('value').text
            ))

        #
        # zoning Map is "special" - it can have multiple value entries. That
        #  requires a separate level of searching. Just not important for
        # what we are trying to do here, since the instruction is 'remove
        # entries'
        #
        # <field name="zoningMap" type="com.emc.storageos.db.client.model.StringSetMap">
        #     <wrapper>
        #         <stringSetMap>
        #             <entry>
        #                 <key>urn:storageos:Initiator:9bb3508c-c608-4859-ab4d-b7fe01e32e51:vdc1</key>
        #                 <value>urn:storageos:StoragePort:3773fefd-4538-40ba-ae64-ee2c0af02ba5:vdc1</value>
        #             </entry>
        #             <entry>
        #                 <key>urn:storageos:Initiator:feeabb48-f09f-4009-a916-c780aa9badb0:vdc1</key>
        #                 <value>urn:storageos:StoragePort:3546e6ec-a4e1-4607-b9c5-46adf09911f3:vdc1</value>
        #                 <value>urn:storageos:StoragePort:64b13d06-5bb5-4783-9868-98f04d01b844:vdc1</value>
        #             </entry>
        #         </stringSetMap>
        #     </wrapper>
        # </field>
        zoningMap = "There may be entries, but algorithm ignores them all"

        #
        # EM: record data in the data_repo
        #
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_ASSOCIATED_FILE_NAME,
                              em_dmp_file_name)
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_CRT_BY_SYSTEM,
                              leaf_createdBySystem.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_INITS,
                              initiator_uris)
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_EXISTING_INITS,
                              "No Entry Exists")
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_MASK_NAME,
                              leaf_maskName.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_NATIVE_ID,
                              "No Entry Exists")
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_SS,
                              leaf_storageDevice.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_SPORTS,
                              storage_ports_uris)
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_USER_ADDED_VOLUMES,
                              userAddedVolumes_uri_cinderID)
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_DEVICE_DATA_MAP,
                              deviceDataMap_key_value)
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_USER_ADDED_INITIATORS,
                              userAddedInitiators_uri_wwn)
        data_repo.get_set_obj(data_repo.IDX_EM,
                              em_uri,
                              data_repo.IDX_EM_ZONING_MAP,
                              zoningMap)

        #
        # EM: recommend updates (not the same as making updates in XML)
        #
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_CRT_BY_SYSTEM,
                                 'false')
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_INITS,
                                 "TODO: remove entries")
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_EXISTING_INITS,
                                 data_repo.get_em_new_existing_inits(em_uri))
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_NATIVE_ID,
                                 "create entry for native ID: {0}".format(
                                     data_repo.get_em_new_native_id()))
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_SS,
                                 data_repo.get_em_new_storage_system_uri())
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_SPORTS,
                                 data_repo.get_em_new_storage_system_ports(
                                     em_uri))
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_USER_ADDED_VOLUMES,
                                 data_repo.get_em_new_user_added_volumes(
                                     em_uri))
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_DEVICE_DATA_MAP,
                                 data_repo.get_em_new_device_data_map())
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_ZONING_MAP,
                                 "TODO: remove entries")
        data_repo.request_update(data_repo.IDX_EM,
                                 em_uri,
                                 data_repo.IDX_EM_USER_ADDED_INITIATORS,
                                 "TODO: remove entries")

    except pE as parse_exc:
        cmn.printMsg(cmn.MSG_LVL_ERROR,
                     "XML parsing error on file [{0}], execution failed: "
                     "".format(em_dmp_file_path) + parse_exc.message)
        raise parse_exc


#
# from Export Group XML file, I can extract this info:
#   - initiators (VPLEX B-E)
#   - exportMasks (next analysis step URN, always is 1 in my use case)
#   - volumes (VPLEX VVols, next analysis step URNs, 0+)
#   * label
#   * project
#   * tenant
#   * varray
#   * generatedName
#
# marked with * are values that I need to change
#
def process_export_group(cmn, data_repo, eg_uri):
    #
    # get XML dump file for Export Group
    #
    eg_dmp_file_name = generate_xml_dump_file_name(
        cmn,
        1,
        "ExportGroup",
        eg_uri)

    eg_dmp_file_path = obtain_xml_dump_file(
        cmn,
        eg_dmp_file_name,
        'ExportGroup',
        eg_uri)

    #
    # parse XML file and load source, next steps, and changes required into
    # data_repo
    #
    try:
        doc_tree = eTree.parse(eg_dmp_file_path)

        # cache reference to 'record'  - this is parent of all fields
        record = doc_tree.getroot().find('./data_object_schema/record')

        #
        # simple attributes, updating them would be
        # leaf.set('attr_name', 'value')
        #
        leaf_label = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='label')[0]
        leaf_project = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='project')[0]
        leaf_tenant = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='tenant')[0]
        leaf_varray = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='varray')[0]
        leaf_gName = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='generatedName')[0]

        #
        # complex attributes, stringMap or stringSet
        # updating them requires lookup of individual members
        #
        leaf_root_initiators = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='initiators')[0]
        leaf_root_exportMasks = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='exportMasks')[0]
        leaf_root_volumes = get_xml_leaves_by_name_from_root(
            cmn, doc_tree, 'field', filter_name='volumes')[0]

        #
        # element.text         - accesses URI of initiator
        # element.text = value - changes text to value
        #
        leaves_initiators = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_initiators, 'stringSet')
        leaves_exportMasks = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_exportMasks, 'stringSet')
        leaves_volumes = get_xml_leaves_by_name_from_root(
            cmn, leaf_root_volumes, 'key')

        initiator_uris = []
        for leaf in leaves_initiators:
            initiator_uris.append(leaf.text)

        exportMask_uris = []
        for leaf in leaves_exportMasks:
            exportMask_uris.append(leaf.text)

        backing_volumes_uris = []
        for leaf in leaves_volumes:
            backing_volumes_uris.append(leaf.text)

        #
        # EG: record data in the data_repo
        #
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_ASSOCIATED_FILE_NAME,
                              eg_dmp_file_name)
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_LABEL,
                              leaf_label.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_PROJECT,
                              leaf_project.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_TENANT,
                              leaf_tenant.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_VARRAY,
                              leaf_varray.attrib['value'])
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_GNAME,
                              leaf_gName.attrib['value'])

        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_INITS,
                              initiator_uris)
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_EMS,
                              exportMask_uris)
        data_repo.get_set_obj(data_repo.IDX_EG,
                              eg_uri,
                              data_repo.IDX_EG_BACKING_VOLS,
                              backing_volumes_uris)

        #
        # EG: recommend updates (not the same as making updates in XML)
        #
        data_repo.request_update(data_repo.IDX_EG,
                                 eg_uri,
                                 data_repo.IDX_EG_GNAME,
                                 data_repo.get_eg_new_generated_name())

        data_repo.request_update(data_repo.IDX_EG,
                                 eg_uri,
                                 data_repo.IDX_EG_LABEL,
                                 data_repo.get_eg_new_label())

        data_repo.request_update(data_repo.IDX_EG,
                                 eg_uri,
                                 data_repo.IDX_EG_PROJECT,
                                 data_repo.get_eg_new_project(eg_uri))

        data_repo.request_update(data_repo.IDX_EG,
                                 eg_uri,
                                 data_repo.IDX_EG_TENANT,
                                 data_repo.get_eg_new_tenant(eg_uri))

        data_repo.request_update(data_repo.IDX_EG,
                                 eg_uri,
                                 data_repo.IDX_EG_VARRAY,
                                 data_repo.get_eg_new_varray())

    except pE as parse_exc:
        cmn.printMsg(cmn.MSG_LVL_ERROR,
                     "XML parsing error on file [{0}], execution failed: "
                     "".format(eg_dmp_file_path) + parse_exc.message)
        raise parse_exc


#
# lookup and return xml tree leaf by field_name
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

    for leaf in leaves:
        msg = "FOUND Element for update: \n" \
              "\tTag       : " + str(leaf.tag) + "\n" \
              "\tAttributes: " + str(leaf.attrib) + "\n" \
              "\tValue     : " + str(leaf) + "\n"
        if leaf.text is not None:
            msg += "\tText      : " + leaf.text + "\n"
        else:
            msg += "\tText      : None\n"
        cmn.printMsg(cmn.MSG_LVL_DEBUG, msg)

    return leaves


def generate_xml_dump_file_name(cmn, number, concept, uri):
    name = '{0}_{1}_{2}'.format(
        '{0:04d}'.format(number),
        concept,
        uri
    ).replace(':','-')

    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Local filename for {0} [{1}] will be: {2}".format(
                     concept,
                     uri,
                     name
                 ))

    return name


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


#
# NOTE: I am turning things into lists in order to store them, BUT:
# but maybe I need to be turning them into hashs, so I can make updates and
# translate back directly into XML
#
class DataRepo:

    IDX_CMN = "lib_cmn"
    IDX_API = "lib_api"

    IDX_ASSOCIATED_FILE_NAME = "xml file name"

    IDX_EG = "export_group"
    IDX_EG_URI = "uri"
    IDX_EG_LABEL = "label"
    IDX_EG_PROJECT = "project"
    IDX_EG_TENANT = "tenant"
    IDX_EG_VARRAY = "varray"
    IDX_EG_GNAME = "generatedName"
    IDX_EG_INITS = "initiators"
    IDX_EG_EMS = "exportMasks"
    IDX_EG_BACKING_VOLS = "volumes"

    IDX_EM = "export_mask"
    IDX_EM_CRT_BY_SYSTEM = "createdBySystem"
    IDX_EM_URI = "uri"
    IDX_EM_INITS = "initiators"
    IDX_EM_EXISTING_INITS = "existingInitiators"
    IDX_EM_MASK_NAME = "maskName"
    IDX_EM_NATIVE_ID = "nativeId"
    IDX_EM_SS = "storageDevice"
    IDX_EM_SPORTS = "storagePorts"
    IDX_EM_USER_ADDED_VOLUMES = "userAddedVolumes"
    IDX_EM_DEVICE_DATA_MAP = "deviceDataMap"
    IDX_EM_ZONING_MAP = "zoningMap"
    IDX_EM_USER_ADDED_INITIATORS = "userAddedInitiators"

    IDX_BE = "volume_backing"
    IDX_BE_LABEL = "label"
    IDX_BE_WWN = "wwn"
    IDX_BE_NATIVE_ID = "nativeId"
    IDX_BE_NATIVE_GUID = "nativeGuid"
    IDX_BE_STORAGE_DEVICE = "storageDevice"
    IDX_BE_EXTENSIONS = "extensions"
    IDX_BE_STORAGE_POOL = "pool"
    IDX_BE_VARRAY = "varray"
    IDX_BE_VPOOL = "virtualPool"

    IDX_VVOL = "volume_virtual"
    IDX_VVOL_VA = "varray"
    IDX_VVOL_VP = "virtualPool"

    IDX_UPDATES = "updates"

    IDX_INFO_TGT_EXP_GRP = "info_target_export_group"
    IDX_INFO_TGT_EXP_MSK = "info_target_export_mask"
    IDX_INFO_TGT_EXP_MSK_NAME = "info_target_export_mask_name"
    IDX_INFO_TGT_EXP_MSK_NATIVE_ID = "info_export_mask_native_id"
    IDX_INFO_TGT_STORAGE_SYSTEM = "info_target_storage_system"
    IDX_INFO_TGT_STORAGE_POOL = "info_target_storage_pool"
    IDX_INFO_SRC_DEV_LIB = "info_devices_additional_info"
    IDX_INFO_TGT_VIRTUAL_ARRAY = "info_target_virtual_array"
    IDX_INFO_TGT_VIRTUAL_POOL = "info_target_virtual_pool"


    #
    # take cmn, vipr_api, target export group uri, target storage system uri,
    # target storage pool name, (+Future: additional file with information)
    #
    # throw exception if anyone item is not found.
    #
    def __init__(self, cmn, vipr_api, args):
        self.data = dict()
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Instantiating Data Repository. Confirming passed in "
                     "variables are good...")

        self.data[self.IDX_CMN] = cmn
        self.data[self.IDX_API] = vipr_api

        #
        # args coming in
        #
        teg_uri = args.target_export_group_uri
        tss_uri = args.target_storage_system_uri
        tsp_name = args.target_storage_pool_name
        tem_name = args.export_mask_name_xiv
        tem_nativeid = args.export_mask_native_id_xiv
        tva_uri = args.target_virtual_array_uri
        tvp_uri = args.target_virtual_pool_uri

        #
        # get data on Target Export Group - that's the group we're going to
        # modify
        #
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Confirming TargetExportGroup [{0}] is "
                     "ok...".format(teg_uri))
        teg_info = vipr_api.get_eg_info_by_uri(teg_uri)
        if teg_info is None or \
           'id' not in teg_info.keys() or \
           teg_info.get('id') != teg_uri or \
           teg_info.get('inactive') == 'true':
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Target Export Group [{0}] - something is "
                         "wrong, check for invalid uri or group may be "
                         "inactive".format(teg_uri))
            raise VseExceptions.VSEViPRAPIExc("problem with target export "
                                              "group uri")
        self.data[self.IDX_INFO_TGT_EXP_GRP] = teg_info

        #
        # get data on Target Storage System - that's the natively discovered
        #  XIV
        #
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Confirming TargetStorageSystem [{0}] is "
                     "ok...".format(tss_uri))
        tss_info = vipr_api.get_storage_system_info_by_uri(tss_uri)
        if tss_info is None or \
           'id' not in tss_info.keys() or \
           tss_info.get('id') != tss_uri or \
           tss_info.get('inactive') == 'true':
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Target Storage System [{0}] - something is "
                         "wrong, check for invalid uri or may be "
                         "inactive".format(tss_uri))
            raise VseExceptions.VSEViPRAPIExc("problem with target storage "
                                              "system uri")
        self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM] = tss_info

        #
        # get data on TSS's Storage Pool - that's the natively discovered
        # storage pool URI where all these devices already are, but need to
        # get the new URI of it.
        #
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Confirming TargetStoragePool [{0}] is "
                     "ok...".format(tsp_name))
        spools_uri_list = vipr_api.get_storage_pool_uris_by_ss_uri(tss_uri)
        tspool_info = None
        for spool_uri_info in spools_uri_list:
            spool_info = vipr_api.get_storage_pool_info_by_uri(
                spool_uri_info.get('id'))
            if spool_info is None or \
               'id' not in spool_info.keys() or \
               spool_info.get('pool_name') != tsp_name or \
               spool_info.get('inactive') == 'true':
                continue
            tspool_info = spool_info
            break
        if tspool_info is None:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Target Storage Pool [{0}] - unable to find"
                         "".format(tsp_name))
            raise VseExceptions.VSEViPRAPIExc("problem with target storage "
                                              "pool - cant find it")
        self.data[self.IDX_INFO_TGT_STORAGE_POOL] = tspool_info

        #
        # get data on Target Virtual Array - that could be URI of the same
        # VA (with added natively discovered XIV system) or a brand new VA
        # that has been pre-created with natively discovered XIV system
        #
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Confirming TargetVirtualArray [{0}] is "
                     "ok...".format(tva_uri))
        tva_info = vipr_api.get_va_info_by_uri(tva_uri)
        if tva_info is None or \
           'id' not in tva_info.keys() or \
           tva_info.get('id') != tva_uri or \
           tva_info.get('inactive') == 'true':
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Target Virtual Array [{0}] - something is "
                         "wrong, check for invalid uri or may be "
                         "inactive".format(tss_uri))
            raise VseExceptions.VSEViPRAPIExc("problem with target virtual "
                                              "array uri")
        self.data[self.IDX_INFO_TGT_VIRTUAL_ARRAY] = tva_info

        #
        # get data on Target Virtual Pool - same premise as TVA
        #
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Confirming TargetVirtualPool [{0}] is "
                     "ok...".format(tva_uri))
        tvp_info = vipr_api.get_vp_info_by_uri(tvp_uri)
        if tvp_info is None or \
           'id' not in tvp_info.keys() or \
           tvp_info.get('id') != tvp_uri or \
           tvp_info.get('inactive') == 'true':
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Target Virtual Pool [{0}] - something is "
                         "wrong, check for invalid uri or may be "
                         "inactive".format(tvp_uri))
            raise VseExceptions.VSEViPRAPIExc("problem with target virtual "
                                              "pool uri")
        self.data[self.IDX_INFO_TGT_VIRTUAL_POOL] = tvp_info


        #
        # need to get name/native_id of export mask from the user.
        #
        self.data[self.IDX_INFO_TGT_EXP_MSK_NAME] = tem_name
        self.data[self.IDX_INFO_TGT_EXP_MSK_NATIVE_ID] = tem_nativeid

        #
        # TODO: load up devices data file
        # at minimum we are missing info on volumes' nativeID and WWN,
        # mapped to their names (volume-[cinder id])
        #

        pass


    #
    # generated name is a combo of
    # [name of export mask]_[systemtype][last 4 of serial]
    #   --- name of export mask is not what ViPR things it is. Export Mask
    # has name as it is "madeup" via Cinder, but in reality who the hell
    # knows. need user input!
    #
    # example: VPLEX_Director1_BE_Ports_ibmxiv2782
    #
    def get_eg_new_generated_name(self):
        return "{0}_{1}{2}".format(
            self.data[self.IDX_INFO_TGT_EXP_MSK_NAME],
            self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get(
                'system_type'),
            self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get(
                'serial_number')[-4:],

        )


    def get_eg_new_label(self):
        return self.get_eg_new_generated_name()


    #
    # project field in database is a combo of [project]:[generated name]
    #
    def get_eg_new_project(self, uri):
        # figure out just the legacy project URI
        legacy_project_field_value = self.get_set_obj(
            self.IDX_EG, uri, self.IDX_EG_PROJECT)
        undesired_suffix = ':{0}'.format(
            self.get_set_obj(self.IDX_EG, uri, self.IDX_EG_GNAME))
        just_project_uri = legacy_project_field_value.replace(
            undesired_suffix, '')

        return "{0}:{1}".format(
            just_project_uri,
            self.get_eg_new_generated_name())


    def get_eg_new_tenant(self, uri):
        # figure out just the legacy tenant URI
        legacy_tenant_field_value = self.get_set_obj(
            self.IDX_EG, uri, self.IDX_EG_TENANT)
        undesired_suffix = ':{0}'.format(
            self.get_set_obj(self.IDX_EG, uri, self.IDX_EG_GNAME))
        just_tenant_uri = legacy_tenant_field_value.replace(
            undesired_suffix, '')

        return "{0}:{1}".format(
            just_tenant_uri,
            self.get_eg_new_generated_name())


    def get_eg_new_varray(self):
        return self.data[self.IDX_INFO_TGT_VIRTUAL_ARRAY].get('id')


    def get_set_obj(self, obj, uri, parameter, value=None):
        if obj not in self.data.keys():
            self.data[obj] = {}
        hash_Obj = self.data[obj]

        if uri not in hash_Obj.keys():
            hash_Obj[uri] = {}
        uri_obj = hash_Obj[uri]

        if value is None:
            return uri_obj[parameter]
        else:
            uri_obj[parameter] = value
            return value


    def request_update(self, obj, uri, parameter, update):
        if self.IDX_UPDATES not in self.data.keys():
            self.data[self.IDX_UPDATES] = {}
        updates_obj = self.data[self.IDX_UPDATES]

        if obj not in updates_obj.keys():
            updates_obj[obj] = {}
        hash_obj = updates_obj[obj]

        if uri not in hash_obj.keys():
            hash_obj[uri] = {}
        uri_obj = hash_obj[uri]

        uri_obj[parameter] = update
        return update


    def print_updates(self, cmn):
        #
        #  build a readable message about all requested updates
        #
        msg = "Updates to be performed: \n"

        updates_hash = self.data[self.IDX_UPDATES]
        for obj_key in sorted(updates_hash.keys()):
            for obj_uri in updates_hash[obj_key].keys():
                changes_hash = updates_hash[obj_key][obj_uri]
                msg += "\n\tOn [{0}]=>[{1}]=>[{2}]\n".format(
                    obj_key,
                    obj_uri,
                    self.get_set_obj(obj_key,
                                     obj_uri,
                                     self.IDX_ASSOCIATED_FILE_NAME))
                for prop in changes_hash.keys():
                    new_value = changes_hash[prop]
                    old_value = self.get_set_obj(obj_key, obj_uri, prop)
                    msg += "\t\tChange property [{0}]:\n" \
                           "\t\t\tOLD VALUE: {1}\n\t\t\tNEW VALUE: {2}\n" \
                           "".format(prop, old_value, new_value)

        cmn.printMsg(cmn.MSG_LVL_INFO, msg)


    def get_em_new_native_id(self):
        # [part of system name in ViPR after + sign
        #  (e.g.: "IBMXIV+IBM.2810-7812782")]-[native id of export
        # mask prefixed with 0s to be 16 digits total]
        # e.g. IBM.2810-7812782-00000a3f14500059
        return "{0}-{1}".format(
            self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('serial_number'),
            str(self.data[self.IDX_INFO_TGT_EXP_MSK_NATIVE_ID]).zfill(16)
        )


    def get_em_new_storage_system_uri(self):
        return self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('id')

    # returns list of natively discovered SS storage port uris that match,
    # by name, a list of storage ports referenced on cinder-discovered
    # system that were pulled from export mask's storage ports.
    def get_em_new_storage_system_ports(self, em_uri):
        cmn = self.data[self.IDX_CMN]
        vipr_api = self.data[self.IDX_API]

        c_port_infos = vipr_api.get_bulk_info_by_list_of_ids(
            vipr_api.API_PST_ALL_STORAGE_PORT_DETAILS,
            self.get_set_obj(self.IDX_EM, em_uri, self.IDX_EM_SPORTS)
        )

        n_all_ports_urns = vipr_api.get_storage_port_uris_by_ss_uri(
            self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('id')
        )
        n_port_infos = vipr_api.get_bulk_info_by_list_of_ids(
            vipr_api.API_PST_ALL_STORAGE_PORT_DETAILS,
            n_all_ports_urns
        )
        n_port_infos_by_wwns = cmn.convert_list_of_dict_objects_into_dict_by_id(
            n_port_infos, 'port_network_id')

        # find matches by storage port wwn
        n_ports_in_em_uris = []
        for c_port_info in c_port_infos:
            c_port_wwn = c_port_info.get('port_network_id')
            if c_port_wwn not in n_port_infos_by_wwns:
                raise VseExceptions.VSEViPRAPIExc(
                    "Cinder port {0}=>[{1}] is not found in native array [{"
                    "2}], when looking by WWN.".format(
                        c_port_wwn,
                        c_port_info.get('id'),
                        self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('id')))
            n_port_info = n_port_infos_by_wwns[c_port_wwn]
            n_ports_in_em_uris.append(n_port_info.get('id'))

        return n_ports_in_em_uris


    def get_em_new_user_added_volumes(self, em_uri):
        cinder_user_added_volumes = self.get_set_obj(
            self.IDX_EM, em_uri, self.IDX_EM_USER_ADDED_VOLUMES)
        native_user_added_volumes = []
        for cuav in cinder_user_added_volumes:
            (cuav_urn, cuav_cinder_id) = cuav.split('=')
            native_user_added_volumes.append(
                "{0}={1}".format(cuav_urn,
                                 self.get_xiv_volume_wwn(cuav_urn)))
        return native_user_added_volumes

    # TODO: from volume URN, retrieve volume data from ViPR, and map to
    # passed in volume map, to get that volume's WWN
    # TODO: cache the volume because it might be requested again
    def get_xiv_volume_wwn(self, urn):
        return "fake_xiv_volume_wwn for urn"

    def get_em_new_device_data_map(self):
        # TODO: figure this out
        return "TODO: instructions say 'remove entries', but need to verify"


    def get_em_new_existing_inits(self, em_uri):
        # userAddedInitiators: [uri=wwn,...] of VPLEX B-E ports
        #   (that's not a precise representation of field in original EM)
        #   (the field uAI needs to be removed, so we mangled for our
        # convenience)
        #
        # need: [wwn,wwn,...] of VPLEX B-E ports
        user_added_initiators = self.get_set_obj(
            self.IDX_EM, em_uri, self.IDX_EM_USER_ADDED_INITIATORS)
        vplex_be_wwns = []
        for uai in user_added_initiators:
            (uri, wwn) = uai.split('=')
            vplex_be_wwns.append(wwn)
        return vplex_be_wwns


    # TODO: get native id of the volume from XIV system. IDK how.
    def get_be_volume_xiv_native_id(self, be_volume_uri):
        # this is native identifier of a volume in XIV system
        # this is a component of ViPR BE Volume's nativeId and nativeGuid
        # fields
        return "fake_value_native_id_of_volume_on_xiv"


    def get_be_new_native_id(self, be_volume_uri):
        # [part of system name after '+' sign]-[actual volume id from xiv]
        return "{0}-{1}".format(
            self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('serial_number'),
            self.get_be_volume_xiv_native_id(be_volume_uri)
        )


    def get_be_new_native_guid(self, be_volume_uri):
        # [storage system name]+VOLUME+[nativeId field]
        return "{0}+VOLUME+{1}".format(
            self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('native_guid'),
            self.get_be_new_native_id(be_volume_uri)
        )


    def get_be_new_storage_device(self):
        return self.data[self.IDX_INFO_TGT_STORAGE_SYSTEM].get('id')


    def get_be_new_storage_pool(self):
        # there is only 1 storage pool existing in XIV, always, so simple.
        return self.data[self.IDX_INFO_TGT_STORAGE_POOL].get('id')


    def get_be_new_varray(self):
        return self.data[self.IDX_INFO_TGT_VIRTUAL_ARRAY].get('id')


    def get_be_new_vpool(self):
        return self.data[self.IDX_INFO_TGT_VIRTUAL_POOL].get('id')


    def get_vvol_new_varray(self):
        return self.data[self.IDX_INFO_TGT_VIRTUAL_ARRAY].get('id')

    def get_vvol_new_vpool(self):
        return self.data[self.IDX_INFO_TGT_VIRTUAL_POOL].get('id')

if __name__ == '__main__':
    main()
