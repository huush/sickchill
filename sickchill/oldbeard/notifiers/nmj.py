import re
import telnetlib
import urllib.parse
import urllib.request
from xml.etree import ElementTree

from sickchill import logger, settings


class Notifier(object):
    @staticmethod
    def notify_settings(host):
        """
        Retrieves the settings from a NMJ/Popcorn hour

        host: The hostname/IP of the Popcorn Hour server

        Returns: True if the settings were retrieved successfully, False otherwise
        """

        # establish a terminal session to the PC
        try:
            terminal = telnetlib.Telnet(host)
        except Exception:
            logger.warning(f"Warning: unable to get a telnet session to {host}")
            return False

        # tell the terminal to output the necessary info to the screen so we can search it later
        logger.debug(f"Connected to {host} via telnet")
        terminal.read_until("sh-3.00# ")
        terminal.write("cat /tmp/source\n")
        terminal.write("cat /tmp/netshare\n")
        terminal.write("exit\n")
        tnoutput = terminal.read_all()

        match = re.search(r"(.+\.db)\r\n?(.+)(?=sh-3.00# cat /tmp/netshare)", tnoutput)

        # if we found the database in the terminal output then save that database to the config
        if match:
            database = match.group(1)
            device = match.group(2)
            logger.debug(f"Found NMJ database {database} on device {device}")
            settings.NMJ_DATABASE = database
        else:
            logger.warning(f"Could not get current NMJ database on {host}, NMJ is probably not running!")
            return False

        # if the device is a remote host then try to parse the mounting URL and save it to the config
        if device.startswith("NETWORK_SHARE/"):
            match = re.search(f".*(?=\r\n?{(re.escape(device[14:]))})", tnoutput)

            if match:
                mount = match.group().replace("127.0.0.1", host)
                logger.debug(f"Found mounting url on the Popcorn Hour in configuration: {mount}")
                settings.NMJ_MOUNT = mount
            else:
                logger.warning("Detected a network share on the Popcorn Hour, but could not get the mounting url")
                return False

        return True

    @staticmethod
    def notify_snatch(ep_name):
        return False
        # Not implemented: Start the scanner when snatched does not make any sense

    def notify_download(self, ep_name):
        if settings.USE_NMJ:
            self._notifyNMJ()

    def notify_subtitle_download(self, ep_name, lang):
        if settings.USE_NMJ:
            self._notifyNMJ()

    @staticmethod
    def notify_git_update(new_version):
        return False
        # Not implemented, no reason to start scanner.

    @staticmethod
    def notify_login(ipaddress=""):
        return False

    def test_notify(self, host, database, mount):
        return self._sendNMJ(host, database, mount)

    @staticmethod
    def _sendNMJ(host, database, mount=None):
        """
        Sends a NMJ update command to the specified machine

        host: The hostname/IP to send the request to (no port)
        database: The database to send the request to
        mount: The mount URL to use (optional)

        Returns: True if the request succeeded, False otherwise
        """

        # if a mount URL is provided then attempt to open a handle to that URL
        if mount:
            try:
                req = urllib.request.Request(mount)
                logger.debug(f"Try to mount network drive via url: {mount}")
                handle = urllib.request.urlopen(req)
            except IOError as e:
                if hasattr(e, "reason"):
                    logger.warning(f"NMJ: Could not contact Popcorn Hour on host {host}: {e.reason}")
                elif hasattr(e, "code"):
                    logger.warning(f"NMJ: Problem with Popcorn Hour on host {host}: {e.code}")
                return False
            except Exception as e:
                logger.exception("NMJ: Unknown exception: " + str(e))
                return False

        # build up the request URL and parameters
        params = {"arg0": "scanner_start", "arg1": database, "arg2": "background", "arg3": ""}
        params = urllib.parse.urlencode(params)
        updateUrl = f"http://{host}:8008/metadata_database?{params}"

        # send the request to the server
        try:
            req = urllib.request.Request(updateUrl)
            logger.debug(f"Sending NMJ scan update command via url: {updateUrl}")
            handle = urllib.request.urlopen(req)
            response = handle.read()
        except IOError as e:
            if hasattr(e, "reason"):
                logger.warning(f"NMJ: Could not contact Popcorn Hour on host {host}: {e.reason}")
            elif hasattr(e, "code"):
                logger.warning(f"NMJ: Problem with Popcorn Hour on host {host}: {e.code}")
            return False
        except Exception as e:
            logger.exception("NMJ: Unknown exception: " + str(e))
            return False

        # try to parse the resulting XML
        try:
            et = ElementTree.fromstring(response)
            result = et.findtext("returnValue")
        except SyntaxError as e:
            logger.exception(f"Unable to parse XML returned from the Popcorn Hour: {e}")
            return False

        # if the result was a number then consider that an error
        if int(result) > 0:
            logger.exception(f"Popcorn Hour returned an error code: {result}")
            return False
        else:
            logger.info("NMJ started background scan")
            return True

    def _notifyNMJ(self, host=None, database=None, mount=None, force=False):
        """
        Sends a NMJ update command based on the SB config settings

        host: The host to send the command to (optional, defaults to the host in the config)
        database: The database to use (optional, defaults to the database in the config)
        mount: The mount URL (optional, defaults to the mount URL in the config)
        force: If True then the notification will be sent even if NMJ is disabled in the config
        """
        if not settings.USE_NMJ and not force:
            logger.debug("Notification for NMJ scan update not enabled, skipping this notification")
            return False

        # fill in omitted parameters
        if not host:
            host = settings.NMJ_HOST
        if not database:
            database = settings.NMJ_DATABASE
        if not mount:
            mount = settings.NMJ_MOUNT

        logger.debug("Sending scan command for NMJ ")

        return self._sendNMJ(host, database, mount)
