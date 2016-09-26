#
#  This is a base of a platform to utilize ViPR API calls through PERL. 
#  * NOTE * - much easier to use Python due to ViPR CLI being written in Python and serving as an example
#
#  This development effort is frozen in favor of Python-based development. However the platform is functional - one is able to login, logout, execute API calls.
#  See example file "vseViPRDriver.pl"
#

*******************
REQUIREMENTS
	ActiveState Perl 5.18.X (everything should work on older versions of PERL also, I do not intend to use anything super new)
	Add [perl installation/bin] to the path
	verify with "#># perl -v"
	debugger access "#># perl -d [script name]"

*******************



1.0 Target High Level
	PERL implementation for some API calls
	w/ potential to be developed into a full scope product
	
	Design
		vseCommon.pm
			logging
			constants
			utility
			
		vseViPRObject.pm
			Summary
				responsible for keeping all details about ViPR instance in question
				handles all work against restful API
				potentically can get created with token already
			Intelligence
				knows if it was created for Block, File, or otherwise
				knows if it has been authenticated
			Functionality
				.authenticate()
					handles authentication
					success or failure
					caches token
				.createBlockVolume(name of va, vp, project, etc, SYNC or ASYNC)
				.createBlockExport(name of a,b,c,d,e,..., SYNC or ASYNC)
					calls getURN on all names
					configures HTTP request
					calls HTTP execution routine
				getURN(TYPE, name)
					setup with fake instead of lookups for now.

		vseWebAgent.pm	
			Summary	
				responsible for nuts and bolts of HTTP communication
				
		vseViPRDriver.pl	
			Summary	
				responsible for driving the implementation
				