package vseViPRObject;

#
#  Author: Stanislav Belenitsky
#  Impl Date: 2014/08/29
#  
#  ViPR Object encapsulates all API calls and authentication
#  against RESTful API.
#
#  Communications are facilitated by LWP, and payloads are in JSON
#

use MIME::Base64;
use JSON;

##########################################################
#  Initialization
#
sub new {
	my $proto = shift;
	my $vseCmn = shift;
	my $vseWA = shift;
	my $vipr_ip = shift;
	my $vipr_port = shift;
	my $vipr_user = shift;
	my $vipr_pwd = shift;
	
	my $self = {
		'CMN' => $vseCmn,
		'WEB_AGENT' => $vseWA,
		'IP' => $vipr_ip,
		'PORT' => $vipr_port,
		'USER' => $vipr_user,
		'PWD' => $vipr_pwd
		};
	
	my $class = ref( $proto ) || $proto;
	bless( $self, $class );
	
	$self->_setAuthenticated( $self->getCmn()->FALSE );
	$self->{'JSON'} = JSON->new->utf8->pretty->allow_nonref->allow_blessed;
	
	return( $self );
}

sub getCmn { my $self = shift; return($self->{'CMN'}); }
sub getWebAgent { my $self = shift; return($self->{'WEB_AGENT'}); }
sub getIP { my $self = shift; return($self->{'IP'}); }
sub getPort { my $self = shift; return($self->{'PORT'}); }
sub getUser { my $self = shift; return($self->{'USER'}); }
sub getPwd { my $self = shift; return($self->{'PWD'}); }
sub getBaseURL { 
	my $self = shift; 
	return( "https://" . $self->getIP() . ":" . $self->getPort() );
}
sub getJSON { my $self = shift; return($self->{'JSON'}); }
#
#  Initialization
##########################################################

##########################################################
#  API Calls
#
sub whoami {
	my $self = shift;
	my $dataHR = shift;
	my $cmn = $self->getCmn();
	my $agent = $self->getWebAgent();

	#
	#  standard authentication verification
	#
	if( !$self->isAuthenticated() &&
		$self->_authenticate() != $cmn->SUCCESS ) {
		return( $cmn->ERROR_AUTHENTICATION );
	} 

	#
	#  configure URL/HTTP Headers
	#
	my $URL = $self->getBaseURL() . "/user/whoami";
	my $httpHeadersHR = $cmn->newHR();
	$agent->setStandardHeaders($httpHeadersHR);
	$agent->setSDSToken($httpHeadersHR, $self->getToken());

	#
	#  HTTP call execution
	#
	my $response = $agent->execute($agent->HTTP_GET, $URL, $httpHeadersHR);

	if( !$response->is_success ) {
		$cmn->printLog($cmn->MSG_ERROR, "API call $URL failed.");
		return( $cmn->ERROR_API_CALL );
	}
	
	#
	#  Retrieve response, return to driver
	#
	my $payloadHR = $self->getJSON()->decode( $response->content );
	%$dataHR = %$payloadHR;
	
	return( $cmn->SUCCESS );
}

sub createBlockVolumes {
	my $self = shift;
	my $dataHR = shift;
	my $varrayURN = shift;
	my $vpoolURN = shift;
	my $projectURN = shift;
	my $volName = shift;
	my $volCount = shift;
	my $volSize = shift;
	my $cmn = $self->getCmn();
	my $agent = $self->getWebAgent();

	#
	#  standard authentication verification
	#
	if( !$self->isAuthenticated() &&
		$self->_authenticate() != $cmn->SUCCESS ) {
		return( $cmn->ERROR_AUTHENTICATION );
	} 

	#
	#  configure URL/HTTP Headers
	#
	my $URL = $self->getBaseURL() . "/block/volumes";
	my $httpHeadersHR = $cmn->newHR();
	$agent->setStandardHeaders($httpHeadersHR);
	$agent->setSDSToken($httpHeadersHR, $self->getToken());
	
	my $reqPayloadHR = $cmn->newHR(); 
	$reqPayloadHR->{"varray"} = $varrayURN;
	$reqPayloadHR->{"vpool"} = $vpoolURN;
	$reqPayloadHR->{"project"} = $projectURN;
	$reqPayloadHR->{"name"} = $volName;
	$reqPayloadHR->{"count"} = $volCount;
	$reqPayloadHR->{"size"} = $volSize;
	$agent->setContent($httpHeadersHR, encode_json($reqPayloadHR));
	
	#
	#  HTTP call execution
	#
	my $response = $agent->execute($agent->HTTP_POST, $URL, $httpHeadersHR);

	if( !$response->is_success ) {
		$cmn->printLog($cmn->MSG_ERROR, "API call $URL failed.");
		return( $cmn->ERROR_API_CALL );
	}
	
	#
	#  Retrieve response, return to driver
	#
	my $respPayloadHR = $self->getJSON()->decode( $response->content );
	%$dataHR = %$respPayloadHR;
	
	return( $cmn->SUCCESS );
}
#
#  API Calls
##########################################################



