#!/usr/bin/env python3

"""
ATASCII Screen Layout Generator for Yahtzee Scorecard
Generates .BYTE tables and label lookup structures for assembly.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

OUTPUT_DIRECTORY = Path("./generated")

ROM_ASM_FILE_NAME = OUTPUT_DIRECTORY / "strings.m65"
RAM_ASM_FILE_NAME = OUTPUT_DIRECTORY / "ram.m65"

# The actual screen width of the Atari.  We handle margins ourselves.
SCREEN_WIDTH = 40
NUMBER_OF_PIPS = 7

ASCII_FILL_CHARACTER = "="

ATASCII_ESCAPE = "␛"
ATASCII_REQUIRES_ESCAPE = ["␛", "↑", "↓", "←", "→", "🢰", "◀", "▶"]

# fmt: off

ATASCII = [
    "♥","├","🮇","┘","┤","┐","╱","╲","◢","▗","◣","▝","▘","🮂","▂","▖",
    "♣","┌","─","┼","•","▄","▎","┬","┴","▌","└","␛","↑","↓","←","→",
    " ","!",'"',"#","$","%","&","'","(",")","*","+",",","-",".","/",
    "0","1","2","3","4","5","6","7","8","9",":",";","<","=",">","?",
    "@","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O",
    "P","Q","R","S","T","U","V","W","X","Y","Z","[","\\","]","^","_",
    "♦","a","b","c","d","e","f","g","h","i","j","k","l","m","n","o",
    "p","q","r","s","t","u","v","w","x","y","z","♠","|","🢰","◀","▶",
]
# fmt: on

HIGHLIGHT_KEY_MARKER = "~"

SCREEN_PLACE_HOLDER = "▂"

ATASCII_MAP = {char: idx for idx, char in enumerate(ATASCII)}


@dataclass
class DiePip:
    """Represents a single pip position on a die."""

    screen_row: int = -1
    screen_col: int = -1


@dataclass
class ScreenElement:
    """
    Base class for any element positioned on screen.

    Provides common fields shared by all positioned elements like labels,
    scores, and dice containers.
    """

    key: str
    screen_row: int = -1
    screen_col: int = -1
    length: int = 0
    asm_bytes: list[str] = field(default_factory=list)
    keyboard_code: int = -1


class TextProcessingMixin:
    """
    Mixin providing unicode text processing functionality.

    Handles highlight key position extraction, unicode filtering, and conversion
    to ATASCII assembly bytes. This eliminates duplication between
    LabelText and DieContainer classes.
    """

    def _process_text(self, unicode: str) -> tuple[str, list[int], list[str], int]:
        """
        Process unicode text to filter markers and convert to ATASCII bytes.

        Args:
            unicode: Input string that may contain HIGHLIGHT_KEY_MARKER characters

        Returns:
            Tuple of (filtered_text, highlight_key_positions, asm_bytes, length)
        """
        filtered_text, highlight_key_positions = find_highlight_idx_in_unicode(unicode)
        asm_bytes = unicode_to_atari_hex2(filtered_text, highlight_key_positions)
        length = len(asm_bytes)

        return filtered_text, highlight_key_positions, asm_bytes, length

    def _initialize_from_text(self, unicode: str) -> None:
        """
        Initialize instance variables from unicode text.

        Processes the text to extract highlight_key_positions and generate assembly bytes,
        then sets all relevant instance attributes. Subclasses can call this
        in their __post_init__ to avoid code duplication.

        Args:
            unicode: Input string that may contain HIGHLIGHT_KEY_MARKER characters
        """
        filtered_text, highlight_key_positions, asm_bytes, length = self._process_text(
            unicode
        )

        # Set common attributes - subclasses may override specific ones after calling this
        self.highlight_key_positions = highlight_key_positions
        self.unicode = filtered_text

        self.asm_bytes = asm_bytes
        self.length = length


@dataclass
class GameValue(ScreenElement):
    """Represents a game value display area on screen (scores, totals, etc.)."""

    default_value: int = 0xFFFF

    # Inherits all fields from ScreenElement:
    # - key
    # - screen_row
    # - screen_col
    # - length
    # - asm_bytes


@dataclass
class LabelText(ScreenElement, TextProcessingMixin):
    """
    Represents a text label with position on screen.

    Extends ScreenElement with unicode text content and automatic
    processing into ATASCII assembly bytes.
    """

    unicode: str = ""
    linked_to: str | None = None
    highlight_key_positions: list[int] = field(default_factory=list)

    def __post_init__(self):
        """Process the unicode text to extract highlight_key_positions and generate assembly bytes."""
        self._initialize_from_text(self.unicode)


@dataclass
class DieContainer(ScreenElement, TextProcessingMixin):
    """
    Represents a die display container with pips and optional label.

    Extends ScreenElement with pip positioning data for rendering
    dice faces, plus optional unicode text for labeling.
    """

    unicode: str = ""
    pips: list[DiePip] = field(default_factory=list)
    pip_fill_asm_bytes: list[str] = field(default_factory=list)
    pip_empty_asm_bytes: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Process the unicode text to extract highlight_key_idx and generate assembly bytes."""
        self._initialize_from_text(self.unicode)


