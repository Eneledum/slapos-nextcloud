##############################################################################
#
# Copyright (c) 2018 Nexedi SA and Contributors. All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import os
import shutil
from urllib.parse import urlparse, parse_qs
import tempfile
import io
import subprocess
from http.server import BaseHTTPRequestHandler
import logging

import pysftp
import psutil
import paramiko
from paramiko.ssh_exception import SSHException
from paramiko.ssh_exception import AuthenticationException

from slapos.testing.testcase import makeModuleSetUpAndTestCaseClass
from slapos.testing.utils import findFreeTCPPort
from slapos.testing.utils import ManagedHTTPServer


setUpModule, SlapOSInstanceTestCase = makeModuleSetUpAndTestCaseClass(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'software.cfg')))


class ProFTPdTestCase(SlapOSInstanceTestCase):
  def _getConnection(self, username=None, password=None, hostname=None):
    """Returns a pysftp connection connected to the SFTP

    username and password can be specified and default to the ones from
    instance connection parameters.
    another hostname can also be passed.
    """
    # this tells paramiko not to verify host key
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None

    parameter_dict = self.computer_partition.getConnectionParameterDict()
    sftp_url = urlparse(parameter_dict['url'])

    return pysftp.Connection(
        hostname or sftp_url.hostname,
        port=sftp_url.port,
        cnopts=cnopts,
        username=username or parameter_dict['username'],
        password=password or parameter_dict['password'])


class TestSFTPListen(ProFTPdTestCase):
  def test_listen_on_ipv4(self):
    self.assertTrue(self._getConnection(hostname=self._ipv4_address))

  def test_does_not_listen_on_all_ip(self):
    with self.assertRaises(SSHException):
      self._getConnection(hostname='0.0.0.0')


class TestSFTPOperations(ProFTPdTestCase):
  """Tests upload / download features we expect in SFTP server.
  """
  def setUp(self):
    self.upload_dir = os.path.join(
        self.computer_partition_root_path, 'srv', 'proftpd')

  def tearDown(self):
    for name in os.listdir(self.upload_dir):
      path = os.path.join(self.upload_dir, name)
      if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
      else:
        shutil.rmtree(path)

  def test_simple_sftp_session(self):
    with self._getConnection() as sftp:
      # put a file
      with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write("Hello FTP !")
        f.flush()
        sftp.put(f.name, remotepath='testfile')

      # it's visible in listdir()
      self.assertEqual(['testfile'], sftp.listdir())

      # and also in the server filesystem
      self.assertEqual(['testfile'], os.listdir(self.upload_dir))

      # download the file again, it should have same content
      tempdir = tempfile.mkdtemp()
      self.addCleanup(lambda: shutil.rmtree(tempdir))
      local_file = os.path.join(tempdir, 'testfile')
      sftp.get('testfile', local_file)
      with open(local_file) as f:
        self.assertEqual(f.read(), "Hello FTP !")

  def test_uploaded_file_not_visible_until_fully_uploaded(self):
    test_self = self

    class PartialFile(io.StringIO):
      def read(self, *args):
        # file is not visible yet
        test_self.assertNotIn('destination', os.listdir(test_self.upload_dir))
        # it's just a hidden file
        test_self.assertEqual(
            ['.in.destination.'], os.listdir(test_self.upload_dir))
        return super().read(*args)

    with self._getConnection() as sftp:
      sftp.sftp_client.putfo(PartialFile("content"), "destination")

    # now file is visible
    self.assertEqual(['destination'], os.listdir(self.upload_dir))

  def test_partial_upload_are_deleted(self):
    test_self = self
    with self._getConnection() as sftp:

      class ErrorFile(io.StringIO):
        def read(self, *args):
          # at this point, file is already created on server
          test_self.assertEqual(
              ['.in.destination.'], os.listdir(test_self.upload_dir))
          # simulate a connection closed
          sftp.sftp_client.close()
          return "something that will not be sent to server"

      with self.assertRaises(IOError):
        sftp.sftp_client.putfo(ErrorFile(), "destination")
    # no half uploaded file is kept
    self.assertEqual([], os.listdir(self.upload_dir))

  def test_user_cannot_escape_home(self):
    with self._getConnection() as sftp:
      with self.assertRaises(PermissionError):
        sftp.listdir('..')
      with self.assertRaises(PermissionError):
        sftp.listdir('/')
      with self.assertRaises(PermissionError):
        sftp.listdir('/tmp/')


class TestUserManagement(ProFTPdTestCase):
  def test_user_can_be_added_from_script(self):
    with self.assertRaisesRegex(AuthenticationException,
                                 'Authentication failed'):
      self._getConnection(username='bob', password='secret')

    subprocess.check_call(
        'echo secret | %s/bin/ftpasswd --name=bob --stdin' %
        self.computer_partition_root_path,
        shell=True)
    self.assertTrue(self._getConnection(username='bob', password='secret'))


class TestBan(ProFTPdTestCase):
  def test_client_are_banned_after_5_wrong_passwords(self):
    # Simulate failed 5 login attempts
    for _ in range(5):
      with self.assertRaisesRegex(AuthenticationException,
                                  'Authentication failed'):
        self._getConnection(password='wrong')

    # after that, even with a valid password we cannot connect
    with self.assertRaisesRegex(SSHException, 'Connection reset by peer'):
      self._getConnection()

    # ban event is logged
    with open(os.path.join(self.computer_partition_root_path,
                           'var',
                           'log',
                           'proftpd-ban.log')) as ban_log_file:
      self.assertRegex(
          ban_log_file.readlines()[-1],
          'login from host .* denied due to host ban')


