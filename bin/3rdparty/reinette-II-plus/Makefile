CC = gcc
FLAGS = -std=c11 -pedantic -Wpedantic -Wall -O3

LIBS = -lSDL2
# comment these two lines if you are under Linux :
#WIN32-LIBS = -lmingw32 -lSDL2main -Wl,-subsystem,windows
#WIN32-RES = reinetteII+.res

reinetteII+: reinetteII+.c puce6502.c
	$(CC) $^ $(FLAGS) $(LIBS) -o $@

.PHONY: wasi
wasi:
	bash -l -c 'source $$HOME/emsdk/emsdk_env.sh >/dev/null 2>&1; \
		make -f Makefile.wasi wasi'

reinetteII+.res: reinetteII+.rc
	windres $^ -O coff -o $(WIN32-RES)

all: reinetteII+

clean:
	rm -f reinetteII+
	rm -f wasi.js apple2.wasm wasi.data