@dataclass
class TextCollection:
    """Container for all text elements on screen."""

    screen_labels: list[LabelText] = field(default_factory=list)
    game_values: list[GameValue] = field(default_factory=list)
    die_container: list[DieContainer] = field(default_factory=list)
    label_replacement_text: list[LabelText] = field(default_factory=list)
    screen_frame: LabelText | None = None


@dataclass
class LabelPosition:
    """Represents a label's position on screen with its name, row, and column."""

    name: str
    screen_row: int
    screen_col: int
    template_length: int


class LabelExtractor:
    """Extracts labels from Unicode art and returns their positions."""

    # Match #NAME or #NAME#### (label name followed by optional # padding)
    LABEL_PATTERN = re.compile(r"#(\w+)(#*)")

    def __init__(self, atari_unicode_art_lines: list[str]):
        self.atari_unicode_art_lines = atari_unicode_art_lines

    def extract_labels(self) -> list[LabelPosition]:
        """
        Extract all labels from the Unicode art lines.

        Returns a list of LabelPosition objects containing name, row, column,
        and template_length (the total width from first # to last #).
        """
        labels = []

        for row_idx, line in enumerate(self.atari_unicode_art_lines):
            for match in self.LABEL_PATTERN.finditer(line):
                label_name = match.group(1)
                col_idx = match.start()

                # Calculate template length: 1 (for leading #) + len(name) + len(padding)
                padding = match.group(2)
                template_length = 1 + len(label_name) + len(padding)

                labels.append(
                    LabelPosition(
                        name=label_name,
                        screen_row=row_idx,
                        screen_col=col_idx,
                        template_length=template_length,
                    )
                )

        return labels


def get_screen_unicode_art() -> list[str]:
    lines = [
        " ┌────────────┤!FIVE DICE!├───────────┐ ",
        " |#L1C####### #S1C |#L3K####### #S3K  | ",
        " |#L2C####### #S2C |#L4K####### #S4K  | ",
        " |#L3C####### #S3C |#LFH####### #SFH  | ",
        " |#L4C####### #S4C |#LSS####### #SSS  | ",
        " |#L5C####### #S5C |#LLS####### #SLS  | ",
        " |#L6C####### #S6C |#L5K####### #S5K  | ",
        " |#LTS####### #STS |#LCH####### #SCH  | ",
        " |#LTB####### #STB |#L5B####### #S5B  | ",
        " |#LUT####### #SUT |#LLT####### #SLT  | ",
        " ├───────────────┬─┴──────────────────┤ ",
        " |#LROL      #RCT| #GTT         #SGT  | ",
        " └───────────────┴────────────────────┘ ",
        "   #DIE0  #DIE1  #DIE2  #DIE3  #DIE4    ",
        "                                        ",
        "                                        ",
        "                                        ",
        "                                        ",
        "                                        ",
        " ────────────────────────────────────── ",
        " #INSTR################################ ",
        "                                        ",
        "                                        ",
        " ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂",
    ]

    return lines


