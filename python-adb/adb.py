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

r"""adb - A (almost) pure python adb module

"""

import errno
import os
import shutil
import socket
import subprocess
import time


# Constants
###############################################################################

#SERVER_HOST = socket.INADDR_LOOPBACK
SERVER_HOST = 'localhost'
SERVER_PORT = 5037

#FIXME: rather unpythonic
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_SERVER = 30

#FIXME: better desc.
HOST_ANY = 'host'
"""."""
HOST_LOCAL = 'host-local'
"""."""
HOST_SERIAL = 'host-serial'
"""."""

#FIXME: better desc.
TRANSPORT_ANY = 'transport-any'
"""One device or emulator connected to the host machine."""
TRANSPORT_LOCAL = 'transport-local'
"""One emulator connected through TCP."""
TRANSPORT_USB = 'transport-usb'
"""One device connected through USB to the host machine."""
TRANSPORT_SERIAL = 'transport'
"""One device identified by serial number."""


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


# Socket Classes
###############################################################################

class Socket(socket.socket):
    """Socket - An asocket analog."""
    
    def __init__(self, address=(SERVER_HOST, SERVER_PORT)):
        """."""
        
        #FIXME: are client sockets non-blocking?
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
    
    #FIXME
    def _status(self):
        """adb_status() analog.
        
        This is a pythonic analog to adb_client.c => adb_status() which raises
        exceptions instead of using return statuses and error messages.
        """
        try:
            status = self.recv(4)
        except BrokenPipeError:
            raise ADBError('protocol fault (no status)')
        
        # Success; return as there may be no response
        if status == b'OKAY':
            return
            
        # Failure
        elif status == b'FAIL':
            try:
                size = int(self.recv(4), 16)
            except BrokenPipeError:
                raise ADBError('protocol fault (status len)')
                
            try:
                fail_str = self.recv(size)
            except:
                raise ADBError('protocol fault (status read)')
                
            raise ADBError(fail_str)
        # Unknown status
        else:
            raise ADBError('protocol fault (status ' + str(status) + '?!)')
    
    def connect(self, address=(SERVER_HOST, SERVER_PORT)):
        """Connect the socket to an ADB server.
        
        If *start_server* is True connect() will try to start the ADB server
        and retry once.
        """
        
        try:
            socket.socket.connect(self, address)
            # FIXME: why does adb_client.c decrement VERSION_SERVER?
            if int(self.query('version'), 16) - 1 > VERSION_SERVER: # returns 0x001f (31)
                raise ADBError('adb server is out of date.  killing...')
            
        # Old server still running
        except ADBError:
            self.command('kill')
            time.sleep(2)
            
            # give the server some time to start properly and detect devices
            subprocess.check_output(['adb', 'start-server'])
            time.sleep(3)
            
            self.connect(address=address)
                
        # Server not running
        except ConnectionRefusedError:
            # give the server some time to start properly and detect devices
            subprocess.check_output(['adb', 'start-server'])
            time.sleep(3)
            
            self.connect(address=address)
            
    def recv(self, size):
        """Receive data from the socket.
        
        A convenience wrapper around socket.recv() that will retry on
        InterruptedError (EINTR) and incomplete receive.  Returns the bytes
        received on success; raises BrokenPipeError on fail."""
        
        total_received = b''
        
        while len(total_received) < size:
            try:
                received = socket.socket.recv(self, size - len(total_received))
            
                if received == b'':
                    self.close()
                    raise BrokenPipeError('connection closed')
                
                total_received += received
            except InterruptedError:
                pass
        else:
            return total_received
            
    def send(self, data):
        """Send data to the socket.
        
        A convenience wrapper around socket.send() that will retry on
        InterruptedError (EINTR) and incomplete send.  Returns the number of
        bytes sent on success and raises BrokenPipeError on fail.
        
        *data* should be a properly formatted ADB message.
        """
        total_sent = 0
        
        while total_sent < len(data):
            try:
                sent = socket.socket.send(self, data[total_sent:])
                
                if sent == 0:
                    self.close()
                    raise BrokenPipeError('disconnected')
                
                total_sent += sent
            except InterruptedError:
                pass
        else:
            return total_sent
        
    #FIXME: doc
    def command(self, service, host=HOST_ANY, serialno=None):
        """Send a formatted request to the server.

        ADB clients send requests as a 4-byte hexadecimal length followed by
        the payload.  This function is a high-level wrapper around
        ClientBase.send() which creates a complete message from *data* and
        *host* before sending.
        
        *host* should be one of the HOST_* constants described above.  If
        *host* is HOST_SERIAL *serialno* must not be None.
        """
        
        if host == HOST_SERIAL:
            service = ':'.join([host, serialno, service])
        else:
            service = ':'.join([host, data])
            
        self.send('{0:0>4x}{1}'.format(len(service), service).encode('ascii'))
            
            
            
            
#FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME#            
#FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME#            
#FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME FIXME#

class Client:
    """Client - An adb_client analog."""
    
    def __init__(self, address=(SERVER_HOST, SERVER_PORT)):
        """."""
        
        self.address = address
        #self.host = host
        #self.serialno = serialno
        self.socket = None

    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    #FIXME: doc
    def query(self, data, host=HOST_ANY, serialno=None):
        """Send a request and receive a response from the server.

        Responses from the server are in the form of a 4-byte return status,
        followed by a 4-byte hex length and finally the payload if hex length is
        greater than 0.

        If the return status is b'FAIL' ADBError will be raised accompanied by the
        error message.

        If the return status is b'OKAY' recv() will return a bytestring.
        """
        
        self.command(data=data, host=host, serialno=serialno)
        self.status()
        
        return self.recv(int(self.recv(4), 16))
            

class HostClient(Client):
    """."""
    
    def version(self):
        """Ask the ADB server for its internal version number.
        
        Returns an integer.
        """
        self.command('version')
        
        return int(self.recvmsg(), 16)
        
    #FIXME: format output
    def devices(self, long=False):
        """Ask to return the list of available Android devices and their state.
        
        Returns a byte string that will be dumped as-is by the client.
        """
        
        with Socket() as sock:
            print('connected')
            if long:
                response = sock.query('devices-l')
            else:
                response = sock.query('devices')
            
        return response
        
    def kill(self):
        """Ask the ADB server to quit immediately.
        
        This is used when the ADB client detects that an obsolete server is
        running after an upgrade.
        """
        
        self.command('kill')
        
        return self.recvmsg()
        
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
        """Inform the server an emulator has started.

        This is a special query that is sent to the ADB server when a
        new emulator starts up. <port> is a decimal number corresponding
        to the emulator's ADB control port, i.e. the TCP port that the
        emulator will forward automatically to the adbd daemon running
        in the emulator system.
        """
        
        self.send('emulator:' + str(port))
        
        return self.recv()
        
    #FIXME: figure it out, doc
    def transport(self, device=TRANSPORT_ANY, serialno=None):
        """Ask to switch the connection to the device/emulator identified by
        <serial-number>.
        
        After the OKAY response, every client request will
        be sent directly to the adbd daemon running on the device.
        (Used to implement the -s option)
        
        Ask to switch the connection to the device or emulator identified by
        *device* which should be one of the TRANSPORT_* constants or a specific
        identifier (eg. 025657124acd8d2d, emulator-5554, 192.168.0.101:5555).
        """
        pass
        
    def get_product(self, host=HOST_ANY):
        """<host-prefix>:get-product"""
        pass
        
    def get_serialno(self, host=HOST_ANY):
        """Return the serial number of the corresponding device/emulator.
    
        Note that emulator serial numbers are of the form 'emulator-5554'
        """
        pass
        
    def get_state(self, host=HOST_ANY):
        """Returns the state of a given device as a string."""
        pass
        
    #FIXME: combine the next 3 methods to be more pythonic
    def forward(self, norebind=False, host=HOST_ANY):
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
        
    def killforward(self, all=False, host=HOST_ANY):
        """<host-prefix>:killforward:<local>
        Remove any existing forward local connection from <local>.
        This is used to implement 'adb forward --remove <local>'

        <host-prefix>:killforward-all
        Remove all forward network connections.
        This is used to implement 'adb forward --remove-all'.
        """
        pass

    def list_forward(self, host=HOST_ANY):
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
        
            
class LocalClient:
    """."""
    
    #FIXME
    def __init__(self, address=(SERVER_HOST, SERVER_PORT), device=TRANSPORT_ANY):
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
        
        
if __name__ == '__main__':
    #TODO: implement a mock adb command-line compatible with the C version
    pass
    
