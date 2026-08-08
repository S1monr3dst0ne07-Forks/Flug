import sys
from dataclasses import dataclass as dc
from dataclasses import field
from typing import Literal
import copy

def error(msg):
    print(f"Error: {msg}")
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
        index  : int

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
                error(f"Expected `{want}` but got `{got}`.")

    state = None
    buffer = ''
    stream = []
    singleton = ('co', 'cc', 'po', 'pc')
    for char in src + '\0':
        kind = get_kind(char)

        if (kind != state and state) or (state in singleton):
            if state != 'format':
                stream.append(buffer)
            buffer = ''

        buffer += char
        state = kind

    return Streamer(stream, 0)


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

    def declare(self, ctx):
        for arg in self.args:
            arg.declare(ctx)

    def compile(self, ctx):
        ctx.env.save(ctx)

        regs = ABI[:len(self.args)]
        for arg in self.args:
            arg.compile(ctx)
            ctx.emit("push rax")
        for reg in regs:
            ctx.emit(f"pop {reg}")

        if self.name not in ('outn'):
            vaddr = ctx.lookup(self.name)
            ctx.emit(f"call qword [vars + {vaddr}]")
        else:
            ctx.emit(f"call {self.name}")

        ctx.env.restore(ctx)


ABI = ['rax', 'rsi', 'rdi', 'rdx']

@dc
class AstAnon:
    args  : list[str]
    const : set[str]
    body  : "AstBlock"

    env = None

    @classmethod
    def parse(cls, stream):
        stream.expect('(') #)
        args = []
        const = []
        while stream.peek() != ')':
            if stream.peek() == 'const':
                stream.pop()
                const.append(stream.peek())

            args.append(stream.pop())
            if stream.peek() == ',': stream.pop()
        stream.expect(')')
        stream.expect('=>')

        body = AstBlock.parse(stream, curly=True)
        return cls(args, const, body)

    def declare(self, ctx):
        self.env = ctx.enter()
        for arg in self.args:
            const = arg in self.const
            ctx.declare(arg, const)
        self.body.declare(ctx)
        ctx.leave()

    def compile(self, ctx):
        skip_label = ctx.fresh()
        func_label = ctx.fresh()

        ctx.enter(self.env)
        ctx.emit(f"jmp {skip_label}")
        ctx.emit(f"{func_label}:")

        #load parameters
        for i, arg in enumerate(self.args):
            vaddr = ctx.lookup(arg)
            ctx.emit(f"mov [vars + {vaddr}], {ABI[i]}")

        self.body.compile(ctx)
        ctx.emit("ret")
        ctx.emit(f"{skip_label}:")
        ctx.emit(f"mov rax, qword {func_label}")

        ctx.leave()


@dc
class AstVar:
    name : str

    def declare(self, ctx): pass

    def compile(self, ctx):
        addr = ctx.lookup(self.name)
        ctx.emit(f"mov rax, [vars + {addr}]")

@dc
class AstLit:
    value : int

    def declare(self, ctx): pass

    def compile(self, ctx):
        ctx.emit(f"mov rax, {self.value}")

class AstLeaf:
    @staticmethod
    def parse(stream):
        match stream.pop():
            case 'true':  return AstLit(1)
            case 'false': return AstLit(0)

            case '(':
                subexpr = AstExpr.parse(stream)
                stream.expect(')')
                return subexpr

            case x if x.isdigit(): 
                return AstLit(int(x))

            case 'func':
                return AstAnon.parse(stream)

            case name if stream.has() and stream.peek() == '(':  #)
                return AstCall.parse(stream, name)

            case var:
                return AstVar(var)


