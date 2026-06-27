#!/usr/bin/env python3

"""
ATASCII Screen Layout Generator for Yahtzee Scorecard
Generates .BYTE tables and label lookup structures for assembly.
"""

from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Optional

ASM_FILE_NAME = Path(__file__).with_name("strings.m65")

ATASCII = [
    '♥','├','🮇','┘','┤','┐','╱','╲','◢','▗','◣','▝','▘','🮂','▂','▖',
    '♣','┌','─','┼','•','▄','▎','┬','┴','▌','└','␛','↑','↓','←','→',
    ' ','!','"','#','$','%','&',"'",'(',')','*','+',',','-','.','/',
    '0','1','2','3','4','5','6','7','8','9',':',';','<','=','>','?',
    '@','A','B','C','D','E','F','G','H','I','J','K','L','M','N','O',
    'P','Q','R','S','T','U','V','W','X','Y','Z','[','\\',']','^','_',
    '♦','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o',
    'p','q','r','s','t','u','v','w','x','y','z','♠','|','🢰','◀','▶',
]

ATASCII_MAP = {char: idx for idx, char in enumerate(ATASCII)}


@dataclass
class Chrome:
    """Represents a line in the screen layout."""
    txt: str
    txt_processed: str = ''
    asm_bytes: list[str] = field(default_factory=list)



@dataclass
class LabelText:
    """Represents a label definition with its position on screen."""
    key: str
    ascii: str
    asm_bytes: list[str] = field(default_factory=list)
    length: int = 0
    screen_row: int = -1
    screen_col: int = -1

    def __post_init__(self):
        self.asm_bytes = ascii_to_atari_hex(self.ascii)
        self.length = len(self.ascii)


@dataclass
class ScoreText:
    """Represents a label definition with its position on screen."""
    key: str
    screen_row: int = -1
    screen_col: int = -1

@dataclass
class TextCollection:
    screenLabels: list[LabelText] = field(default_factory=list)
    screenScores: list[ScoreText] = field(default_factory=list)
    screenFrame: LabelText = None



def getScreenAsciiArt() -> list[str]:
  lines = [
" ┌────────────┤!FIVE DICE&├───────────┐ ",
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
" | ♥♣♦♠  | #GTT         #SGT  | ♥♣♦♠  | ",
" └───────┴────────────────────┴───────┘ ",
  ]

  return lines

def getScreenFrame() -> LabelText:
    txt = "".join(getScreenAsciiArt())
    label = LabelText("MAIN", txt)
    label.screen_col = 0
    label.screen_row = 0

    return label

def byte_as_hex(byte: int) -> str:
    if byte > 255 or byte < 0:
        raise ValueError(f"byte_as_hex '{byte}' is out of range")

    return f"${byte:02X}"

def ascii_to_atari_hex(ascii: str) -> list[str]:
    """Convert ASCII string to ATSCII hex bytes."""
    result = []
    for char in ascii:
        if char not in ATASCII_MAP:
            raise ValueError(f"Character '{char}' is not ATASCII")
        result.append(byte_as_hex(ATASCII_MAP[char]))
    return result

