
#TARGET=prg/hello.flug
#TARGET=../test/test_recur.flug
TARGET=../test/test_reassign.flug

run:
	python3 main.py $(TARGET)
	fasm build.asm build
	chmod +x build
	./build