@dc
class AstExpr:
    op : Literal['+', '-', '*', '>', '<', '>=', '<=', '==', '!=']
    left  : "AstExpr | AstLeaf"
    right : "AstExpr | AstLeaf"

    def declare(self, ctx): pass

    @classmethod
    def parse_lower(cls, stream, level):
        if not level:
            return AstLeaf.parse(stream)

        return cls.parse(stream, level-1)

    @classmethod
    def parse(cls, stream, level=1):
        node = cls.parse_lower(stream, level)

        while stream.has() and stream.peek() in PREC[level]:
            op = stream.pop()
            right = cls.parse_lower(stream, level)
            node = cls(op, node, right)

        return node


    def compile(self, ctx):
        self.right.compile(ctx)
        ctx.emit("push rax")
        self.left.compile(ctx)
        ctx.emit("pop rbx")

        match self.op:
            case '+': ctx.emit("add rax, rbx")
            case '-': ctx.emit("sub rax, rbx")
            case '*': ctx.emit("mul rbx")
            case '==' | '<' | '>' | '!=' | '<=' | '>=': 
                ctx.emit("cmp rax, rbx")
                match self.op:
                    case '==': ctx.emit("sete cl")
                    case '!=': ctx.emit("setne cl")
                    case '<':  ctx.emit("setb cl")
                    case '>':  ctx.emit("seta cl")
                    case '<=': ctx.emit("setbe cl")
                    case '>=': ctx.emit("setae cl")
                ctx.emit("movzx rax, cl")



@dc
class AstDecl:
    kind : Literal['const', 'let']
    dst : str
    src : AstExpr

    @classmethod
    def parse(cls, stream, kind):
        dst = stream.pop()
        stream.expect('=')
        src = AstExpr.parse(stream)
        return cls(kind, dst, src)

    def declare(self, ctx):
        self.src.declare(ctx)
        ctx.declare(self.dst, const=(self.kind=='const'))

    def compile(self, ctx):
        vaddr = ctx.lookup(self.dst)
        self.src.compile(ctx)
        ctx.emit(f"mov [vars + {vaddr}], rax")
        


@dc
class AstAssign:
    dst : str
    src : AstExpr

    @classmethod
    def parse(cls, stream, dst):
        stream.expect('=')
        src = AstExpr.parse(stream)
        return cls(dst, src)

    def declare(self, ctx):
        self.src.declare(ctx)

    def compile(self, ctx):
        vaddr = ctx.lookup(self.dst, check_write=True)
        self.src.compile(ctx)
        ctx.emit(f"mov [vars + {vaddr}], rax")

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

    def declare(self, ctx):
        self.body.declare(ctx)
        if self.other: 
            self.other.declare(ctx)

    def compile(self, ctx):
        skip_label = ctx.fresh()
        done_label = ctx.fresh()

        if self.cond:
            self.cond.compile(ctx)
            ctx.emit("cmp rax, 0")
            ctx.emit(f"je {skip_label}")
        self.body.compile(ctx)
        ctx.emit(f"jmp {done_label}")
        ctx.emit(f"{skip_label}:")

        if self.other:
            self.other.compile(ctx)

        ctx.emit(f"{done_label}:")

@dc
class AstWhile:
    cond : AstExpr
    body : "AstBlock"

    @classmethod
    def parse(cls, stream):
        stream.expect('(')
        cond = AstExpr.parse(stream)
        stream.expect(')')
        body = AstBlock.parse(stream, curly=True)
        return cls(cond, body)

    def declare(self, ctx):
        self.body.declare(ctx)

    def compile(self, ctx):
        loop_label = ctx.fresh()
        done_label = ctx.fresh()

        ctx.emit(f"{loop_label}:")
        self.cond.compile(ctx)
        ctx.emit("cmp rax, 0")
        ctx.emit(f"je {done_label}")
        self.body.compile(ctx)
        ctx.emit(f"jmp {loop_label}")
        ctx.emit(f"{done_label}:")



@dc
class AstStmt:
    @staticmethod
    def parse(stream):
        match stream.pop():
            case 'if'   : return AstIf.parse(stream)
            case 'while': return AstWhile.parse(stream)
            case kind if kind in ('const', 'let'): 
                return AstDecl.parse(stream, kind)
            case dst if stream.has() and stream.peek() == '=': 
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

            if stream.has() and stream.peek() == ';': 
                stream.pop()
            else: break

        if curly: stream.expect('}')
        return cls(stmts)

    def declare(self, ctx):
        for stmt in self.stmts:
            stmt.declare(ctx)

    def compile(self, ctx):
        for stmt in self.stmts:
            stmt.compile(ctx)



def vaddr_to_addr(vaddr):
    return vaddr * 8

