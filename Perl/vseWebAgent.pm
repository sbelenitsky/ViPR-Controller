package vseWebAgent;

#
#  Author: Stanislav Belenitsky
#  Impl Date: 2014/08/29
#  
#  Web Agent is the library that ViPR Object uses to communicate
#  with the API
#

use LWP;

##########################################################
#  HTTP HEADERS / CONSTANTS
#

#
#  Anything under CONTENT will be treated as payload by LWP
#
sub CONTENT { return("Content"); }

#
#  HTTP Headers
#
sub CONTENT_TYPE { return("Content-Type"); }
sub ACCEPT_TYPE { return("Accept"); }
sub SDS_TOKEN { return("x-sds-auth-token"); }
sub TYPE_JSON { return("application/json"); }
sub LOCATION { return("Location"); }
sub AUTHORIZATION { return("Authorization"); }

#
#  HTTP Methods
#
sub HTTP_GET { return("get"); }
sub HTTP_POST { return("post"); }

#
#  HTTP HEADERS / CONSTANTS
##########################################################

##########################################################
#  Initialization
#
sub new {
	my $proto = shift;
	my $vseCmn = shift;
	my $agentTitle = shift;
	my $agentFrom = shift;
	
	my $self = {
		CMN => $vseCmn,
		TITLE => $agentTitle,
		FROM => $agentFrom
		};
	
	my $class = ref( $proto ) || $proto;
	bless( $self, $class );
	
	$self->_web_agent_init();
	return( $self );	
}

sub _getCmn { my $self = shift; return($self->{'CMN'}); }
sub _getTitle { my $self = shift; return($self->{'TITLE'}); }
sub _getFrom { my $self = shift; return($self->{'FROM'}); }

sub _setWebAgent { my $self = shift; $self->{'WEB_AGENT'} = shift; }
sub _getWebAgent { my $self = shift; return($self->{'WEB_AGENT'}); }

sub _web_agent_init {
	my $self = shift;

	#
	#  relax security so you dont need to install Mozilla::CA module
	#  http://search.cpan.org/~mschilli/libwww-perl/lib/LWP.pm
	#  PERL_LWP_SSL_VERIFY_HOSTNAME
	#
	$ENV{'PERL_LWP_SSL_VERIFY_HOSTNAME'} = $self->_getCmn()->FALSE;
	
	#
	#  create web agent
	#  MUST happen after variable instantiation above
	#  other a LOT of extra headache
	#
	my $web_agent = LWP::UserAgent->new;
	
	#
	#  set a few headers, so you could be identified
	#  and contacted if this software is causing havoc 
	#
	$web_agent->agent($self->_getTitle());
	$web_agent->from($self->_getFrom());
	
	#
	#  stop all automatic redirects
	#  (otherwise what the heck is going on? hard to debug)
	#
	$web_agent->requests_redirectable( $self->_getCmn()->newLR() );
	
	#
	#  cache web agent
	#	
	$self->_setWebAgent( $web_agent );
}
#
#  Initialization
##########################################################

##########################################################
#  Configuration HTTP Requests
#
sub setStandardHeaders {
	my $self = shift;
	my $href = shift;
	$href->{$self->CONTENT_TYPE} = TYPE_JSON;
	$href->{$self->ACCEPT_TYPE} = TYPE_JSON;
}

sub setSDSToken {
	my $self = shift;
	my $href = shift;
	my $auth = shift;
	$href->{$self->SDS_TOKEN} = $auth;
}

sub setAuthHeader {
	my $self = shift;
	my $href = shift;
	my $basic = shift;
	$href->{$self->AUTHORIZATION} = $basic;
}

sub setContent {
	my $self = shift;
	my $href = shift;
	my $content = shift;
	$href->{$self->CONTENT} = $content;
}
#
#  Configuration HTTP Requests
##########################################################

##########################################################
#  Execute HTTP Requests
#
sub execute {
	my $self = shift;
	my $method = shift;
	my $url = shift;
	my $headersHR = shift;
	my $cmn = $self->_getCmn();
	
	my $response = $self->_getWebAgent()->$method(
							$url, 
							%$headersHR);
	
	$cmn->printLog($cmn->MSG_DEBUG, 
		"--------------HTTP REQUEST------------------");
	$cmn->printLog($cmn->MSG_DEBUG, $response->request->as_string);
	$cmn->printLog($cmn->MSG_DEBUG, 
		"--------------HTTP RESPONSE-----------------");
	$cmn->printLog($cmn->MSG_DEBUG, $response->as_string);
	
	return($response);
}
#
#  Execute HTTP Requests
##########################################################



1;