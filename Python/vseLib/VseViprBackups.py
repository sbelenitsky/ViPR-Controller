__author__ = 'belens'

"""
facade for ViPR CLI "viprcli system *-backup" functionality

To "simulate" PYTHONPATH runtime modification, one can use
File->Settings->ProjectStructure->AddContentRoot->[add CLI python libraries
path]
"""

import os
import time
from vseCmn import module_var
from VseViprApi import VseViprApi


class VseViprBackups:
    """
    VseViprBackups handles taking backup of ViPR environment
    """

    IDX_CMN = "Module_Ref_Common"
    IDX_VIPR_API = "Module_Ref_ViPR_API"
    IDX_VIPR_BKP_REPO_PATH = "Backups_Repository_Path"

    #
    # required arguments
    #
    IDX_VIPR_RETENTION_POLICY_DAYS = "BACKUP_RETENTION_DAYS"
    IDX_VIPR_RETENTION_POLICY_AT_LEAST = "BACKUP_RETAIN_AT_LEAST"
    IDX_VIPR_BACKUPS_PATH = "PATH_BKP_FILES"
    REQUIRED_VARS = [IDX_VIPR_RETENTION_POLICY_DAYS,
                     IDX_VIPR_RETENTION_POLICY_AT_LEAST,
                     IDX_VIPR_BACKUPS_PATH]


    def __init__(self, cmn):
        cmn.read_config_file_for_module(
            self,
            cmn.get_env_settings_file(),
            self.__class__.__name__,
            self.REQUIRED_VARS)

        module_var(self,
                   self.IDX_CMN,
                   value=cmn)

        backups_repo_path = os.path.join(
            module_var(self, self.IDX_VIPR_BACKUPS_PATH),
            "ViPR_BACKUPS")

        if not os.path.isdir(backups_repo_path):
            os.makedirs(backups_repo_path)

        module_var(self,
                   self.IDX_VIPR_BKP_REPO_PATH,
                   value=backups_repo_path)

        module_var(self,
                   self.IDX_VIPR_API,
                   value=VseViprApi(cmn))

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "VseViprBackups module initialization is complete")


    def __get_repo_path(self):
        return module_var(self, self.IDX_VIPR_BKP_REPO_PATH)


    def __get_bckp_name(self):
        # name of backup cannot have underscores, and all alphabetic characters
        # must be lower case
        cmn = module_var(self, self.IDX_CMN)
        return str(cmn.get_session_name()).replace('_', '-').lower()


    def __get_bckp_dl_name(self, name):
        return name + ".zip"


    def __get_bckp_dl_full_file_path(self, name):
        cmn = module_var(self, self.IDX_CMN)
        return os.path.join(cmn.get_session_path(),
                            self.__get_bckp_dl_name(name))


    def take_bckp(self, verify_repo=True):
        cmn = module_var(self, self.IDX_CMN)

        bckp_name = self.__get_bckp_name()
        bkp_dl_path = self.__get_bckp_dl_full_file_path(bckp_name)

        #
        # create, download, delete files on ViPR
        #
        cmn.printMsg(cmn.MSG_LVL_INFO,
                     "Taking a backup: " + bckp_name)
        vipr_api = module_var(self,
                              self.IDX_VIPR_API)
        vipr_api.login()
        vipr_api.backup_create(bckp_name)
        vipr_api.backup_download(bckp_name, bkp_dl_path)
        vipr_api.backup_delete(bckp_name)
        vipr_api.logout()

        #
        # save downloaded file in appropriate place
        #
        src_full_path = self.__get_bckp_dl_full_file_path(bckp_name)
        tgt_full_path = os.path.join(self.__get_repo_path(),
                                     self.__get_bckp_dl_name(bckp_name))
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Saving downloaded backup into repository: " +
                     src_full_path)
        cmn.copyFile(src_full_path, tgt_full_path)
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Backup saved in repository: " + tgt_full_path)

        #
        # make sure retention policy is observed
        #
        if verify_repo:
            self.__vrf_repo_for_policy_compliance()

        return


    def __vrf_repo_for_policy_compliance(self):
        cmn = module_var(self, self.IDX_CMN)

        #
        # assume to have to keep nothing, unless specified in config file
        #
        keep_cnt = 0
        plc_retain_at_least = module_var(
            self,
            self.IDX_VIPR_RETENTION_POLICY_AT_LEAST)

        if cmn.is_simple_value_defined(plc_retain_at_least):
            keep_cnt = int(plc_retain_at_least)

        #
        # assume to retain forever, unless specified in config file
        #
        plc_retain_days = module_var(self,
                                     self.IDX_VIPR_RETENTION_POLICY_DAYS)
        if cmn.is_simple_value_defined(plc_retain_days):
            return

        #
        # create a sorted map of backups, by created timestamp
        #
        bkps_dict = {}
        for bkpFile in os.listdir(self.__get_repo_path()):
            bkp_file_path = os.path.join(self.__get_repo_path(), bkpFile)
            bkps_dict[os.path.getmtime(bkp_file_path)] = bkp_file_path
        bkp_time_stamps = bkps_dict.keys()
        bkp_time_stamps.sort()

        #
        # - only if we have more backups will we try to retain per keep_cnt
        # - since list is sorted, iterate from 0 to last possible element we
        # would want to delete based on retention count
        # - evaluate if elements are beyond date-based retention and delete
        # them
        #
        # python ranges are not inclusive of the ending element
        #
        if len(bkp_time_stamps) > keep_cnt:
            for idx, bkp_time in enumerate(
                    bkp_time_stamps[0:len(bkp_time_stamps) - keep_cnt]):
                if bkp_time < time.time() - int(plc_retain_days) * 86400:
                    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                                 "Backup file " + bkps_dict[bkp_time] +
                                 " has expired, deleting.")
                    cmn.deleteFile(bkps_dict[bkp_time])

        return