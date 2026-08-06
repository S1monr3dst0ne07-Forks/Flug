import sys
from dataclasses import dataclass as dc

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
            return len(self.tokens) > 0
        def expect(self, want):
            got = self.pop()
            if got != want:
                print(f"Error: Expected `{want}` but got `{got}`.")
                sys.exit(1)

    state = None
    buffer = ''
    stream = []
    singleton = ('co', 'cc', 'po', 'pc')
    for char in src:
        kind = get_kind(char)

        if (kind != state and state) or (state in singleton):
            if state != 'format':
                stream.append(buffer)
            buffer = ''

        buffer += char
        state = kind

    return Streamer(stream, 0)







def main():
    stream = tokenize(sys.argv[1])
    print(stream)

if __name__ == '__main__':
    main()
