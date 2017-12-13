
import sys
import multiprocessing as mp

import sopvm

def valtoarray(val):
    return [str(int(x)) for x in val]

class ReplInterface:

    def __init__(self):
        self.equation = None
        self.variables = []
        self.loop = True

        self.obex = None        # BlueObex reference
        self.ocrhelper = None   # OCRHelper
        self.bt_queue = None    # Process-safe queue for transferring data from worker process to main process

    def start_ocr(self):
        """ Start OCR and Bluetooth. This is optional. """
        import sopocr
        import blueobex

        self.bt_queue = mp.Queue()
        self.ocrhelper = sopocr.OCRHelper()
        self.obex = blueobex.BlueObex(lambda path: self._obex_callback(path))

        print('Starting Bluetooth')
        self.obex.start()
        print('Bluetooth running')

    def _obex_callback(self, path):
        """ Callback for when we recieve a file over Bluetooth. """
        self.bt_queue.put_nowait(path)

    def _process_text(self, text):
        """
        Update self.equation by parsing text. Handles errors correctly.
        """
        try:
            varids = sopvm.get_variables(text)
            self.equation = sopvm.parse(text, varids)
        except sopvm.UnexpectedToken as e:
            token = e.token
            print('Error: Unexpected token %s at line %i, column %i' % (token, token.line, token.column))
        except sopvm.ParseError as e:
            print(e)

    def run(self):
        print("Welcome to the Boolean Equation Analyzer! To see all available commands, type \"help\".")
        try:
            while self.loop:
                comm = input("> ")
                command = getattr(self, 'cmd_'+comm.lower(), None)
                if command is not None:
                    command()
                else:
                    print("Sorry, that command was not found. Try typing \"help\" for a list of commands.")
        finally:
            if self.obex:
                self.obex.stop()
            
    def cmd_help(self):
        """help \t\t Prints out this lovely set of commands"""

        print("Welcome to the Boolean Equation Analyzer help page!"
              "\nThe following are the available commands: \n")

        for attribute in dir(self):
            if attribute.startswith("cmd_"):
                print(getattr(self, attribute).__doc__)

    def cmd_text(self):
        """text \t\t Allows you to enter your Boolean Equation by typing it here in the console"""
        comm = input("Please input your Boolean Equation, using only letters of the English alphabet as variables: \n")
        # input("Please input your Boolean Equation in the form \"[variables]:[equation]\" (e.g., \"xyx:x+(y'z)\"")
        self._process_text(comm)

    def cmd_image(self):
        """image \t\t Allows you to enter your Boolean Equation by transmitting an image of it to the device"""
        print("Send the image via Bluetooth.")
        path = self.bt_queue.get()
        print("Received Bluetooth file.")
        text = self.ocrhelper.process(path)
        print("Processed image as \"%s\"." % text)
        self._process_text(text)

    def cmd_solve(self):
        """solve \t\t Solves the Boolean Equation using given input values"""

        if self.equation is not None:

            row = [0 for i in range(len(self.variables))]

            print("Finding solution for equation "+str(self.equation))
            print("Please enter values of either 0 or 1 for each variable in your equation, separated by spaces.")
            for i in self.equation.inputs:
                print(i, end=" ")
            print()
            comm = input()
            # Convert list of 1s and 0s to array of bools
            inputs = [bool(int(x)) for x in comm.split()]
            val = self.equation.eval(inputs)
            print("Solution: " + " ".join(valtoarray(val)))
        else:
            print("You must enter an equation with either \"text\" or \"image\" first. ")

    def cmd_table(self):
        """table \t\t Displays a truth table of the most recently entered Boolean Equation"""
        if self.equation is not None:

            varids = self.equation.inputs
            row = [0 for i in range(len(varids))]

            for i in varids:
                print(i, end="  ")
            print(str(self.equation))

            for i in range(2**len(varids)):
                for j in range(len(varids)):
                    row[j] = int((i/(2**j))) % 2
                val = self.equation.eval(row)
                fullrow = [str(x) for x in row] + valtoarray(val)
                print("  ".join(fullrow))
            print()
        else:
            print("You must enter an equation with either \"text\" or \"image\" first. ")

    def cmd_quit(self):
        """quit \t\t Exits the program. """
        self.loop = False
        # TODO Handle anything else that needs quiting?

if __name__ == '__main__':
    test = ReplInterface()
    test.start_ocr()
    test.run()




