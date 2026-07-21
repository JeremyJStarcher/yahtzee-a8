CC65 = /home/jjs/Projects/atari800/cc65/bin
CA65 = $(CC65)/ca65
LD65 = $(CC65)/ld65

TARGET = hello
SOURCES = hello.s

all: $(TARGET).xex

$(TARGET).o: $(SOURCES)
	$(CA65) -t atari -o $@ $<

$(TARGET).xex: $(TARGET).o
	$(LD65) -C /home/jjs/Projects/atari800/cc65/cfg/atari-asm-xex.cfg -o $@ $<

clean:
	rm -f $(TARGET).o $(TARGET).xex

.PHONY: all clean
