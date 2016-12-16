__author__ = 'belens'

"""
facade for ViPR CLI block volume features

To "simulate" PYTHONPATH runtime modification, one can use
File->Settings->ProjectStructure->AddContentRoot->[add CLI python libraries
path]
"""

import string
import time
import re

from vseCmn import module_var
from VseHttp import VseHttp, json_decode, json_encode


class VseViprApi:
    IDX_CMN = "Module_Ref_Common"
    IDX_VIPR_SESSION = "ViPR_Session"

    #
    # GET = GET
    # PST = POST
    # PUT = PUT
    # DEL = DELETE
    # MLT = Multiple methods
    #

    #
    # search API calls
    #
    IDX_SEARCH_TYPE_HOST = '/compute/hosts'
    IDX_SEARCH_TYPE_CLUSTER = '/compute/clusters'
    IDX_SEARCH_TYPE_PROJECT = '/projects'
    IDX_SEARCH_TYPE_VOLUME = '/block/volumes'
    IDX_SEARCH_TYPE_VA = '/vdc/varrays'
    IDX_SEARCH_TYPE_VP = '/block/vpools'

    API_GET_SEARCH_BY_NAME = "{0}/search?name={1}"

    #
    # tag resource API calls
    #
    IDX_TAG_BLOCK_VOLUME = "/block/volumes"

    IDX_TAG_ACTION_GET = "get volume tags"
    IDX_TAG_ACTION_ADD = "add volume tags"
    IDX_TAG_ACTION_RMV = "remove volume tags"

    API_GET_TAGS = "{0}/{1}/tags"
    API_PUT_TAGS = "{0}/{1}/tags"

    #
    # initiators
    #
    API_PST_INIT_BULK_INFO = "/compute/initiators/bulk"

    #
    # hosts
    #
    API_PST_HOST_BULK_INFO = "/compute/hosts/bulk"
    API_GET_HOST_INITIATORS = "/compute/hosts/{0}/initiators"

    #
    # clusters
    #
    API_PST_CLUSTER_BULK_INFO = "/compute/clusters/bulk"
    API_GET_CLUSTER_HOSTS = "/compute/clusters/{0}/hosts"

    #
    # projects
    #
    API_GET_PROJECT = "/projects/{0}"
    API_GET_PROJECT_SEARCH_BY_NAME = "/projects/search?name={0}"
    API_GET_PROJECT_RESOURCES = "/projects/{0}/resources"

    #
    # storage systems
    #
    API_GET_STORAGE_SYSTEMS = "/vdc/storage-systems"
    API_GET_STORAGE_SYSTEM = "/vdc/storage-systems/{0}"
    API_GET_STORAGE_SYSTEM_POOLS = "/vdc/storage-systems/{0}/storage-pools"
    API_GET_STORAGE_POOL = "/vdc/storage-pools/{0}"
    API_GET_STORAGE_SYSTEM_PORTS = "/vdc/storage-systems/{0}/storage-ports"
    API_PST_ALL_STORAGE_PORT_DETAILS = "/vdc/storage-ports/bulk"

    #
    # volumes
    #
    API_GET_ALL_VOLUME_URNS = "/block/volumes/bulk"
    API_PST_ALL_VOLUME_DETAILS = "/block/volumes/bulk"
    API_PST_ALL_VOLUME_EXPORT_PATHS = "/block/volumes/exports/bulk"
    API_GET_VOLUME_PROTECTION = "/block/volumes/{0}/protection/{1}"

    #
    # export groups
    #
    API_GET_EXPORT_GROUP = "/block/exports/{0}"

    #
    # replication and mirrors
    #
    API_PST_RDF_SET_MODE = \
        "/block/volumes/{0}/protection/continuous-copies/copymode"
    API_GET_RDFG_ON_STORAGE_SYSTEM = \
        "/vdc/storage-systems/{0}/rdf-groups/{1}"
    API_POST_RDF_OP = \
        "/block/volumes/{0}/protection/continuous-copies/{1}"
    API_GET_NATIVE_MIRROR = \
        "/block/volumes/{0}/protection/continuous-copies/{1}"
    API_PST_NATIVE_MIRROR_OP = \
        "/block/volumes/{0}/protection/continuous-copies/{1}"

    #
    # virtual arrays
    #
    API_GET_VA = "/vdc/varrays/{0}"

    #
    # virtual pools
    #
    API_GET_BLOCK_VP = "/block/vpools/{0}"

    #
    # consistency groups
    #
    API_GET_BLOCK_CG = "/block/consistency-groups/{0}"

    #
    # tasks
    #
    API_GET_TASK = "/vdc/tasks/{0}"

    #
    # Service Catalog, Orders
    #
    API_GET_ALL_CATALOG_SERVICES = "/catalog/services/bulk"
    API_PST_ALL_CATALOG_SERVICES = "/catalog/services/bulk"
    API_GET_ORDER = "/catalog/orders/{0}"
    API_PST_ORDER = "/catalog/orders"

    #
    # UnManagedVolumes
    #
    API_GET_UNMNGD_VOLS_HST = "/compute/hosts/{0}/unmanaged-volumes"
    API_GET_UNMNGD_VOLS_CLS = "/compute/clusters/{0}/unmanaged-volumes"
    API_PST_UNMNGD_VOLUME_DETAILS = "/vdc/unmanaged/volumes/bulk"
    API_GET_UNMNGD_VOLUME_URNS = "/vdc/unmanaged/bulk"

    #
    # backups
    #
    API_MLT_BCKP = "/backupset/backup?tag={0}"
    API_GET_BCKP = "/backupset/download?tag={0}"

    #
    # cached data
    #
    IDX_CACHED_SS_INFO = "cached_storage_systems_list"
    IDX_CACHED_SS_DETAILS = "cached_storage_systems_details_dict_by_id"
    IDX_CACHED_SP_DETAILS = "cached_storage_pools_details_dict_by_id"
    IDX_CACHED_PROJECT_DETAILS = "cached_project_details_dict_by_id"
    IDX_CACHED_VA_DETAILS = "cached_va_details_dict_by_id"
    IDX_CACHED_VP_DETAILS = "cached_vp_details_dict_by_id"
    IDX_CACHED_CG_DETAILS = "cached_cg_details_dict_by_id"
    IDX_CACHED_CATALOG_DETAILS = 'cached_sc_svc_details_dict_by_name'

    def __init__(self, cmn):
        self.data = {}
        module_var(self, self.IDX_CMN, cmn)
        module_var(self, self.IDX_VIPR_SESSION,
                   VseHttp(cmn,
                           cmn.get_vipr_host_name(),
                           cmn.get_vipr_host_port(),
                           vipr_user=cmn.get_vipr_user(),
                           vipr_password=cmn.get_vipr_password()))

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "VseViprApi module initialization is complete")


    def login(self):
        module_var(self, self.IDX_VIPR_SESSION).vipr_login()


    def logout(self):
        module_var(self, self.IDX_VIPR_SESSION).vipr_logout()


    def manage_resource_tags(self,
                             tag_resource_type,
                             tag_action,
                             target_urn,
                             tags_delta_list=None):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Attempting action [{2}] on resource {0}/{1}...".format(
                         tag_resource_type,
                         target_urn,
                         tag_action
                     ))

        if tag_action == self.IDX_TAG_ACTION_GET:
            (r_code, r_text) = session.request(
                'GET',
                self.API_GET_TAGS.format(tag_resource_type, target_urn)
            )
        elif tag_action == self.IDX_TAG_ACTION_ADD:
            (r_code, r_text) = session.request(
                'PUT',
                self.API_PUT_TAGS.format(tag_resource_type, target_urn),
                body=json_encode("add", tags_delta_list)
            )
        elif tag_action == self.IDX_TAG_ACTION_RMV:
            (r_code, r_text) = session.request(
                'PUT',
                self.API_PUT_TAGS.format(tag_resource_type, target_urn),
                body=json_encode("remove", tags_delta_list)
            )
        else:
            msg = "Unrecognized action [{0}]".format(tag_action)
            cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
            from VseExceptions import VSEViPRAPIExc
            raise VSEViPRAPIExc(msg)

        #
        # collect results from API Call, always a list of tags, same key.
        #
        final_volume_tags = json_decode(r_text).get('tag')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Volume [{0}] tags now are:".format(target_urn),
                     final_volume_tags)

        return final_volume_tags


    def get_list_of_all_vipr_volume_uris(self):
        """
        get ALL volume urns in ViPR.

        this operation is not supported with Python SDK, so we are using
        raw API call.

        This is an efficient single call that returns a list of URNs,
        that are fodder for the POST block volumes call which returns all
        volumes details
        :return:  list of volume URIs
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Attempting to list URNs of all volumes...")

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_ALL_VOLUME_URNS
        )
        list_urns = json_decode(r_text).get('id')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "List of all volume URNs: ",
                     cmn.ppFormat(list_urns),
                     print_only_in_full_debug_mode=True)

        return list_urns


    def get_list_of_vipr_volume_details(self, list_urns=None):
        """
        get volume details in ViPR

        If "urns (a list)" is passed in, it becomes the argument. Otherwise
        method will retrieve list of _ALL_ volumes in ViPR.
            this is clearly a stupid thing to do
            that has a scalability issue to it...
            in future I might have to break it
            or somehow else limit # of IDs I am passing into API call.
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        if list_urns is None:
            list_urns = self.get_list_of_all_vipr_volume_uris()
            cmn.printMsg(
                cmn.MSG_LVL_DEBUG,
                "Attempting to retrieve details for all devices...")
        else:
            cmn.printMsg(
                cmn.MSG_LVL_DEBUG,
                "Attempting to retrieve details for devices in: ",
                cmn.ppFormat(list_urns),
                print_only_in_full_debug_mode=True)

        (r_code, r_text) = session.request(
            'POST',
            self.API_PST_ALL_VOLUME_DETAILS,
            body=json_encode("id", list_urns)
        )

        list_volumes_details = json_decode(r_text).get('volume')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Details of requested volumes: ",
                     list_volumes_details,
                     print_only_in_full_debug_mode=True)

        return list_volumes_details


    def get_volumes_per_project(self, project, project_uri=None):
        """
        gets all resources for a project and filters by type volume,
        then queries for all volumes with the URIs detected in a project.

        :param project: project name
        :param project_uri: project uri (can be figured out from name)
        :return: list of volume objects
        """
        cmn = module_var(self, self.IDX_CMN)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving all volumes for project [" + project + "].")

        if project_uri is None:
            cmn.printMsg(
                cmn.MSG_LVL_DEBUG,
                "Retrieving project URI for project [" + project + "].")
            project_obj = self.get_project_info_by_name(project)
            project_uri = project_obj.get('id')

        project_resources = self.get_project_resources_list(project_uri)

        v_uris = []
        for project_resource in project_resources:
            if project_resource.get('resource_type') != 'volume':
                continue
            v_uris.append(project_resource.get('id'))

        return self.get_list_of_vipr_volume_details(list_urns=v_uris)


    #
    # returns list of dictionaries for storage systems basic info -
    #  name, id, uri.
    # TODO: add cache refresh option
    #
    def get_list_of_storage_systems(self, name_filter=None, type_filter=None):
        """
        :return: list of storage system objects
        """
        cmn = module_var(self, self.IDX_CMN)

        #
        # handle retrieval of systems from cache or from ViPR
        #
        cached_storage_systems = module_var(
            self, self.IDX_CACHED_SS_INFO)

        if cached_storage_systems is None:
            session = module_var(self, self.IDX_VIPR_SESSION)
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Retrieving list of all storage systems")

            (r_status, r_text) = session.request(
                'GET',
                self.API_GET_STORAGE_SYSTEMS
            )

            cached_storage_systems = json_decode(r_text).get(
                'storage_system')

            # create a list module variable entry
            module_var(self, self.IDX_CACHED_SS_INFO,
                       cached_storage_systems)

            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Storage Systems list JSON retrieved (from ViPR):",
                         cached_storage_systems,
                         print_only_in_full_debug_mode=True)

        else:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Storage Systems list JSON retrieved (from cache):",
                         cached_storage_systems,
                         print_only_in_full_debug_mode=True)

        # create a copy of the list - wouldn't want to delete items from
        # cached list, that would defeat the purpose of caching
        return_systems_list = cached_storage_systems[:]

        #
        #  handle filtering by name field value - this may stop working if
        #  system name internally in ViPR will change
        #
        if name_filter is not None:
            adj_ret_list = list()

            pattern = re.compile(r"".join(name_filter), re.IGNORECASE)
            for ss_info_dict in return_systems_list:
                system_name = ss_info_dict.get('name')
                if pattern.match(system_name):
                    adj_ret_list.append(ss_info_dict)

            return_systems_list = adj_ret_list

        #
        #  handle filtering by type - this requires drilling down into systems
        #
        if type_filter is not None:
            adj_ret_list = list()

            pattern = re.compile(r"".join(type_filter), re.IGNORECASE)
            for ss_info_dict in return_systems_list:
                ss_uri = ss_info_dict.get('id')
                ss_details = self.get_storage_system_info_by_uri(ss_uri)
                if pattern.match(ss_details.get('system_type')):
                    adj_ret_list.append(ss_info_dict)

            return_systems_list = adj_ret_list

        return return_systems_list


    #
    # returns dictionary of virtual array details
    # TODO: add cache refresh option
    #
    def get_va_info_by_uri(self, uri):
        """
        get va info by URI

        :param uri:  va uri
        :return:  va dict details
        """
        cmn = module_var(self, self.IDX_CMN)

        cached_va_details = module_var(
            self,
            self.IDX_CACHED_VA_DETAILS)

        if cached_va_details is not None and \
           cached_va_details.get(uri) is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Data for virtual array (cached) - " + uri,
                         cached_va_details.get(uri),
                         print_only_in_full_debug_mode=True)
            return cached_va_details.get(uri)

        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for virtual array - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_VA.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Data for virtual array (retrieved) - " + uri,
                     data,
                     print_only_in_full_debug_mode=True)

        #
        #  cache for later consumption
        #
        if cached_va_details is None:
            cached_va_details = dict()
            module_var(self, self.IDX_CACHED_VA_DETAILS,
                       cached_va_details)
        cached_va_details[uri] = data

        return data


    #
    # returns dictionary of virtual pool details
    # TODO: add cache refresh option
    #
    def get_vp_info_by_uri(self, uri):
        """
        get virtual pool info by URI

        :param uri:  vp uri
        :return:  vp dict details
        """
        cmn = module_var(self, self.IDX_CMN)

        cached_vp_details = module_var(
            self,
            self.IDX_CACHED_VP_DETAILS)

        if cached_vp_details is not None and \
           cached_vp_details.get(uri) is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Data for virtual pool (cached) - " + uri,
                         cached_vp_details.get(uri),
                         print_only_in_full_debug_mode=True)
            return cached_vp_details.get(uri)

        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for virtual pool - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_BLOCK_VP.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Data for virtual pool (retrieved) - " + uri,
                     data,
                     print_only_in_full_debug_mode=True)

        #
        #  cache for later consumption
        #
        if cached_vp_details is None:
            cached_vp_details = dict()
            module_var(self, self.IDX_CACHED_VP_DETAILS,
                       cached_vp_details)
        cached_vp_details[uri] = data

        return data


    #
    # returns dictionary of export group details
    #
    def get_eg_info_by_uri(self, uri):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for Export Group - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_EXPORT_GROUP.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Data for export group (retrieved) - " + uri,
                     data,
                     print_only_in_full_debug_mode=True)

        return data


    #
    # implements lookup of initiators for hosts and clusters by name
    #
    def get_initiators_for_compute(self, type, name, uri, protocol=None):
        cmn = module_var(self, self.IDX_CMN)
        initiators_dict = dict()

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Looking up initiators for [{0}]=>[{1}]...".format(
                         name, type))

        # if we are passed a cluster we need to get a list of hosts first
        # else - make it up from provided data
        if type == self.STORAGE_TYPE_SHARED:
            hosts = self.get_cluster_hosts(name, uri)
        else:
            hosts = [{"id": uri, "name": name}]

        init_infos = list()
        for host in hosts:
            h_uri = host.get('id')
            h_name = host.get('name')
            h_wwn_infos = self.get_host_initiators(h_name, h_uri)
            for h_wwn_info in h_wwn_infos:
                if protocol is not None and \
                    h_wwn_info.get('protocol') != protocol:
                    continue
                init_infos.append(h_wwn_info)

        return init_infos


    #
    # implements lookup of initiators for a host.
    # returns list of full infos [ {info1}, {info2}, etc ]
    #
    def get_host_initiators(self, name, uri):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving initiators for host - " + name)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_HOST_INITIATORS.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Hosts of cluster [{0}]=>[{1}] (retrieved):".format(
                         name, uri
                     ),
                     data)

        # use generator to get a list of ID values. aka - URNs of all inits
        init_uris = list(init.get('id') for init in data.get('initiator'))

        return self.get_bulk_info_by_list_of_ids(self.API_PST_INIT_BULK_INFO,
                                                 init_uris)


    #
    # implements lookup of hosts in a cluster
    #
    def get_cluster_hosts(self, name, uri):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving hosts for cluster - " + name)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_CLUSTER_HOSTS.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Hosts of cluster [{0}]=>[{1}] (retrieved):".format(
                         name, uri
                     ),
                     data)

        # return a list of dictionaries, 1 per host (name, id)
        return data.get("host")


    #
    # implements hierarchical lookup of initiators
    # returns a map objects with info on initiator, its host owner, and its
    # cluster if there is such
    #
    IDX_INIT_INFO = 'initiator_info'
    IDX_INIT_HOST_INFO = 'host_info'
    IDX_INIT_CLUSTER_INFO = 'cluster_info'
    init_hierarchy_cache = {}

    def get_initiator_hierarchy(self, init_urn, init_wwn=None):
        cmn = module_var(self, self.IDX_CMN)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Looking up hierarchy for initiator [{0}]=>[{"
                     "1}]...".format(init_urn, init_wwn))

        if init_urn in self.init_hierarchy_cache.keys():
            cmn.printMsg(cmn.MSG_LVL_DEBUG, "Retrieving hierarchy from cache")
            return self.init_hierarchy_cache[init_urn]

        init_info = self.get_bulk_info_by_list_of_ids(
            self.API_PST_INIT_BULK_INFO,
            [init_urn]
        )[0]

        host_info = self.get_bulk_info_by_list_of_ids(
            self.API_PST_HOST_BULK_INFO,
            [init_info.get('host').get('id')]
        )[0]

        if 'cluster' in host_info.keys():
            cluster_info = self.get_bulk_info_by_list_of_ids(
                self.API_PST_CLUSTER_BULK_INFO,
                [host_info.get('cluster').get('id')]
            )[0]
        else:
            cluster_info = None

        # fill in the cache
        hierarchy = dict()
        hierarchy[self.IDX_INIT_INFO] = init_info
        hierarchy[self.IDX_INIT_HOST_INFO] = host_info
        hierarchy[self.IDX_INIT_CLUSTER_INFO] = cluster_info
        self.init_hierarchy_cache[init_urn] = hierarchy

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Hierarchy data (retrieved):",
                     hierarchy,
                     print_only_in_full_debug_mode=True)

        return hierarchy


    #
    # implements a number of working search queries
    # as named in available variables
    # returns list of matched URNs that need to later be queried further
    # for their full information
    #
    def search_by_name(self, type, name, exact_match=False):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Searching for [{0}] matching name [{1}].".format(
                         type, name
                     ))

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_SEARCH_BY_NAME.format(type, name)
        )
        search_matches_list = json_decode(r_text).get('resource')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Entries for [{0}] matching name [{1}]:".format(
                         type, name),
                     search_matches_list)

        ids_list = list()
        for match in search_matches_list:
            if exact_match is True and name != match.get('match'):
                cmn.printMsg(cmn.MSG_LVL_DEBUG,
                             'Exact match is ON, and [{0}]=>[{1}] does not '
                             'match [{2}], skipping...'.format(
                                 match.get('match'),
                                 match.get('id'),
                                 name
                             ))
            else:
                ids_list.append(match.get('id'))

        return ids_list

    #
    # implements a number of working bulk lookup by IDs queries
    # as named in available variables
    # returns list of dictionaries of information for each one
    #
    def get_bulk_info_by_list_of_ids(self, post_api, list_urns):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(
            cmn.MSG_LVL_DEBUG,
            "Attempting to get bulk details for [{0}] in: ".format(post_api),
            cmn.ppFormat(list_urns),
            print_only_in_full_debug_mode=True)

        (r_code, r_text) = session.request(
            'POST',
            post_api,
            body=json_encode("id", list_urns)
        )

        if post_api == self.API_PST_HOST_BULK_INFO:
            response_dict_key = 'host'
        elif post_api == self.API_PST_CLUSTER_BULK_INFO:
            response_dict_key = 'cluster'
        elif post_api == self.API_PST_ALL_VOLUME_DETAILS:
            response_dict_key = 'volume'
        elif post_api == self.API_PST_ALL_STORAGE_PORT_DETAILS:
            response_dict_key = 'storage_port'
        elif post_api == self.API_PST_ALL_VOLUME_EXPORT_PATHS:
            response_dict_key = 'itl'
        elif post_api == self.API_PST_INIT_BULK_INFO:
            response_dict_key = 'initiators'
        else:
            from VseExceptions import VSEViPRAPIExc
            raise VSEViPRAPIExc(
                'unsupported bulk lookup api call - need to '
                'code dictionary keyword for [{0}]'.format(
                    post_api))

        list_of_details = json_decode(r_text).get(response_dict_key)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Details of queried objects: ",
                     list_of_details,
                     print_only_in_full_debug_mode=True)

        return list_of_details

    #
    # returns dictionary of cg details
    # TODO: add cache refresh option
    #
    def get_cg_info_by_uri(self, uri):
        """
        get cg info by URI

        :param uri:  cg uri
        :return:  cg dict details
        """
        cmn = module_var(self, self.IDX_CMN)

        cached_cg_details = module_var(
            self,
            self.IDX_CACHED_CG_DETAILS)

        if cached_cg_details is not None and \
           cached_cg_details.get(uri) is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Data for CG (cached) - " + uri,
                         cached_cg_details.get(uri),
                         print_only_in_full_debug_mode=True)
            return cached_cg_details.get(uri)

        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for CG - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_BLOCK_CG.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Data for CG (retrieved) - " + uri,
                     data,
                     print_only_in_full_debug_mode=True)

        #
        #  cache for later consumption
        #
        if cached_cg_details is None:
            cached_cg_details = dict()
            module_var(self, self.IDX_CACHED_CG_DETAILS,
                       cached_cg_details)
        cached_cg_details[uri] = data

        return data


    #
    # returns dictionary of storage system details
    # TODO: add cache refresh option
    #
    def get_storage_system_info_by_uri(self, uri):
        """
        get storage system info by URI

        :param uri:  SS uri
        :return:  SS object
        """
        cmn = module_var(self, self.IDX_CMN)

        cached_sss_details = module_var(
            self,
            self.IDX_CACHED_SS_DETAILS)

        if cached_sss_details is not None and \
           cached_sss_details.get(uri) is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Data for storage system (cached) - " + uri,
                         cached_sss_details.get(uri),
                         print_only_in_full_debug_mode=True)
            return cached_sss_details.get(uri)

        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for storage system - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_STORAGE_SYSTEM.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Data for storage system (retrieved) - " + uri,
                     data,
                     print_only_in_full_debug_mode=True)

        #
        #  cache for later consumption
        #
        if cached_sss_details is None:
            cached_sss_details = dict()
            module_var(self, self.IDX_CACHED_SS_DETAILS,
                       cached_sss_details)
        cached_sss_details[uri] = data

        return data


    #
    # return list of storage pool URIs for storage system
    #
    def get_storage_pool_uris_by_ss_uri(self, ss_uri):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving storage pools for ss - " + ss_uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_STORAGE_SYSTEM_POOLS.format(ss_uri)
        )
        data = json_decode(r_text)['storage_pool']

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "List of storage pools for ss - " + ss_uri,
                     data)

        return data


    #
    # return list of storage port URIs for storage system
    #
    def get_storage_port_uris_by_ss_uri(self, ss_uri):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving storage ports for ss - " + ss_uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_STORAGE_SYSTEM_PORTS.format(ss_uri)
        )
        data = json_decode(r_text)['storage_port']

        storage_port_uris = []
        for brief in data:
            storage_port_uris.append(brief.get('id'))

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "List of storage ports for ss - " + ss_uri,
                     storage_port_uris)

        return storage_port_uris


    #
    # returns dictionary of storage pool details
    # TODO: add cache refresh option
    #
    def get_storage_pool_info_by_uri(self, uri):
        """
        get storage pool info by URI

        :param uri:  SS uri
        :return:  SS object
        """
        cmn = module_var(self, self.IDX_CMN)

        cached_sps_details = module_var(
            self,
            self.IDX_CACHED_SP_DETAILS)

        if cached_sps_details is not None and \
           cached_sps_details.get(uri) is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Data for storage system (cached) - " + uri,
                         cached_sps_details.get(uri),
                         print_only_in_full_debug_mode=True)
            return cached_sps_details.get(uri)

        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for storage pool - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_STORAGE_POOL.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Data for storage pool (retrieved) - " + uri,
                     data,
                     print_only_in_full_debug_mode=True)

        #
        #  cache for later consumption
        #
        if cached_sps_details is None:
            cached_sps_details = dict()
            module_var(self, self.IDX_CACHED_SP_DETAILS,
                       cached_sps_details)
        cached_sps_details[uri] = data

        return data


    def get_project_info_by_name(self, name, ignore_inactive=True):
        """
        get project info by name. ignores inactive projects by default

        :param name: project name
        :return: project dictionary, or NONE
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Searching projects by name - " + name)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_PROJECT_SEARCH_BY_NAME.format(name)
        )
        projects = json_decode(r_text).get('resource')

        if projects is None or len(projects) <= 0:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "No project [{0}] found".format(name))
            return None

        for project in projects:
            if project.get('match') == name:
                project_uri = project.get('id')
                project_obj = self.get_project_info_by_uri(project_uri)
                if ignore_inactive and project_obj.get('inactive'):
                    continue
                cmn.printMsg(
                    cmn.MSG_LVL_DEBUG,
                    "Active project [{0}] ".format(name),
                    project_obj,
                    print_only_in_full_debug_mode=True)
                return project_obj

        cmn.printMsg(cmn.MSG_LVL_WARNING,
                     "No active project [{0}] found".format(name))

        return None


    # TODO: add cache refresh option
    def get_project_info_by_uri(self, uri):
        """
        get project information by URI, retrieves whether active or inactive

        :param uri: Project URI
        :return: project data dictionary
        """
        cmn = module_var(self, self.IDX_CMN)

        # attempt to retrieve from cache
        cached_projects = module_var(self, self.IDX_CACHED_PROJECT_DETAILS)
        if cached_projects is not None and \
           cached_projects.get(uri) is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Project [{0}] info (cached):".format(uri),
                         cached_projects.get(uri),
                         print_only_in_full_debug_mode=True)
            return cached_projects.get(uri)

        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving info for project - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_PROJECT.format(uri)
        )
        data = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Project [{0}] info (retrieved):".format(uri),
                     data,
                     print_only_in_full_debug_mode=True)

        # commit project to cache
        if cached_projects is None:
            cached_projects = dict()
            module_var(self, self.IDX_CACHED_PROJECT_DETAILS, cached_projects)
        cached_projects[uri] = data

        return data


    def get_project_resources_list(self, uri):
        """
        get project resources. they come back as a list. each
        resource has id, name, and resource_type.

        resource_type can be volume, block_export,
        block_consistency_group, others --- use API to find out
        if need be.

        :param uri: Project URI
        :return: list of resource dictionaries, each is id/name/resource_type
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving resources for project - " + uri)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_PROJECT_RESOURCES.format(uri)
        )
        data = json_decode(r_text).get('project_resource')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Project [{0}] resources:".format(uri),
                     data,
                     print_only_in_full_debug_mode=True)

        return data


    TASK_STATE_COMPLETED = "ready"
    TASK_STATE_PENDING = "pending"
    TASK_STATE_ERROR = "error"


    # TODO: wait period should be configurable with optional arg
    def await_vipr_task_completion(self, task_dict):
        """
        await completion of asynchronous tasks
        """
        cmn = module_var(self, self.IDX_CMN)

        task_id = task_dict.get('id')
        task_full_name = "{0} [{1}]".format(task_dict.get('name'),
                                            task_dict.get('description'))
        task_state = task_dict.get('state')

        msg = \
            """
            Looking into ViPR Task [{0}]:
                Name/Description: {1}
                State: {2}
            """.format(task_id, task_full_name, task_state)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     msg,
                     task_dict,
                     print_only_in_full_debug_mode=True)

        if task_state == self.TASK_STATE_COMPLETED and \
           task_dict.get('message') == "Operation completed successfully":

            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Task [" + task_id + "], " + task_full_name +
                         ", completed.")

            return True, None

        if task_state == self.TASK_STATE_ERROR:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Task [" + task_id + "], " + task_full_name +
                         ", failed:",
                         task_dict.get('service_error'))
            return False, None

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Task [" + task_id + "], " + task_full_name +
                     ", did not finish, sleeping for 20 seconds...")
        time.sleep(20)

        return self.await_vipr_task_completion(self.query_task_state(task_id))


    def query_task_state(self, task_urn):
        session = module_var(self, self.IDX_VIPR_SESSION)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_TASK.format(task_urn)
        )

        return json_decode(r_text)


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # Volume Protection Detection
    ###########################################################################
    ###########################################################################
    ###########################################################################

    #
    # implements a number of queries to return block volume protection
    #
    IDX_BLOCK_PROTECTION_S = 'snapshots'
    IDX_BLOCK_PROTECTION_SS = 'snapshot-sessions'
    IDX_BLOCK_PROTECTION_CC = 'continuous-copies'
    IDX_BLOCK_PROTECTION_FC = 'full-copies'

    def get_block_volume_protection(self, protection_type, volume_info):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Volume [{0}], [{1}] protections, searching...".format(
                         volume_info.get("name"), protection_type
                     ))

        #
        # diff protection queries return different keys
        # also this if-then-else servers as verification for whether
        # protection_type submitted is legal
        #
        key = None
        if protection_type == self.IDX_BLOCK_PROTECTION_S:
            keyword = "snapshot"
        elif protection_type == self.IDX_BLOCK_PROTECTION_SS:
            keyword = "snapshot_session"
        elif protection_type == self.IDX_BLOCK_PROTECTION_CC:
            keyword = "mirror"
        elif protection_type == self.IDX_BLOCK_PROTECTION_FC:
            keyword = "volume"
        else:
            msg = "Lookup for protection type [{0}] is not " \
                  "implemented.".format(protection_type)
            cmn.printMsg(cmn.MSG_LVL_WARNING, msg)
            from VseExceptions import VSEViPRAPIExc
            raise VSEViPRAPIExc(msg)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_VOLUME_PROTECTION.format(
                volume_info.get("id"), protection_type)
        )
        search_matches_list = json_decode(r_text).get(keyword)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Volume [{0}], [{1}] protections, found [{2}]:".format(
                         volume_info.get("name"),
                         protection_type,
                         len(search_matches_list)),
                     search_matches_list)

        #
        # EXAMPLE OF WHAT IS RETURNED BY THE API
        #
        # {
        #   "snapshot": [
        #     {
        #       "id": "urn:storageos:BlockSnapshot:c1b2af4a-1ece-4d56-bcca-9c6d629fb554:vdc1",
        #       "name": "slb--t-the-snap",
        #       "link": {
        #         "rel": "self",
        #         "href": "/block/snapshots/urn:storageos:BlockSnapshot:c1b2af4a-1ece-4d56-bcca-9c6d629fb554:vdc1"
        #       }
        #     }
        #   ]
        # }

        return search_matches_list

    ###########################################################################
    ###########################################################################
    ###########################################################################
    # /Volume Protection Detection
    ###########################################################################
    ###########################################################################
    ###########################################################################


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # SRDF Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################


    def get_pp_r1r2_pairs(self, project_name=None):
        """
        pp_r1r2_pairs
        get CSV list of
            project name/project urn segment/r1SN/r1DevId/r2SN/r2DevId

        :param project_name:
        :return:
        """
        cmn = module_var(self, self.IDX_CMN)

        #
        # retrieve a list of storage systems and sort by ID
        # this is needed to be able to display system names and not URNs
        #
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Retrieving _all_ storage systems")
        arrays_dict = \
            cmn.convert_list_of_dict_objects_into_dict_by_id(
                self.get_list_of_storage_systems()
            )

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Listing R1R2 pairs:")

        #
        # retrieving volumes and converting them into
        # Hash of ID->DICT
        #
        if project_name is not None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Retrieving volumes for project " + project_name)
            vs_dict = cmn.convert_list_of_dict_objects_into_dict_by_id(
                self.get_volumes_per_project(project_name)
            )
        else:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Retrieving _all_ volumes")
            vs_dict = cmn.convert_list_of_dict_objects_into_dict_by_id(
                self.get_list_of_vipr_volume_details()
            )

        #
        # separating out all source devices into
        # Hash of ID->DICT
        #
        # getting/caching their project info
        #
        sources_dict = {}
        projects_dict = {}
        for urn in vs_dict.keys():
            device_json = vs_dict.get(urn)
            #
            # drop all unprotected; non-SRDF; non-SOURCE from consideration
            #
            if device_json.get('protection') is None:
                continue
            if device_json.get('protection').get('srdf') is None:
                continue
            if device_json.get('protection').get('srdf').get(
                    'personality') != 'SOURCE':
                continue
            sources_dict[urn] = device_json

            #
            # check if device's project has been cached, and cache if not.
            #
            project_urn = device_json.get('project').get('id')
            if projects_dict.get(project_urn) is None:
                projects_dict[project_urn] = self.get_project_info_by_uri(
                    project_urn)

        #
        # - 2nd pass:
        # -- for all R1 volume records, get R2 records and their details
        #
        out_table = []
        for r1_device_key in sources_dict.keys():
            r1_device = sources_dict.get(r1_device_key)
            r2_device = vs_dict.get(
                r1_device.get('protection').get('srdf').get('volumes')[0].get(
                    'id')
            )

            project_urn = r1_device.get('project').get('id')
            project_urn_segment = string.split(project_urn, ':')[3]

            project_name = projects_dict.get(project_urn).get('name')

            r1_sn = string.replace(
                arrays_dict.get(
                    r1_device.get('storage_controller')).get('name'),
                'SYMMETRIX+',
                '',
                1)

            r1_dev_id = r1_device.get('native_id')

            r2_sn = string.replace(
                arrays_dict.get(
                    r2_device.get('storage_controller')).get('name'),
                'SYMMETRIX+',
                '',
                1)

            r2_dev_id = r2_device.get('native_id')

            out_row = [
                project_name,
                project_urn_segment,
                r1_sn,
                # get last 4 chars, IDK why, but ViPR API gives me 5 chars
                r1_dev_id[-4:],
                r2_sn,
                # get last 4 chars, IDK why, but ViPR API gives me 5 chars
                r2_dev_id[-4:]
            ]

            out_table.append(out_row)

        #
        #  print
        #
        csv_out = "===================================================\n"
        csv_out += "Project Name,Project UID Segment,R1 Frame," + \
                   "R1 Device,R2 Frame,R2 Device\n"
        sorted_out_table = sorted(out_table)
        for i in range(len(sorted_out_table)):
            csv_out += string.join(sorted_out_table[i], ',') + "\n"
        csv_out += "===================================================\n"

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "R1 -> R2 volumes map: \n" + csv_out)

        return csv_out


    def get_rdfg_on_storage_system_info_by_urn(self, ss_urn, rdfg_urn):
        """
        get RDFG information from ViPR API by RDFG URI
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Getting RDFG info by URN - " + rdfg_urn + ".")

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_RDFG_ON_STORAGE_SYSTEM.format(ss_urn, rdfg_urn)
        )
        rdfg_info = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Details of RDFGroup: ",
                     rdfg_info,
                     print_only_in_full_debug_mode=True)

        return rdfg_info


    SRDF_MODE_SYNC = "SYNCHRONOUS"
    SRDF_MODE_ASYNC = "ASYNCHRONOUS"
    SRDF_MODE_ACP = "ADAPTIVECOPY"

    SRDF_MODE_SE_ACP = "Adaptive Copy"
    SRDF_MODE_SE_ASYNC = "Asynchronous"
    SRDF_MODE_SE_SYNC = "Asynchronous"

    SRDF_STATE_SE_SUSPENDED = "Suspended"
    SRDF_STATE_SE_SYNCHRONIZED = "Synchronized"
    SRDF_STATE_SE_CONSISTENT = "Consistent"

    def set_srdf_mode(self, sid, rdfg, source_dev_uri, target_dev_uri, mode):
        """
        Changes mode of replication on SRDF link
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Setting RDF Mode on [" + str(sid) + "/" + str(rdfg) +
                     "] to [" + mode + "], using device pair [" +
                     source_dev_uri + "/" + target_dev_uri + "] as handles.")

        xml_payload = """
                <copies>
                    <copy>
                        <type>SRDF</type>
                        <copyID>{0}</copyID>
                        <copyMode>{1}</copyMode>
                    </copy>
                </copies>
                """

        #
        # this is async api operation, returns a list of tasks,
        # (really only 1, but API returns a list here) need to wait
        # on task to complete
        #
        (r_code, r_text) = session.request(
            'POST',
            self.API_PST_RDF_SET_MODE.format(source_dev_uri),
            body=xml_payload.format(target_dev_uri, mode),
            content_type='application/xml'
        )
        tasks_dict = json_decode(r_text)
        task_dict = tasks_dict.get('task')[0]

        return self.await_vipr_task_completion(task_dict)


    SRDF_OP_SUSPEND = "suspend"
    SRDF_OP_ESTABLISH = "establish"

    def srdf_link_op(self, sid, rdfg, source_dev_uri, target_dev_uri, op):
        """
        execute srdf link manipulation operation
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Executing SRDF Operation [" + op +
                     "] on [" + str(sid) + "/" + str(rdfg) +
                     "], using device pair [" +
                     source_dev_uri + "/" + target_dev_uri + "] as handles.")

        if op == self.SRDF_OP_ESTABLISH:
            url = self.API_POST_RDF_OP.format(source_dev_uri, "sync")
            payload = [
                {
                    "type": "SRDF",
                    "copyID": target_dev_uri,
                    "syncDirection": "SOURCE_TO_TARGET"
                }
            ]

        #
        # sync: false   <--- causes SRDF FAIL OVER
        # sync: true    <--- causes SRDF SUSPEND
        #
        elif op == self.SRDF_OP_SUSPEND:
            url = self.API_POST_RDF_OP.format(source_dev_uri, "pause")
            payload = [
                {
                    "type": "SRDF",
                    "copyID": target_dev_uri,
                    "sync": "true"
                }
            ]

        else:
            from VseExceptions import VSEUnsupportedSRDFOperationExc

            raise VSEUnsupportedSRDFOperationExc(
                "Operation [" + op + "] is not supported.")

        payload_encoded = json_encode("copy", payload)

        #
        #  this is async api operation, returns a list of tasks, need to wait
        #  on task to complete
        #
        (r_code, r_text) = session.request(
            'POST',
            url,
            payload_encoded
        )

        tasks_dict = json_decode(r_text)
        task_dict = tasks_dict.get('task')[0]

        return self.await_vipr_task_completion(task_dict)


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # /SRDF Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # CONTINUOUS COPIES Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################

    #
    # these states are hard coded somewhere in ViPR source code. Possibly in
    # future they will need to be re-syncd with ViPR if engineer decide to
    # change them.
    #
    # sometimes API reports these values as words, SYNCRHONIZED, etc,
    # so here I am forced to treat them as strings to, otherwise too much
    # error checking.
    #
    # For more information, find BlockMirror.java in ViPR
    # source code
    #
    IDX_STATE_UNKNOWN = '0'
    IDX_STATE_RESYNCHRONIZING = '5'
    IDX_STATE_SYNCHRONIZED = '6'
    IDX_STATE_FRACTURED = '13'
    IDX_STATE_COPYINPROGRESS = '15'


    def get_mirror_details(self, source_name, source_uri, mirror_uri):
        """
        return mirror object, but NONE if it is inactive
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        info = "{0}/{1}'s mirror {2}".format(
            source_name, source_uri, mirror_uri
        )

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Attempting to show [{0}]...".format(info))

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_NATIVE_MIRROR.format(source_uri, mirror_uri)
        )

        mirror_obj = json_decode(r_text)

        if mirror_obj is None:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Unable to get information for [{0}]".format(info))

        elif mirror_obj.get('inactive'):
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Mirror [{0}] is INACTIVE, skipping".format(info))
            mirror_obj = None

        else:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Retrieved information for [{0}] - ".format(info),
                         mirror_obj,
                         print_only_in_full_debug_mode=True)

        return mirror_obj


    IDX_NATIVE_MIRROR_SPLIT = "pause"
    IDX_NATIVE_MIRROR_SYNC = "sync"


    def native_mirror_op(self, op, source_obj, mirror_obj):
        """
        execute local mirror manipulation operation
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        #
        # get details; I don't want to query storage_controller here,
        # but maybe a good idea to cache these things on initialization?
        #
        src_storage_system = source_obj.get('storage_controller')
        src_label = source_obj.get('device_label')
        src_uri = source_obj.get('id')
        mirror_label = mirror_obj.get('device_label')
        mirror_uri = mirror_obj.get('id')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Executing native mirror operation [{0}] on "
                     "Storage System [{1}], Source URI/Label: {2}/{3}, "
                     "Mirror URI/Label: {4}/{5}".format(
                         op,
                         src_storage_system,
                         src_uri,
                         src_label,
                         mirror_uri,
                         mirror_label
                     ))

        if op == self.IDX_NATIVE_MIRROR_SPLIT:
            url = self.API_PST_NATIVE_MIRROR_OP.format(
                src_uri, "pause")
            payload = [
                {
                    "type": "native",
                    "copyID": mirror_uri,
                }
            ]

        elif op == self.IDX_NATIVE_MIRROR_SYNC:
            url = self.API_PST_NATIVE_MIRROR_OP.format(
                src_uri, "resume")
            payload = [
                {
                    "type": "native",
                    "copyID": mirror_uri,
                    "sync": "true"
                }
            ]

        else:
            from VseExceptions import VSEUnsupportedMirrorOperationExc

            raise VSEUnsupportedMirrorOperationExc(
                "Operation [" + op + "] is not supported.")

        payload_encoded = json_encode("copy", payload)

        #
        #  this is async api operation, returns a list of tasks, need to wait
        #  on task to complete
        #
        (r_code, r_text) = session.request(
            'POST',
            url,
            payload_encoded
        )

        tasks_dict = json_decode(r_text)
        task_dict = tasks_dict.get('task')[0]

        return self.await_vipr_task_completion(task_dict)


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # /CONTINUOUS COPIES Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # BACKUPS Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################


    def backup_create(self, name):
        cmn = module_var(self, self.IDX_CMN)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Creating a backup on ViPR vApp: " + name)
        vipr_session = module_var(self, self.IDX_VIPR_SESSION)
        vipr_session.request('POST', self.API_MLT_BCKP.format(name))
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Backup created successfully on ViPR vApp: " + name)


    def backup_download(self, name, path):
        cmn = module_var(self, self.IDX_CMN)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Downloading backup from ViPR vApp: " + name)
        vipr_session = module_var(self, self.IDX_VIPR_SESSION)
        vipr_session.request('GET',
                             self.API_GET_BCKP.format(name),
                             filename=path)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Backup downloaded from ViPR vApp: " + path)


    def backup_delete(self, name):
        cmn = module_var(self, self.IDX_CMN)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Deleting backup from ViPR vApp: " + name)
        vipr_session = module_var(self, self.IDX_VIPR_SESSION)
        vipr_session.request('DELETE', self.API_MLT_BCKP.format(name))
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Backup deleted from ViPR vApp: " + name)
        return


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # /BACKUPS Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # SERVICE CATALOG Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################

    # TODO: this is too raw, needs a wrapper inside VseViprApi

    # BSS = Block Storage Services
    SC_BSS_UXP_RMV_VOLUME = 'Remove Block Volumes'
    SC_BSS_DISCOVER_UMNGD = 'Discover Unmanaged Volumes'
    SC_BSS_INGEST_EXPORTED_UMNGD = 'Ingest Exported Unmanaged Volumes'


    def fetch_sc_urn(self, service_name):
        cmn = module_var(self, self.IDX_CMN)

        #
        # cache empty dictionary in case there is nothing yet.
        #
        if module_var(self, self.IDX_CACHED_CATALOG_DETAILS) is None:
            services_info_list = self.fetch_list_of_sc_services_info()
            cached_catalog = dict()
            for service_info in services_info_list:
                cached_catalog[service_info['title']] = service_info
            module_var(self, self.IDX_CACHED_CATALOG_DETAILS, cached_catalog)

        cached_sc = module_var(self, self.IDX_CACHED_CATALOG_DETAILS)

        #
        # if service_name is not present - tough luck, we are done.
        # else return its URN
        #
        if service_name not in cached_sc.keys():
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         'Catalog service [{0}] is not found.'.format(
                             service_name
                         ))
            return None

        cached_service_info = cached_sc[service_name]

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     'Catalog service [{0}] is found, its URN is [{1}]'.format(
                         service_name, cached_service_info['id']),
                     cached_service_info)

        return cached_service_info['id']


    def fetch_list_of_sc_services_info(self, list_of_service_urns=None):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        if list_of_service_urns is None:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Attempting to get details for all SC services...")
            list_of_service_urns = self.list_all_sc_service_urns()
        else:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Attempting to get details for SC services in:",
                         list_of_service_urns)

        (r_code, r_text) = session.request(
            'POST',
            self.API_PST_ALL_CATALOG_SERVICES,
            body=json_encode("id", list_of_service_urns)
        )

        list_of_services_details = json_decode(r_text).get('catalog_service')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Details of all service catalog services fetched - this "
                     "is too much useless output even for Full Debug Mode. "
                     "The code to produce output is right below this code "
                     "and is commented out.")

        # cmn.printMsg(cmn.MSG_LVL_DEBUG,
        #              "Details of service catalog services fetched: ",
        #              list_of_services_details,
        #              print_only_in_full_debug_mode=True)

        return list_of_services_details


    def list_all_sc_service_urns(self):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Attempting to list URNs of all catalog services...")

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_ALL_CATALOG_SERVICES
        )
        list_urns = json_decode(r_text).get('id')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "List of all catalog services URNs: ",
                     cmn.ppFormat(list_urns),
                     print_only_in_full_debug_mode=True)

        return list_urns


    STORAGE_TYPE_EXCLUSIVE = 'exclusive'
    STORAGE_TYPE_SHARED = 'shared'

    # Usage:
    #   if catalog_execute(...): success
    #   if not catalog_execute(...): error
    def catalog_execute(self,
                        catalog_service_name,
                        catalog_service_urn,
                        tenant_urn,
                        parameters_dict):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        catalog_xml_template = """
        <order_create>
            <catalog_service>{0}</catalog_service>
            <tenantId>{1}</tenantId>
            {2}
        </order_create>
        """

        parameters_xml_template = """
            <parameters>
                <label>{0}</label>
                <value>{1}</value>
            </parameters>
        """

        parameters = ""

        # for each parameter in parameters_dict:
        #   if string, format; if list, format
        for param_label in parameters_dict.keys():
            param_value = parameters_dict[param_label]
            if isinstance(param_value, list):
                xml_string_list = ""
                for item in param_value:
                    xml_string_list += '"' + item + '",'
                # cutoff last char - it is always a comma
                param_value = xml_string_list[:-1]

            parameters += parameters_xml_template.format(
                param_label,
                param_value)

        payload = catalog_xml_template.format(
            catalog_service_urn,
            tenant_urn,
            parameters
        )

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Executing service catalog: [" + catalog_service_name +
                     "]",
                     "======> POST {0} \n".format(
                         self.API_PST_ORDER) + payload)

        #
        #  this is async api operation, returns a list of tasks, need to wait
        #  on task to complete
        #
        (r_code, r_text) = session.request(
            'POST',
            self.API_PST_ORDER,
            payload,
            content_type='application/xml'
        )

        order_dict = json_decode(r_text)

        return self.await_vipr_order_completion(order_dict)


    ORDER_STATE_COMPLETED = 'SUCCESS'
    ORDER_STATE_PENDING = 'PENDING'
    ORDER_STATE_ERROR = 'ERROR'


    def await_vipr_order_completion(self, order_dict, previous_state=None):
        """
        await completion of asynchronous orders
        """
        cmn = module_var(self, self.IDX_CMN)

        order_id = order_dict.get('id')
        order_number = order_dict.get('order_number')
        order_summary = order_dict.get('summary')
        order_state = order_dict.get('order_status')

        msg = \
            """
            Looking into ViPR Order #[{0}] / [{1}]:
                Name/Description: {2}
                State: {3}
            """.format(order_number, order_id, order_summary, order_state)

        # only output order dictionary on state change.
        if previous_state is None or previous_state != order_state:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         msg,
                         order_dict,
                         print_only_in_full_debug_mode=True)
        else:
            cmn.printMsg(cmn.MSG_LVL_DEBUG, msg)

        if order_state == self.ORDER_STATE_COMPLETED:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Order #{0} / [{1}] / [{2}] completed.".format(
                             order_number, order_summary, order_id))

            return True, None

        if order_state == self.ORDER_STATE_ERROR:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Order #{0} / [{1}] / [{2}] failed:".format(
                             order_number, order_summary, order_id),
                         order_dict.get('message'))
            return False, None

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Order #{0} / [{1}] / [{2}] did not finish yet, "
                     "sleeping for 10 seconds...".format(
                         order_number, order_summary, order_id))
        time.sleep(10)

        return self.await_vipr_order_completion(
            self.query_order_state(order_id), order_state)


    def query_order_state(self, order_urn):
        session = module_var(self, self.IDX_VIPR_SESSION)

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_ORDER.format(order_urn)
        )

        return json_decode(r_text)


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # /SERVICE CATALOG Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################

    ###########################################################################
    ###########################################################################
    ###########################################################################
    # UnManaged Volumes Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################
    def get_list_of_unmanaged_volume_urns_by_owner(self,
                                                   storage_type,
                                                   owner_urn):
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Attempting to list unmanaged volumes that are {0} to {"
                     "1}".format(storage_type, owner_urn))

        if storage_type == self.STORAGE_TYPE_EXCLUSIVE:
            url = self.API_GET_UNMNGD_VOLS_HST
        elif storage_type == self.STORAGE_TYPE_SHARED:
            url = self.API_GET_UNMNGD_VOLS_CLS
        else:
            from VseExceptions import VSEViPRAPIExc
            raise VSEViPRAPIExc('unsupported storage owner type')

        (r_code, r_text) = session.request(
            'GET',
            url.format(owner_urn)
        )
        response_dict = json_decode(r_text)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "API Response: ",
                     cmn.ppFormat(response_dict),
                     print_only_in_full_debug_mode=True)

        # there are 2 separate lists of dictionaries in response dictionary
        # 1) unmanaged_volume
        # 2) named_unmanaged_volume
        # the info dictionaries are the same,
        #   (1) id + link
        #   (2) id + link + name
        response_list_of_urns = []
        for x in response_dict.get('unmanaged_volume'):
            response_list_of_urns.append(x.get('id'))
        for x in response_dict.get('named_unmanaged_volume'):
            response_list_of_urns.append(x.get('id'))

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "List of unmanaged volume URNs for {0}: ".format(
                         owner_urn),
                     cmn.ppFormat(response_list_of_urns),
                     print_only_in_full_debug_mode=True)

        return response_list_of_urns


    def get_list_of_all_unmanaged_vipr_volume_uris(self):
        """
        get ALL unmanaged volume urns in ViPR.

        This is an efficient single call that returns a list of URNs,
        that are fodder for the POST block volumes call which returns all
        volumes details
        :return:  list of volume URIs
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Attempting to list URNs of all unmanaged volumes...")

        (r_code, r_text) = session.request(
            'GET',
            self.API_GET_UNMNGD_VOLUME_URNS
        )
        list_urns = json_decode(r_text).get('id')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "List of all unmanaged volume URNs: ",
                     cmn.ppFormat(list_urns),
                     print_only_in_full_debug_mode=True)

        return list_urns


    def get_list_unmanaged_volumes_info(self, list_urns=None):
        """
        get unmanaged volume details in ViPR

        If "urns (a list)" is passed in, it becomes the argument. Otherwise
        method will retrieve list of _ALL_ volumes in ViPR.
            this is clearly a stupid thing to do
            that has a scalability issue to it...
            in future I might have to break it
            or somehow else limit # of IDs I am passing into API call.
        """
        cmn = module_var(self, self.IDX_CMN)
        session = module_var(self, self.IDX_VIPR_SESSION)

        if list_urns is None:
            list_urns = self.get_list_of_all_unmanaged_vipr_volume_uris()
            cmn.printMsg(
                cmn.MSG_LVL_DEBUG,
                "Attempting to retrieve details for all devices...")
        else:
            cmn.printMsg(
                cmn.MSG_LVL_DEBUG,
                "Attempting to retrieve details for unmanaged devices in: ",
                cmn.ppFormat(list_urns),
                print_only_in_full_debug_mode=True)

        (r_code, r_text) = session.request(
            'POST',
            self.API_PST_UNMNGD_VOLUME_DETAILS,
            body=json_encode("id", list_urns)
        )

        list_volumes_details = json_decode(r_text).get('unmanaged_volume')

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Details of requested volumes: ",
                     list_volumes_details,
                     print_only_in_full_debug_mode=True)

        return list_volumes_details


    ###########################################################################
    ###########################################################################
    ###########################################################################
    # UnManaged Volumes Stuff
    ###########################################################################
    ###########################################################################
    ###########################################################################