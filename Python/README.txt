DEPLOYMENT STEPS ON VIPR NODES
    - copy [my_python_driver_script], help files, and vseLib libraries
    - chmod a+x [my_python_driver_script]
        - "./[my_python_driver_script] -h", - shows errors, needs interpreter
    - Edit [my_python_driver_script] file, add top line "#!/usr/bin/python"
        - "./[my_python_driver_script] -h", - shows errors, needs ^M gone (windows EoL char)
    - Edit [my_python_driver_script] file, use VIM option ":set fileformat=unix"
        - "./[my_python_driver_script] -h", - shows errors, unable to find vseLib.vseCmn
    - Edit shell variable PYTHONPATH, add path to vseLib folder. Alternative - create local symblic link to vseLib folder, and add ['.' - localpath] to PYTHONPATH
        - export PYTHONPATH=.:$PYTHONPATH
        - "./[my_python_driver_script] -h", - shows errors, unable to find vseLib.vseCmn
    - Add '__init__.py' file to vseLib folder if it doesn't exist. This empty file tells Python that vseLib is a package
        - "./[my_python_driver_script] -h", - should work. if it still does not - google the error.
    - configure env_cfg.ini settings

OPTIONS FOR CONVERTING End-Of-Line character from WINDOWS TO LINUX:
    to convert files from Windows to UNIX format:
        dos2unix filename

        open VIM, and use ":set fileformat=unix", and then save files.

        # gets rid of extra windows char
        tr -d '\r' < input.file  > new.file

        # lets you see the hidden chars
        cat -e filename

