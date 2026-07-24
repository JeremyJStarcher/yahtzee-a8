# ca65/ca65 Build System for 6502 BIOS
# Tool paths - adjust if needed
CA65 = ca65
LD65 = ld65
DA65 = da65

# Source files
ASM_SOURCES = src/bios.asm src/vectors.asm

# Output files
ROM_IMAGE = bios.bin
OBJ_FILES = $(ASM_SOURCES:.asm=.o)
LINKED_LISTING = bios.lst

# Linker configuration
LINKER_CONFIG = bios.cfg

# Assembly flags
CA65_FLAGS = --cpu 6502 --debug-info

# Disassemble the linked image so addresses and relocations are resolved.
DA65_FLAGS = --cpu 6502 --start-addr '$$F000' --multi-pass

# Linker flags
LD65_FLAGS = -C $(LINKER_CONFIG) -m $(ROM_IMAGE).map

.PHONY: all clean

all: $(LINKED_LISTING)

# Link object files into ROM image
$(ROM_IMAGE): $(OBJ_FILES)
	@echo "Linking $@..."
	$(LD65) $(LD65_FLAGS) -o $@ $^

# Generate an address-resolved listing from the linked ROM image.
$(LINKED_LISTING): $(ROM_IMAGE)
	@echo "Disassembling $< to $@..."
	$(DA65) $(DA65_FLAGS) -o $@ $<

# Assemble source files
%.o: %.asm
	@mkdir -p $(dir $@)
	@echo "Assembling $<..."
	$(CA65) $(CA65_FLAGS) -o $@ $<

clean:
	rm -f $(ROM_IMAGE) $(ROM_IMAGE).map $(OBJ_FILES) $(LINKED_LISTING) src/*.lst
