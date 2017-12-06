
import multiprocessing as mp
import re
import signal
import sys

import sopvm

from PIL import Image
import pyocr

# List of valid file extensions
VALID_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
# Regex for Sum of Products equations. Not perfect but it gets the job done
SOP_REGEX = re.compile(r"[\sa-zA-Z:();'+]+")
# Get Tesseract OCR
OCRTOOL = pyocr.get_available_tools()[0]

def _worker_init():
    """ Initializer for worker threads so KeyboardInterrupt doesn't throw tons of errors. """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

class OCRHelper:
    def __init__(self, cb_worked, cb_error, pool_size=None):
        self.cb_worked = cb_worked
        self.cb_error = cb_error

        pool_size = pool_size or mp.cpu_count()
        self.pool = mp.Pool(processes=pool_size, initializer=_worker_init)
        self.lock = mp.Lock()
        
    def process(self, path):
        self.pool.apply_async(self._perform, (self, path))

    def _perform(self, path):
        ext = os.path.splitext(filename)[1]
        
        # Ignore if not an image file
        if ext not in VALID_IMAGE_EXTENSIONS:
            return

        # If it was a valid image process it
        with PyTessBaseAPI() as ocr:
            ocr.SetImageFile(path)
            text = ocr.GetUTF8Text()

            print(text)

            # Now we have to determine which line is the correct one
            found_match = False
            for line in text.split('\n'):
                match = SOP_REGEX.search(line)
                if match:
                    # Format the text and send it to the main program
                    message = None # TODO format the text
                    with self.lock:
                        self.cb_worked(message)
                    found_match = True
                    break
            # If we didn't find a match, notify the main program
            if not found_match:
                message = None # TODO format the error message
                with self.lock:
                    self.cb_error(message)
        # Delete the file once we've processed it
        os.remove(path)

    def close(self):
        with self.lock:
            self.pool.close()

def main(argv):
    # OBEX Push daemon wrapper
    obexd = blueobex.BlueObex(obex_callback)
    # And start the listener
    obexd.start(async=False)
    ocr_pool.close()
    
if __name__ == '__main__':
    main(sys.argv[1:])

