__author__ = 'belens'

"""
v1.0 - 2014/11/15

vseCmn library helps with:
 - setting up pre-ViPR Python SDK execution environment
 - reading a config file
 - controlling screen and logging output
 - clean exits from failures
 - sending email
 -

"""

import os
import sys
import ConfigParser
import pprint
import inspect
import string
import time
import datetime
import traceback
import shutil
import smtplib

from vseLib import VseExceptions


class vseCmn:
    ONSCREEN_OUTPUT_FILE = "out.txt"
    DEBUG_OUTPUT_FILE = "log.txt"

    IDX_LOCAL_EXECUTION_PATH = "Path_To_Where_Execution_Started_From"
    IDX_ENV_SETTINGS_FILE = "Path_To_Env_Settings_File"
    IDX_ENV_SETTINGS = "Parsed_Env_Settings_File"
    IDX_PPRINT = "Pretty_Print_Ref"
    IDX_APP_NAME = "Application_Name_User_Given"

    #
    # define arguments that the code will be looking for in the
    # environment settings file
    #
    IDX_VIPR_HOSTNAME = "VIPR_HOSTNAME"
    IDX_VIPR_PORT = "VIPR_PORT"
    IDX_VIPR_USER = "VIPR_USER"
    IDX_VIPR_PASSWORD = "VIPR_PASSWORD"
    IDX_VIPR_CLI_INSTALL_PATH = "VIPR_CLI_INSTALL_DIR"
    IDX_VIPR_LOGS_PATH = "PATH_LOGS"
    IDX_VIPR_CLI_PKG_PATH = "PATH_VIPR_CLI_PKG"
    IDX_VIPR_CLI_PKG_VERSION = "VIPR_CONTROL_API_VERSION"
    IDX_VIPR_LOGS_RETENTION = "LOGS_RETENTION_DAYS"
    IDX_EMAIL_SENDER = "EMAIL_SENDER"
    IDX_EMAIL_RECEIVERS = "EMAIL_RECEIVERS"
    IDX_EMAIL_SMTP_RELAY = "EMAIL_SMTP_RELAY"

    """
    IDX_VIPR_CLI_INSTALL_PATH,
    IDX_VIPR_CLI_PKG_PATH,
    IDX_VIPR_CLI_PKG_VERSION,
    """

    REQUIRED_VARS = [IDX_VIPR_HOSTNAME, IDX_VIPR_PORT,
                     IDX_VIPR_USER, IDX_VIPR_PASSWORD,
                     IDX_VIPR_LOGS_PATH,
                     IDX_VIPR_LOGS_RETENTION,
                     IDX_EMAIL_SENDER, IDX_EMAIL_RECEIVERS,
                     IDX_EMAIL_SMTP_RELAY]

    #
    # session specific things
    #
    IDX_VIPR_SCRIPT_LOGS_PATH = "Script_Specific_Logs_Path"
    IDX_SESSION_PATH = "Session_Path"
    IDX_SESSION_NAME = "Session_Name"
    IDX_SESSION_LOGFH = "Session_Log_FH"
    IDX_SESSION_OUTFH = "Session_Out_FH"

    #
    # logging specs, default is INFO.
    # All messages go into the log.
    # Only messages with level above the level that was set go onscreen.
    #
    MSG_LVL_DEBUG = 0
    MSG_LVL_INFO = 1
    MSG_LVL_WARNING = 2
    MSG_LVL_ERROR = 3
    MSG_LVLS = {MSG_LVL_DEBUG: "DEBUG",
                MSG_LVL_INFO: "INFO",
                MSG_LVL_WARNING: "WARNING",
                MSG_LVL_ERROR: "ERROR"}
    MSG_LVL = "Message_Level"

    #
    # full debug mode - this is a flag whether full output will be getting
    # printed into log.txt file for large data sets that are provided as
    # extra argument to printMsg(). Default is FALSE, but if set to TRUE on
    # launch and printMsg receives additional argument
    # "print_only_in_full_debug" then it will only be printed in full debug.
    #
    # boolean
    #
    IDX_FULL_DEBUG = "Full Debug (print extra large objects?)"

    #
    # Exit/Error Codes
    #
    SUCCESS = 0
    ERROR_GENERIC = 1
    ERROR_TASK_FAILED = 2


    #
    # Logging modes
    #
    SESSION_BASED = "Log every session separately by timestamp"
    VALUE_BASED = "Log sessions into the same folder/files set by value"

    def __init__(self,
                 app_name,
                 msg_level,
                 args,
                 logging_mode=SESSION_BASED,
                 logging_value=None,
                 full_debug=False):
        self.data = {}

        #
        # parameter is used in the email title and possibly logging
        #
        self.__handle_bean(self.IDX_APP_NAME, app_name)

        #
        # this level dictates what shows up on screen. if set to
        # MSG_LVL_ERROR then nothing will show up on screen unless it is an
        # error message
        #
        self.setMsgLevel(msg_level)

        #
        # this will get used by self.printMsg method
        #
        self.__handle_bean(self.IDX_PPRINT, pprint.PrettyPrinter(indent=4))

        #
        # minimum data that is expected at initialization
        #
        if args.env_settings is None or args.default_local_path is None:
            raise VseExceptions.VSEInitExc(
                "Environment settings file path [args.env_settings] and " +
                "script execution file path [args.default_local_path] " +
                "are minimum required arguments to initialize vseCmn module")
        self.__handle_bean(self.IDX_ENV_SETTINGS_FILE,
                           args.env_settings)
        self.__handle_bean(self.IDX_LOCAL_EXECUTION_PATH,
                           args.default_local_path)

        #
        # does env file exist? Raises IOError if not
        # parse env file and load required variables, IOError if file cannot
        # be parsed
        #
        self.is_file(self.get_env_settings_file())
        self.read_config_file_for_module(self,
                                         self.get_env_settings_file(),
                                         self.__class__.__name__,
                                         self.REQUIRED_VARS)

        """
        #
        # below line adds ViPR CLI Bin path to be used by Python interpreter
        # it has been replaced by code directly below -
        # - reading config file, expecting a path to viprcli library directory
        # - adding that to PATH
        #
        # sys.path.append(
        # r'C:\_my\dev\tools\vipr-2.1.0.1.437-cli\' +
        # 'bin\viprcli-2.1-py2.7.egg\viprcli')

        #
        # Is ViPR CLI installed? If not, what's point of it all?
        # check if self.data[self.IDX_VIPR_CLI_PKG_PATH] is a valid path
        # check if self.data[self.IDX_VIPR_CLI_PKG_PATH]/common.py is present
        #
        if not os.path.isdir(self.__get_vipr_cli_path()):
            raise VseExceptions.VSEInitExc(
                "ViPR CLI path is not a directory: " +
                self.__get_vipr_cli_path())
        if not os.path.isfile(
                os.path.join(self.__get_vipr_cli_path(),
                             'common.py')):
            raise VseExceptions.VSEInitExc(
                "ViPR CLI path provided does not include file 'common.py', "
                "Please provide path to folder containing CLI Python "
                "libraries: " + self.__get_vipr_cli_path())
        sys.path.append(self.__get_vipr_cli_path())
        """

        # ---------------------------------------------------------------------
        # Nail down where logs will be going and open a file handle to log file
        #

        #
        # who is calling?
        #
        (caller_file,
         caller_function,
         caller_line) = self.__getCallerInfo()

        #
        # Session Name: get time stamp and process ID
        #
        p_id = os.getpid()
        date, hrs_mins_secs, milli_secs = self.getTimeStamp()
        session_time_stamp = date + '_' + hrs_mins_secs + '_pid' + str(p_id)

        #
        # Log Folders and Files: identify paths in play
        # Differentiate between 2 different ways of logging.
        #
        vipr_logs_path = self.__handle_bean(self.IDX_VIPR_LOGS_PATH)

        self.__handle_bean(self.IDX_VIPR_SCRIPT_LOGS_PATH,
                           os.path.join(vipr_logs_path,
                                        "logsFor_" + caller_file))

        if logging_mode not in [self.SESSION_BASED, self.VALUE_BASED]:
            raise VseExceptions.VSEInitExc("Invalid logging mode.")

        elif logging_mode == self.VALUE_BASED and logging_value is None:
            raise VseExceptions.VSEInitExc("Must provide value for value-based logs")

        elif logging_mode == self.SESSION_BASED:
            session_logs_path = os.path.join(self.__get_logs_path(),
                                             session_time_stamp)
            log_file_open_mode = 'w'

        elif logging_mode == self.VALUE_BASED:
            session_logs_path = os.path.join(self.__get_logs_path(),
                                             str(logging_value))
            log_file_open_mode = 'a'

        session_dbg_file = os.path.join(session_logs_path,
                                        self.DEBUG_OUTPUT_FILE)

        session_out_file = os.path.join(session_logs_path,
                                        self.ONSCREEN_OUTPUT_FILE)

        #
        # Log Folders: create/verify log folders
        #
        if not os.path.isdir(vipr_logs_path):
            raise VseExceptions.VSEInitExc(
                "Log folder [" + vipr_logs_path + "] does not exist.")
        if not os.access(vipr_logs_path, os.W_OK):
            raise VseExceptions.VSEInitExc(
                "Log folder [" + vipr_logs_path + "] is not writable.")
        if not os.path.isdir(self.__get_logs_path()):
            os.makedirs(self.__get_logs_path())
        if not os.path.isdir(session_logs_path):
            os.makedirs(session_logs_path)

        #
        # Log Files: open log files with buffer size 0
        # Cache file handles and session variables
        #
        debug_file_handle = open(session_dbg_file, log_file_open_mode, 0)
        output_file_handle = open(session_out_file, log_file_open_mode, 0)
        self.__handle_bean(self.IDX_SESSION_PATH, session_logs_path)
        self.__handle_bean(self.IDX_SESSION_NAME, session_time_stamp)
        self.__handle_bean(self.IDX_SESSION_LOGFH, debug_file_handle)
        self.__handle_bean(self.IDX_SESSION_OUTFH, output_file_handle)

        #
        # Nail down where logs will be going and open a file handle to log file
        # ----------------------------------------------------------------------

        #
        # Script is starting log messages
        # - print a separator/header to DEBUG file only
        # - print initialization complete
        #
        script_kickoff_message = \
            """
\n\n\n
-------------------------------------------------------------
- SCRIPT STARTING - SESSION: {0} -
-------------------------------------------------------------
\n\n\n""".format(session_time_stamp)

        debug_file_handle.write(script_kickoff_message)

        self.printMsg(self.MSG_LVL_DEBUG,
                      "vseCmn module initialization is complete.")
        self.printMsg(self.MSG_LVL_INFO,
                      "\n\tSession Name: " + self.get_session_name() +
                      "\n\tSession Path: " + self.get_session_path())

        #
        # deal with full_debug
        #
        self.__handle_bean(self.IDX_FULL_DEBUG,
                           full_debug)
        if full_debug:
            self.printMsg(self.MSG_LVL_DEBUG,
                          "FULL DEBUG mode is turned on - expect a lot of "
                          "output")

    """
    getter and setter for anything that is stored in self.data dictionary
    """
    def __handle_bean(self, name, value=None):
        if value is not None:
            self.data[name] = value
        else:
            return self.data.get(name)

    def get_app_name(self):
        return self.__handle_bean(self.IDX_APP_NAME)

    def get_env_settings_file(self):
        return self.__handle_bean(self.IDX_ENV_SETTINGS_FILE)

    def get_session_name(self):
        return self.__handle_bean(self.IDX_SESSION_NAME)

    def __get_logs_path(self):
        return self.__handle_bean(self.IDX_VIPR_SCRIPT_LOGS_PATH)

    def get_session_path(self):
        return self.__handle_bean(self.IDX_SESSION_PATH)

    def __get_vipr_cli_path(self):
        return self.__handle_bean(self.IDX_VIPR_CLI_PKG_PATH)

    def __get_session_log_fh(self):
        return self.__handle_bean(self.IDX_SESSION_LOGFH)

    def __get_session_out_fh(self):
        return self.__handle_bean(self.IDX_SESSION_OUTFH)

    def setMsgLevel(self, msgLevel):
        if msgLevel not in self.MSG_LVLS.keys():
            raise VseExceptions.VSEInitExc(
                "Unsupported msg level, supported levels are: " +
                self.ppFormat(self.MSG_LVLS.keys()))
        self.data[self.MSG_LVL] = msgLevel

    def get_vipr_host_name(self):
        return self.__handle_bean(self.IDX_VIPR_HOSTNAME)

    def get_vipr_host_port(self):
        return int(self.__handle_bean(self.IDX_VIPR_PORT))

    def get_vipr_user(self):
        return module_var(self, self.IDX_VIPR_USER)

    def get_vipr_password(self):
        return module_var(self, self.IDX_VIPR_PASSWORD)


    #
    # Assumption: __getCallerInfo is called by either vseCmn.__init__ or
    # vseCmn.printMsg, to reveal higher level script name that
    # triggered the call. Which means that whomever triggered those
    # calls sits 2 levels up (3rd element of the stack at index 2)
    #
    # Variable "scopeLevel" defined for default
    #
    # Returns tuple of (FileName, FunctionName, LineNumber)
    #
    def __getCallerInfo(self, scopeLevel=None):
        if scopeLevel is None:
            scopeLevel = 2
        frame = inspect.currentframe()
        try:
            (cFrame, cFilePath, cLineNr, cFName, cContext, cIndex) = \
                inspect.getouterframes(frame)[scopeLevel]
            #
            # Assume: file has extension.
            # Use rsplit function, to strip any chars after the last "."
            #
            (cFileName, cFileExt) = os.path.basename(cFilePath).rsplit(".", 1)
            cFileName = string.upper(cFileName)
        finally:
            del frame
        return cFileName, cFName, cLineNr,

    #
    # does file exist, is it a file?
    #
    def is_file(self, path):
        if not os.path.isfile(path):
            raise IOError("File " + path + " is not found on the file system")
        return True


    def read_config_file_simple(self, cfg_file_path):
        self.printMsg(self.MSG_LVL_DEBUG,
                      "Reading CFG file [{0}]...".format(cfg_file_path))
        cfg = ConfigParser.SafeConfigParser()
        cfg.read(cfg_file_path)
        return cfg


    #
    # parse file using ConfigParser, load variables into self.data and into
    # os.environ
    #
    def read_config_file_for_module(self, vse_mod_ref, cfg_file_path, section,
                                    vars):
        #
        # cannot use printMsg yet - logFH isn't configured.
        #
        # self.printMsg(self.MSG_LVL_DEBUG,
        # "Reading CFG file [{0}], section [{1}]...".format(
        #                   cfg_file_path, section))
        cfg = ConfigParser.SafeConfigParser()
        cfg.read(cfg_file_path)
        for var_name in vars:
            try:
                var_value = cfg.get(section, var_name)
            except ConfigParser.NoOptionError as e:
                raise VseExceptions.VSEInitExc(e.message)
            if var_value is None:
                raise VseExceptions.VSEInitExc(
                    "Variable " + var_name +
                    " is not found in section " + section +
                    " of config file " + cfg_file_path)
            if var_name.startswith('PATH_'):
                if var_value == 'LOCAL':
                    var_value = self.__handle_bean(
                        self.IDX_LOCAL_EXECUTION_PATH)
                elif not os.path.isdir(var_value):
                    raise VseExceptions.VSEInitExc(
                        "Path specified for variable " + var_name +
                        " (" + var_value + ") " + " is not a directory."
                    )
            module_var(vse_mod_ref, var_name, var_value)
            os.environ[var_name] = var_value

    def getTimeStamp(self):
        dt = datetime.datetime.today()
        date = dt.date().isoformat()

        hrMinsSecs = None
        milliSecs = None
        fullTS = dt.time().isoformat().replace(':', '-', 2)
        if "." in fullTS:
            hrMinsSecs, milliSecs = fullTS.rsplit('.', 1)
        else:
            hrMinsSecs = fullTS
            milliSecs = '000000'

        return date, hrMinsSecs, milliSecs

    #
    # prints separator, meta data, and msgText of error message
    # also uses pretty print to nicely format collateralObj, which could be
    # a list of some other known type that is easy to print. I am not sure
    # what the limitations are for pretty print, so will play it by ear
    #
    def printMsg(self, msgLevel, msgText, collateralObj=None,
                 print_only_in_full_debug_mode=False):
        #
        # first, compose the message
        #    Line: separator
        #    Line: date + timestamp + originator
        #    Line: msgText
        #    Line*: collateralObj dump with pretty print
        #  second, dump it into log.txt file
        #  third, determine if it needs to go onscreen
        #  forth, dump it on screen and into out.txt
        #
        date, hrMinsSecs, milliSecs = self.getTimeStamp()
        cFile, cFunction, cLine = self.__getCallerInfo()

        msg = "-------------------------------------------------------------\n"
        msg += "{6}\t{0}\t{1}.{2}\t{3}->{4}->{5}\n".format(
            date,
            hrMinsSecs.replace('-', ':', 2),
            milliSecs,
            cFile,
            cFunction,
            str(cLine),
            self.get_session_name()
        )
        msg += "{0}: {1}\n".format(self.MSG_LVLS[msgLevel], msgText)

        collateralObj if isinstance(collateralObj, basestring) else \
            self.ppFormat(collateralObj)

        if collateralObj is not None:

            obj_string = collateralObj \
                if isinstance(collateralObj, basestring) \
                else self.ppFormat(collateralObj)

            is_in_full_debug = self.__handle_bean(self.IDX_FULL_DEBUG)

            if not print_only_in_full_debug_mode:
                msg += obj_string + "\n"

            if print_only_in_full_debug_mode and is_in_full_debug:
                msg += obj_string + "\n"

            if print_only_in_full_debug_mode and not is_in_full_debug:
                msg += "\t==> Full detail is hidden to conserve hard drive " \
                       "space. To see full detail " \
                       "execute in full debug mode <==\n"

        msg += "\n"

        self.__get_session_log_fh().write(msg)

        if msgLevel >= self.__handle_bean(self.MSG_LVL):
            self.__get_session_out_fh().write(msg)
            print msg


    def ppFormat(self, ds):
        return pprint.pformat(ds, indent=4)

    #
    # forces end to program execution
    # check log folders to be compliant with retention policy
    # close file handles
    #
    def exit(self, exitCode, exitText=None):
        self.__disposeOfOldLogs()

        lvl = self.MSG_LVL_INFO
        if exitCode is not self.SUCCESS:
            lvl = self.MSG_LVL_ERROR
        msg = "finishing execution:\n" + \
              "\texit code: " + str(exitCode) + "\n"
        if exitText is not None:
            msg += "\texit message: " + str(exitText) + "\n"

        self.printMsg(lvl, msg)
        self.__get_session_log_fh().close()
        self.__get_session_out_fh().close()
        self.__email_session_results(exitCode)
        sys.exit(exitCode)

    #
    # use simplistic email scheme - non-authenticating SMTP relay
    #
    def __email_session_results(self, code):
        if (self.is_simple_value_defined(
                self.__handle_bean(self.IDX_EMAIL_SENDER))
            and self.is_simple_value_defined(
                    self.__handle_bean(self.IDX_EMAIL_RECEIVERS))
            and self.is_simple_value_defined(
                    self.__handle_bean(self.IDX_EMAIL_SMTP_RELAY))):

            app_name = self.__handle_bean(self.IDX_APP_NAME)

            message_from = app_name
            message_subject = app_name + "[{0}]:" + self.get_session_name()

            if code == self.SUCCESS:
                status_suffix = "Success"
            else:
                status_suffix = "FAILED"

            message_subject = message_subject.format(status_suffix)

            out_file = open(os.path.join(self.get_session_path(),
                                         self.ONSCREEN_OUTPUT_FILE))
            message_text = out_file.read()

            try:
                self.send_email(message_from, message_subject, message_text)
            except Exception as e:
                #
                # do NOT allow this failure to go un-recorded, at least.
                # re-open LOG and OUT files, and dump this guy in there
                # also kick it up the chain
                #
                out_file = open(
                    os.path.join(self.get_session_path(),
                                 self.ONSCREEN_OUTPUT_FILE),
                    'a')
                log_file = open(
                    os.path.join(self.get_session_path(),
                                 self.DEBUG_OUTPUT_FILE),
                    'a')
                out_file.write(e.message + "\n" + traceback.format_exc())
                log_file.write(e.message + "\n" + traceback.format_exc())
                raise e


    def send_email(self, message_from, message_subject, message_text):
        #
        # modify so SMTP recognizes from and subject.
        #
        message_from = "From: " + message_from
        message_subject = "Subject: " + message_subject

        relay = smtplib.SMTP(self.__handle_bean(self.IDX_EMAIL_SMTP_RELAY))

        relay.sendmail(
            self.__handle_bean(self.IDX_EMAIL_SENDER),
            self.__handle_bean(self.IDX_EMAIL_RECEIVERS).split(),
            "\n".join([message_from, message_subject, message_text])
        )


    def __disposeOfOldLogs(self):
        if self.is_simple_value_defined(
                self.__handle_bean(self.IDX_VIPR_LOGS_RETENTION)):
            self.printMsg(self.MSG_LVL_DEBUG,
                          "Cleaning up log directories that are out of "
                          "retention compliance...")

            # if older then "daysToKeep times seconds in a day 86400" -
            # delete
            deleteIfCreatedBefore = \
                time.time() - \
                int(self.__handle_bean(self.IDX_VIPR_LOGS_RETENTION)) * 86400

            for d in os.listdir(self.__get_logs_path()):
                # skip hidden folders that OSs create
                # skip this session folder
                if d.__contains__("."):
                    continue
                if d == self.get_session_name():
                    continue

                dPath = os.path.join(self.__get_logs_path(), d)

                if os.path.getmtime(dPath) < deleteIfCreatedBefore:
                    self.printMsg(self.MSG_LVL_DEBUG,
                                  "Log directory " + d + " is older than "
                                                         "policy allows, deleting.")
                    self.deleteDir(dPath)


    def copyFile(self, sourceFP, targetFP):
        shutil.copy(sourceFP, targetFP)


    def deleteDir(self, path, ignoreErrors=True):
        shutil.rmtree(path, ignoreErrors)


    def deleteFile(self, path):
        os.remove(path)

    #
    # to simplify checking parameters. looking for not None and not empty
    #
    def is_simple_value_defined(self, value):
        return value is not None and len(str(value)) > 0

    #
    # to take a list of JSON entries, and produce a dictionary by ID key
    #
    def convert_list_of_dict_objects_into_dict_by_id(self, objs_list):
        """

        :rtype : dict
        """
        return_dict = {}
        for obj in objs_list:
            if type(obj) is not dict:
                self.printMsg(self.MSG_LVL_WARNING,
                              "Object provided is NOT a dictionary, " +
                              "cannot process...",
                              obj)
                continue
            if obj.get('id') is None:
                self.printMsg(self.MSG_LVL_WARNING,
                              "Dictionary does NOT have key 'ID', cannot "
                              "process...",
                              obj)
                continue
            return_dict[obj.get('id')] = obj
        return return_dict

    #
    # write string into a file - can be used to create specific output files
    # along the way or to create symmetrix configuration files that need to
    #  be presented to symcli
    #
    def write_to_file(self, file_path, file_name, output):
        full_path = os.path.join(file_path, file_name)
        self.printMsg(self.MSG_LVL_DEBUG,
                      "Writing output into " + full_path + ": ",
                      output,
                      print_only_in_full_debug_mode=True)
        with open(full_path, 'w') as f:
            f.write(output)
            f.close()


def module_var(module, var, value=None, delete=False):
    """
    module_var will set or get a variable from within a module

    Use: cmn.module_var(self, IDX_VAR, Optional: Value)

    :param module:
    :param var:
    :param value:
    :return:
    """
    if not hasattr(module, 'data'):
        module.data = {}

    if value is not None:
        module.data[var] = value
    else:
        if var in module.data.keys():
            if delete:
                del module.data[var]
            else:
                return module.data[var]
        else:
            return None
