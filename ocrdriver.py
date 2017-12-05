
import argparse
import logging
import multiprocessing as mp
import os
import os.path
from subprocess import Popen, PIPE
import sys
import tempfile
import traceback
import threading

import inotify.adapters
from tesserocr import PyTessBaseAPI

# Logger for this module
_LOGGER = logging.getLogger(__name__)

# List of valid file extensions
VALID_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
# Regex for Sum of Products equations. Not perfect but it gets the job done
SOP_REGEX = re.compile('[a-zA-Z:();\']+')

class OBEXPush:
    """
    Wrapper around the obexpushd program.
    Manages the subprocess and calls event handlers as appropriate.

    When debug mode is enabled obexpushd will have debug mode enabled and all output will be forwarded to
    the top console.
    """

    EXE_NAME = 'obexpushd'

    def __init__(self, callback, channel=6, debug=False):
        """
        Initialize an OBEXPush.
        :param channel: Bluetooth channel to listen on
        :param debug: enable/disable debug mode
        """
        # Bluetooth channel to listen on
        self.channel = channel
        # If debug mode is enabled
        self.debug = debug
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
        # Flag that stops the service
        self.kill_flag = mp.Event()

    def start(self):
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
        _LOGGER.info('Starting ' + EXE_NAME + ' in ' + self.directory.name)
        
        command = [OBEXPush.EXE_NAME, '-C' + self.channel, '-n']
        self.process = Popen(command, cwd=self.directory.name, encoding='utf-8')
        self.running = True

        watcher = inotify.adapters.Inotify()
        watcher.add_watch(bytes(self.directory.name))

        try:
            while not self.kill_flag.is_set():
                for event in watcher.event_gen():
                    if event is not None:
                        (header, type_names, watch_path, filename) = event
                        wdir = watch_path.decode('utf-8')
                        wfile = filename.decode('utf-8')
                        _LOGGER.debug('dir = %s  file = %s' % (wdir, wfile))
                        self.callback(wdir, wfile)
            self.kill_flag.clear()
        finally:
            # Brutally murder the subprocess and stop stalking the directory
            self.process.terminate()
            self.watcher.remove_watch(self.directory.name)
            self.directory.cleanup()
            self.running = False

        # We return True if for some reason the caller wants to know that it ran successfully
        return True

    def stop(self):
        """ End the OBEXPush service. Only useful if it's being run in a separate thread/process. """
        if not self.running:
            return True
        self.kill_flag.set()

class OutputContext:
    def __init__(self, pipe):
        self.__pipe = pipe
        self.__lock = mp.Lock()
        self.__output = open(pipe, 'w')

    def __enter__(self):
        self.__lock.acquire()
        return self.__output

    def __exit__(self):
        self.__lock.release()

    def close(self):
        # Grab the lock and close the output for good
        with self as output:
            output.close()

def process_ocr(context, events, directory, filename):
    path = os.path.join(directory, filename)
    (,ext) = os.path.splitext(filename)
    
    # If it's not an image file, delete and ignore
    if ext not in VALID_IMAGE_EXTENSIONS:
        os.remove(path)
        return
    
    # If it was a valid image process it
    with PyTessBaseAPI() as ocr:
        ocr.SetImageFile(path)
        text = ocr.GetUTF8Text()

        # Now we have to determine which line is the correct one
        found_match = False
        for line in text.split('\n'):
            match = SOP_REGEX.match(line)
            if match:
                # Format the text and send it to the main program
                message = None # TODO format the text
                with context as output:
                    output.write(result)
                found_match = True
                break
        # If we didn't find a match, notify the main program
        if not found_match:
            message = None # TODO format the error message
            with context as output:
                output.write(message)
    
    # And we're done processing now so delete the image
    os.remove(path)


def main(argv):
    # Create an executor pool with one subprocess for each CPU
    ocr_pool = mp.Pool(processes=mp.cpu_count())
    # The OCR decoder uses this synchronize output
    out_context = OutputContext('ocr.txt')
    # This is the callback for OBEXPush
    def obex_callback(events, directory, filename):
        ocr_pool.apply_async(process_ocr, (out_context, events, directory, filename))

    # OBEX Push daemon wrapper
    obexd = OBEXPush(obex_callback)
    # And start the listener
    obexd.start()


# If this is the main program, invoke main
if __name__ == '__main__':
    main(sys.argv[1:])
