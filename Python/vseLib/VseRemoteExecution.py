__author__ = 'belens'

"""
VseRemoteExecution Remote Execution library uses python's paramiko library

SSH tunnel is opened for every command

throws exceptions that should be handled above
"""


from paramiko import AutoAddPolicy
from paramiko import SSHClient
import hashlib
import time
from vseCmn import module_var


class VseRemoteExecution:
    IDX_CMN = "Module_Ref_Common"

    def __init__(self, cmn):
        module_var(self, self.IDX_CMN, cmn)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "VseRemoteExecution module is initialized...")


    def rx_cmd_simple(self, ip, username, pwd, cmd, sleepTimerSeconds=1):
        """
        execute any command on targeted system.


        returns tuple of (exitCode, output)
            exitCode - command final exit code.
            output - merged output from STDIN and STDERR
        """
        cmn = module_var(self, self.IDX_CMN)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "To server [" + str(ip) + "], sending " +
                     "command [" + str(cmd) + "]...")

        ssh_session = SSHClient()
        ssh_session.set_missing_host_key_policy(AutoAddPolicy())
        ssh_session.connect(hostname=ip, username=username, password=pwd)

        # reach out to lower level Channel class in order to reach exit code.
        channel = ssh_session.get_transport().open_session()
        # combine stderr and stdout on this channel
        #    -- this doesn't have to be done, they can be treated separately
        # set timeout to 60 seconds

        channel.set_combine_stderr(True)
        channel.settimeout(60.0)

        # execute
        channel.exec_command(cmd)

        #
        # keep checking channel buffer until exit code is available
        # every check draw down all buffered content
        # exit code will not be available until remote process
        # is able to push all its output into channel, so if buffer fills up
        # and is not drawn down the whole thing gets stuck (happens for
        # large outputs)
        #
        # i need to put in a sleep timer because otherwise buffer
        # checking happens at millisecond intervals and output is flooded
        #
        output = ''
        exit_code = 0
        while True:
            if not channel.exit_status_ready():
                cmn.printMsg(
                    cmn.MSG_LVL_DEBUG,
                    "Processing is ongoing or more output is coming through, "
                    "absorbing buffer...")
                output += get_buffered_output(channel)
                time.sleep(sleepTimerSeconds)
            else:
                output += get_buffered_output(channel)
                exit_code = channel.recv_exit_status()
                break

        ssh_session.close()

        # report event in the logfiles
        msg_level = cmn.MSG_LVL_DEBUG
        if exit_code != 0:
            msg_level = cmn.MSG_LVL_WARNING
        cmn.printMsg(msg_level,
                     "Command exited with code [" + str(exit_code) +
                     "], and output: \n",
                     output,
                     print_only_in_full_debug_mode=True)

        return exit_code, output


    #
    # Paramiko SFTP client options are described in detail @
    # http://docs.paramiko.org/en/2.0/api/sftp.html
    #
    # Bottom line - SFTP client can do on remote system nearly everything
    # that regular file manipulations can do on local system.
    # Upload/Download a file are some of the simplest things only. Can
    # mkdir, chown, ls, pwd, and more.
    #
    XFER_OP_UP = 'Upload'
    XFER_OP_DL = 'Download'
    def xfer_file_sftp(self, xfer_op,
                       remote_host, username, pwd,
                       local_path, remote_path):

        cmn = module_var(self, self.IDX_CMN)

        if xfer_op not in [self.XFER_OP_DL, self.XFER_OP_UP]:
            cmn.printMsg(cmn.MSG_LVL_WARNING,
                         "Unsupported SFTP operation, not in:",
                         [self.XFER_OP_UP, self.XFER_OP_DL])
            raise Exception("Unsupported SFTP operation")

        #
        # figuring out welcome message
        #
        if xfer_op == self.XFER_OP_UP:
            msg = "{0}ing {1} to {2}@{3}:{4}...".format(
                xfer_op, local_path, username, remote_host, remote_path
            )
        else:
            msg = "{0}ing {1}@{2}:{3} to {4}...".format(
                xfer_op, username, remote_host, remote_path, local_path
            )
        cmn.printMsg(cmn.MSG_LVL_DEBUG, msg)

        #
        # open SFTP client session
        #
        ssh_session = SSHClient()
        ssh_session.set_missing_host_key_policy(AutoAddPolicy())
        ssh_session.connect(hostname=remote_host, username=username, password=pwd)
        sftp = ssh_session.open_sftp()

        #
        # File transfer, up or down
        #
        if xfer_op == self.XFER_OP_UP:
            sftp.put(local_path, remote_path, callback=None, confirm=True)
        else:
            sftp.get(remote_path, local_path, callback=None)

        #
        # compare MD5s
        # newlines are different on different OSs, so drop them
        #
        local_text = open(local_path,'r').read().replace(
            '\n','').replace('\r','')
        remote_text = sftp.open(remote_path).read().replace(
            '\n','').replace('\r','')
        md5_local = hashlib.md5(local_text).digest()
        md5_remote = hashlib.md5(remote_text).digest()

        #
        # cleanup before ending
        #
        sftp.close()
        ssh_session.close()

        if md5_local != md5_remote:
            raise Exception("File {0} transferred to {1}@{2}:{3}, "
                            "but MD5 checksum is wrong, consider "
                            "operation a failure.")


def get_buffered_output(channel):
    out = ''
    if channel.recv_ready():
        next_kb = channel.recv(1024)
        while next_kb:
            out += next_kb
            next_kb = channel.recv(1024)
    return out