##########################################################
#  Authentication and Token 
#
sub _setToken { 
	my $self = shift; 
	$self->{'X-SDS-AUTH-TOKEN'} = shift;
}
sub getToken { 
	my $self = shift; 
	
	if( $self->isAuthenticated() ) {
		return($self->{'X-SDS-AUTH-TOKEN'});
	}
	
	return( $self->getCmn()->NULL );
}

sub isAuthenticated {
	my $self = shift;
	return($self->{'IS_AUTHENTICATED'});
}

sub _setAuthenticated {
	my $self = shift;
	my $isAuth = shift;
	my $token = shift;
	
	$self->{'IS_AUTHENTICATED'} = $isAuth;
	$self->_setToken( $token );
}

#
#  ViPR uses HTTP Basic Authentication.
#  Details of the protocol:
#    http://en.wikipedia.org/wiki/Basic_access_authentication
#  ViPR documents (1 of many available at EMC Community Network):
#    http://www.emc.com/techpubs/vipr/authenticate_controller_rest_api-1.htm
#    
#  Details from WIKIPEDIA:
#    When the user agent wants to send the server authentication
#      credentials it may use the Authorization header.
#    The Authorization header is constructed as follows:
#      User name and password are combined 
#        into a string "[user name]:[password]"
#      The resulting string is then encoded 
#        using the RFC2045-MIME variant of Base64, 
#        except not limited to 76 char/line[9]
#      The authorization method and a space i.e. "Basic " 
#        is then put before the encoded string.
#     
#  For example, 
#    with user name 'Aladdin' and password 'open sesame'
#    the header is formed as follows:
#       "Authorization: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="
#
sub _getHTTPBasicAuth {
	my $self = shift;
	return( "Basic " .
		encode_base64(
			$self->getUser() . ":" . $self->getPwd()
		)
	);
}	

sub _authenticate {
	my $self = shift;
	my $cmn = $self->getCmn();
	my $agent = $self->getWebAgent();
	
	#
	#  Follow HTTP redirect to .../login, to receive authorization challenge
	#
	my $response = $cmn->NULL;
	my $URL = $self->getBaseURL() . "/login";
	my $httpHeadersHR = $cmn->newHR();
	$agent->setStandardHeaders($httpHeadersHR);
	$response = $agent->execute($agent->HTTP_GET, $URL, $httpHeadersHR);

	#
	#  Verify that this is indeed an authorization challenge
	#
	if( $response->code != 401 ) {
		$cmn->printLog($cmn->MSG_ERROR, 
			"HTTP Authorization - unexpected code, check logs" );
		return($cmn->ERROR_AUTHENTICATION);
	}
	
	#
	#  Reply to authorization challenge with the "Authorization" header
	#
	$agent->setAuthHeader($httpHeadersHR, $self->_getHTTPBasicAuth());
	$response = $agent->execute(
						$agent->HTTP_GET, 
						$URL, 
						$httpHeadersHR);

	#
	#  Verify successful authorization is achieved, 
	#  set authenticated, and token
	#
	if( $response->code != 200 ) {
		$cmn->printLog($cmn->MSG_ERROR, 
			"HTTP Authorization - failed authorization" );
		return($cmn->ERROR_AUTHENTICATION);
	}

	$self->_setAuthenticated( 
				$cmn->TRUE, 
				$response->header( $agent->SDS_TOKEN )
				);
	$cmn->printLog($cmn->MSG_DEBUG, "Authentication Succeeded.\n" .
	               "SDS AUTH TOKEN received: [" . $self->getToken() . "]");
	
	return( $cmn->SUCCESS );
}
#
#  Authentication and Token 
##########################################################



1;