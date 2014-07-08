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

# Copyright 2014 Andrew Holmes <andrew.g.r.holmes@gmail.com>

"""Common code for ADB and Fastboot.

Common usb browsing, and usb communication.
"""
import logging
import threading
import weakref

import libusb1
import usb1

import usb_exceptions

DEFAULT_TIMEOUT_MS = 1000

_LOG = logging.getLogger('android_usb')


def GetInterface(setting):
    """Get the class, subclass, and protocol for the given USB setting."""
    return (setting.getClass(), setting.getSubClass(), setting.getProtocol())


def InterfaceMatcher(clazz, subclass, protocol):
    """Returns a matcher that returns the setting with the given interface."""
    interface = (clazz, subclass, protocol)
    
    def Matcher(device):
        for setting in device.iterSettings():
            if GetInterface(setting) == interface:
                return setting
                
        return Matcher
  
  
class TCPHandle(socket.socket):
    """TCP communication object. Not thread-safe.
    
    Handles reading and writing over USB with the proper endpoints, exceptions,
    and interface claiming.

    Important methods:
        FlushBuffers()
        BulkRead(int length)
        BulkWrite(bytes data)
    """
    
    def __init__(self, address=(SERVER_HOST, SERVER_PORT)):
        """."""
        
        #FIXME: are client sockets non-blocking?
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
    
    #FIXME
    def _status(self):
        """adb_status() analog.
        
        The server should answer a request with one of the following:

            1. For success, the 4-byte "OKAY" string

            2. For failure, the 4-byte "FAIL" string, followed by a
               4-byte hex length, followed by a string giving the reason
               for failure.

            3. As a special exception, for 'host:version', a 4-byte
               hex string corresponding to the server's internal version number

        Note that the connection is still alive after an OKAY, which allows the
        client to make other requests. But in certain cases, an OKAY will even
        change the state of the connection. 
        
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
        InterruptedError (EINTR) and incomplete receive.
        
        Returns:
            bytes object of bytes received
            
        Raises:
            BrokenPipeError on fail.
        """
        
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
        InterruptedError (EINTR) and incomplete send.
        
        Returns:
            Number of bytes sent
        
        Raises:
            BrokenPipeError: Raised if socket.send() returns 0.
        
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


