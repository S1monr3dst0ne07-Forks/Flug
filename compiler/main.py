import sys
from dataclasses import dataclass as dc
from typing import Literal

def error(line, msg):
    print(f"Error on line {line}: {msg}")
    sys.exit(1)


def tokenize(path):
    with open(path, 'r') as f:
        src = f.read()

    def get_kind(char):
        match char:
            case x if x.isdigit(): return "numb"
            case x if x.isalpha(): return "iden"
            case '_': return "iden"
            case '{': return 'co'
            case '}': return 'cc'
            case '(': return 'po'
            case ')': return 'pc'
            case ' ' | "\t" | "\n": return "format"
            case '\0': 'terminator'
            case _: return "symb"

    @dc
    class Streamer:
        tokens : list[str]
        lines  : list[int]
        index  : int

        def line(self):
            return self.lines[self.index]

        def peek(self):
            return self.tokens[self.index]
        def pop(self):
            t = self.peek()
            self.index += 1
            return t
        def has(self):
            return len(self.tokens) > self.index
        def expect(self, want):
            got = self.pop()
            if got != want:
                error(self.line(), f"Expected `{want}` but got `{got}`.")

    state = None
    buffer = ''
    stream = []
    lines  = []
    lineno = 1
    singleton = ('co', 'cc', 'po', 'pc')
    for char in src + '\0':
        kind = get_kind(char)

        if char == '\n': lineno += 1

        if (kind != state and state) or (state in singleton):
            if state != 'format':
                stream.append(buffer)
                lines.append(lineno)
            buffer = ''

        buffer += char
        state = kind

    return Streamer(stream, lines, 0)


PREC = {
    0 : ('+', '-', '*'),
    1 : ('>', '<', '>=', '<=', '==', '!='),
}


@dc
class AstCall:
    name : str
    args : list["AstExpr"]

    @classmethod
    def parse(cls, stream, name):
        stream.expect('(') #)
        args = []
        while stream.peek() != ')':
            args.append(AstExpr.parse(stream))
            if stream.peek() == ',': stream.pop()
        stream.expect(')')

        return cls(name, args)


@dc
class AstAnon:
    args : list["AstExpr"]
    body : "AstBlock"

    @classmethod
    def parse(cls, stream):
        stream.expect('(') #)
        args = []
        while stream.peek() != ')':
            args.append(AstExpr.parse(stream))
            if stream.peek() == ',': stream.pop()
        stream.expect(')')
        stream.expect('=>')

        body = AstBlock.parse(stream, curly=True)
        return cls(args, body)

@dc
class AstVar:
    name : str

@dc
class AstLit:
    value : int

class AstLeaf:
    @staticmethod
    def parse(stream):
        match stream.pop():
            case '(':
                subexpr = AstExpr.parse(stream)
                stream.expect(')')
                return subexpr

            case x if x.isdigit(): 
                return AstLit(int(x))

            case 'func':
                return AstAnon.parse(stream)

            case name if stream.peek() == '(':  #)
                return AstCall.parse(stream, name)

            case var:
                return AstVar(var)


@dc
class AstExpr:
    op : Literal['+', '-', '*', '>', '<', '>=', '<=', '==', '!=']
    left  : "AstExpr | AstLeaf"
    right : "AstExpr | AstLeaf"

    @classmethod
    def parse(cls, stream, level=1):
        left = AstExpr.parse(stream, level-1) if level else AstLeaf.parse(stream)

        if not stream.has():
            return left
        if stream.peek() not in PREC[level]:
            return left

        op = stream.pop()
        right = AstExpr.parse(stream, level)
        return cls(op, left, right)



@dc
class AstDecl:
    kind : Literal['const', 'let']
    dst : str
    src : AstExpr
    line : int

    @classmethod
    def parse(cls, stream, kind):
        line = stream.line()
        dst = stream.pop()
        stream.expect('=')
        src = AstExpr.parse(stream)
        stream.expect(';')
        return cls(kind, dst, src, line)


@dc
class AstAssign:
    dst : str
    src : AstExpr

    @classmethod
    def parse(cls, stream, dst):
        stream.expect('=')
        src = AstExpr.parse(stream)
        stream.expect(';')
        return cls(dst, src)

@dc
class AstIf:
    cond  : "AstExpr | None" #none for else block
    body  : "AstBlock"
    other : "AstIf | None"

    @classmethod
    def parse(cls, stream, final=False):
        cond = None if final else AstExpr.parse(stream)
        body = AstBlock.parse(stream, curly=True)

        word = stream.peek() if stream.has() else None
        other = None
        if word in ('elif', 'else'):
            stream.pop()
            final = word == 'else'
            other = AstIf.parse(stream, final)

        return cls(cond, body, other)


@dc
class AstStmt:
    @staticmethod
    def parse(stream):
        match stream.pop():
            case 'if'   : return AstIf.parse(stream)
            case 'while': return AstWhile.parse(stream)
            case kind if kind in ('const', 'let'): 
                return AstDecl.parse(stream, kind)
            case dst if stream.peek() == '=': 
                return AstAssign.parse(stream, dst)
            case x:
                stream.index -= 1
                return AstExpr.parse(stream)

@dc
class AstBlock:
    stmts : list["AstStmt"]

    @classmethod
    def parse(cls, stream, curly=False):
        if curly: stream.expect('{') #}

        stmts = []
        while stream.has() and stream.peek() != '}':
            stmts.append(AstStmt.parse(stream))

        if curly: stream.expect('}')
        return cls(stmts)






def main():
    stream = tokenize(sys.argv[1])
    root = AstBlock.parse(stream)
    print(root)

if __name__ == '__main__':
    main()
