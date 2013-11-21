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

r"""adb - A (almost) pure python adb client

"""

import errno
import os
import shutil
import socket
import subprocess


# Constants
###############################################################################

SERVER_HOST = 'localhost'
SERVER_PORT = 5037

MSG_SYNC = 0x434e5953
MSG_CNXN = 0x4e584e43
MSG_OPEN = 0x4e45504f
MSG_OKAY = 0x59414b4f
MSG_CLSE = 0x45534c43
MSG_WRTE = 0x45545257
MSG_STAT = 0x54415453
MSG_LIST = 0x5453494c
MSG_ULNK = 0x4b4e4c55
MSG_SEND = 0x444e4553
MSG_RECV = 0x56434552
MSG_DENT = 0x544e4544
MSG_DONE = 0x454e4f44
MSG_DATA = 0x41544144
MSG_FAIL = 0x4c494146
MSG_QUIT = 0x54495551


# Constants
###############################################################################

class ADBError(Exception):
    """Base class for ADB errors."""    
    pass


class ConnectionError(ADBError, ConnectionError):
    """Class for errors connecting and disconnecting from TCP/IP devices."""
    pass
    
    
class ADBClientError(ADBError):
    """."""
    pass


# Client Classes
###############################################################################    
    
class ClientBase:
    """Base class for clients of the ADB Server."""
    
    socket = None
    
    def __init__(self, address=(SERVER_HOST, SERVER_PORT)):
        """."""
        
        if address:
            self.connect(address=address)
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
        
    def _start_server(self):
        """Start the server via adb command line client."""
        adb_bin = shutil.which('adb')
        
        if not adb_bin:
            raise ADBError('can not find "adb" binary in PATH')
        
        return subprocess.check_output([adb_bin, 'start-server'])
    
    #FIXME: test, doc
    def connect(self, address=(SERVER_HOST, SERVER_PORT), retry=3):
        """."""
        
        if self.socket:
            return
        
        while retry:
            try:
                self.socket = socket.create_connection(address)
                break
            except ConnectionRefusedError:
                self._start_server()
                retry -= 1
        else:
            #FIXME: use ConnectionError
            raise ADBError("Could not connect to server.")

    #FIXME: test, doc
    def disconnect(self):
        """."""
        if self.socket:
            self.socket.close()
            self.socket = None

    def request(self, query):
        """Send a request to the server.

        Responses from the server are in the form of a 4-byte return status,
        followed by a 4-byte hex length and finally the payload if hex length is
        greater than 0.

        If the return status is b'FAIL' ADBError will be raised accompanied by the
        error message.

        If the return status is b'OKAY' recv() will return a bytestring unless the
        expected length is not None but the return size is 0, in which case it is
        assumed a 'host:version' query was sent and a version string will be
        returned.
        """
        
        if not self.socket:
            self.connect()

        request = bytes('{0:0>4x}{1}'.format(len(query), query), 'ascii')
        self.socket.send(request)
        
        #
        status = self.socket.recv(4)
        
        #FIXME
        print(b'return status: ' + status)
        
        #
        if status == b'OKAY':
            ret_size = int(self.socket.recv(4), 16)
            return self.socket.recv(ret_size)
        #
        elif status == b'FAIL':
            err_size = int(self.socket.recv(4), 16)
            raise ADBError(self.socket.recv(err_size))
            

