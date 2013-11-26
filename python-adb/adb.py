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

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 5037
DEFAULT_SERVER = (DEFAULT_HOST, DEFAULT_PORT)

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

HOST_ANY = b'host'
HOST_LOCAL = b'host-local'
HOST_SERIAL = b'host-serial'

TRANSPORT_ANY = b'transport-any'
"""Either the device or emulator connect to/running on the host."""
TRANSPORT_LOCAL = b'transport-local'
"""Ask to switch the connection to one emulator connected through TCP."""
TRANSPORT_USB = b'transport-usb'
"""One device connected through USB to the host machine."""
#FIXME: TRANSPORT_SERIAL = b'transport-serial'
#FIXME: """."""


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
    
    def __init__(self, address=DEFAULT_SERVER):
        """."""
        
        if address:
            self.connect(address=address)
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
        
    def _recv(self, size):
        """A simple buffered wrapper around socket.recv()."""
        
        data = b''
        
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            
            if chunk == b'':
                raise BrokenPipeError('socket closed')
                
            data += chunk
        else:
            return data
            
    def _send(self, data):
        """A simple buffered wrapper around socket.send()."""
        total_sent = 0
        
        while total_sent < len(data):
            sent = self.socket.send(data[total_sent:])
            
            if sent == 0:
                raise BrokenPipeError('connection closed')
            
            total_sent += sent
        else:
            return total_sent
        
    def _start_server(self):
        """Start the server via adb command line client."""
        adb_bin = shutil.which('adb')
        
        if not adb_bin:
            raise ADBError('can not find "adb" binary in PATH')
        
        return subprocess.check_output([adb_bin, 'start-server'])
    
    #FIXME: test
    def connect(self, address=DEFAULT_SERVER, retry=3):
        """Connect to an ADB server.
        
        By default connect() will attempt to connect to server on localhost,
        port 5037, and failing to do so will try to (re)start the ADB server
        and reconnect *retry* times.
        """
        
        if self.socket:
            self.disconnect()
        
        while retry:
            try:
                #FIXME: AF_INET, SOCK_STREAM, SOCK_NONBLOCK
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
        try:
            if self.socket:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
                self.socket = None
        except:
            self.socket = None
            return
            
    #FIXME
    def recv(self):
        """Receive a response from the server.

        Responses from the server are in the form of a 4-byte return status,
        followed by a 4-byte hex length and finally the payload if hex length is
        greater than 0.

        If the return status is b'FAIL' ADBError will be raised accompanied by the
        error message.

        If the return status is b'OKAY' recv() will return a bytestring
        (possibly b'').
        """
        
        status = self._recv(4)
        size = int(self._recv(4), 16)
        
        #
        if status == b'OKAY':
            return self._recv(size)
        #
        elif status == b'FAIL':
            raise ADBError(self._recv(size))
        else:
            raise ADBError('unknown protocol error')
        
    def send(self, data, host=HOST_ANY):
        """Send a '<host-prefix>:<service-name>' request to the server.

        ADB clients send requests as a 4-byte hexadecimal length followed by
        the payload."""
        
        dataf = bytes('{0:0>4x}{1}'.format(len(data), data), 'ascii')
        return self._send(dataf)
            