def createLabelTextRegion(prefix: str, labels: list[LabelText]) -> list[str]:
    out = []

    out.append(f";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
    out.append(f"; REGION_{prefix}")


    equates = [
        "; Equates in case we ever need to access a specific label by its ID.",
        "; also serves as documentation",
        "",
    ]

    len_lsb = [f"{prefix}_LEN_LSB_TABLE"]
    len_msb = [f"{prefix}_LEN_MSB_TABLE"]


    len_row = [f"{prefix}_ROW_TABLE"]
    len_col_lsb = [f"{prefix}_COL_LSB_TABLE"]
    len_col_msb = [f"{prefix}_COL_MSB_TABLE"]

    outtxt = [f"{prefix}_TEXT"]
    txt_lsb = [f"{prefix}_TXT_LSB_TABLE"]
    txt_msb = [f"{prefix}_TXT_MSB_TABLE"]

    for i, label in enumerate(labels):
        equates.append(f"{prefix}_{label.key} = {i}")

        len_lsb.append(f"  .BYTE <{label.length}; {i} - {label.key}")
        len_msb.append(f"  .BYTE >{label.length}; {i} - {label.key}")


        len_row.append(f"  .BYTE {label.screen_row}; {i} - {label.key}")
        len_col_lsb.append(f"  .BYTE <{label.screen_col}; {i} - {label.key}")
        len_col_msb.append(f"  .BYTE >{label.screen_col}; {i} - {label.key}")

        txtlabel = f"{prefix}_{label.key}_TEXT"

        outtxt.append(f"{txtlabel}\n .BYTE " + "\n .BYTE ".join(label.asm_bytes))

        txt_lsb.append(f"  .BYTE <{txtlabel}; {i} - {label.key}")
        txt_msb.append(f"  .BYTE >{txtlabel}; {i} - {label.key}")

    return (
        out +
        equates +
        len_msb +
        len_lsb +
        len_row +
        len_col_lsb +
        len_col_msb +
        txt_lsb +
        txt_msb +
        outtxt
      )

def main():
    print("Hello to main")
    textCollection = TextCollection()

    textCollection.screenFrame = getScreenFrame()

    with open(ASM_FILE_NAME, 'w', encoding='utf-8') as file:

        out = createLabelTextRegion("TITLE", [textCollection.screenFrame])
        file.write("\n".join(out))

# class SheetParser:
#     """Handles parsing the ASCII-art sheet and extracting label positions."""

#     LABEL_PATTERN = re.compile(r'#(\w+)')

#     def __init__(self, sheet: list[Chrome]):
#         self.sheet = sheet
#         self.label_positions = self._find_all_label_positions()

#     def _find_all_label_positions(self) -> dict[str, tuple[int, int]]:
#         """Find all label positions in one pass through the sheet."""
#         positions = {}
#         for row_idx, chrome in enumerate(self.sheet):
#             for match in self.LABEL_PATTERN.finditer(chrome.txt):
#                 key = match.group(1)
#                 if key in positions:
#                     raise ValueError(f"Label '{key}' appears multiple times in sheet")
#                 positions[key] = (row_idx, match.start() + 1)  # +1 to skip '#'
#         return positions

#     def get_label_position(self, key: str) -> tuple[int, int]:
#         """Get the row and column for a given label key."""
#         if key not in self.label_positions:
#             raise ValueError(f"Label '{key}' not found in sheet")
#         return self.label_positions[key]

#     def process_sheet_for_assembly(self) -> list[Chrome]:
#         """Convert the sheet to assembly-ready format with dots for labels."""
#         processed_sheet = []

#         for line in self.sheet:
#             chars = list(line.txt)
#             in_label = False

#             for i, char in enumerate(chars):
#                 if char == '#':
#                     in_label = True
#                     chars[i] = '.'  # Replace the # marker with a dot
#                 elif char in (' ', '|'):
#                     in_label = False

#                 if in_label and char not in ('#', ' '):
#                     chars[i] = '.'

#             processed = "".join(chars)
#             processed_sheet.append(Chrome(
#                 txt=line.txt,
#                 txt_processed=processed,
#                 asm_bytes=ascii_to_atari_hex(processed)
#             ))

#         return processed_sheet

#     def render_populated_sheet(self, label_values: dict[str, str], all_label_values: dict[str, str]) -> list[str]:
#         """Render the sheet with actual label values filled in."""
#         output = []

#         for line in self.sheet:
#             rendered = list(line.txt)
#             idx = 0

#             while idx < len(line.txt):
#                 if line.txt[idx] == '#':
#                     # Extract the full key (all word characters after #)
#                     match = self.LABEL_PATTERN.match(line.txt, idx)
#                     if not match:
#                         idx += 1
#                         continue

#                     key = match.group(1)
#                     if key not in all_label_values:
#                         raise ValueError(f"Unknown label key '{key}'")

#                     value = all_label_values[key]
#                     key_end = match.end()

#                     # Find end of field (next non-space character)
#                     end_idx = key_end
#                     while end_idx < len(rendered) and rendered[end_idx] == ' ':
#                         end_idx += 1

#                     field_width = end_idx - idx
#                     fitted_value = value[:field_width].ljust(field_width)

#                     for i, char in enumerate(fitted_value):
#                         rendered[idx + i] = char

#                     idx = end_idx
#                     continue

#                 idx += 1

#             output.append(";; FULL >" + "".join(rendered) + "<")

#         return output


# def get_labels() -> TextCollection:
#     """Define all labels with their display text."""

#     label_collections = TextCollection()

#     def add_it(it: LabelText | ScoreText):
#         if isinstance(it, LabelText):
#             label_collections.screenLabels.append(it)
#         elif isinstance(it, ScoreText):
#             label_collections.screenScores.append(it)
#         else:
#             raise ValueError(f"Unknown label type: {type(it)}")

#     # Left column labels
#     add_it(LabelText('L1C', 'Aces'))        # Left column labels

#     add_it(ScoreText('S1C'))
#     add_it(LabelText('L2C', 'Twos'))
#     add_it(ScoreText('S2C'))
#     add_it(LabelText('L3C', 'Threes'))
#     add_it(ScoreText('S3C'))
#     add_it(LabelText('L4C', 'Fours'))
#     add_it(ScoreText('S4C'))
#     add_it(LabelText('L5C', 'Fives'))
#     add_it(ScoreText('S5C'))
#     add_it(LabelText('L6C', 'Sixes'))
#     add_it(ScoreText('S6C'))
#     add_it(LabelText('LTS', 'Top Score'))
#     add_it(ScoreText('STS'))
#     add_it(LabelText('LTB', 'Upper Bonus'))
#     add_it(ScoreText('STB'))
#     add_it(LabelText('LUT', 'Upper Total'))
#     add_it(ScoreText('SUT'))

#     # Right column labels
#     add_it(LabelText('L3K', '3 of a Kind'))
#     add_it(ScoreText('S3K'))
#     add_it(LabelText('L4K', '4 of a Kind'))
#     add_it(ScoreText('S4K'))
#     add_it(LabelText('LFH', 'Full House'))
#     add_it(ScoreText('SFH'))
#     add_it(LabelText('LSS', 'S Straight'))
#     add_it(ScoreText('SSS'))
#     add_it(LabelText('LLS', 'L Straight'))
#     add_it(ScoreText('SLS'))
#     add_it(LabelText('L5K', '5 of a Kind'))
#     add_it(ScoreText('S5K'))
#     add_it(LabelText('LCH', 'Chance'))
#     add_it(ScoreText('SCH'))
#     add_it(LabelText('L5B', '5K Bonus'))
#     add_it(ScoreText('S5B'))
#     add_it(LabelText('LLT', 'Lower Total'))
#     add_it(ScoreText('SLT'))

#     # Bottom labels
#     add_it(LabelText('GTT', 'Grand Total'))
#     add_it(ScoreText('SGT'))

#     return label_collections


# def convert_line_to_m65(asm_bytes: list[str]) -> str:
#     """Convert a list of byte strings to a .BYTE directive line."""
#     return " .BYTE " + ", ".join(asm_bytes)


# class AssemblyGenerator:
#     """Generates assembly code from the parsed sheet and labels."""

#     def __init__(self, sheet_parser: SheetParser, labels: TextCollection):
#         self.sheet_parser = sheet_parser
#         self.labels = labels
#         self.processed_sheet = sheet_parser.process_sheet_for_assembly()

#         # Run the sanity check BEFORE doing anything else
#         self._validate_labels()

#         # Set label positions
#         for label in self.labels.screenLabels + self.labels.screenScores:
#             row, col = sheet_parser.get_label_position(label.key)
#             label.screen_row = row
#             label.screen_col = col

#     def _validate_labels(self) -> None:
#         sheet_keys = set(self.sheet_parser.label_positions)
#         label_keys = {label.key for label in self.labels.screenLabels + self.labels.screenScores}

#         missing = sheet_keys - label_keys
#         extra = label_keys - sheet_keys

#         if missing:
#             raise ValueError(f"Sheet has labels with no values: {sorted(missing)}")
#         if extra:
#             raise ValueError(f"Labels defined but not used in sheet: {sorted(extra)}")

#         if len(label_keys) != len(self.labels.screenLabels) + len(self.labels.screenScores):
#             raise ValueError("Duplicate labels in label definitions")

#     def _make_key_full(self, key: str) -> str:
#         """Generate the full label identifier for assembly."""
#         return f"LABEL_{key}_F"

#     def build_message_section(self) -> list[str]:
#         """Build the MESSAGE section with full screen preview."""
#         lines = []
#         screen_label_values = {label.key: label.ascii for label in self.labels.screenLabels}
#         all_label_values = {label.key: label.ascii for label in self.labels.screenLabels + self.labels.screenScores}

#         lines.append(';; FULLY POPULATED SCREEN PREVIEW')

#         lines.extend(self.sheet_parser.render_populated_sheet(screen_label_values, all_label_values))
#         lines.append('')
#         lines.append('MESSAGE')

#         for chrome in self.processed_sheet:
#             lines.append(";; >" + chrome.txt_processed + "<")
#             lines.append(convert_line_to_m65(chrome.asm_bytes))

#         lines.append('MESSAGE_END')
#         lines.append('MESSAGE_LEN = MESSAGE_END - MESSAGE')
#         lines.append('')

#         return lines

#     def build_label_full_section(self) -> list[str]:
#         """Build the full label lookup section."""
#         lines = ['LABEL_LOOKUP_FULL']

#         for label in self.labels:
#             lines.append(f"{self._make_key_full(label.key)}")
#             lines.append(f' .WORD ${label.length:04X} ; Length')
#             lines.append(f' .BYTE ${label.screen_row:02X} ; row')
#             lines.append(f' .WORD ${label.screen_col:04X} ; col')
#             lines.append(f'; Rendered Text: {label.ascii}')
#             lines.append(convert_line_to_m65(label.asm_bytes))

#         return lines

#     def build_label_pointer_sections(self) -> tuple[list[str], list[str], int]:
#         """Build high and low byte pointer tables."""
#         high_lines = ['LABEL_LOOKUP_HIGH']
#         low_lines = ['LABEL_LOOKUP_LOW']

#         for label in self.labels:
#             full_key = self._make_key_full(label.key)
#             high_lines.append(f"LABEL_{label.key}_H .BYTE >{full_key}")
#             low_lines.append(f"LABEL_{label.key}_L .BYTE <{full_key}")

#         return high_lines, low_lines, len(self.labels)

#     def generate(self) -> str:
#         """Generate the complete assembly output."""
#         sections = []

#         sections.extend(self.build_message_section())
#         sections.extend(self.build_label_full_section())

#         high_section, low_section, num_labels = self.build_label_pointer_sections()
#         sections.extend(high_section)
#         sections.extend(low_section)

#         num_labels = f"NUM_LABELS .BYTE ${num_labels:02X} ; Number of labels ({num_labels})'"
#         sections.append(num_labels)

#         return '\n'.join(sections) + '\n'


# def main() -> None:
#     """Main entry point: parse sheet, set up labels, and generate assembly."""
#     sheet = get_sheet()
#     parser = SheetParser(sheet)
#     labels = get_labels()

#     generator = AssemblyGenerator(parser, labels)
#     output = generator.generate()

#     with open(ASM_FILE_NAME, 'w', encoding='utf-8') as file:
#         file.write(output)

#     print(f"Generated {ASM_FILE_NAME}")


if __name__ == '__main__':
    main()