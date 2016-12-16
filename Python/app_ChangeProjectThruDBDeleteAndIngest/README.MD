Tested on ViPR C 3.5.0.1

Deployment:
      - copy vseLib folder, config and utility.py file to the same location on ViPR node. 
      - execute with "python [].py [arguments]"

Sample Deployment:
		vipr1:/tmp/vseTools # pwd -P
		/tmp/vseTools
		vipr1:/tmp/vseTools # ls -alh
		total 52K
		drwx------  4 root root 4.0K Sep 26 17:01 .
		drwxrwxrwt 16 root root 4.0K Sep 26 18:23 ..
		-rw-------  1 root root  31K Sep 20 22:12 drop_and_ingest_volume.py
		-rw-------  1 root root 1.6K Sep 12 17:46 env_cfg.ini
		drwx------  3 root root 4.0K Sep 26 17:12 logsFor_DROP_AND_INGEST_VOLUME
		drwx------  2 root root 4.0K Sep 26 17:09 vseLib
		vipr1:/tmp/vseTools # ls -alh ./vseLib/
		total 240K
		drwx------ 2 root root 4.0K Sep 26 17:09 .
		drwx------ 4 root root 4.0K Sep 26 17:01 ..
		-rw------- 1 root root 1.4K Sep  3  2015 VseExceptions.py
		-rw------- 1 root root 3.0K Jul 18 16:56 VseExceptions.pyc
		-rw------- 1 root root  12K Sep 26 17:09 VseHttp.py
		-rw------- 1 root root 7.8K Sep 26 17:09 VseHttp.pyc
		-rw------- 1 root root 3.4K Sep 15  2015 VseRemoteExecution.py
		-rw------- 1 root root 4.8K Jul 25 22:01 VseSymCli.py
		-rw------- 1 root root  67K Sep 20 21:41 VseViprApi.py
		-rw------- 1 root root  39K Sep 20 21:41 VseViprApi.pyc
		-rw------- 1 root root 5.9K Sep 15  2015 VseViprBackups.py
		-rw------- 1 root root 5.8K Sep  3  2015 VseViprProject.py
		-rw------- 1 root root 4.3K Sep 12 20:09 VseViprProject.pyc
		-rw------- 1 root root  100 May 23  2015 __init__.py
		-rw------- 1 root root  175 Jul 18 16:56 __init__.pyc
		-rw------- 1 root root  26K Jul 19 17:45 vseCmn.py
		-rw------- 1 root root  17K Jul 25 17:47 vseCmn.pyc


Example of output of "-h":
	usage: drop_and_ingest_volume.py [-h] -source_project SOURCE_PROJECT
									 -target_project TARGET_PROJECT -storage_type
									 {shared,exclusive} -storage_owner
									 STORAGE_OWNER -virtual_array VIRTUAL_ARRAY
									 -virtual_pool VIRTUAL_POOL
									 [-volume_name VOLUME_NAME]
									 [-msg_level MSG_LEVEL] [-full_debug]
									 [-catalog_uxp_rmv_volume CATALOG_UXP_RMV_VOLUME]
									 [-catalog_discover_unmanaged_volumes CATALOG_DISCOVER_UNMANAGED_VOLUMES]
									 [-catalog_ingest_exported_volume CATALOG_INGEST_EXPORTED_VOLUME]

	drop_and_ingest_volume.py deletes a volume from database and ingests it back
	under a new project

	optional arguments:
	  -h, --help            show this help message and exit

	Required Arguments:
	  -source_project SOURCE_PROJECT, -sp SOURCE_PROJECT
							Specify name of source project.
	  -target_project TARGET_PROJECT, -tp TARGET_PROJECT
							Specify name of target project to ingest volumes into.
	  -storage_type {shared,exclusive}, -st {shared,exclusive}
							Specify type of storage, either shared or exclusive
	  -storage_owner STORAGE_OWNER, -so STORAGE_OWNER
							Specify name of storage owner (host or cluster).
	  -virtual_array VIRTUAL_ARRAY, -va VIRTUAL_ARRAY
							Specify name of virtual array
	  -virtual_pool VIRTUAL_POOL, -vp VIRTUAL_POOL
							Specify name of virtual pool

	Optional Arguments:
	  -volume_name VOLUME_NAME, -vn VOLUME_NAME
							Optionally filter volumes by name (startswith).
	  -msg_level MSG_LEVEL, -m MSG_LEVEL
							Specify output level: 0-DEBUG, 1-INFO, 2-WARNING,
							3-ERROR. INFO is default.
	  -full_debug           Full Debug will cause full output of API calls and
							other extra large objects

	Optional Service Catalog Arguments:
	  -catalog_uxp_rmv_volume CATALOG_UXP_RMV_VOLUME
							Specify name of service catalog service inside the
							catalog folder that is used to unexport and remove
							block volume. Default value is [Remove Block Volumes].
	  -catalog_discover_unmanaged_volumes CATALOG_DISCOVER_UNMANAGED_VOLUMES
							Specify name of service catalog service inside the
							catalog folder that is used to discover unmanaged
							block volumes. Default value is [Discover Unmanaged
							Volumes].
	  -catalog_ingest_exported_volume CATALOG_INGEST_EXPORTED_VOLUME
							Specify name of service catalog service inside the
							catalog folder that is used to ingest exported
							unmanaged block volume. Default value is [Ingest
							Exported Unmanaged Volumes].

Example of command line to execute:

	#
	# will move all exported FC block volumes in Source Project to Target Project. Volume filters for VA, VP, and SO will be applied. 
	#
	#@# python drop_and_ingest_volume.py -sp MvVols1 
										 -tp MvVols2 
										 -st shared 
										 -so VSECluster 
										 -va MvVols1186 
										 -vp "VMAX Local"

