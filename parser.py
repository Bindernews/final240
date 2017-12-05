
import pprint

import lark

sop_parser = lark.Lark(r'''
    out : ";"
    orr : "+"
    ?variable_id : /[a-zA-Z]/
    variable : variable_id
    prefix : variable_id+
    ?expression : variable+
                | nested
                | expression "'"  -> invert
    ?nested : "(" equation ")"
    ?equation : expression+ (orr expression+)*
    main : prefix ":" equation (out equation)*

    %import common.WS
    %ignore WS
    ''', start='main', parser='lalr')

ORD_CUT = ord('a')

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
        self.variables = set()

    def variable(self, name_):
        name, = name_
        self.variables.add(name)

    def main(self, tree_):
        lis = list(self.variables)
        lis.sort(key=lambda x: ord(x) - ORD_CUT if ord(x) >= ORD_CUT else ord(x))
        return lis

class TransCompile(lark.Transformer):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self._opid = 0

    def _next_opid(self):
        self._opid += 1
        return self._opid
        
    def orr(self, _):
        return OpOr(0)

    def out(self, _):
        return OpOut(0)

    def expression(self, children):
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
        sub = sub_[0]
        if isinstance(sub, OpAnd):
            # If it's a simple expression it's a simple NAND
            return OpNand(sub.param, self.inputs)
        else:
            # If it's an equation we need to invert POP
            sub[-1].param = True
            return sub
        
    def variable(self, name):
        return OpAnd(name[0], self.inputs)
    
    def prefix(self, variables):
        count = 0
        for varid in variables:
            self.inputs[varid[0]] = count
            count += 1
        return self.inputs

    def main(self, tree):
        """ Converts the nested lists to a single list. """
        #return [self.inputs, [str(x) for x in flatten(tree[1:])]]
        return flatten(tree[1:] + [OpOut(0)])

class ParseError(BaseException):
    pass

def _compile(text):
    """
    Compile the given text.
    Returns an array of opcodes or raises a ParseError.
    """
    try:
        opcodes = TransCompile().transform(sop_parser.parse(text))
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
    except lark.common.ParseError as e:
        raise ParseError(e)

def _test_compile():
    """ Tests for _compile() """
    TESTS = [
        "abc:ab+(b+c)'",
        "abc:ab+(c)'+c'",
        "ab:a+((b))'",
        "ab:a(a+b)",
        'ab:ab',
        "ab:ab;a+b;a'b",
    ]
    for expr in TESTS:
        print('Parsing ', expr)
        try:
            opcodes = _compile(expr)
            pprint.pprint([str(x) for x in opcodes], width=20)
        except ParseError as e:
            print(e)


class Opcode:
    def __init__(self, param):
        self.param = param

class OpAnd(Opcode):
    def __init__(self, param, inputs):
        self.param = param
        self.var = inputs[param]
    def eval(self, ctx):
        ctx.v &= ctx.input[self.var]
    def __str__(self):
        return 'AND ' + self.param
        
class OpNand(OpAnd):
    def eval(self, ctx):
        ctx.v &= not ctx.input[self.var]
    def __str__(self):
        return 'NAND ' + self.param
        
class OpPop(Opcode):
    def __init__(self, opid):
        self.opid = opid
        self.param = False
    def eval(self, ctx):
        ctx.v = (ctx.v ^ self.param) and ctx.stack.pop()
    def __str__(self):
        return 'POP ' + ('NOT ' if self.param else '')

class OpOr(Opcode):
    def eval(self, ctx):
        if ctx.v:
            ctx.pos += self.param - 1
        ctx.v = True
    def __str__(self):
        return 'OR ' + str(self.param)

class OpOut(Opcode):
    def eval(self, ctx):
        ctx.output.append(ctx.v)
        ctx.v = True
    def __str__(self):
        return 'OUT'

class OpPush(Opcode):
    def eval(self, ctx):
        ctx.stack.append(ctx.v)
        ctx.v = True
    def __str__(self):
        return 'PUSH'

class EvalContext:
    def __init__(self, inputs):
        self.v = True
        self.output = []
        self.stack = []
        self.input = inputs
        self.done = False
        self.pos = 0

class SOPCode:
    def __init__(self, opcodes):
        self._code = opcodes

    def eval(self, inputs):
        ctx = EvalContext(inputs)
        code = self._code
        codelen = len(code)
        while ctx.pos < codelen:
            code[ctx.pos].eval(ctx)
            ctx.pos += 1
        return ctx.output

def parse(text):
    opcodes = _compile(text)
    return SOPCode(opcodes)

def get_variables(text):
    try:
        return TransGetVariables().transform(sop_parser.parse(text))
    except lark.common.ParseError as e:
        raise ParseError(e)


_test_compile()