def replace_template(orig_text: str, _new_text: str, idx: int, template_length: int):
    a = list(orig_text)
    # t = list(new_text)

    # length = min(len(new_text), len(orig_text))

    # for i in range(length):
    #     if i + idx >= len(orig_text):
    #         break
    #     a[i + idx] = t[i]
    #     a[i + idx] = "."

    for i in range(template_length):
        a[i + idx] = ASCII_FILL_CHARACTER

    return "".join(a)


def center_string(unicode: str, width: int) -> str:
    """
    Calculate the number of spaces needed on the left and right to center a string.

    Args:
        unicode: Input string that may contain special markers
        width: The total widthof the field
    Returns:
        The sting centered.
    """
    filtered_unicode = filter_special_markers_from_unicode(unicode)
    text_length = len(filtered_unicode)

    total_padding = width - text_length

    if total_padding <= 0:
        return unicode

    left_spaces = total_padding // 2
    right_spaces = total_padding - left_spaces

    return (" " * left_spaces) + unicode + (" " * right_spaces)


def get_label_text() -> TextCollection:
    """Define all labels with their display text."""

    text_collection = TextCollection()

    def add_it(it: LabelText | GameValue | DieContainer):
        if isinstance(it, LabelText):
            if it.linked_to is None:
                text_collection.screen_labels.append(it)
            else:
                text_collection.label_replacement_text.append(it)
        elif isinstance(it, GameValue):
            text_collection.game_values.append(it)
        elif isinstance(it, DieContainer):
            text_collection.die_container.append(it)
        else:
            raise ValueError(f"Unknown label type: {type(it)}")

    # Left column labels
    add_it(LabelText(key="L1C", unicode="~A~c~e~s"))  # Left column labels
    add_it(GameValue(key="S1C", default_value=11))
    add_it(LabelText(key="L2C", unicode="T~wos"))
    add_it(GameValue(key="S2C", default_value=12))
    add_it(LabelText(key="L3C", unicode="Threes"))
    add_it(GameValue(key="S3C", default_value=13))
    add_it(LabelText(key="L4C", unicode="Fours"))
    add_it(GameValue(key="S4C", default_value=14))
    add_it(LabelText(key="L5C", unicode="Fives"))
    add_it(GameValue(key="S5C", default_value=15))
    add_it(LabelText(key="L6C", unicode="Sixes"))
    add_it(GameValue(key="S6C", default_value=111))
    add_it(LabelText(key="LTS", unicode="Top Score"))
    add_it(GameValue(key="STS", default_value=113))
    add_it(LabelText(key="LTB", unicode="Upper Bonus"))
    add_it(GameValue(key="STB", default_value=1134))
    add_it(LabelText(key="LUT", unicode="Upper Total"))
    add_it(GameValue(key="SUT", default_value=113))

    # Right column labels
    add_it(LabelText(key="L3K", unicode="3 of a Kind"))
    add_it(GameValue(key="S3K", default_value=143))
    add_it(LabelText(key="L4K", unicode="4 of a Kind"))
    add_it(GameValue(key="S4K", default_value=11))
    add_it(LabelText(key="LFH", unicode="Full House"))
    add_it(GameValue(key="SFH", default_value=11))
    add_it(LabelText(key="LSS", unicode="S Straight"))
    add_it(GameValue(key="SSS", default_value=11))
    add_it(LabelText(key="LLS", unicode="L Straight"))
    add_it(GameValue(key="SLS", default_value=11))
    add_it(LabelText(key="L5K", unicode="5 of a Kind"))
    add_it(GameValue(key="S5K", default_value=11))
    add_it(LabelText(key="LCH", unicode="Chance"))
    add_it(GameValue(key="SCH", default_value=11))
    add_it(LabelText(key="L5B", unicode="5K Bonus"))
    add_it(GameValue(key="S5B", default_value=11))
    add_it(LabelText(key="LLT", unicode="Lower Total"))
    add_it(GameValue(key="SLT", default_value=11))

    # Bottom labels
    add_it(LabelText(key="GTT", unicode="Grand Total"))
    add_it(GameValue(key="SGT", default_value=9999))

    add_it(LabelText(key="LROL", unicode="Roll #"))
    add_it(GameValue(key="RCT", default_value=11))

    add_it(DieContainer(key="DIE0", unicode="  ~1  "))
    add_it(DieContainer(key="DIE1", unicode="  ~2  "))
    add_it(DieContainer(key="DIE2", unicode="  ~3  "))
    add_it(DieContainer(key="DIE3", unicode="  ~4  "))
    add_it(DieContainer(key="DIE4", unicode="  ~5  "))

    instr_label_width = 38

    l1 = center_string("", instr_label_width)
    add_it(LabelText(key="INSTR", unicode=l1))
    l1 = center_string("~Roll or ~Score", instr_label_width)
    add_it(LabelText(key="INSTR_OR_SCORE", unicode=l1, linked_to="INSTR"))
    l2 = center_string("Start ~New Game", instr_label_width)
    add_it(LabelText(key="INSTR_START", unicode=l2, linked_to="INSTR"))

    return text_collection


