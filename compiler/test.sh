#!/usr/bin/bash

all=1

run()
{
    local name=$1
    local output=$2

    local path="../test/test_$name.flug"

    local res=$(mktemp)
    local ref=$(mktemp)
    echo "$output" > $ref

    python3 main.py $path > $res && {
        fasm build.asm build > /dev/null
        chmod +x build
        ./build > $res
    }

    if diff $res $ref > /dev/null; then
        echo "$path: passed"
    else
        all=0
        echo "$path: failed"
        diff $res $ref
    fi
}



run "const" "141"
run "const2" "Error: Trying to assign into constant: \`x\`"
run "const3" "Error: Trying to assign into constant: \`b\`"
run "elif" "1"
run "factorial" "141"
run "func" "3"
run "let" "5"
run "let_return" "40"
run "reassign" "10"
run "recur" "0"
run "sum" "4"
run "subtract" "5"
run "while" "$(cat << EOF
1
1
2
3
5
8
13
21
34
55
89
0
EOF
)"


if [[ $all == 1 ]]; then
    echo "All tests passed!"
fi


