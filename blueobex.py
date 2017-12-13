
import logging
import os
import os.path
from subprocess import Popen
import multiprocessing as mp
import tempfile
import time

import pyinotify

# Logger for this module
_LOGGER = logging.getLogger(__name__)

# System command to start obexpushd
OBEXPUSHD_CMD = ['obexpushd', '-B' '-I']

class InotifyHandler(pyinotify.ProcessEvent):
    def my_init(self, callback):
        self.callback = callback
        
    def process_IN_CLOSE_WRITE(self, event):
        #print('Received CLOSE_WRITE')
        if not event.dir:
            self.callback(event.pathname)

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
        self.proc_obex = None
        self.proc_notify = None

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
        self.directory = tempfile.TemporaryDirectory(dir='.')
        _LOGGER.info('Starting in ' + self.directory.name)
        
        try:
            # Now start OBEX listener
            self.proc_obex = Popen(OBEXPUSHD_CMD, cwd=self.directory.name)
            # Wait to see if it started successfully
            time.sleep(2)
            if self.proc_obex.poll():
                # If we got a non-None value, an error occured
                raise Exception('obexpushd failed to start')
            # Create the watch manager
            self.watch_manager = pyinotify.WatchManager()
            self.watch_manager.add_watch(self.directory.name,
                    pyinotify.IN_CLOSE_WRITE)
            # Let the system know we've started successfully
            self.running = True
            self.notifier = pyinotify.Notifier(self.watch_manager,
                    InotifyHandler(callback=self.callback))
            if async:
                self.proc_notify = mp.Process(target=lambda: self.notifier.loop())
                self.proc_notify.start()
            else:
                self.notifier.loop(daemonize=False)
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
        # Kill subprocess and stop stalking the directory
        if self.notifier:
            self.notifier.stop()
        if self.proc_obex:
            self.proc_obex.terminate()
        if self.proc_notify:
            self.proc_notify.terminate()
        if self.watch_manager:
            pass  # self.watch_manager.close()  # Apparently terminating proc_notify closes this already. 
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
