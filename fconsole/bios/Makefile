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
LD65_FLAGS = -C $(LINKER_CONFIG) -m $(ROM_IMAGE).map --dbgfile jjs.jjs

.PHONY: all clean vectors

all: $(LINKED_LISTING)

vectors: $(ROM_IMAGE)
	@echo "Vector table addresses:"
	@python3 -c 'import pathlib; p=pathlib.Path("bios.bin"); data=p.read_bytes(); entries=[("NMI",0xFFFA),("RESET",0xFFFC),("IRQ",0xFFFE)]; [print(f"  {n:<6} {((data[addr-0xF000+1]<<8)|data[addr-0xF000]):04X} @ {addr:04X}") for n,addr in entries if len(data) > (addr-0xF000)+1]'
	@echo ""
	@echo "Linker exports:"
	@grep -E '(^_reset_handler|^_nmi_handler|^_irq_handler|^JTCLS)' $(ROM_IMAGE).map || true

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
