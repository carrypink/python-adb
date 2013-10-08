#!/usr/bin/env python3
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor Boston, MA 02110-1301, USA

# Copyright 2012 Andrew Holmes <andrew.g.r.holmes@gmail.com>

r"""adb - A python wrapper for the Android Debugging Bridge

This module is meant as a pure wrapper for the 'adb' binary, primarily to wrap
its commands as functions and raise errors as python exceptions.

"""


import errno
import os
import shutil
import subprocess


###############################################################################
# Constants

ADB_PATH = shutil.which('adb')

# Environmental Variables
# FIXME: Negotiate with os.environ (http://stackoverflow.com/questions/2231227/python-subprocess-popen-with-a-modified-environment)
# FIXME: shell=False so find away to avoid os.environ

# Print debug information. A comma separated list of the following values
# 1 or all, adb, sockets, packets, rwx, usb, sync, sysdeps, transport, jdwp
ADB_TRACE = None
    
# The serial number to connect to. -s takes priority over this if given.
ANDROID_SERIAL = None
    
# When used with the logcat option, only these debug tags are printed.
ANDROID_LOG_TAGS = None

# A path to a product out directory like 'out/target/product/sooner'. If -p
# is not specified, the ANDROID_PRODUCT_OUT environment variable is used,
# which must be an absolute path.
ANDROID_PRODUCT_OUT = '/home/andrew/Downloads/Android'


###############################################################################
# Exceptions
# FIXME: all of it


class ADBError(Exception):
    """Base class for ADB errors."""

    def __init__(self, errno, cmd, output=None):
        self.returncode = errno
        self.cmd = cmd
        self.output = output or None

    def __str__(self):
        """."""
        return ''.join([self.output])


class ADBWarning(Warning):
    """Base class for ADB errors which the adb tool does not treat as fatal."""

    def __init__(self, errno, errmsg):
        self.errno = errno
        self.errmsg = errmsg

class ConnectionError(ADBError):
    """Class for errors connecting and disconnecting from TCP/IP devices."""
    pass


class SyncError(ADBWarning):
    """Class for errors during sync()."""
    pass


# Base function
###############################################################################


class ADBCommand(subprocess.Popen):
    """."""

    def __init__(self, *opts, stdout=None, stdin=None, product=None):
        """."""

        try:
            #FIXME wtf, this is ugly
            cmd_line = [ADB_PATH]
            [cmd_line.append(opt) for opt in opts]

            subprocess.Popen.__init__(self,
                                      cmd_line,
                                      stdin=stdin,
                                      stdout=stdout,
                                      # adb seems to arbitrarily print to stderr
                                      stderr=subprocess.STDOUT,
                                      universal_newlines=True)
        except OSError as exc:
            raise ADBError(exc.errno, ' '.join(cmd_line), exc.strerror)


def output(*args):
    """."""

    with ADBCommand(*args, stdout=subprocess.PIPE) as proc:
        stdout = proc.communicate()[0].splitlines()

    return [line for line in stdout if not line.startswith('*')]


def check_output(*args):
    """Slightly modified subprocess.check_output()"""

    with ADBCommand(*args, stdout=subprocess.PIPE) as proc:
        stdout = proc.communicate()[0].splitlines()

        if proc.wait():
            raise ADBError(proc.returncode, ' '.join(args), '\n'.join(stdout))

    # Return a list of lines, stripping server start/stop messages
    return [line for line in stdout if not line.startswith('*')]



# General Commands
###############################################################################


#FIXME: see AAFM.py crazy ass regex
def devices():
    """Return a list of device/permissions pairs."""

    output = check_output('devices')

    return [line.split('\t') for line in output if '\t' in line]


#FIXME: sketchy error handling
def connect(host, port=5555):
    """Connect to a TCP/IP device."""

    for line in check_output('connect', ':'.join([host, str(port)])):
        if line.startswith('unable to connect to '):
            #return errno.EHOSTUNREACH
            raise ConnectionError()
        if line.startswith('already connected to '):
            #return errno.EISCONN
            raise ConnectionError()

    return 0


#FIXME: sketchy error handling
def disconnect(host=None, port=5555):
    """Disconnect from a TCP/IP device.

    If *host* is None the adb server will disconnect from all connected TCP/IP
    devices.
    """

    args = ['disconnect']

    if host:
        args.append(':'.join([host, str(port)]))

    for line in check_output(*args):
        if line.startswith('No such device'):
            return errno.ENXIO

    return 0


# Device Commands
###############################################################################


def push(local, remote):
    """Copy file or directory *local* to device as *remote*."""
    check_output('push', local, remote)


