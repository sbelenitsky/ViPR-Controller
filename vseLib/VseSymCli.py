__author__ = 'belens'
"""
encapsulates shell out to SymCLI and its commands/parsing of output
into necessary/usable form

depends on VseRemoteExecution
"""

from vseCmn import module_var
from vseLib.VseRemoteExecution import VseRemoteExecution
from app_DirectDbUpdateViPR.etree import ElementTree


class VseSymCli:
    IDX_CMN = "Module_Ref_Common"
    IDX_RX = "Module_Ref_vseRX"
    IDX_IP = "server_ip"
    IDX_USER = "server_user"
    IDX_PWD = "server_password"

    IDX_CMD_LIST_RDFG_XML = \
        "/usr/symcli/bin/symrdf -sid {0} list -rdfg {1} -output xml"


    def __init__(self, cmn, ip):
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Initializing VseSymCli for server [" + ip + "].")

        #
        # reading config file, section self.__class__.__name__
        # expecting variable named after SE IP/Name, to have value of
        # username_///_password
        #
        cmn.read_config_file_for_module(self,
                                        cmn.get_env_settings_file(),
                                        self.__class__.__name__,
                                        [ip])

        (username, password) = module_var(self, ip).split('_///_')

        module_var(self, self.IDX_CMN, cmn)
        module_var(self, self.IDX_IP, ip)
        module_var(self, self.IDX_USER, username)
        module_var(self, self.IDX_PWD, password)
        module_var(self, self.IDX_RX, VseRemoteExecution(cmn))


    def check_srdfa_grp_state(self, sid, rdfg):
        """
        verify state of ASYNC replication and # of invalid tracks queued up
        returns (
            checked: True/False, was the group checked or not (only when 1 or
                more RDF devices were found devices)
            mode: ACP, Sync, Async
            state: Consistent/Suspended/FailedOver, etc. States of replication.
            tracks_owed: integer, # of tracks that the target is behind source

        :param sid:
        :param rdfg:
        :return:
        """
        cmn = module_var(self, self.IDX_CMN)
        rx = module_var(self, self.IDX_RX)
        command = self.IDX_CMD_LIST_RDFG_XML.format(sid, rdfg)

        rdf_checked = False
        rdf_mode = None
        rdf_state = None
        rdf_tracks_total_owed = None

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Checking status of rdfg [" + sid + " / " + rdfg + "]...")
        (cmd_return_code, cmd_output) = rx.rx_cmd_simple(
            module_var(self, self.IDX_IP),
            module_var(self, self.IDX_USER),
            module_var(self, self.IDX_PWD),
            command
        )

        if cmd_return_code != cmn.SUCCESS:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Command [" + command + "] failed with code [" +
                         cmd_return_code + "], and output:\n" + cmd_output)

        else:
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "Parsing output of cmd [" + command + "]...")

            lvl0_symcli_ml = ElementTree.fromstring(cmd_output)
            lvl1_symmetrix = lvl0_symcli_ml[0]
            for element in lvl1_symmetrix:
                # skip element Symm_Info - generic symmetrix information
                if element.tag == 'Symm_Info':
                    continue
                # find 1st device mentioned, capture its status. for Async
                # SRDF groups that should be enough
                if element.tag == 'Device':
                    if rdf_checked:
                        continue
                    for devInfoEl in element:
                        if devInfoEl.tag != 'RDF':
                            continue
                        for devRdfInfoEl in devInfoEl:
                            if devRdfInfoEl.tag == 'RDF_Info':
                                for devRdfInfoDetailsEl in devRdfInfoEl:
                                    if devRdfInfoDetailsEl.tag != 'pair_state':
                                        continue
                                    rdf_state = str(devRdfInfoDetailsEl.text)
                                    rdf_checked = True
                            if devRdfInfoEl.tag == 'Mode':
                                for devRdfModeDetailsEl in devRdfInfoEl:
                                    if devRdfModeDetailsEl.tag != 'mode':
                                        continue
                                    rdf_mode = str(devRdfModeDetailsEl.text)
                if element.tag == 'RDF_Totals':
                    for rdfTotalsEl in element:
                        if rdfTotalsEl.tag != 'r2_invalids':
                            continue
                        rdf_tracks_total_owed = int(rdfTotalsEl.text)

        return rdf_checked, rdf_mode, rdf_state, rdf_tracks_total_owed