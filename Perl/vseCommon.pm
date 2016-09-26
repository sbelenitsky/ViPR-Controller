package vseCommon;

#
#  Author: Stanislav Belenitsky
#  Impl Date: 2014/08/29
#  
#  vseCommon library contains some generic constants, utility methods,
#  and takes care of logging output
#  can open a close files for reading/writing/appending
#

sub TRUE { return(1); }
sub FALSE { return(0); }
sub NULL { return(undef); }

sub MSG_DEBUG { return(4); }
sub MSG_NORMAL { return(3); }
sub MSG_WARNING { return(2); }
sub MSG_ERROR { return(1); }

sub SUCCESS { return(0); }
sub ERROR_AUTHENTICATION { return(9); }
sub ERROR_API_CALL { return(10); }

sub new {
	my $proto = shift;
	my $self = {};
	my $class = ref( $proto ) || $proto;
	bless( $self, $class );

	#
	#  setting up a log file
	#
	my $logFH = $self->NULL;
	my $logFile = "log.txt";
	if( $self->openFile( \$logFile, 'a', \$logFH ) != $self->SUCCESS ) {
		$self->printLog($self->MSG_ERROR,
				"Cannot open output file >$logFile<, $!" );
		$self->destroy();
		return( undef );
	}
	$self->setLog( $logFH );
	$self->setLogLevel( $self->MSG_NORMAL );
	
	$self->printLog($self->MSG_NORMAL,
			"*********************************************");
	$self->printLog($self->MSG_NORMAL,
			"Starting a new execution...");
	
	return( $self );
}

sub setLog { my $self = shift; $self->{'LOG_FH'} = shift; }
sub getLog { my $self = shift; return($self->{'LOG_FH'}); }

sub setLogLevel { my $self = shift; $self->{'LOG_LEVEL'} = shift; }
sub getLogLevel { my $self = shift; return($self->{'LOG_LEVEL'}); }

sub openFile {
	my $self = shift;
	my $pathRef = shift;
	my $access = shift;
	my $handle = shift;
	my $rwa = $access eq 'w' ? '>' : ($access eq 'a' ? '>>' : '<');
	if( !open($$handle, $rwa, $$pathRef) ) {
		return( $self->ERROR_CANNOT_OPEN_FILE );
	}
	return( $self->SUCCESS );
}

sub printLog {
	my $self = shift;
	my $level = shift;
	my $msg = shift;
	
	$msg .= "\n";
	
	#
	#  TODO: implement:
	#    better formatted logging, 
	#    with timestamps, 
	#    where message is coming from, etc.
	#
	
	#
	#  if msg is more urgent than default level, print to STDOUT
	#  default message priority level is MSG_NORMAL,
	#  which means that all messages marked as MSG_DEBUG will not be shown
	#
	if( $level <= $self->getLogLevel() ) {
		print STDOUT $msg;
	}
	
	#
	#  print all messages to log file
	#
	my $logFH = $self->getLog();
	print $logFH $msg;
	
	return( $self->SUCCESS );
}

sub setAutoFlush {
	select(STDOUT);
	$|++;
	select(STDERR);
	$|++;
	select($self->LOGFH);
	$|++;
}

sub newLR { my @list = (); return( \@list ); }
sub newHR { my %hr = (); return( \%hr ); }

sub exit {
	my $self = shift;
	my $code = shift;
	$self->printLog( $self->MSG_NORMAL,
		"*********************************************" );
	$self->printLog( $self->MSG_NORMAL,
		"Finishing Execution - exit code $code" );
	$self->destroy();
	CORE::exit();
}

sub destroy {
	my $self = shift;
	my $logFH = $self->getLog();
	if( defined($logFH) ) {
		close( $$logFH );
	}
}

1;