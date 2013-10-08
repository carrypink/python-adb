python-adb
==========

A python wrapper for the Android Debugging Bridge

This module is meant as a pure wrapper for the 'adb' binary, primarily to wrap
its commands as functions and raise errors as python exceptions.  The only class
defined is ADBCommand(), a sub-class of subprocess.Popen().  Like the subclass
module there are convenience functions for running custom ADB commands, but the
intent is to provide functions with proper error handling and IO for each
command.



