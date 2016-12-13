__author__ = 'Stanislav Belenitsky, EMC, stanislav.belenitsky@emc.com'

import argparse
import sys
import os

from vseLib.vseCmn import vseCmn, VseExceptions

#
# default variables used to help the setup, in case not enough arguments
# are provided on the command line or in config file
#
DEFAULT_ENV_CFG_FILE = r'./env_cfg.ini'
DEFAULT_LOCAL_PATH = os.path.dirname(os.path.realpath(__file__))


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="%(prog)s will take backup of a targeted ViPR "
                    "environment. Backup files will be saved locally and  "
                    "retained per settings in configuration file."
    )

    optional_args = parser.add_argument_group('optional arguments')
    optional_args.add_argument('-env_settings', '-env',
                               required=False,
                               help='Specify a config file, default is ' +
                                    DEFAULT_ENV_CFG_FILE)

    return parser.parse_args()


def main():
    #
    # read/parse commandline
    # print help if required
    # if env_settings_file is not explicitly provided - use default variable
    # set default local execution path for vseCmn (if any PATH_* = LOCAL)
    #
    args = parse_arguments()
    if args.env_settings is None:
        args.env_settings = DEFAULT_ENV_CFG_FILE
    args.default_local_path = DEFAULT_LOCAL_PATH

    #
    # Initialize environment. If any errors - quit gruesomely
    #
    try:
        cmn = vseCmn("ViPR Backup Application",
                            vseCmn.MSG_LVL_DEBUG,
                            args)
    except VseExceptions.VSEInitExc as e:
        print "Basic environment initialization error: " + e.value
        sys.exit(1)

    #
    # Execute main logic.
    # Catch all exceptions, announce them, and exit gracefully.
    #
    exit_code = cmn.SUCCESS
    exit_msg = None
    try:
        from vseLib.VseViprBackups import VseViprBackups
        vse_bkp_obj = VseViprBackups(cmn)
        vse_bkp_obj.take_bckp()

    except Exception as e:
        VseExceptions.announce_exception(cmn, e)
        exit_code = cmn.ERROR_GENERIC
        exit_msg = e.message

    cmn.exit(exit_code, exit_msg)


if __name__ == '__main__':
    main()
