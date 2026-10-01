"""Trusted child launcher: resource limits before entering Seatbelt, no threaded preexec_fn."""
import os
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU,(8,8))
resource.setrlimit(resource.RLIMIT_FSIZE,(64_000,64_000))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
policy,python,script=sys.argv[1:4]
os.execv("/usr/bin/sandbox-exec",["sandbox-exec","-f",policy,python,"-I","-S","-B",script])
