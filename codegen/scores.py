#!/usr/bin/env python3

"""
ATASCII Screen Layout Generator for Yahtzee Scorecard
Generates .BYTE tables and label lookup structures for assembly.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

ROM_ASM_FILE_NAME = Path(__file__).with_name("strings.m65")
RAM_ASM_FILE_NAME = Path(__file__).with_name("ram.m65")

# The actual screen width of the Atari.  We handle margins ourselves.
SCREEN_WIDTH = 40
NUMBER_OF_PIPS = 7


ATASCII_ESCAPE = "␛"
ATASCII_REQUIRES_ESCAPE = ["␛", "↑", "↓", "←", "→", "🢰", "◀", "▶"]

ATASCII = [
    "♥",
    "├",
    "🮇",
    "┘",
    "┤",
    "┐",
    "╱",
    "╲",
    "◢",
    "▗",
    "◣",
    "▝",
    "▘",
    "🮂",
    "▂",
    "▖",
    "♣",
    "┌",
    "─",
    "┼",
    "•",
    "▄",
    "▎",
    "┬",
    "┴",
    "▌",
    "└",
    "␛",
    "↑",
    "↓",
    "←",
    "→",
    " ",
    "!",
    '"',
    "#",
    "$",
    "%",
    "&",
    "'",
    "(",
    ")",
    "*",
    "+",
    ",",
    "-",
    ".",
    "/",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    ":",
    ";",
    "<",
    "=",
    ">",
    "?",
    "@",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "[",
    "\\",
    "]",
    "^",
    "_",
    "♦",
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "♠",
    "|",
    "🢰",
    "◀",
    "▶",
]

HOTKEY_MARKER = "~"

SCREEN_PLACE_HOLDER = "▂"

ATASCII_MAP = {char: idx for idx, char in enumerate(ATASCII)}


@dataclass
class DiePip:
    screen_row: int = -1
    screen_col: int = -1


@dataclass
class DieContainer:
    """Represents a label definition with its position on screen."""

    key: str
    unicode: str
    hot_key: str = ""
    asm_bytes: list[str] = field(default_factory=list)
    length: int = 0
    screen_row: int = -1
    screen_col: int = -1
    pips: list[DiePip] = field(default_factory=list)

    pip_fill_asm_bytes: list[str] = field(default_factory=list)
    pip_empty_asm_bytes: list[str] = field(default_factory=list)

    def __post_init__(self):
        filtered_text, hotkey, hotkey_position = find_hotkeys_in_unicode(self.unicode)
        self.hotkey = hotkey
        self.hotkey_position = hotkey_position
        self.unicode = filtered_text
        print(filtered_text)

        self.asm_bytes = unicode_to_atari_hex2(filtered_text, hotkey_position)

        self.length = len(self.asm_bytes)


@dataclass
class LabelText:
    """Represents a label definition with its position on screen."""

    key: str
    unicode: str
    asm_bytes: list[str] = field(default_factory=list)
    length: int = 0
    screen_row: int = -1
    screen_col: int = -1
    hotkey_position: int = -1
    hotkey: str = ""

    def __post_init__(self):
        filtered_text, hotkey, hotkey_position = find_hotkeys_in_unicode(self.unicode)
        self.hotkey = hotkey
        self.hotkey_position = hotkey_position
        self.asm_bytes = unicode_to_atari_hex2(filtered_text, hotkey_position)
        self.unicode = filtered_text
        self.length = len(self.asm_bytes)


@dataclass
class ScoreText:
    """Represents a label definition with its position on screen."""

    key: str
    screen_row: int = -1
    screen_col: int = -1
    length: int = 0
    asm_bytes: list[str] = field(default_factory=list)


@dataclass
class TextCollection:
    screen_labels: list[LabelText] = field(default_factory=list)
    screen_scores: list[ScoreText] = field(default_factory=list)
    die_container: list[DieContainer] = field(default_factory=list)
    screen_frame: LabelText | None = None


@dataclass
class LabelPosition:
    """Represents a label's position on screen with its name, row, and column."""

    name: str
    screen_row: int
    screen_col: int


