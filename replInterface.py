
import sys

import sopvm
# import sopocr
# import blueobex

class ReplInterface:

    def __init__(self):
        self.equation = None
        self.variables = []
        self.loop = True

    def run(self):
        print("Welcome to the Boolean Equation Analyzer! To see all available commands, type \"help\".")
        while self.loop:
            comm = input("> ")
            command = getattr(self, 'cmd_'+comm.lower(), None)
            if command is not None:
                command()
            else:
                print("Sorry, that command was not found. Try typing \"help\" for a list of commands.")

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
        try:
            varids = sopvm.get_variables(comm)
            self.equation = sopvm.parse(comm, varids)
        except sopvm.UnexpectedToken as e:
            token = e.token
            print('Error: Unexpected token %s at line %i, column %i' % (token, token.line, token.column))
        except sopvm.ParseError as e:
            print(e)

    # TODO this
    def cmd_image(self):
        """image \t\t Allows you to enter your Boolean Equation by transmitting an image of it to the device"""
        print("Drew, how do interface with image thing?? How do??")
        self.equation = None
        self.variables = []

    def cmd_solve(self):
        """solve \t\t Solves the Boolean Equation using given input values"""

        if self.equation is not None:

            row = [0 for i in range(len(self.variables))]

            print("Finding solution for equation "+self.equation)
            print("Please enter values of either 0 or 1 for each variable in your equation, separated by spaces.")
            for i in self.variables:
                print(i, end=" ")
            print()
            comm = input()

            row = comm.split()

            # TODO Get val from analyzer, using row
            val = self.equation.eval(row)

            print("Solution: " + str(val))
        else:
            print("You must enter an equation with either \"text\" or \"image\" first. ")

    def cmd_table(self):
        """table \t\t Displays a truth table of the most recently entered Boolean Equation"""
        if self.equation is not None:

            row = [0 for i in range(len(self.variables))]

            for i in self.variables:
                print(i, end="\t")
            print(self.equation)

            for i in range(2**len(self.variables)):

                for j in range(len(self.variables)):
                    row[j] = int((i/(2**j))) % 2
                    print(row[j], end="\t")

                # TODO Get val from analyzer, using row
                val = 1
                print(val)
            print()
        else:
            print("You must enter an equation with either \"text\" or \"image\" first. ")

    def cmd_quit(self):
        """quit \t\t Exits the program. """
        self.loop = False
        # TODO Handle anything else that needs quiting?

if __name__ == '__main__':
    test = ReplInterface()
    test.run()