def pull(remote, local=None):
    """Copy file or directory *remote* from device to *local*, if specified."""
    if local:
        check_output('pull', remote, local)
    else:
        check_output('pull', remote)


#FIXME: ANDROID_PRODUCT_OUT
def sync(directory=None, list_only=False):
    """Sync from host to client.

    The *directory* parameter should be either 'system', 'data' or None if both
    should be synced.  If *list_only* is True then a simulated sync() will be
    run.
    """
    args = ['sync']
    output = {}

    if list_only:
        args.append('-l')

    if directory:
        args.append(directory)

    proc = ADBCommand(*args, stdout=subprocess.PIPE)
    stdout = proc.communicate()[0].splitlines()

    if proc.wait():
        error = True

    for line in stdout:
        if line.startswith('syncing'):
            output[line[9:-3]] = []

            for transaction in stdout[stdout.index(line) + 1:]:
                if 'files pushed' in transaction:
                    break
                elif 'push:' in transaction:
                    transaction = transaction.lstrip('would ')
                    transaction = transaction.lstrip('push: ')

                    output[line[9:-3]].append(transaction)
                else:
                    raise ADBError(proc.returncode, ' '.join(args), os.strerror(proc.returncode))

    return output


#FIXME: http://stackoverflow.com/questions/18407470/using-adb-sendevent-in-python
def shell(argstr):
    """run remote shell command."""
    with ADBCommand(args, interactive=True) as proc:
        pass


#FIXME
def emu(*args):
    """run emulator console command."""
    with ADBCommand(args, interactive=True) as proc:
        pass


#FIXME
def logcat(filter_spec=None):
    """View device log."""
    with ADBCommand(args, interactive=True) as proc:
        pass


#FIXME
def forward(local, remote):
    """Forward socket connections.

    forward specs are one of:

    tcp:<port>
    localabstract:<unix domain socket name>
    localreserved:<unix domain socket name>
    localfilesystem:<unix domain socket name>
    dev:<character device name>
    jdwp:<process pid> (remote only).
    """
    pass


#FIXME
def jdwp():
    """list PIDs of processes hosting a JDWP transport."""
    pass


#FIXME: test and cleanup
def install(filename, lock=False, reinstall=False, sdcard=False,
            encryption=None):
    """Push *filename* to the device and install it.

    If *lock* is True the app will be forward locked.
    If *reinstall* is True the app will be reinstalled if already installed.
    If *sdcard* is True the app will be installed to the SD card using the
    native App2SD method.
    If *encryption* is not None it should be a sequence object of three strings
    in the form [ algorithm-name, hex-encoded-key, hex-encoded-iv ].
    """
    cmd = ['install', filename]

    if lock:
        cmd.append('-l')
    if reinstall:
        cmd.append('-r')
    if sdcard:
        cmd.append('-s')

    if encryption:
        cmd.append('--algo')
        cmd.append(encryption[0])
        cmd.append('--key')
        cmd.append(encryption[1])
        cmd.append('--iv')
        cmd.append(encryption[2])

    with ADBCommand(*cmd) as proc:
        return proc.lines


#FIXME: test and cleanup
def uninstall(filename, keep=False):
    """Uninstall *filename* from the device.

    If *keep* is True the application's data and cache will not be cleared.
    """

    cmd = ['uninstall', filename]

    if keep:
        cmd.append('-k')

    return ADBCommand(*cmd)


#FIXME: major output 3Mb+
def bugreport():
    """Return a string containing all information from the device that should
    be included in a bug report.
    """
    return ADBCommand('bugreport').lines


#FIXME
def backup(file='backup.ab', apk=False, shared=False, all=False, system=True,
           *packages):
    """Create an archive of the device's data called *file*.

    If *apk* is True the APK files themselves will be included.
    If *shared* is True the contents of the device's shared/external storage
    will be included.
    If *all* is True all installed applications will be included.
    If *all* is True but *system* is False then system applications will be
    excluded, unless they are explicity listed in *packages*.
    """
    pass


#FIXME
def restore(file):
    """restore device contents from the <file> backup archive."""
    pass


def version():
    """Return version number as a string."""
    return ADBCommand('version').lines[0][29:]


# Scripting
# FIXME: missing commands
###############################################################################


#FIXME
def get_serialno():
    """."""
    pass


#FIXME
def get_state():
    """."""
    pass


#FIXME
def wait_for_device():
    """."""
    pass


# Networking
# FIXME: missing commands
###############################################################################


#FIXME
def ppp(local, remote):
    """.
    """
    pass


###############################################################################
# Testing


if __name__ == '__main__':
    
    #print(connect('192.168.0.11'))
    print(devices())
    #ADBCommand('devices')
