# Flug Compiler
Now made with 100% more unreadable Python!

This compiler targets native x86_64 linux,
using FASM as the backend.
Make sure FASM is installed.
To compile and run a program, simply use the generic makefile:
```bash
make test_<name>
```
Here, `name` selects a test from `test/`.

Example: `make test_factorial`

# Features
All features are implemented,
aside from closures because they would require
dynamic memory management and hence
a user-heap implementation. 
(And i'm too lazy to impl that :3)

# Test Bench
This directory includes a small test banch `test.sh`
which will compile and execute test found in `test/`,
which the compiler supports. Currently the only
exempt tests are `test_closure.flug` and `test_twocounters.flug`
because they are the only ones using closures.