class LabelExtractor:
    """Extracts labels from Unicode art and returns their positions."""

    LABEL_PATTERN = re.compile(r"#(\w+)")

    def __init__(self, atari_unicode_art_lines: list[str]):
        self.atari_unicode_art_lines = atari_unicode_art_lines

    def extract_labels(self) -> list[LabelPosition]:
        """
        Extract all labels from the Unicode art lines.
        Returns a list of LabelPosition objects containing name, row, and column.
        """
        labels = []

        for row_idx, line in enumerate(self.atari_unicode_art_lines):
            for match in self.LABEL_PATTERN.finditer(line):
                label_name = match.group(1)
                col_idx = match.start()

                labels.append(
                    LabelPosition(
                        name=label_name, screen_row=row_idx, screen_col=col_idx
                    )
                )

        return labels


def get_screen_unicode_art() -> list[str]:
    lines = [
        " ┌────────────┤!FIVE DICE!├───────────┐ ",
        " |#L1C        #S1C |#L3K        #S3K  | ",
        " |#L2C        #S2C |#L4K        #S4K  | ",
        " |#L3C        #S3C |#LFH        #SFH  | ",
        " |#L4C        #S4C |#LSS        #SSS  | ",
        " |#L5C        #S5C |#LLS        #SLS  | ",
        " |#L6C        #S6C |#L5K        #S5K  | ",
        " |#LTS        #STS |#LCH        #SCH  | ",
        " |#LTB        #STB |#L5B        #S5B  | ",
        " |#LUT        #SUT |#LLT        #SLT  | ",
        " ├───────┬─────────┴──────────┬───────┤ ",
        " | ↑↓←→  | #GTT         #SGT  |  ♠🢰◀▶ | ",
        " └───────┴────────────────────┴───────┘ ",
        "   #DIE0  #DIE1  #DIE2  #DIE3  #DIE4    ",
        "                                        ",
        "                                        ",
        "                                        ",
        "                                        ",
        "                                        ",
        " LINE4                                  ",
        " LINE3                                  ",
        " LINE2                                  ",
        " LINE1                                  ",
        " ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂",
    ]

    return lines


def replace_template(orig, newt, idx):
    a = list(orig)
    t = list(newt)

    length = min(len(newt), len(orig))

    for i in range(length):
        if i + idx >= len(orig):
            break
        a[i + idx] = t[i]
        a[i + idx] = "."

    return "".join(a)


def get_label_text() -> TextCollection:
    """Define all labels with their display text."""

    label_collections = TextCollection()

    def add_it(it: LabelText | ScoreText | DieContainer):
        if isinstance(it, LabelText):
            label_collections.screen_labels.append(it)
        elif isinstance(it, ScoreText):
            label_collections.screen_scores.append(it)
        elif isinstance(it, DieContainer):
            label_collections.die_container.append(it)
        else:
            raise ValueError(f"Unknown label type: {type(it)}")

    # Left column labels
    add_it(LabelText("L1C", "~Aces"))  # Left column labels
    add_it(ScoreText("S1C"))
    add_it(LabelText("L2C", "Twos"))
    add_it(ScoreText("S2C"))
    add_it(LabelText("L3C", "Threes"))
    add_it(ScoreText("S3C"))
    add_it(LabelText("L4C", "Fours"))
    add_it(ScoreText("S4C"))
    add_it(LabelText("L5C", "Fives"))
    add_it(ScoreText("S5C"))
    add_it(LabelText("L6C", "Sixes"))
    add_it(ScoreText("S6C"))
    add_it(LabelText("LTS", "Top Score"))
    add_it(ScoreText("STS"))
    add_it(LabelText("LTB", "Upper Bonus"))
    add_it(ScoreText("STB"))
    add_it(LabelText("LUT", "Upper Total"))
    add_it(ScoreText("SUT"))

    # Right column labels
    add_it(LabelText("L3K", "3 of a Kind"))
    add_it(ScoreText("S3K"))
    add_it(LabelText("L4K", "4 of a Kind"))
    add_it(ScoreText("S4K"))
    add_it(LabelText("LFH", "Full House"))
    add_it(ScoreText("SFH"))
    add_it(LabelText("LSS", "S Straight"))
    add_it(ScoreText("SSS"))
    add_it(LabelText("LLS", "L Straight"))
    add_it(ScoreText("SLS"))
    add_it(LabelText("L5K", "5 of a Kind"))
    add_it(ScoreText("S5K"))
    add_it(LabelText("LCH", "Chance"))
    add_it(ScoreText("SCH"))
    add_it(LabelText("L5B", "5K Bonus"))
    add_it(ScoreText("S5B"))
    add_it(LabelText("LLT", "Lower Total"))
    add_it(ScoreText("SLT"))

    # Bottom labels
    add_it(LabelText("GTT", "Grand Total"))
    add_it(ScoreText("SGT"))

    add_it(DieContainer("DIE0", "  ~1  "))
    add_it(DieContainer("DIE1", "  ~2  "))
    add_it(DieContainer("DIE2", "  ~3  "))
    add_it(DieContainer("DIE3", "  ~4  "))
    add_it(DieContainer("DIE4", "  ~5  "))

    return label_collections


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
                display = "."

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
        + label_text_info.screen_scores
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
                replacement = SCREEN_PLACE_HOLDER * (len(record.key) + 1)

                if isinstance(record, (LabelText, DieContainer)):
                    replacement = record.unicode

                unicode_art_lines[ai] = replace_template(
                    txt, replacement, label.screen_col
                )

    for record in combined_list:
        if record.screen_row < 0 or record.screen_col < 0:
            raise ValueError(f"{record.key} was defined but never placed")

    atari_unicode_art = "".join(unicode_art_lines)

    for die in label_text_info.die_container:
        atari_unicode_art = add_dice_boxes(die, atari_unicode_art)

    label = LabelText("MAIN", atari_unicode_art)
    label.screen_col = 0
    label.screen_row = 0

    ret: TextCollection = TextCollection(
        screen_frame=label,
        screen_labels=label_text_info.screen_labels,
        screen_scores=label_text_info.screen_scores,
        die_container=label_text_info.die_container,
    )

    return ret


