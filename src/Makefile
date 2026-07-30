
include ../venv.mk

.DEFAULT_GOAL := all

PYTHON ?= $(VENV_PY)
PROJECT_ROOT := $(abspath ..)
RUN_WASI := $(PYTHON) $(PROJECT_ROOT)/bin/run_wasi.py

CA65 = $(RUN_WASI) ca65
LD65 = $(RUN_WASI) ld65

TARGET = hello
SOURCES = hello.s

all: $(TARGET).xex
$(TARGET).o: $(SOURCES)
	$(CA65) -t atari -o $@ $<

$(TARGET).xex: $(TARGET).o
	$(LD65) -C /cc65/cfg/atari-asm-xex.cfg -o $@ $<

clean:
	rm -f $(TARGET).o $(TARGET).xex

.PHONY: all clean
