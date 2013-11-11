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

# Copyright 2012,2013 Andrew Holmes <andrew.g.r.holmes@gmail.com>

r"""adb - A pure python adb module

"""

import errno
import os
import shutil
import socket
import subprocess


#FIXME: req py3.3
ADB_PATH = shutil.which('adb')
"""Location of the adb binary."""

SERVER_HOST = 'localhost'
SERVER_PORT = 5037


A_SYNC = 0x434e5953
A_CNXN = 0x4e584e43
A_OPEN = 0x4e45504f
A_OKAY = 0x59414b4f
A_CLSE = 0x45534c43
A_WRTE = 0x45545257

ID_STAT = 0x54415453
ID_LIST = 0x5453494c
ID_ULNK = 0x4b4e4c55
ID_SEND = 0x444e4553
ID_RECV = 0x56434552
ID_DENT = 0x544e4544
ID_DONE = 0x454e4f44
ID_DATA = 0x41544144
ID_OKAY = 0x59414b4f
ID_FAIL = 0x4c494146
ID_QUIT = 0x54495551




class ADBError(Exception):
    """Base class for ADB errors."""
    
    pass
    
    
class CommandProcessError(ADBError, subprocess.CalledProcessError):
    """."""

    def __init__(self, errno, cmd, output=None):
        self.returncode = errno
        self.cmd = cmd
        self.output = output

    def __str__(self):
        """."""
        return str(self.output)


class ConnectionError(ADBError, ConnectionError):
    """Class for errors connecting and disconnecting from TCP/IP devices."""
    pass
    
    
class ADBClientError(ADBError):
    """."""
    pass


# Base function
###############################################################################

class ADBCommand(subprocess.Popen):
    """."""

    def __init__(self, *args, bufsize=-1, stdin=None, stdout=None, stderr=None,
                 product=None, serial=None):
        """Warning: adb may print server start/stop messages to stdout."""
        
        cmd_line = [ADB_PATH]
        
        #FIXME: 
        if product:
            cmd_line.append('-p')
            cmd_line.append(product)
        if serial:
            cmd_line.append('-s')
            cmd_line.append(serial)

        #FIXME wtf, this is ugly
        [cmd_line.append(arg) for arg in args]

        subprocess.Popen.__init__(self, cmd_line,
                                        bufsize=bufsize,
                                        shell=False,
                                        stdin=stdin,
                                        stdout=stdout,
                                        stderr=stderr,
                                        universal_newlines=True)
                                        

# FIXME: doc, adb proc args (-s, -p)
def check_output(*args, timeout=None, **kwargs):
    r"""Run command with arguments and return its output."""
    
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    with ADBCommand(*args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs) as proc:
        try:
            output, unused_err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, unused_err = proc.communicate()
            raise subprocess.TimeoutExpired(proc.args, timeout, output=output)
        except:
            proc.kill()
            proc.wait()
            raise
            
        if proc.poll():
            raise CommandProcessError(proc.returncode, proc.args, output=output)
            
    return output.splitlines()
    
    
class Client:
    """."""
    
    _server = None
    _socket = None
    
    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        """."""
        
        self._server = (host, port)
        self._connect()

    def _communicate(self, query):
    
        # Send the command
        message = bytes('{0:0>4x}{1}'.format(len(query), query), 'ascii')
        self._socket.send(message)
        
        return_status = self._socket.recv(4)
        
        if return_status == b'FAIL':
            err_size = int(self._socket.recv(4), 16)
            err_str = self._socket.recv(err_size)
            raise ADBError(err_str)
        elif return_status == b'OKAY':
            if query == 'host:version':
                return int(self._socket.recv(4), 16)
            else:
                ret_size = int(self._socket.recv(4), 16)
                ret_str = str(self._socket.recv(return_size))
                return ret_str
    
    #FIXME    
    def _connect(self, retry=3):
        """."""
        
        while retry:
            try:
                self._socket = socket.create_connection(self._server)
                break
            except ConnectionRefusedError:
                check_output('start-server')
                retry -= 1
        else:
            raise ADBError("Could not connect to server.")
            
    def _disconnect(self):
        """."""
        if self._socket:
            self._socket.close()
         
            
class Device(Client):
    """."""
    
    def __init__(self):
        """."""
        pass
        
        
class Server:
    """."""
    
    pass
        
        
if __name__ == '__main__':
    
    adbc = Client()
    print(adbc._communicate('host:version'))
    print(adbc._communicate('host:devices'))
    