DEPLOYING VIPR MODULES ON SUSE LINUX (if need to install on ViPR C) (specifically module PARAMIKO needs to be installed for Rx library)
    vipr1:/data/app_IngestUnmanagedExportedVolumes # ./ingest_unmanaged_exported_volumes.py
    Traceback (most recent call last):
      File "./ingest_unmanaged_exported_volumes.py", line 30, in <module>
        from vseLib.VseRemoteExecution import VseRemoteExecution
      File "/data/app_IngestUnmanagedExportedVolumes/vseLib/VseRemoteExecution.py", line 12, in <module>
        from paramiko import AutoAddPolicy
    ImportError: No module named paramiko

    vipr1:~ # zypper addrepo http://download.opensuse.org/distribution/11.4/repo/oss/ oss
    Adding repository 'oss' ...................................................................................................[done]
    Repository 'oss' successfully added
    Enabled: Yes
    Autorefresh: No
    GPG check: Yes
    URI: http://download.opensuse.org/distribution/11.4/repo/oss/

    vipr1:~ # zypper -v refresh
    Verbosity: 1
    Initializing Target
    Specified repositories:
    Checking whether to refresh metadata for Python Modules (openSUSE_Tumbleweed)
    Retrieving: repomd.xml ....................................................................................................[done]
    Repository 'Python Modules (openSUSE_Tumbleweed)' is up to date.
    Checking whether to refresh metadata for oss
    Retrieving: media .........................................................................................................[done]
    Retrieving: content.asc ...................................................................................................[done]
    Retrieving: content.key ...................................................................................................[done]
    Retrieving: content .......................................................................................................[done]
    Warning: The gpg key signing file 'content' has expired.
      Repository:       oss
      Key Name:         openSUSE Project Signing Key <opensuse@opensuse.org>
      Key Fingerprint:  22C07BA5 34178CD0 2EFE22AA B88B2FD4 3DBDC284
      Key Created:      Wed May  5 15:01:33 2010
      Key Expires:      Sun May  4 15:01:33 2014 (EXPIRED)
      Rpm Name:         gpg-pubkey-3dbdc284-4be1884d
    Retrieving: dvd-11.4-6.9.1.i586.pat.gz ....................................................................................[done]
    Retrieving: dvd-11.4-6.9.1.x86_64.pat.gz ..................................................................................[done]
    Retrieving: ftp-11.4-6.9.1.i586.pat.gz ....................................................................................[done]
    Retrieving: ftp-11.4-6.9.1.x86_64.pat.gz ..................................................................................[done]
    Retrieving: non_oss-11.4-6.9.1.i586.pat.gz ................................................................................[done]
    Retrieving: non_oss-11.4-6.9.1.x86_64.pat.gz ..............................................................................[done]
    Retrieving: packages.DU.gz ..................................................................................[done (237.4 KiB/s)]
    Retrieving: packages.en.gz ................................................................................................[done]
    Retrieving: packages.gz .....................................................................................[done (814.4 KiB/s)]
    Retrieving: patterns ......................................................................................................[done]
    Retrieving: license.tar.gz ................................................................................................[done]
    Retrieving: gpg-pubkey-0dfb3188-41ed929b.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-307e3d54-4be01a65.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-3d25d3d9-36e12d04.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-3dbdc284-4be1884d.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-56b4177a-4be18cab.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-7e2e3b05-4be037ca.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-9c800aca-4be01999.asc ..............................................................................[done]
    Retrieving: gpg-pubkey-a1912208-446a0899.asc ..............................................................................[done]
    Retrieving repository 'oss' metadata ......................................................................................[done]
    Building repository 'oss' cache ...........................................................................................[done]
    Checking whether to refresh metadata for update
    Retrieving: repomd.xml ....................................................................................................[done]
    Repository 'update' is up to date.
    All repositories have been refreshed.

    vipr1:~ # zypper install python-paramiko
    Loading repository data...
    Reading installed packages...
    Resolving package dependencies...
    The following 2 NEW packages are going to be installed:
      python-paramiko python2-pycrypto
    2 new packages to install.
    Overall download size: 918.4 KiB. Already cached: 0 B  After the operation, additional 9.7 MiB will be used.
    Continue? [y/n/? shows all options] (y): y
    Retrieving package python2-pycrypto-2.6.1-6.1.x86_64                               (1/2), 396.2 KiB (  2.2 MiB unpacked)
    Retrieving: python2-pycrypto-2.6.1-6.1.x86_64.rpm ..................................................[done (117.3 KiB/s)]
    Retrieving package python-paramiko-1.7.6-4.1.noarch                                (2/2), 522.2 KiB (  7.6 MiB unpacked)
    Retrieving: python-paramiko-1.7.6-4.1.noarch.rpm ...................................................[done (161.1 KiB/s)]
    Checking for file conflicts: .....................................................................................[done]
    (1/2) Installing: python2-pycrypto-2.6.1-6.1 .....................................................................[done]
    (2/2) Installing: python-paramiko-1.7.6-4.1 ......................................................................[done]


    vipr1:/tmp/deploy_ingest_exp_vols # ./ingest_unmanaged_exported_volumes.py
    usage: ingest_unmanaged_exported_volumes.py [-h] -target_project
                                                TARGET_PROJECT -storage_type
                                                {shared,exclusive} -storage_owner
                                                STORAGE_OWNER
                                                [-prevent_umv_replicas]
                                                [-msg_level MSG_LEVEL]
                                                [-full_debug]
                                                [-catalog_ingest_exported_volume CATALOG_INGEST_EXPORTED_VOLUME]
    ingest_unmanaged_exported_volumes.py: error: argument -target_project/-tp is required

DEPLOYING ON ViPR C Nodes
    FAIR WARNING: anything copied, installed, or placed not into the /data will be wiped out on the next reboot. That means anything, including extra modules installed with the help of zypper.

PACKAGING (not sure if these instructions are worthwhile):
    cxfreeze

    download/install platform binary:
        https://pypi.python.org/pypi?:action=display&name=cx_Freeze&version=4.3.4

    simple cxfreeze scripts placed in PythonDir/Scripts/cxfreeze*

    Sample execution:
        C:\_my\dev\tools\Python 2.7.3\Scripts>python cxfreeze --version
        cxfreeze 4.3.4
        Copyright (c) 2007-2013 Anthony Tuininga. All rights reserved.
        Copyright (c) 2001-2006 Computronix Corporation. All rights reserved.

    Documentation:
        http://cx-freeze.readthedocs.org/en/latest/script.html

