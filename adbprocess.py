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


import os
import subprocess
import posixpath


###############################################################################
# Constants

ADB_PATH = 'adb'

# Environmental Variables
# FIXME: Negotiate with os.environ

ADB_TRACE = ''
ANDROID_SERIAL = ''
ANDROID_LOG_TAGS = ''

# Other Environmental Variables ??? FIXME

ANDROID_PRODUCT_OUT = '/home/andrew/Downloads/Android'

ADB_ENVIRON = {
    #'ADB_TRACE': ADB_TRACE,
    #'ANDROID_SERIAL': ANDROID_SERIAL,
    #'ANDROID_LOG_TAGS': ANDROID_LOG_TAGS,

    'ANDROID_PRODUCT_OUT': ANDROID_PRODUCT_OUT
}


###############################################################################
# Exceptions
# FIXME: all of it


class ADBProcessError(Exception, subprocess.CalledProcessError):
    """Base class for ADB process errors."""

    def __str__(self):
        """."""
        return self.output


# Base function
###############################################################################


def _clean_output(raw_output):
    """return output data as a list of lines."""
    return raw_output.splitlines()


def check_output(*args, **kwargs):
    """Slightly modified subprocess.check_output()"""
    try:
        cmd_line = [ADB_PATH]
        [cmd_line.append(arg) for arg in args]

        proc = subprocess.Popen(cmd_line,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                env=ADB_ENVIRON,
                                universal_newlines=True,
                                **kwargs)

        stdout = proc.communicate()[0].splitlines()

    except OSError as exc:
        if exc.errno == 2:
            errmsg = 'adb binary "%s" not found' % ADB_PATH
        else:
            errmsg = exc.strerror

        raise ADBProcessError(exc.errno, errmsg)

    if proc.wait():
        raise ADBProcessError(proc.returncode, ' '.join(args), stdout)

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
            raise ConnectionError(line)

    return True


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
            raise ConnectionError(line)


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

    if list_only:
        args.append('-l')

    if directory:
        args.append(directory)

    output = check_output(*args)

    indices = [output.index(l) for l in output if l.startswith('syncing')]

    poutput = {}

    for index in indices:
        list_start = index + 1

        if len(indices) > indices.index(index):
            pass

        poutput[output[index][9:-3]] = output[index + 1:len(output) - 1]

    return poutput


#FIXME
def shell(*args):
    """run remote shell command."""
    with ADBProcess(args, interactive=True) as proc:
        pass


#FIXME
def emu(*args):
    """run emulator console command."""
    with ADBProcess(args, interactive=True) as proc:
        pass


#FIXME
def logcat(filter_spec=None):
    """View device log."""
    with ADBProcess(args, interactive=True) as proc:
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

    with ADBProcess(*cmd) as proc:
        return proc.lines


#FIXME: test and cleanup
def uninstall(filename, keep=False):
    """Uninstall *filename* from the device.

    If *keep* is True the application's data and cache will not be cleared.
    """

    cmd = ['uninstall', filename]

    if keep:
        cmd.append('-k')

    return ADBProcess(*cmd)


#FIXME: major output 3Mb+
def bugreport():
    """Return a string containing all information from the device that should
    be included in a bug report.
    """
    return ADBProcess('bugreport').lines


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
    return ADBProcess('version').lines[0][29:]


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
    connect('192.168.1.102')
    print(devices())

    print(sync(directory='system', list_only=True))

    disconnect('192.168.1.102')