def byte_as_hex(byte: int) -> str:
    if byte > 255 or byte < 0:
        raise ValueError(f"byte_as_hex '{byte}' is out of range")

    return f"${byte:02X}"


def filter_unicode(unicode: str) -> str:
    # Filter out HOTKEY_MARKER characters from the text
    filtered_text = "".join(char for char in unicode if char != HOTKEY_MARKER)
    return filtered_text


def find_hotkeys_in_unicode(unicode: str) -> tuple[str, str, int]:
    """
    Filter HOTKEY_MARKER (∼) characters from the text and return its position.

    Args:
        unicode: Input string containing at most one HOTKEY_MARKER character

    Returns:
        Tuple of (filtered_string, hot_key, marker_position)
        - filtered_string: The input with HOTKEY_MARKER removed
        - hot_key: The string of the hotkey, or "" if none
        - marker_position: Index where HOTKEY_MARKER was found, or -1 if none

    Raises:
        ValueError: If more than one HOTKEY_MARKER is found
    """
    # Find and record HOTKEY_MARKER positions
    hotkey_positions = [i for i, char in enumerate(unicode) if char == HOTKEY_MARKER]

    # Validate that there's at most one marker
    if len(hotkey_positions) > 1:
        print(unicode)
        raise ValueError(
            f"Multiple HOTKEY_MARKERs found: {hotkey_positions}. Only one is allowed."
        )

    # Filter out HOTKEY_MARKER characters from the text
    filtered_text = filter_unicode(unicode)

    # Return position or -1 if no marker found
    marker_position = hotkey_positions[0] if hotkey_positions else -1

    hot_key = "" if (marker_position == -1) else filtered_text[marker_position]

    return filtered_text, hot_key, marker_position


def unicode_to_atari_hex2(unicode: str, hotkey_position: int) -> list[str]:
    """Convert UNICODE string to ATSCII hex bytes."""
    result = []
    for idx, char in enumerate(unicode):
        if char not in ATASCII_MAP:
            raise ValueError(f"Character '{char}' is not ATASCII")

        modifier = 0x80 if idx == hotkey_position else 0x00

        if char in ATASCII_REQUIRES_ESCAPE:
            result.append(byte_as_hex(ATASCII_MAP[ATASCII_ESCAPE]))

        result.append(byte_as_hex(ATASCII_MAP[char] + modifier))

    return result


def create_ram_region(prefix: str, labels: list[ScoreText]) -> list[str]:
    header = []
    footer = []

    header.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
    header.append(f"START_REGION_{prefix}")

    len_lsb = [f"{prefix}_SCORE_LSB_TABLE"]
    len_msb = [f"{prefix}_SCORE_MSB_TABLE"]

    for _i, label in enumerate(labels):
        len_lsb.append(f"{prefix}_SCORE_LSB_{label.key}  .BYTE 1")
        len_msb.append(f"{prefix}_SCORE_MSB_{label.key}  .BYTE 1")

    footer.append(f"END_REGION_{prefix}")
    footer.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")

    return header + len_msb + len_lsb + footer


