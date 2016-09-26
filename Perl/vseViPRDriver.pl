#!/usr/bin/perl 

#
#  Author: Stanislav Belenitsky
#  Impl Date: 2014/08/29
#  
#  Driver script is meant to demo functionality of attached libraries
#
use strict;
use warnings;
use vseCommon;
use vseViPRObject;
use vseWebAgent;
use Data::Dumper;
$Data::Dumper::Indent = 1;
$Data::Dumper::Sortkeys = 1;

#
#  set ViPR environment variables
#
my $vipr_ip = 'xxx.xxx.xxx.xxx';
my $vipr_port = '4443';
my $vipr_user = 'xxxxx';
my $vipr_pwd = 'xxxxx';

#
#  instantiate vseCommon, vseWebAgent, vseViPRObject
#
my $vseCmn = vseCommon->new();
my $vseWA = vseWebAgent->new($vseCmn, 
                             '[Your Company Name Here]', 
							 '[Your Contact Email Here]');
my $viprObj = vseViPRObject->new($vseCmn, $vseWA,
                                 $vipr_ip, $vipr_port, 
								 $vipr_user, $vipr_pwd);

#
#  trigger a basic API call and get data back
#								 
my $dataHR = $vseCmn->newHR();
if( $viprObj->whoami($dataHR) != $vseCmn->SUCCESS ) {
	$vseCmn->printLog($vseCmn->MSG_ERROR, "whoami API Call failed");
	
} else {
	$vseCmn->printLog($vseCmn->MSG_NORMAL, "whoami API Call succeeded");
	$Data::Dumper::Varname = "HTTP Response Payload: \n";
	$vseCmn->printLog($vseCmn->MSG_NORMAL, Dumper( $dataHR ) );
	
}

#
#  trigger a createBlockVolume API call
#  set specific URNs and values for testing API calls
#

#/vdc/varrays
my $varrayURN = "urn:storageos:VirtualArray:f37a6a21-a20a-45f8-80a2-dca46534df75:vdc1";
#/block/vpools
my $vpoolURN = "urn:storageos:VirtualPool:f3a3eda2-362a-4cc0-90fd-b91f6a789fa4:vdc1";
#/tenant, get tenant URN, use it to find projects, /tenants/{id}/projects
my $projectURN = "urn:storageos:Project:5ed717b7-6180-4b8a-8141-92503c88d5af:global";
#user choice for below values
my $volName = "testing_api_driver";
my $volCount = "3";
my $volSize = "19GB";

$dataHR = $vseCmn->newHR();
if( $viprObj->createBlockVolumes($dataHR,
							$varrayURN,
							$vpoolURN,
							$projectURN,
							$volName,
							$volCount,
							$volSize
							) != $vseCmn->SUCCESS ) {
	$vseCmn->printLog($vseCmn->MSG_ERROR, "createBlockVolumes API Call failed");
	
} else {
	$vseCmn->printLog($vseCmn->MSG_NORMAL, "createBlockVolumes API Call succeeded");
	$Data::Dumper::Varname = "HTTP Response Payload: \n";
	$vseCmn->printLog($vseCmn->MSG_NORMAL, Dumper( $dataHR ) );
	
}


$vseCmn->exit( $vseCmn->SUCCESS );