class TestInstanceParameterPort(ProFTPdTestCase):
  @classmethod
  def getInstanceParameterDict(cls):
    cls.free_port = findFreeTCPPort(cls._ipv4_address)
    return {'port': cls.free_port}

  def test_instance_parameter_port(self):
    parameter_dict = self.computer_partition.getConnectionParameterDict()
    sftp_url = urlparse(parameter_dict['url'])
    self.assertEqual(self.free_port, sftp_url.port)
    self.assertTrue(self._getConnection())


class TestFilesAndSocketsInInstanceDir(ProFTPdTestCase):
  """Make sure the instance only have files and socket in software dir.
  """
  def setUp(self):
    """sets `self.proftpdProcess` to `psutil.Process` for the running proftpd in the instance.
    """
    with self.slap.instance_supervisor_rpc as supervisor:
      all_process_info = supervisor.getAllProcessInfo()
    # there is only one process in this instance
    process_info, = [p for p in all_process_info if p['name'] != 'watchdog']
    process = psutil.Process(process_info['pid'])
    self.assertEqual('proftpd', process.name())  # sanity check
    self.proftpdProcess = process

  def test_only_write_file_in_instance_dir(self):
    self.assertEqual(
        [],
        [
            f for f in self.proftpdProcess.open_files() if f.mode != 'r'
            if not f.path.startswith(self.computer_partition_root_path)
        ])

  def test_only_unix_socket_in_instance_dir(self):
    self.assertEqual(
        [],
        [
            s for s in self.proftpdProcess.connections('unix')
            if not s.laddr.startswith(self.computer_partition_root_path)
        ])


class TestSSHKey(TestSFTPOperations):
  @classmethod
  def getInstanceParameterDict(cls):
    cls.ssh_key = paramiko.DSSKey.generate(1024)
    return {
        'ssh-key':
        '---- BEGIN SSH2 PUBLIC KEY ----\n{}\n---- END SSH2 PUBLIC KEY ----'.
        format(cls.ssh_key.get_base64())
    }

  def _getConnection(self, username=None):
    """Override to log in with the SSH key
    """
    parameter_dict = self.computer_partition.getConnectionParameterDict()
    sftp_url = urlparse(parameter_dict['url'])
    username = username or parameter_dict['username']

    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None

    with tempfile.NamedTemporaryFile(mode='w') as keyfile:
      self.ssh_key.write_private_key(keyfile)
      keyfile.flush()
      return pysftp.Connection(
          sftp_url.hostname,
          port=sftp_url.port,
          cnopts=cnopts,
          username=username,
          private_key=keyfile.name,
      )

  def test_authentication_failure(self):
    parameter_dict = self.computer_partition.getConnectionParameterDict()
    sftp_url = urlparse(parameter_dict['url'])

    with self.assertRaisesRegex(AuthenticationException,
                                'Authentication failed'):
      self._getConnection(username='wrong username')

    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None

    # wrong private key
    with tempfile.NamedTemporaryFile(mode='w') as keyfile:
      paramiko.DSSKey.generate(1024).write_private_key(keyfile)
      keyfile.flush()
      with self.assertRaisesRegex(AuthenticationException,
                                  'Authentication failed'):
        pysftp.Connection(
            sftp_url.hostname,
            port=sftp_url.port,
            cnopts=cnopts,
            username=parameter_dict['username'],
            private_key=keyfile.name,
        )

  def test_published_parameters(self):
    # no password is published, we only login with key
    parameter_dict = self.computer_partition.getConnectionParameterDict()
    self.assertIn('username', parameter_dict)
    self.assertNotIn('password', parameter_dict)


class TestAuthenticationURL(TestSFTPOperations):
  class AuthenticationServer(ManagedHTTPServer):
    class RequestHandler(BaseHTTPRequestHandler):
      def do_POST(self):
        # type: () -> None
        assert self.headers[
            'Content-Type'] == 'application/x-www-form-urlencoded', self.headers[
                'Content-Type']
        posted_data = dict(
            parse_qs(
                self.rfile.read(int(self.headers['Content-Length'])).decode()))
        if posted_data['login'] == ['login'] and posted_data['password'] == [
            'password'
        ]:
          self.send_response(200)
          self.send_header("X-Proftpd-Authentication-Result", "Success")
          self.end_headers()
          return self.wfile.write(b"OK")
        self.send_response(401)
        return self.wfile.write(b"Forbidden")

      log_message = logging.getLogger(__name__ + '.AuthenticationServer').info

  @classmethod
  def getInstanceParameterDict(cls):
    return {
        'authentication-url':
        cls.getManagedResource('authentication-server',
                               TestAuthenticationURL.AuthenticationServer).url
    }

  def _getConnection(self, username='login', password='password'):
    """Override to log in with the HTTP credentials by default.
    """
    return super()._getConnection(username=username, password=password)

  def test_authentication_success(self):
    with self._getConnection() as sftp:
      self.assertEqual(sftp.listdir('.'), [])

  def test_authentication_failure(self):
    with self.assertRaisesRegex(AuthenticationException,
                                'Authentication failed'):
      self._getConnection(username='login', password='wrong')

  def test_published_parameters(self):
    # no login or password are published, logins are defined by their
    # user name
    parameter_dict = self.computer_partition.getConnectionParameterDict()
    self.assertNotIn('username', parameter_dict)
    self.assertNotIn('password', parameter_dict)
