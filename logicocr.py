
import multiprocessing as mp
import re
import signal
import sys
import traceback
import threading

from PIL import Image
import pyocr
import blueobex

# List of valid file extensions
VALID_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
# Regex for Sum of Products equations. Not perfect but it gets the job done
SOP_REGEX = re.compile('[a-zA-Z:();\']+')
# Get Tesseract OCR
OCRTOOL = pyocr.get_available_tools()[0]

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

def process_ocr(context, directory, filename):
    path = os.path.join(directory, filename)
    ext = os.path.splitext(filename)[1]
    
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('output',
        help='File name parsed text will be written to')
    args = parser.parse_args(argv)
    
    # Create an executor pool with one subprocess for each CPU
    def worker_init():
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    ocr_pool = mp.Pool(processes=mp.cpu_count(), initializer=worker_init)
    # The OCR decoder uses this synchronize output
    out_context = OutputContext(args.output)
    # This is the callback for OBEXPush
    def obex_callback(directory, filename):
        print('Event ' + directory + ' : ' + filename)
        # ocr_pool.apply_async(process_ocr, (out_context, events, directory, filename))
    # OBEX Push daemon wrapper
    obexd = blueobex.BlueObex(obex_callback)
    # And start the listener
    obexd.start(async=False)
    ocr_pool.close()
    
if __name__ == '__main__':
    main(sys.argv[1:])

