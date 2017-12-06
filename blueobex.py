
import logging
import os
import os.path
from subprocess import Popen
import tempfile
import time

import pyinotify

# Logger for this module
_LOGGER = logging.getLogger(__name__)

# System commands
BLUETOOTH_CMD = ['bluetoothd', '--compat']
OBEXPUSHD_CMD = ['obexpushd', '-B', '-n']

class InotifyHandler(pyinotify.ProcessEvent):
    def my_init(self, callback):
        self.callback = callback
        
    def process_IN_CLOSE_WRITE(self, event):
        if not event.dir:
            dirname, filename = os.path.split(event.pathname)
            self.callback(dirname, filename)

class BlueObex:
    """
    Wrapper around the obexpushd program.
    Manages the subprocess and calls event handlers as appropriate.

    When debug mode is enabled obexpushd will have debug mode enabled and all output will be forwarded to
    the top console.
    """
    def __init__(self, callback):
        """
        Initialize an OBEXPush.
        :param channel: Bluetooth channel to listen on
        :param debug: enable/disable debug mode
        """
        # obexpushd subprocess
        self.process = None
        # Callback which we will call when a new file is received
        self.callback = callback
        # Boolean for if started or not
        self.started = False
        # Boolean for if we're currently running
        self.running = False
        # Temp directory
        self.directory = None
        # Services
        self.proc_blue = None
        self.proc_obex = None

    def start(self, async=True):
        """
        Start the obexpushd and watch for received files.
        Executes callback when a new file is received.
        """

        # We're only allowed to start once. If we already started then return false.
        if self.started:
            return False
        self.started = True

        # Create the temp directory
        self.directory = tempfile.TemporaryDirectory()
        _LOGGER.info('Starting in ' + self.directory.name)
        
        try:
            # Start bluetooth
            self.proc_blue = Popen(BLUETOOTH_CMD)
            # Wait for it to be ready
            time.sleep(1)
            # Now start OBEX listener
            self.proc_obex = Popen(OBEXPUSHD_CMD, cwd=self.directory.name)
            # Wait to see if it started successfully
            time.sleep(2)
            if self.proc_obex.poll():
                # If we got a non-None value, an error occured
                raise Exception('obexpushd failed')
            # Create the watch manager
            self.watch_manager = pyinotify.WatchManager()
            self.watch_manager.add_watch(self.directory.name,
                    pyinotify.IN_CLOSE_WRITE)
            # Let the system know we've started successfully
            self.running = True
                
            self.notifier = pyinotify.Notifier(self.watch_manager,
                    InotifyHandler(callback=self.callback))
            self.notifier.loop(daemonize=async)
            return True
        except KeyboardInterrupt:
            self.running = True
            self.stop()
            return True
        except BaseException as e:
            print(e)
            self.running = True
            self.stop()
            return False

    def stop(self):
        """ End the OBEXPush service. Only useful if it's being run in a separate thread/process. """
        if not self.running:
            return True
        self.running = False
        # Brutally murder the subprocess and stop stalking the directory
        if self.proc_blue:
            self.proc_blue.terminate()
        if self.proc_obex:
            self.proc_obex.terminate()
        if self.notifier:
            self.notifier.stop()
        if self.watch_manager:
            self.watch_manager.close()
        self.directory.cleanup()

def test():
    # This is the callback for OBEXPush
    def obex_callback(directory, filename):
        print('Event ' + directory + ' : ' + filename)
    # OBEX Push daemon wrapper
    obexd = BlueObex(obex_callback)
    # And start the listener
    obexd.start(async=False)

# If this is the main program, invoke main
if __name__ == '__main__':
    test()