def create_pip_region(dice_containers: list[DieContainer]) -> list[str]:

    pip_header: list[str] = []
    #    pos_col_lsb: list[str] = []
    #    pos_col_msb: list[str] = []
    #    pos_row: list[str] = []

    pip_header.append("; The location of each pip on each die")

    pip_list: list[str] = []
    pip_ptr_lsb: list[str] = []
    pip_ptr_msb: list[str] = []

    pip_ptr_lsb.append("PIP_PTR_LSB")
    pip_ptr_msb.append("PIP_PTR_MSB")

    for di, die in enumerate(dice_containers):
        die_label = f"DIE_{di}_PIPS"

        pip_ptr_lsb.append(f" .BYTE <{die_label}")
        pip_ptr_msb.append(f" .BYTE >{die_label}")

        pip_list.append(die_label)

        for pi, pip in enumerate(die.pips):
            cmt: str = f"; Die {di}- Pip {pi}"
            pip_list.append(f"  .BYTE {pip.screen_row}; {cmt} row")
            pip_list.append(f"  .BYTE <{pip.screen_col}; {cmt} clst")
            pip_list.append(f"  .BYTE >{pip.screen_col}; {cmt} cmsb")

    return pip_header + pip_list + pip_ptr_lsb + pip_ptr_msb


def create_dice_region(dice_containers: list[DieContainer]) -> list[str]:
    die_header: list[str] = []
    die_header.append("; the value of each die")
    die_header.append("DICE_VALUES")
    for _i, _die in enumerate(dice_containers):
        die_header.append(f"DICE_{_i}_VALUE  .BYTE {_i}; die {_i}")
    die_header.append("DICE_VALUES_END")
    return die_header


def create_label_text_region(
    prefix: str, labels: list[LabelText | ScoreText | DieContainer]
) -> list[str]:
    header = []

    header.append(";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
    header.append(f"; REGION_{prefix}")

    equates = [
        "; Equates in case we ever need to access a specific label by its ID.",
        "; also serves as documentation",
        "",
    ]

    len_lsb = [f"{prefix}_LEN_LSB_TABLE"]
    len_msb = [f"{prefix}_LEN_MSB_TABLE"]

    pos_row = [f"{prefix}_ROW_TABLE"]
    pos_col_lsb = [f"{prefix}_COL_LSB_TABLE"]
    pos_col_msb = [f"{prefix}_COL_MSB_TABLE"]

    outtxt = [f"{prefix}_TEXT"]
    txt_lsb = [f"{prefix}_TXT_LSB_TABLE"]
    txt_msb = [f"{prefix}_TXT_MSB_TABLE"]

    for i, label in enumerate(labels):
        equates.append(f"{prefix}_{label.key} = {i}")

        len_lsb.append(f"  .BYTE <{label.length}; {i} - {label.key}")
        len_msb.append(f"  .BYTE >{label.length}; {i} - {label.key}")

        pos_row.append(f"  .BYTE {label.screen_row}; {i} - {label.key}")
        pos_col_lsb.append(f"  .BYTE <{label.screen_col}; {i} - {label.key}")
        pos_col_msb.append(f"  .BYTE >{label.screen_col}; {i} - {label.key}")

        txtlabel = f"{prefix}_{label.key}_TEXT"

        outtxt.append(f"{txtlabel}\n .BYTE " + "\n .BYTE ".join(label.asm_bytes))

        txt_lsb.append(f"  .BYTE <{txtlabel}; {i} - {label.key}")
        txt_msb.append(f"  .BYTE >{txtlabel}; {i} - {label.key}")

    return (
        header
        + equates
        + len_msb
        + len_lsb
        + pos_row
        + pos_col_lsb
        + pos_col_msb
        + txt_lsb
        + txt_msb
        + outtxt
    )


def main():
    print("Hello to main")
    text_collection = get_screen_frame()
    all_labels: list[LabelText | ScoreText | DieContainer] = []
    all_labels.extend(text_collection.screen_labels)
    if text_collection.screen_frame:
        all_labels.append(text_collection.screen_frame)
    all_labels.extend(text_collection.die_container)

    with open(ROM_ASM_FILE_NAME, "w", encoding="utf-8") as file:
        out = create_label_text_region("TITLE", all_labels)
        out.extend(create_pip_region(text_collection.die_container))
        file.write("\n".join(out))

    with open(RAM_ASM_FILE_NAME, "w", encoding="utf-8") as file:
        out = create_ram_region("RAM", text_collection.screen_scores)
        out.extend(create_dice_region(text_collection.die_container))
        file.write("\n".join(out))


if __name__ == "__main__":
    main()
