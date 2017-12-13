
import pprint
import re

import lark
from lark.common import ParseError, UnexpectedToken

sop_parser = lark.Lark(r'''
    out : ";"
    orr : "+"
    ?variable_id : /[a-zA-Z]/
    variable : variable_id
    prefix : variable_id+
    ?expression : variable
                | "(" equation ")"
                | expression "'"  -> invert
    ?equation : expression+ (orr expression+)*
    main : prefix? ":" equation (out equation)*

    %import common.WS
    %ignore WS
    ''', start='main', parser='lalr')

# Matches any illegal character
INV_TOKEN_REGEX = re.compile(r"[^\sa-zA-Z()+;':]")

ORD_CUT = ord('a')

# We declare this here so that clients can import sopvm.<whatever>
ParseError = ParseError
UnexpectedToken = UnexpectedToken

def flatten(lis):
    out = []
    for item in lis:
        if type(item) is list:
            out.extend(flatten(item))
        else:
            out.append(item)
    return out

class TransGetVariables(lark.Transformer):
    """
    Transformer which gets a list of variables.
    """
    def __init__(self):
        super().__init__()
        self._variables = set()
        self._prefix = None

    def variable(self, name_):
        name, = name_
        self._variables.add(name)

    def prefix(self, variables):
        self._prefix = ''.join([x[0] for x in variables])
        return self._prefix

    def main(self, tree_):
        if self._prefix:
            # Return the user-defined prefix
            return self._prefix
        else:
            # Return a list of variables sorted according to a logical sorting order
            lis = list(self._variables)
            lis.sort(key=lambda x: ord(x) - ORD_CUT if ord(x) >= ORD_CUT else ord(x))
            return ''.join(lis)

class TransCompile(lark.Transformer):
    """ Transformer that generates a list of Opcode objects from a lark.Tree """
    def __init__(self, inputs=None):
        """
        Initialize a 
        :param inputs: user-supplied prefix string (optional)
        """
        super().__init__()
        self.inputs = {}
        self._opid = 0
        self._has_prefix = False

        if inputs:
            self._process_prefix(inputs)

    def _next_opid(self):
        """
        Generate a unique Opcode ID for this program.
        Used when we need unique Opcode IDs, mostly for specifying where an OP_OR is going to jump to.
        """
        self._opid += 1
        return self._opid

    def _process_prefix(self, variables):
        """ Process a string of variables into the inputs variables """
        count = 0
        for varid in variables:
            self.inputs[varid] = count
            count += 1
        return self.inputs
        
    def orr(self, _):
        """ OP_OR """
        return OpOr(0)

    def out(self, _):
        """ OP_OUT """
        return OpOut(0)

    def expression(self, children):
        """ Transform an expression """
        return children

    def equation(self, children):
        """
        Transform an equation into opcodes, also fill in OP_OR params.
        """
        # Fill in OP_OR to jump to this OP_POP
        oppop = OpPop(self._next_opid())
        for i in range(len(children)):
            op = children[i]
            if isinstance(op, OpOr):
                op.param = oppop.opid
        return [OpPush(0)] + children + [oppop]
    
    def invert(self, sub_):
        """ NOT the previous expression. """
        sub = sub_[0]
        if isinstance(sub, OpAnd):
            # If it's a simple expression it's a simple NAND
            return OpNand(sub.param, self.inputs)
        else:
            # If it's an equation we need to invert POP
            sub[-1].param = True
            return sub
        
    def variable(self, name):
        """ Convert a variable to an Opcode """
        return OpAnd(name[0], self.inputs)
    
    def prefix(self, variables):
        """ Handle the prefix if present. """
        # Collect a series of tokens into a string
        varids = [x[0] for x in variables]
        self._has_prefix = True
        return self._process_prefix(varids)

    def main(self, tree):
        """ Converts the nested lists to a single list. """
        # Remove the prefix if it wasn't implied
        if self._has_prefix:
            tree = tree[1:]
        return flatten(tree + [OpOut(0)])

def _compile(text, inputs=None):
    """
    Compile the given text, returns an array of opcodes or raises a ParseError.
    :param text: Text to compile, if no prefix is supplied, inputs must be supplied
    :param inputs: replacement for "prefix" if prefix is not part of "text"
    """
    # The text MUST contain a :
    if ':' not in text:
        text = ':' + text
    tree = sop_parser.parse(text)
    opcodes = TransCompile(inputs).transform(tree)
    # We've got an array of opcodes, we just need to fill in OP_OR jumps
    jumplist = {}
    for i in range(len(opcodes) - 1, 0, -1):
        op = opcodes[i]
        if isinstance(op, OpPop):
            jumplist[op.opid] = i
        elif isinstance(op, OpOr):
            # Fill in the jump value from the jumplist
            op.param = jumplist[op.param] - i
    return opcodes

