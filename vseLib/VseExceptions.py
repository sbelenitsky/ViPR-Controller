__author__ = 'belens'

""" vseExceptions will contain all the custom defined exceptions """
import traceback


class VSEInitExc(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class VSEUnsupportedSRDFOperationExc(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class VSEUnsupportedMirrorOperationExc(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class VSEViPRAPIExc(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


#
# log exception nicely, control where readable message goes,
# while saving stack trace in the log file
#
# TODO: start catching specific types of exceptions, such as common.SOSError
# TODO: and formatting their output according to their properties
#
def announce_exception(cmn, e):
    msg = "Exception caught (review log files for exception details):\n"
    msg += "\tType: " + e.__class__.__name__ + "\n"
    msg += "\tError Message: " + str(e) + "\n"
    cmn.printMsg(cmn.MSG_LVL_ERROR, msg)
    cmn.printMsg(cmn.MSG_LVL_DEBUG,
                 "Exception stack trace:\n " + traceback.format_exc())
