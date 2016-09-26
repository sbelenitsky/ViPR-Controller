__author__ = 'belens'

"""
Role of VseViprProject is to objectify project concept

project knows a bunch of things, and instantiating this object will learn
those things about itself
"""

from vseLib import VseExceptions
from vseCmn import module_var


class VseViprProject:
    IDX_CMN = "Module_Ref_Common"
    IDX_VIPR_API = "Module_Ref_ViPR_API"

    IDX_PROJECT = "full_project"
    IDX_NAME = "prop_name"
    IDX_VOLUMES = "full_volumes"

    def __init__(self, cmn, vipr_api, name):
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Initializing project [" + name + "].")

        module_var(self, self.IDX_NAME, name)
        module_var(self, self.IDX_CMN, cmn)
        module_var(self, self.IDX_VIPR_API, vipr_api)
        self.initialize()

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Initialized project [" + name + "].")


    def initialize(self):
        """
        initialize project from ViPR APIs to the extent demanded by
        implementations
        """
        block = module_var(self, self.IDX_VIPR_API)

        project_json = block.get_project_info_by_name(
            module_var(self, self.IDX_NAME)
        )
        module_var(self, self.IDX_PROJECT, project_json)

        #
        # this could be a tremendous amount of data.
        # in a 3000 device project it takes about 20 seconds to receive JSON
        #  and about 3 minutes to __handle it.
        #
        # some performance ideas here
        #   - cut back on data stored, transmuting each volume's dict to
        # carry only what is necessary, and storing THAT instead.
        #
        volumes_json = block.get_volumes_per_project(
            module_var(self, self.IDX_NAME),
            project_uri=project_json.get('id')
        )
        module_var(self, self.IDX_VOLUMES, volumes_json)


    def get_project_id(self):
        return module_var(self, self.IDX_PROJECT).get('id')


    def get_devices_by_id(self):
        cmn = module_var(self, self.IDX_CMN)
        return cmn.convert_list_of_dict_objects_into_dict_by_id(
            module_var(self, self.IDX_VOLUMES)
        )


    def get_involved_rdfs(self):
        """
        returns dictionary of lists for what Symmetrix/RDFG is involved
        D{smisip/sid/rdfg}->[r1devices,r1device,r1device]

        should only be one, really - but maybe more will be supported in the
        future...
        :return:
        """
        cmn = module_var(self, self.IDX_CMN)
        block = module_var(self, self.IDX_VIPR_API)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Obtaining RDFGs involved in project...")

        cached_arrays = {}
        cached_rdf_groups = {}
        devices_in_rdfgs = {}

        devs_by_id = self.get_devices_by_id()

        for urn in devs_by_id.keys():
            device = devs_by_id.get(urn)
            #
            # drop all unprotected; non-SRDF; non-SOURCE from consideration
            #
            if device.get('protection') is None:
                continue
            if device.get('protection').get('srdf') is None:
                continue
            if device.get('protection').get('srdf').get(
                    'personality') != 'SOURCE':
                continue

            #
            # get volume's array details, and cache them
            #
            array_urn = device.get('storage_controller')
            if cached_arrays.get(array_urn) is None:
                array_info = block.get_storage_system_info_by_uri(array_urn)
                cached_arrays[array_urn] = array_info

            #
            # get volume array name and smis ip address
            #
            array_sid = cached_arrays[array_urn].get('serial_number')
            smis_ip = cached_arrays[array_urn].get('smis_provider_ip')

            #
            # getting RDF group is a bit harder - RDFG URI is coded
            # in R2 volume's GET, and needs to be retrieved with another API
            #
            r2_volumes = device.get('protection').get('srdf').get('volumes')
            r2_partner_urn = r2_volumes[0].get('id')
            r2_partner = devs_by_id.get(r2_partner_urn)
            r2_array_urn = r2_partner.get('storage_controller')
            rdfg_urn = r2_partner.get('protection').get('srdf').get(
                'srdf_group_uri')
            if cached_rdf_groups.get(rdfg_urn) is None:
                rdfg_info = block.get_rdfg_on_storage_system_info_by_urn(
                    r2_array_urn, rdfg_urn)
                cached_rdf_groups[rdfg_urn] = rdfg_info
            rdfg = cached_rdf_groups[rdfg_urn].get('remote_group_id')

            #
            # this happened to me a few times, so printing a warning for users
            #
            if smis_ip is None:
                cmn.printMsg(cmn.MSG_LVL_WARNING,
                             "Unable to identify SMI-S provider for array {"
                             "0}, please verify that ViPR has provider "
                             "assigned.".format(array_sid))
                raise VseExceptions.VSEViPRAPIExc(
                    "SMI-S Provider for {0} is None".format(array_sid))

            #
            # key things together into a string
            #
            key = smis_ip + '/' + array_sid + '/' + rdfg

            #
            # cache device under RDFG and continue iterations
            #
            if devices_in_rdfgs.get(key) is None:
                devices_in_rdfgs[key] = {}
            devices_in_rdfg = devices_in_rdfgs[key]
            devices_in_rdfg[urn] = device

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Determined project has devices on these RDF groups:",
                     ", ".join(devices_in_rdfgs.keys()))

        return devices_in_rdfgs