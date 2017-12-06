
import multiprocessing as mp
import re
import os
import signal
import sys

import sopvm

from PIL import Image
import pyocr
import pyocr.builders

# List of valid file extensions
VALID_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
# Regex for Sum of Products equations. Not perfect but it gets the job done
SOP_REGEX = re.compile(r"[\sa-zA-Z:();'+]+")
# Get Tesseract OCR
OCR_TOOL = pyocr.get_available_tools()[0]
OCR_LANG = 'eng' # equ, osd, eng

def _worker_init():
    """ Initializer for worker threads so KeyboardInterrupt doesn't throw tons of errors. """
    #signal.signal(signal.SIGINT, signal.SIG_IGN)
    pass

class OCRHelper:
    def __init__(self):
        pass
        
    def process(self, path):
        ext = os.path.splitext(path)[1]

        print("Processing file " + path)
        
        # Ignore if not an image file
        if ext not in VALID_IMAGE_EXTENSIONS:
            self.cb_error('Not an image')
            return

        # If it was a valid image process it
        text = OCR_TOOL.image_to_string(
            Image.open(path),
            lang=OCR_LANG,
            builder=pyocr.builders.TextBuilder()
        )
        text = text.replace("’", "'")
        return text

def main(argv):
    helper = OCRHelper()
    print(helper.process(argv[0]))
    
if __name__ == '__main__':
    main(sys.argv[1:])

