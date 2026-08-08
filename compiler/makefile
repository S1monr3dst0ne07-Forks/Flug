
TESTS=../test

test_%:
	python3 main.py "$(TESTS)/$@.flug"
	fasm build.asm build
	chmod +x build
	./build