class HostClient(ClientBase):
    """."""
    
    def __init__(self):
        """."""
        pass
        
    def version(self):
        """Ask the ADB server for its internal version number.
        
        Returns an integer.
        """
        self.send('host:version')
        
        return int(self.recv(), 16)
        
    #FIXME: long, conn closed after, format response
    def devices(self, long=False):
        """Ask to return the list of available Android devices and their state.
        
        Returns a byte string that will be dumped as-is by the client.
        """
        
        self.send('host:devices')
        
        return self.recv()
        
    def kill(self):
        """Ask the ADB server to quit immediately.
        
        This is used when the ADB client detects that an obsolete server is
        running after an upgrade.
        """
        
        self.send('host:kill')
        
        return self.recv()
        
    def track_devices(self):
        """This is a variant of devices() which doesn't close the
        connection. Instead, a new device list description is sent
        each time a device is added/removed or the state of a given
        device changes (hex4 + content). This allows tools like DDMS
        to track the state of connected devices in real-time without
        polling the server repeatedly."""
        pass
    
    #FIXME: response, doc, test
    def emulator(self, port):
        """host:emulator:<port>
        This is a special query that is sent to the ADB server when a
        new emulator starts up. <port> is a decimal number corresponding
        to the emulator's ADB control port, i.e. the TCP port that the
        emulator will forward automatically to the adbd daemon running
        in the emulator system.

        This mechanism allows the ADB server to know when new emulator
        instances start."""
        
        self.send('host:emulator:' + str(port))
        
        return self.recv()
        
    #FIXME: figure it out
    def transport(self, device=TRANSPORT_ANY, serialno=None):
        """host:<transport>:<serial-number>
        
        Ask to switch the connection to the device/emulator identified by
        <serial-number>. After the OKAY response, every client request will
        be sent directly to the adbd daemon running on the device.
        (Used to implement the -s option)
        
        Ask to switch the connection to the device or emulator identified by
        *device* which should be one of the TRANSPORT_* constants or a specific
        identifier (eg. 025657124acd8d2d, emulator-5554, 192.168.0.101:5555).
        """
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
        """<host-prefix>:get-product"""
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
        
    def forward(self, norebind=False):
        """<host-prefix>:forward:<local>;<remote>
        Asks the ADB server to forward local connections from <local>
        to the <remote> address on a given device.

        <host-prefix>:forward:norebind:<local>;<remote>
        Same as <host-prefix>:forward:<local>;<remote> except that it will
        fail it there is already a forward connection from <local>.

        Used to implement 'adb forward --no-rebind <local> <remote>'

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
        
    def killforward(self, all=False):
        """<host-prefix>:killforward:<local>
        Remove any existing forward local connection from <local>.
        This is used to implement 'adb forward --remove <local>'

        <host-prefix>:killforward-all
        Remove all forward network connections.
        This is used to implement 'adb forward --remove-all'.
        """
        pass

    def list_forward(self):
        """
        <host-prefix>:list-forward
            List all existing forward connections from this server.
            This returns something that looks like the following:

               <hex4>: The length of the payload, as 4 hexadecimal chars.
               <payload>: A series of lines of the following format:

                 <serial> " " <local> " " <remote> "\n"

            Where <serial> is a device serial number.
                  <local>  is the host-specific endpoint (e.g. tcp:9000).
                  <remote> is the device-specific endpoint.

            Used to implement 'adb forward --list'."""
        pass
        
            
class LocalClient(ClientBase):
    """."""
    
    #FIXME
    def __init__(self, address=DEFAULT_SERVER, device=TRANSPORT_ANY):
        """."""
        pass
        
    #FIXME
    def shell(self, args=None):
        """Run 'command arg1 arg2 ...' in a shell on the device, and return
        its output and error streams.
        
        Note that arguments must be separated
        by spaces. If an argument contains a space, it must be quoted with
        double-quotes. Arguments cannot contain double quotes or things
        will go very wrong.

        Note that this is the non-interactive version of 'adb shell'
        
        ************************************************************
        

        shell:
        Start an interactive shell session on the device. Redirect
        stdin/stdout/stderr as appropriate. Note that the ADB server uses
        this to implement "adb shell", but will also cook the input before
        sending it to the device (see interactive_shell() in commandline.c)
        """
        pass

    #FIXME
    def remount(self):
        """
        remount:
        Ask adbd to remount the device's filesystem in read-write mode,
        instead of read-only. This is usually necessary before performing
        an "adb sync" or "adb push" request.

        This request may not succeed on certain builds which do not allow
        that."""
        pass
        
    #FIXME
    def dev(self, path):
        """

        dev:<path>
        Opens a device file and connects the client directly to it for
        read/write purposes. Useful for debugging, but may require special
        privileges and thus may not run on all devices. <path> is a full
        path from the root of the filesystem.
        """
        pass

"""
tcp:<port>
    Tries to connect to tcp port <port> on localhost.

tcp:<port>:<server-name>
    Tries to connect to tcp port <port> on machine <server-name> from
    the device. This can be useful to debug some networking/proxy
    issues that can only be revealed on the device itself.

local:<path>
    Tries to connect to a Unix domain socket <path> on the device

localreserved:<path>
localabstract:<path>
localfilesystem:<path>
    Variants of local:<path> that are used to access other Android
    socket namespaces.

log:<name>
    Opens one of the system logs (/dev/log/<name>) and allows the client
    to read them directly. Used to implement 'adb logcat'. The stream
    will be read-only for the client.

framebuffer:
    This service is used to send snapshots of the framebuffer to a client.
    It requires sufficient privileges but works as follow:

      After the OKAY, the service sends 16-byte binary structure
      containing the following fields (little-endian format):

            depth:   uint32_t:    framebuffer depth
            size:    uint32_t:    framebuffer size in bytes
            width:   uint32_t:    framebuffer width in pixels
            height:  uint32_t:    framebuffer height in pixels

      With the current implementation, depth is always 16, and
      size is always width*height*2

      Then, each time the client wants a snapshot, it should send
      one byte through the channel, which will trigger the service
      to send it 'size' bytes of framebuffer data.

      If the adbd daemon doesn't have sufficient privileges to open
      the framebuffer device, the connection is simply closed immediately.

dns:<server-name>
    This service is an exception because it only runs within the ADB server.
    It is used to implement USB networking, i.e. to provide a network connection
    to the device through the host machine (note: this is the exact opposite of
    network tethering).

    It is used to perform a gethostbyname(<address>) on the host and return
    the corresponding IP address as a 4-byte string.

recover:<size>
    This service is used to upload a recovery image to the device. <size>
    must be a number corresponding to the size of the file. The service works
    by:

       - creating a file named /tmp/update
       - reading 'size' bytes from the client and writing them to /tmp/update
       - when everything is read successfully, create a file named /tmp/update.start

    This service can only work when the device is in recovery mode. Otherwise,
    the /tmp directory doesn't exist and the connection will be closed immediately.

jdwp:<pid>
    Connects to the JDWP thread running in the VM of process <pid>.

track-jdwp
    This is used to send the list of JDWP pids periodically to the client.
    The format of the returned data is the following:

        <hex4>:    the length of all content as a 4-char hexadecimal string
        <content>: a series of ASCII lines of the following format:
                        <pid> "\n"

    This service is used by DDMS to know which debuggable processes are running
    on the device/emulator.

    Note that there is no single-shot service to retrieve the list only once.

sync:
    This starts the file synchronisation service, used to implement "adb push"
    and "adb pull". Since this service is pretty complex, it will be detailed
    in a companion document named SYNC.TXT."""
        
        
class ServerBase:
    """."""
    
    pass
    
    
class HostServer(ServerBase):
    """."""
    
    pass
    
    
class LocalServer(ServerBase):
    """."""
    
    pass
        
        
if __name__ == '__main__':
    
    with HostClient() as adbc:
        #print('version: ' + str(adbc.version()))
        print('devices: ' + str(adbc.devices()))
        print('kill: ' + str(adbc.kill()))
    