def add_dice_boxes(die: DieContainer, unicode_art: str) -> str:

    small_die = [
        "┌───┐",
        "|0 1|",
        "|234|",
        "|5 6|",
        "└───┘",
    ]

    this_die = small_die
    header_offset = 1

    pips_digits = [str(i) for i in range(NUMBER_OF_PIPS)]

    for _d in pips_digits:
        die.pips.append(DiePip())

    for li, line in enumerate(this_die):
        for ci, c in enumerate(line):
            row = li + die.screen_row + header_offset
            col = ci + die.screen_col

            display = c
            if c in pips_digits:
                die.pips[int(c)] = DiePip(screen_col=col, screen_row=row)
                display = ASCII_FILL_CHARACTER

            pos = (row * SCREEN_WIDTH) + col
            unicode_art = unicode_art[:pos] + display + unicode_art[pos + 1 :]
    return unicode_art


def get_screen_frame() -> TextCollection:
    unicode_art_lines = get_screen_unicode_art()

    ex = LabelExtractor(atari_unicode_art_lines=unicode_art_lines)
    label_collection = ex.extract_labels()
    label_text_info = get_label_text()

    combined_list = (
        label_text_info.screen_labels
        + label_text_info.game_values
        + label_text_info.die_container
    )

    for _li, label in enumerate(label_collection):
        record = next((z for z in combined_list if z.key == label.name), None)

        if record is None:
            raise ValueError(f"Unknown screen placeholder #{label.name}")

        if record:
            record.screen_col = label.screen_col
            record.screen_row = label.screen_row

        for ai, txt in enumerate(unicode_art_lines):
            if label.screen_row == ai:
                replacement: str = SCREEN_PLACE_HOLDER * (len(record.key) + 1)

                if isinstance(record, (LabelText, DieContainer)):
                    replacement = record.unicode

                unicode_art_lines[ai] = replace_template(
                    txt, replacement, label.screen_col, label.template_length
                )

    for record in combined_list:
        if record.screen_row < 0 or record.screen_col < 0:
            raise ValueError(f"{record.key} was defined but never placed")

    atari_unicode_art = "".join(unicode_art_lines)

    for die in label_text_info.die_container:
        atari_unicode_art = add_dice_boxes(die, atari_unicode_art)

    label = LabelText(key="MAIN", unicode=atari_unicode_art)
    label.screen_col = 0
    label.screen_row = 0

    ret: TextCollection = TextCollection(
        screen_frame=label,
        screen_labels=label_text_info.screen_labels,
        game_values=label_text_info.game_values,
        die_container=label_text_info.die_container,
        label_replacement_text=label_text_info.label_replacement_text,
    )

    return ret


def byte_as_hex(byte: int) -> str:
    if byte > 255 or byte < 0:
        raise ValueError(f"byte_as_hex '{byte}' is out of range")

    return f"${byte:02X}"


def filter_special_markers_from_unicode(unicode: str) -> str:
    # Filter out HIGHLIGHT_KEY_MARKER characters from the text
    filtered_text = "".join(char for char in unicode if char != HIGHLIGHT_KEY_MARKER)
    return filtered_text


