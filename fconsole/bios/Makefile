# ca65/ca65 Build System for 6502 BIOS
# Tool paths - adjust if needed
CA65 = ../../../cc65/bin/ca65
LD65 = ../../../cc65/bin/ld65

# Source files
ASM_SOURCES = src/bios.asm src/vectors.asm

# Output files
ROM_IMAGE = bios.bin
OBJ_FILES = $(ASM_SOURCES:.asm=.o)

# Linker configuration
LINKER_CONFIG = bios.cfg

# Assembly flags
CA65_FLAGS = --cpu 6502 --debug-info

# Linker flags
LD65_FLAGS = -C $(LINKER_CONFIG) -m $(ROM_IMAGE).map

.PHONY: all clean

all: $(ROM_IMAGE)

# Link object files into ROM image
$(ROM_IMAGE): $(OBJ_FILES)
	@echo "Linking $@..."
	$(LD65) $(LD65_FLAGS) -o $@ $^

# Assemble source files
%.o: %.asm
	@mkdir -p $(dir $@)
	@echo "Assembling $<..."
	$(CA65) $(CA65_FLAGS) -o $@ $<

clean:
	rm -f $(ROM_IMAGE) $(ROM_IMAGE).map $(OBJ_FILES)