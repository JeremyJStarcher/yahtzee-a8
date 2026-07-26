# ca65 Build System for 6502 BIOS

# Tool paths
CA65 = ca65
LD65 = ld65
DA65 = da65
PYTHON = python3
FMT = $(PYTHON) ../../dev-tools/fmt6502.py

# Source files
ASM_SOURCES = src/bios.asm src/vectors.asm
ASM_INCLUDES = src/branches.inc src/math.inc
FORMAT_SOURCES = $(ASM_SOURCES) $(ASM_INCLUDES)

# Output files
ROM_IMAGE = bios.bin
OBJ_FILES = $(ASM_SOURCES:.asm=.o)
LINKED_LISTING = bios.lst

# Linker configuration
LINKER_CONFIG = bios.cfg

# Assembly flags
CA65_FLAGS = --cpu 6502 --debug-info

# Formatter settings
FMT_FLAGS = \
	--strict \
	--indent-size 4 \
	--comment-indent 40 \
	--min-comment-gap 2

# Disassemble the linked image so addresses and relocations are resolved.
DA65_FLAGS = --cpu 6502 --start-addr '$$F000' --multi-pass

# Linker flags
LD65_FLAGS = -C $(LINKER_CONFIG) -m $(ROM_IMAGE).map


.PHONY: all clean format format-check format-diff vectors


all: $(LINKED_LISTING)


# Rewrite source files atomically.
#
# All related files are passed in one invocation so the formatter can match
# macro definitions with macro calls across file boundaries.
format:
	@echo "Formatting assembly sources..."
	$(FMT) $(FMT_FLAGS) --in-place $(FORMAT_SOURCES)
	@echo "Formatting complete."


# Report files that require formatting.
#
# fmt6502 exits with status 1 when changes are required, making this suitable
# for CI, pre-commit hooks, and validation builds.
format-check:
	@echo "Checking assembly source formatting..."
	$(FMT) $(FMT_FLAGS) --check $(FORMAT_SOURCES)


# Display the proposed changes without modifying any files.
format-diff:
	@echo "Assembly formatting differences:"
	$(FMT) $(FMT_FLAGS) --diff $(FORMAT_SOURCES)


vectors: $(ROM_IMAGE)
	@echo "Vector table addresses:"
	@$(PYTHON) -c 'import pathlib; p=pathlib.Path("bios.bin"); data=p.read_bytes(); entries=[("NMI",0xFFFA),("RESET",0xFFFC),("IRQ",0xFFFE)]; [print(f"  {n:<6} {((data[addr-0xF000+1]<<8)|data[addr-0xF000]):04X} @ {addr:04X}") for n,addr in entries if len(data) > (addr-0xF000)+1]'
	@echo ""
	@echo "Linker exports:"
	@grep -E '(^_reset_handler|^_nmi_handler|^_irq_handler|^JTCLS)' $(ROM_IMAGE).map || true


# Link object files into ROM image.
$(ROM_IMAGE): $(OBJ_FILES) $(LINKER_CONFIG)
	@echo "Linking $@..."
	$(LD65) $(LD65_FLAGS) -o $@ $(OBJ_FILES)


# Generate an address-resolved listing from the linked ROM image.
$(LINKED_LISTING): $(ROM_IMAGE)
	@echo "Disassembling $< to $@..."
	$(DA65) $(DA65_FLAGS) -o $@ $<


# Assemble source files.
%.o: %.asm
	@mkdir -p $(dir $@)
	@echo "Assembling $<..."
	$(CA65) $(CA65_FLAGS) -o $@ $<


# Include-file dependencies.
#
# bios.asm includes these files, so changing either one must rebuild bios.o.
src/bios.o: src/branches.inc src/math.inc


clean:
	rm -f $(ROM_IMAGE) $(ROM_IMAGE).map \
		$(OBJ_FILES) $(LINKED_LISTING) src/*.lst