def _test_compile():
    """ Tests for _compile() """
    TESTS = [
        "abc:ab+(b+c)'",
        "abc:ab+(c)'+c'",
        "ab:a+((b))'",
        "ab:a(a+b)",
        "ab:ab",
        "ab:ab;a+b;a'b",
        ("ab'+a'b", "ab"),
    ]
    for expr in TESTS:
        print('Parsing ', expr)
        try:
            if isinstance(expr, str):
                opcodes = _compile(expr)
            else:
                opcodes = _compile(expr[0], expr[1])
            pprint.pprint([str(x) for x in opcodes], width=20)
        except ParseError as e:
            print(e)


#########################################################################################
# These Op* classes basically implement the VM. The interpreter calls the eval() method
# for each Opcode in the list, and that's how it all works.
#########################################################################################

class Opcode:
    """ Base Opcode class. """
    def __init__(self, param):
        self.param = param

class OpAnd(Opcode):
    """ AND the current value with the param. """
    def __init__(self, param, inputs):
        self.param = param
        self.var = inputs[param]
    def eval(self, ctx):
        ctx.v &= ctx.input[self.var]
    def __str__(self):
        return 'AND ' + self.param
        
class OpNand(OpAnd):
    """ NAND the current value with the param. """
    def eval(self, ctx):
        ctx.v &= not ctx.input[self.var]
    def __str__(self):
        return 'NAND ' + self.param
        
class OpPop(Opcode):
    """ POP a value from the stack and AND (if !param) or NAND (if param) with the current value. """
    def __init__(self, opid):
        self.opid = opid
        self.param = False
    def eval(self, ctx):
        # ctx.v XOR self.param = NAND if param, AND if !param
        ctx.v = (ctx.v ^ self.param) and ctx.stack.pop()
    def __str__(self):
        return 'POP ' + ('NOT ' if self.param else '')

class OpOr(Opcode):
    """ If the current value is True, short-circuit. """
    def eval(self, ctx):
        if ctx.v:
            # change the interpreter position
            ctx.pos += self.param - 1
        ctx.v = True
    def __str__(self):
        return 'OR ' + str(self.param)

class OpOut(Opcode):
    """ Write the current value to the next output slot. """
    def eval(self, ctx):
        ctx.output.append(ctx.v)
        ctx.v = True
    def __str__(self):
        return 'OUT'

class OpPush(Opcode):
    """ Push the current value on to the stack. """
    def eval(self, ctx):
        ctx.stack.append(ctx.v)
        ctx.v = True
    def __str__(self):
        return 'PUSH'

class EvalContext:
    """ Interpreter context. """
    def __init__(self, inputs):
        self.v = True           # Current evaluated value
        self.output = []        # List of outputs, usually only 1
        self.stack = []         # Stack (see PUSH and POP)
        self.input = inputs     # list of input values (booleans)
        self.done = False       # Is the interpreter done?
        self.pos = 0            # Position in Opcode list

class SOPCode:
    def __init__(self, opcodes, inputs, text=""):
        self._code = opcodes
        self.text = text
        self.inputs = inputs

    def eval(self, inputs):
        """
        Evaluate this equation with the given inputs.
        :param inputs: list of bools
        """
        ctx = EvalContext(inputs)
        code = self._code
        codelen = len(code)
        while ctx.pos < codelen:
            code[ctx.pos].eval(ctx)
            ctx.pos += 1
        return ctx.output

    def __str__(self):
        return self.text

def token_check(text):
    """ Throw a parse error if an invalid token is in text. """
    bad_match = INV_TOKEN_REGEX.search(text)
    if bad_match:
        raise ParseError('Invalid token \'%s\' at index %i' % (bad_match[0], bad_match.start(0)))

def parse(text, inputs=None):
    """
    Compile the given text, returns a SOPCode or raises a ParseError
    :param text: Text to compile, if no prefix is supplied, inputs must be supplied
    :param inputs: replacement for "prefix" if prefix is not part of "text", may be None
    """
    token_check(text)
    opcodes = _compile(text, inputs)
    inputs = get_variables(text)
    return SOPCode(opcodes, inputs, text)

def get_variables(text):
    """
    Returns a string of the names of the variables the equation uses in order.
    :param text: Equation string to extract variables from.
    :throws ParseError: if text is not a valid equation
    """
    token_check(text)
    try:
        # We don't need a real prefix, but it does need to exist
        if ":" not in text:
            text = ':' + text
        return TransGetVariables().transform(sop_parser.parse(text))
    except lark.common.ParseError as e:
        raise e

if __name__ == '__main__':
    _test_compile()