class ServerClient(ClientBase):
    """."""
    
    def __init__(self):
        """."""
        pass
        
    def version(self):
        """Ask the ADB server for its internal version number."""
        return int(self.request('host:version'), 16)
        
    def devices(self):
        """Ask to return the list of available Android devices and their state.
        
        Returns a byte string that will be dumped as-is by the client.
        """
        
        return self.request('host:devices')
        
    def kill(self):
        """Ask the ADB server to quit immediately.
        
        This is used when the ADB client detects that an obsolete server is
        running after an upgrade.
        """
        
        return self.request('host:kill')
        
    def track_devices(self):
        """This is a variant of devices() which doesn't close the
        connection. Instead, a new device list description is sent
        each time a device is added/removed or the state of a given
        device changes (hex4 + content). This allows tools like DDMS
        to track the state of connected devices in real-time without
        polling the server repeatedly."""
        pass
        
    def emulator(self, port):
        """host:emulator:<port>
        This is a special query that is sent to the ADB server when a
        new emulator starts up. <port> is a decimal number corresponding
        to the emulator's ADB control port, i.e. the TCP port that the
        emulator will forward automatically to the adbd daemon running
        in the emulator system.

        This mechanism allows the ADB server to know when new emulator
        instances start."""
        pass
        
    def transport(self, serial_number):
        """host:transport:<serial-number>
        Ask to switch the connection to the device/emulator identified by
        <serial-number>. After the OKAY response, every client request will
        be sent directly to the adbd daemon running on the device.
        (Used to implement the -s option)"""
        pass
        
    def transport_usb(self):
        """host:transport-usb
        Ask to switch the connection to one device connected through USB
        to the host machine. This will fail if there are more than one such
        devices. (Used to implement the -d convenience option)"""
        pass
        
    def transport_local(self):
        """host:transport-local
        Ask to switch the connection to one emulator connected through TCP.
        This will fail if there is more than one such emulator instance
        running. (Used to implement the -e convenience option)"""
        pass

    def transport_any(self):
        """host:transport-any
    Another host:transport variant. Ask to switch the connection to
    either the device or emulator connect to/running on the host.
    Will fail if there is more than one such device/emulator available.
    (Used when neither -s, -d or -e are provided)"""
        pass
        
    def host_serial(self, serial_number, request):
        """host-serial:<serial-number>:<request>
        This is a special form of query, where the 'host-serial:<serial-number>:'
        prefix can be used to indicate that the client is asking the ADB server
        for information related to a specific device. <request> can be in one
        of the format described below."""
        pass
            
    def host_usb(self, request):
        """host-usb:<request>
    A variant of host-serial used to target the single USB device connected
    to the host. This will fail if there is none or more than one."""
        pass
        
    def host_local(self, request):
        """host-local:<request>
    A variant of host-serial used to target the single emulator instance
    running on the host. This will fail if there is none or more than one."""
        pass
        
    def host(self, request):
        """host:<request>
    When asking for information related to a device, 'host:' can also be
    interpreted as 'any single device or emulator connected to/running on
    the host'."""
        pass
        
    def get_product(self):
        """<host-prefix>:get-product
    XXX"""
        pass
        
    def get_serialno(self):
        """<host-prefix>:get-serialno
    Returns the serial number of the corresponding device/emulator.
    Note that emulator serial numbers are of the form 'emulator-5554'"""
        pass
        
    def get_state(self):
        """<host-prefix>:get-state
    Returns the state of a given device as a string."""
        pass
        
    def forward(self):
        """<host-prefix>:forward:<local>;<remote>
    Asks the ADB server to forward local connections from <local>
    to the <remote> address on a given device.

    There, <host-prefix> can be one of the
    host-serial/host-usb/host-local/host prefixes as described previously
    and indicates which device/emulator to target.

    the format of <local> is one of:

        tcp:<port>      -> TCP connection on localhost:<port>
        local:<path>    -> Unix local domain socket on <path>

    the format of <remote> is one of:

        tcp:<port>      -> TCP localhost:<port> on device
        local:<path>    -> Unix local domain socket on device
        jdwp:<pid>      -> JDWP thread on VM process <pid>

    or even any one of the local services described below."""
        pass
         
            
class DeviceClient(ClientBase):
    """."""
    
    def __init__(self):
        """."""
        pass
        
        
class Server:
    """."""
    
    pass
        
        
if __name__ == '__main__':
    
    with ServerClient() as adbc:
        print('version: ' + str(adbc.version()))
        print('devices: ' + str(adbc.devices()))
        print('kill: ' + str(adbc.kill()))
    