def find_highlight_idx_in_unicode(unicode: str) -> tuple[str, list[int]]:
    """
    Filter HIGHLIGHT_KEY_MARKER (~) characters from the text and return their positions.

    Args:
        unicode: Input string containing zero or more HIGHLIGHT_KEY_MARKER characters

    Returns:
        Tuple of (filtered_string, highlight_key_positions)
        - filtered_string: The input with HIGHLIGHT_KEY_MARKER removed
        - highlight_key_positions: List of indices in the filtered string where
                                   HIGHLIGHT_KEY_MARKER was found (adjusted to account
                                   for removed markers), empty list if none found
    """
    # Find and record all HIGHLIGHT_KEY_MARKER positions
    raw_positions = [
        i for i, char in enumerate(unicode) if char == HIGHLIGHT_KEY_MARKER
    ]

    # Adjust positions to account for removed markers
    # Since we're removing N markers before position P, the adjusted position is P - count_of_markers_before_P
    highlight_key_positions = []
    marker_count = 0
    current_raw_idx = 0

    for pos in raw_positions:
        # Count markers between last position and this one
        while current_raw_idx < pos:
            if unicode[current_raw_idx] != HIGHLIGHT_KEY_MARKER:
                marker_count += 1
            current_raw_idx += 1
        # Add adjusted position (position minus number of non-marker chars seen so far)
        highlight_key_positions.append(marker_count)
        current_raw_idx += 1  # Skip the marker itself

    # Filter out HIGHLIGHT_KEY_MARKER characters from the text
    filtered_text = filter_special_markers_from_unicode(unicode)

    return filtered_text, highlight_key_positions


def unicode_to_atari_hex2(
    unicode: str, highlight_key_positions: list[int]
) -> list[str]:
    """Convert UNICODE string to ATASCII hex bytes, setting high bit on highlighted chars."""
    result = []
    highlight_set = set(highlight_key_positions)  # for fast membership test

    for idx, char in enumerate(unicode):
        if char not in ATASCII_MAP:
            raise ValueError(f"Character '{char}' is not ATASCII")

        modifier = 0x80 if idx in highlight_set else 0x00

        if char in ATASCII_REQUIRES_ESCAPE:
            result.append(byte_as_hex(ATASCII_MAP[ATASCII_ESCAPE]))

        result.append(byte_as_hex(ATASCII_MAP[char] + modifier))

    return result


def create_ram_region(prefix: str, labels: list[GameValue]) -> list[str]:
    header = []
    footer = []

    header.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
    header.append(f"START_REGION_{prefix}")

    lsb_name = "_VALUE_LSB_"
    msb_name = "_VALUE_MSB_"

    value_lsb = [f"{prefix}{lsb_name}_TABLE"]
    value_msb = [f"{prefix}{msb_name}_TABLE"]

    for _i, label in enumerate(labels):
        value_lsb.append(f"{prefix}{lsb_name}{label.key}  .BYTE <{label.default_value}")
        value_msb.append(f"{prefix}{msb_name}{label.key}  .BYTE >{label.default_value}")

    footer.append(f"END_REGION_{prefix}")
    footer.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")

    return header + value_msb + value_lsb + footer


def create_pip_region(dice_containers: list[DieContainer]) -> list[str]:

    pip_header: list[str] = []
    pip_header.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
    pip_header.append("; The location of each pip on each die")
    pip_header.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")

    pip_list: list[str] = []
    pip_ptr_lsb: list[str] = []
    pip_ptr_msb: list[str] = []

    pip_ptr_lsb.append("PIP_PTR_LSB")
    pip_ptr_msb.append("PIP_PTR_MSB")

    for di, die in enumerate(dice_containers):
        die_label = f"DIE_{di}_PIPS"

        pip_ptr_lsb.append(f"  .BYTE <{die_label}")
        pip_ptr_msb.append(f"  .BYTE >{die_label}")

        pip_list.append(die_label)

        for pi, pip in enumerate(die.pips):
            cmt: str = f"; Die {di}- Pip {pi}"
            pip_list.append(f"  .BYTE {pip.screen_row}; {cmt} row (byte)")
            pip_list.append(f"  .BYTE <{pip.screen_col}; {cmt} column (lsb)")
            pip_list.append(f"  .BYTE >{pip.screen_col}; {cmt} column (msb)")

    return pip_header + pip_list + pip_ptr_lsb + pip_ptr_msb