@dc
class Ctx:
    output : list[str] = field(default_factory=lambda: [])
    index : int = 0

    @dc
    class Var:
        name  : str
        const : bool
        vaddr : int | None = None

    @dc
    # LISP-like recursively 
    # layered environments.
    class Env:
        hyper : "Env" = None
        sub   : list["Env"]      = field(default_factory=lambda: [])
        var   : dict[str, "Var"] = field(default_factory=lambda: {})

        # depth into local variable stack.
        # used to do env save/restore.
        depth : int = None

        def alloc(self, index=0):
            # allocate on this layer
            for var in self.var.values():
                var.vaddr = index
                index += 1

            # gauge current depth
            self.depth = index

            # go down into lower layers
            for sub in self.sub:
                sub.alloc(index)

        def save(self, ctx):
            for i in range(self.depth):
                vaddr = vaddr_to_addr(i)
                ctx.emit(f"push qword [vars + {vaddr}]")
        def restore(self, ctx):
            for i in range(self.depth):
                vaddr = vaddr_to_addr(self.depth - (i + 1))
                ctx.emit(f"pop qword [vars + {vaddr}]")

        def lookup(self, name):
            if name not in self.var:
                if self.hyper is None:
                    error(f"Variable lookup for `{name}` failed.")

                # recursive ascend up though the layers.
                # *insert inception reference here*
                return self.hyper.lookup(name)

            return self.var[name]


    env : Env = field(default_factory=lambda: Ctx.Env())

    def alloc(self):
        self.env.alloc()

    def enter(self, sub=None):
        if not sub:
            sub = self.Env(hyper=self.env)
        self.env.sub.append(sub)
        self.env = sub 
        return sub

    def leave(self):
        self.env = self.env.hyper

    def lookup(self, name, check_write=False):
        var = self.env.lookup(name)
        if check_write and var.const:
            error(f"Trying to assign into constant: `{name}`")
        return vaddr_to_addr(var.vaddr)

    def declare(self, name, const):
        self.env.var[name] = self.Var(name, const, None)

    def fresh(self):
        out = f"__fresh_{self.index}"
        self.index += 1
        return out

    def emit(self, x):
        self.output.append(x)


def header(ctx):
    ctx.emit("format ELF64 executable")
    ctx.emit("segment readable executable")
    ctx.emit("entry _start")
    ctx.emit("""
outn:
    cmp rax, 0
    je outn_zero
    mov rsi, 10             ; divisor = 10
    mov rdi, 4095           ; digit index
outn_loop:
    xor rdx, rdx            ; clear high register
    div rsi                 ; extract digit
    add dl, 48              ; convert to ascii
    mov [buf + rdi], dl     ; save digit
    dec rdi

    cmp rax, 0
    jne outn_loop           ; check loop exit
    inc rdi

    mov rdx, 4096           ; compute length
    sub rdx, rdi
    inc rdx

outn_zero_inject:
    lea rsi, byte [rdi+buf] ; buf = buffer + index
    mov rdi, 1              ; fd = stdout
    mov rax, 1              ; sys_write
    syscall

    xor rax, rax            ; make sure return value is zero
    ret

outn_zero:
    mov rdi, 0
    mov [buf+0], byte '0'
    mov [buf+1], byte 10
    mov rdx, 2
    jmp outn_zero_inject
             """)

    ctx.emit("_start:")
    ctx.emit("call main")
    ctx.emit("call outn")
    ctx.emit("mov rax, 60")
    ctx.emit("mov rdi, 0")
    ctx.emit("syscall")
    ctx.emit("main:")

def footer(ctx):
    ctx.emit("ret")
    ctx.emit("segment readable writable")
    ctx.emit("vars: rq 100")
    ctx.emit("buf : rb 4096 \n db 10")

def main():
    stream = tokenize(sys.argv[1])
    root = AstBlock.parse(stream)
    ctx = Ctx()

    header(ctx)
    root.declare(ctx)
    ctx.alloc()
    root.compile(ctx)
    footer(ctx)


    with open('build.asm', 'w') as f:
        f.write('\n'.join(ctx.output))

if __name__ == '__main__':
    main()