class UsbHandle(object):
  """USB communication object. Not thread-safe.

  Handles reading and writing over USB with the proper endpoints, exceptions,
  and interface claiming.

  Important methods:
    FlushBuffers()
    BulkRead(int length)
    BulkWrite(bytes data)
  """

  _HANDLE_CACHE = weakref.WeakValueDictionary()
  _HANDLE_CACHE_LOCK = threading.Lock()

  def __init__(self, device, setting, usb_info=None, timeout_ms=None):
    """Initialize USB Handle.

    Arguments:
      device: libusb_device to connect to.
      setting: libusb setting with the correct endpoints to communicate with.
      usb_info: String describing the usb path/serial/device, for debugging.
      timeout_ms: Timeout in milliseconds for all I/O.
    """
    self._setting = setting
    self._device = device
    self._handle = None

    self._usb_info = usb_info or ''
    self._timeout_ms = timeout_ms or DEFAULT_TIMEOUT_MS

  @property
  def usb_info(self):
    try:
      sn = self.serial_number
    except libusb1.USBError:
      sn = ''
    if sn and sn != self._usb_info:
      return '%s %s' % (self._usb_info, sn)
    return self._usb_info

  def Open(self):
    """Opens the USB device for this setting, and claims the interface."""
    # Make sure we close any previous handle open to this usb device.
    port_path = tuple(self.port_path)
    with self._HANDLE_CACHE_LOCK:
      old_handle = self._HANDLE_CACHE.get(port_path)
      if old_handle is not None:
        old_handle.Close()

    self._read_endpoint = None
    self._write_endpoint = None

    for endpoint in self._setting.iterEndpoints():
      address = endpoint.getAddress()
      if address & libusb1.USB_ENDPOINT_DIR_MASK:
        self._read_endpoint = address
        self._max_read_packet_len = endpoint.getMaxPacketSize()
      else:
        self._write_endpoint = address

    assert self._read_endpoint is not None
    assert self._write_endpoint is not None

    handle = self._device.open()
    iface_number = self._setting.getNumber()
    try:
      if handle.kernelDriverActive(iface_number):
        handle.detachKernelDriver(iface_number)
    except libusb1.USBError as e:
      if e.value == libusb1.LIBUSB_ERROR_NOT_FOUND:
        _LOG.warning('Kernel driver not found for interface: %s.', iface_number)
      else:
        raise
    handle.claimInterface(iface_number)
    self._handle = handle
    self._interface_number = iface_number

    with self._HANDLE_CACHE_LOCK:
      self._HANDLE_CACHE[port_path] = self
    # When this object is deleted, make sure it's closed.
    weakref.ref(self, self.Close)

  @property
  def serial_number(self):
    return self._device.getSerialNumber()

  @property
  def port_path(self):
    return [self._device.getBusNumber()] + self._device.getPortNumberList()

  def Close(self):
    if self._handle is None:
      return
    try:
      self._handle.releaseInterface(self._interface_number)
      self._handle.close()
    except libusb1.USBError:
      _LOG.info('USBError while closing handle %s: ',
                self.usb_info, exc_info=True)
    finally:
      self._handle = None

  def Timeout(self, timeout_ms):
    return timeout_ms if timeout_ms is not None else self._timeout_ms

  def FlushBuffers(self):
    while True:
      try:
        self.BulkRead(self._max_read_packet_len, timeout_ms=10)
      except usb_exceptions.ReadFailedError as e:
        if e.usb_error.value == libusb1.LIBUSB_ERROR_TIMEOUT:
          break
        raise

  def BulkWrite(self, data, timeout_ms=None):
    if self._handle is None:
      raise usb_exceptions.WriteFailedError(
          'This handle has been closed, probably due to another being opened.',
          None)
    try:
      return self._handle.bulkWrite(
          self._write_endpoint, data, timeout=self.Timeout(timeout_ms))
    except libusb1.USBError as e:
      raise usb_exceptions.WriteFailedError(
          'Could not send data to %s (timeout %sms)' % (
              self.usb_info, self.Timeout(timeout_ms)), e)

  def BulkRead(self, length, timeout_ms=None):
    if self._handle is None:
      raise usb_exceptions.ReadFailedError(
          'This handle has been closed, probably due to another being opened.',
          None)
    try:
      return self._handle.bulkRead(
          self._read_endpoint, length, timeout=self.Timeout(timeout_ms))
    except libusb1.USBError as e:
      raise usb_exceptions.ReadFailedError(
          'Could not receive data from %s (timeout %sms)' % (
              self.usb_info, self.Timeout(timeout_ms)), e)

  def PortPathMatcher(cls, port_path):
    """Returns a device matcher for the given port path."""
    if isinstance(port_path, basestring):
      # Convert from sysfs path to port_path.
      port_path = [int(part) for part in SYSFS_PORT_SPLIT_RE.split(port_path)]
    return lambda device: device.port_path == port_path

  @classmethod
  def SerialMatcher(cls, serial):
    """Returns a device matcher for the given serial."""
    return lambda device: device.serial_number == serial

  @classmethod
  def FindAndOpen(cls, setting_matcher,
                  port_path=None, serial=None, timeout_ms=None):
    dev = cls.Find(
        setting_matcher, port_path=port_path, serial=serial,
        timeout_ms=timeout_ms)
    dev.Open()
    dev.FlushBuffers()
    return dev

  @classmethod
  def Find(cls, setting_matcher, port_path=None, serial=None, timeout_ms=None):
    """Gets the first device that matches according to the keyword args."""
    if port_path:
      device_matcher = cls.PortPathMatcher(port_path)
      usb_info = port_path
    elif serial:
      device_matcher = cls.SerialMatcher(serial)
      usb_info = serial
    else:
      device_matcher = None
      usb_info = 'first'
    return cls.FindFirst(setting_matcher, device_matcher,
                         usb_info=usb_info, timeout_ms=timeout_ms)

  @classmethod
  def FindFirst(cls, setting_matcher, device_matcher=None, **kwargs):
    """Find and return the first matching device.

    Args:
      setting_matcher: See cls.FindDevices.
      device_matcher: See cls.FindDevices.
      **kwargs: See cls.FindDevices.

    Returns:
      An instance of UsbHandle.

    Raises:
      DeviceNotFoundError: Raised if the device is not available.
    """
    try:
      return next(cls.FindDevices(
          setting_matcher, device_matcher=device_matcher, **kwargs))
    except StopIteration:
      raise usb_exceptions.DeviceNotFoundError(
          'No device available, or it is in the wrong configuration.')

  @classmethod
  def FindDevices(cls, setting_matcher, device_matcher=None,
                  usb_info='', timeout_ms=None):
    """Find and yield the devices that match.

    Args:
      setting_matcher: Function that returns the setting to use given a
        usb1.USBDevice, or None if the device doesn't have a valid setting.
      device_matcher: Function that returns True if the given UsbHandle is
        valid. None to match any device.
      usb_info: Info string describing device(s).
      timeout_ms: Default timeout of commands in milliseconds.

    Yields:
      UsbHandle instances
    """
    ctx = usb1.USBContext()
    for device in ctx.getDeviceList(skip_on_error=True):
      setting = setting_matcher(device)
      if setting is None:
        continue

      handle = cls(device, setting, usb_info=usb_info, timeout_ms=timeout_ms)
      if device_matcher is None or device_matcher(handle):
        yield handle