def create_dice_region(dice_containers: list[DieContainer]) -> list[str]:
    die_header: list[str] = []
    die_header.append("; the value of each die")
    die_header.append("DICE_VALUES")
    for _i, _die in enumerate(dice_containers):
        die_header.append(f"DICE_{_i}_VALUE  .BYTE {_i}; die {_i}")
    die_header.append("DICE_VALUES_END")
    return die_header


def add_auto_generated_notes(l1: list[str]) -> None:
    l1.append(
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;"
    )
    l1.append(
        ";; This file is auto-generated and you should not try to modify it by hand. ;;"
    )
    l1.append(
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;"
    )
    l1.append("")


@dataclass
class ScreenElements:
    offset_counter: int = 0
    header: list[str] = field(default_factory=list)
    equates: list[str] = field(default_factory=list)
    len_lsb: list[str] = field(default_factory=list)
    len_msb: list[str] = field(default_factory=list)
    pos_row: list[str] = field(default_factory=list)
    pos_col_lsb: list[str] = field(default_factory=list)
    pos_col_msb: list[str] = field(default_factory=list)
    out_text: list[str] = field(default_factory=list)
    txt_lsb: list[str] = field(default_factory=list)
    txt_msb: list[str] = field(default_factory=list)


def add_game_values_to_region(
    prefix: str,
    labels: list[GameValue],
    h: ScreenElements,
) -> None:

    # We are going to reset the offset_counter, because these values are completely isolated from
    # the other values.
    h.offset_counter = 0

    h.pos_row.append(f"{prefix}_ROWS")
    h.pos_col_lsb.append(f"{prefix}_COL_LSB")
    h.pos_col_msb.append(f"{prefix}_COL_MSB")

    h.equates.append(f"{prefix}_START = {h.offset_counter}")
    for _li, label in enumerate(labels):
        i = h.offset_counter
        h.offset_counter = h.offset_counter + 1
        h.equates.append(f"{prefix}_{label.key} = {byte_as_hex(i)}")

        h.pos_row.append(f"  .BYTE {label.screen_row}; {i} - {label.key}")
        h.pos_col_lsb.append(f"  .BYTE <{label.screen_col}; {i} - {label.key}")
        h.pos_col_msb.append(f"  .BYTE >{label.screen_col}; {i} - {label.key}")

    h.equates.append(f"{prefix}_LAST = {byte_as_hex(h.offset_counter - 1)}")
    h.equates.append("")


def complete_replaement_text(text_collection: TextCollection) -> None:

    for replacement_label in text_collection.label_replacement_text:
        label = next(
            (
                p
                for p in text_collection.screen_labels
                if p.key == replacement_label.linked_to
            ),
            None,
        )

        if label is None:
            raise ValueError(
                f"Oh woah unto is. the linked_to of {replacement_label.linked_to} is not found"
            )

        replacement_label.screen_col = label.screen_col
        replacement_label.screen_row = label.screen_row


def add_text_to_region(
    prefix: str,
    labels: list[LabelText | GameValue | DieContainer],
    h: ScreenElements,
) -> None:

    h.equates.append(f"{prefix}_START = {h.offset_counter}")

    for _li, label in enumerate(labels):
        i = h.offset_counter
        h.offset_counter = h.offset_counter + 1
        h.equates.append(f"{prefix}_{label.key} = {i}")

        h.len_lsb.append(
            f"  .BYTE <{label.length}; Idx: {i} - {label.key} - len {label.length}"
        )
        h.len_msb.append(
            f"  .BYTE >{label.length}; Idx: {i} - {label.key} - len {label.length}"
        )

        h.pos_row.append(f"  .BYTE {label.screen_row}; {i} - {label.key}")
        h.pos_col_lsb.append(f"  .BYTE <{label.screen_col}; {i} - {label.key}")
        h.pos_col_msb.append(f"  .BYTE >{label.screen_col}; {i} - {label.key}")

        txtlabel = f"{prefix}_{label.key}_TEXT"

        # Write .BYTE lines in chunks of 40 elements
        chunk_size = 40
        byte_lines = []
        for i in range(0, len(label.asm_bytes), chunk_size):
            chunk = label.asm_bytes[i : i + chunk_size]
            byte_lines.append("  .BYTE " + ",".join(chunk))

        h.out_text.append(f"{txtlabel}\n" + "\n".join(byte_lines))

        h.txt_lsb.append(f"  .BYTE <{txtlabel}; {i} - {label.key}")
        h.txt_msb.append(f"  .BYTE >{txtlabel}; {i} - {label.key}")

    h.equates.append(f"{prefix}_LAST = {h.offset_counter - 1}")
    h.equates.append("")


def create_label_text_region(prefix: str, text_collection: TextCollection) -> list[str]:
    """Create assembly region for label text data from a TextCollection."""

    h: ScreenElements = ScreenElements()
    h.header = []

    add_auto_generated_notes(h.header)

    h.header.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
    h.header.append(f"; REGION_{prefix}")

    h.equates = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; Equates to locate a specific label by its ID.",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
    ]

    h.len_lsb = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; The length of each label, low-byte",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_LEN_LSB_TABLE",
    ]
    h.len_msb = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; The length of each label, high-byte",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_LEN_MSB_TABLE",
    ]

    h.pos_row = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; The row each label appears on",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_ROW_TABLE",
    ]

    h.pos_col_lsb = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; The column each label appears on (LSB)",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_COL_LSB_TABLE",
    ]
    h.pos_col_msb = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; The column each label appears on (MSB)",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_COL_MSB_TABLE",
    ]

    h.out_text = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; The text of the label - encoded into either the local system encoding or",
        "; screen memory code",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_TEXT",
    ]

    h.txt_lsb = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; Pointer to the text LSB",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_TXT_LSB_TABLE",
    ]
    h.txt_msb = [
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "; Pointer to the text MSB",
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;",
        "",
        f"{prefix}_TXT_MSB_TABLE",
    ]

    h.equates.append("")
    h.equates.append(
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;"
    )
    h.equates.append("; GAME VALUE EQUATES")
    h.equates.append(
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;"
    )

    h.equates.append("")
    h.equates.append(
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;"
    )
    h.equates.append("; LABEL EQUATES")
    h.equates.append(
        ";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;"
    )

    # Cast required because mypy doesn't narrow list subclasses automatically
    labels_list: list[LabelText | GameValue | DieContainer] = cast(
        list[LabelText | GameValue | DieContainer], text_collection.screen_labels
    )

    label_replacement_list: list[LabelText | GameValue | DieContainer] = cast(
        list[LabelText | GameValue | DieContainer],
        text_collection.label_replacement_text,
    )

    dice_list: list[LabelText | GameValue | DieContainer] = cast(
        list[LabelText | GameValue | DieContainer], text_collection.die_container
    )

    frame_list: list[LabelText | GameValue | DieContainer] = cast(
        list[LabelText | GameValue | DieContainer], [text_collection.screen_frame]
    )

    complete_replaement_text(text_collection=text_collection)

    add_text_to_region("FRAME", frame_list, h)
    add_text_to_region("DICE", dice_list, h)
    add_text_to_region("LABELS", labels_list, h)
    add_text_to_region("REPLACEMENT_LABELS", label_replacement_list, h)

    add_game_values_to_region("GAME_VALUES", text_collection.game_values, h)

    return (
        h.header
        + h.equates
        + h.len_msb
        + h.len_lsb
        + h.pos_row
        + h.pos_col_lsb
        + h.pos_col_msb
        + h.txt_lsb
        + h.txt_msb
        + h.out_text
    )


def main():
    # Ensure output directory exists before writing files
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    text_collection = get_screen_frame()

    with open(ROM_ASM_FILE_NAME, "w", encoding="utf-8") as file:
        out = create_label_text_region("TITLE", text_collection)
        out.extend(create_pip_region(text_collection.die_container))
        file.write("\n".join(out))

    with open(RAM_ASM_FILE_NAME, "w", encoding="utf-8") as file:
        out = create_ram_region("RAM", text_collection.game_values)
        out.extend(create_dice_region(text_collection.die_container))
        file.write("\n".join(out))


if __name__ == "__main__":
    main()
