#!/usr/bin/env python3

# Source of truth: the ASCII-art sheet in get_sheet(), where each #KEY marker
# anchors a label on screen. We derive row/column metadata from those markers,
# render a populated preview, and emit ATASCII .BYTE tables for assembly.

ASM_FILE_NAME = "strings.m65"

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


from dataclasses import dataclass
from typing import Optional

@dataclass
class Chrome:
    txt: str
    txt_processed: str = ''
    asm_bytes: Optional[list[str]] = None

@dataclass
class ScreenLabel:
    key: str
    ascii: str

    asm_bytes: Optional[list[str]] = None
    length: int = 0
    screen_row: int = -1
    screen_col: int = -1

    def __init__(self,key:str, ascii:str):
        self.key = key
        self.ascii = ascii
        self.asm_bytes = ascii_to_atari_hex(ascii)
        self.length = len(ascii)

        # Get sheet and find the row and column where the label appears
        # We use '#' to show the start of a label.
        sheet = get_sheet()
        for row_idx, chrome in enumerate(sheet):
            col_idx = chrome.txt.find('#' + key)
            if col_idx != -1:

                if self.screen_row != -1:
                    raise Exception(f"Label '{key}' appears more than once in the sheet")

                self.screen_row = row_idx
                self.screen_col = col_idx + 1  # +1 to skip the '#'

        if self.screen_row == -1:
            raise Exception(f"Label '{key}' was not found in the sheet")

def get_sheet() -> list[Chrome]:
    sheet = [
        Chrome(" ┌────────────┤!FIVE DICE ├───────────┐ "),
        Chrome(" |#L1C        #S1C |#L3K        #S3K  | "),
        Chrome(" |#L2C        #S2C |#L4K        #S4K  | "),
        Chrome(" |#L3C        #S3C |#LFH        #SFH  | "),
        Chrome(" |#L4C        #S4C |#LSS        #SSS  | "),
        Chrome(" |#L5C        #S5C |#LLS        #SLS  | "),
        Chrome(" |#L6C        #S6C |#L5K        #S5K  | "),
        Chrome(" |#LTS        #STS |#LCH        #SCH  | "),
        Chrome(" |#LTB        #STB |#L5B        #S5B  | "),
        Chrome(" |#LUT        #SUT |#LLT        #SLT  | "),
        Chrome(" ├───────┬─────────┴──────────┬───────┤ "),
        Chrome(" | ♥♣♦♠  | #GTT         #SGT  | ♥♣♦♠  | "),
        Chrome(" └───────┴────────────────────┴───────┘ "),
    ]
    return sheet

def get_labels() -> list[ScreenLabel]:
    num = '00000'
    out: list[ScreenLabel] = [
        ScreenLabel('L1C', 'Aces'),
        ScreenLabel('S1C', num),
        ScreenLabel('L2C', 'Twos'),
        ScreenLabel('S2C', num),
        ScreenLabel('L3C', 'Threes'),
        ScreenLabel('S3C', num),
        ScreenLabel('L4C', 'Fours'),
        ScreenLabel('S4C', num),
        ScreenLabel('L5C', 'Fives'),
        ScreenLabel('S5C', num),
        ScreenLabel('L6C', 'Sixes'),
        ScreenLabel('S6C', num),
        ScreenLabel('LTS', 'Top Score'),
        ScreenLabel('STS', num),
        ScreenLabel('LTB', 'Upper Bonus'),
        ScreenLabel('STB', num),
        ScreenLabel('LUT', 'Upper Total'),
        ScreenLabel('SUT', num),

        ScreenLabel('L3K', '3 of a Kind'),
        ScreenLabel('S3K', num),
        ScreenLabel('L4K', '4 of a Kind'),
        ScreenLabel('S4K', num),
        ScreenLabel('LFH', 'Full House'),
        ScreenLabel('SFH', num),
        ScreenLabel('LSS', 'S Straight'),
        ScreenLabel('SSS', num),
        ScreenLabel('LLS', 'L Straight'),
        ScreenLabel('SLS', num),
        ScreenLabel('L5K', '5 of a Kind'),
        ScreenLabel('S5K', num),
        ScreenLabel('LCH', 'Chance'),
        ScreenLabel('SCH', num),
        ScreenLabel('L5B', '5K Bonus'),
        ScreenLabel('S5B', num),
        ScreenLabel('LLT', 'Lower Total'),
        ScreenLabel('SLT', num),

        ScreenLabel('GTT', 'Grand Total'),
        ScreenLabel('SGT', num),
    ]
    return out;

def ascii_to_atari_hex(ascii: str) -> list[str]:
    atari: list[str] = []
    for char in ascii:
        if char not in ATASCII_MAP:
            raise ValueError(f"character '{char}' is not ATASCII")

        idx = ATASCII_MAP[char]
        atari.append('$' + f"{idx:02X}")

    return atari

def get_sheet_for_screen() -> list[Chrome]:
    sheet = get_sheet()

    for line in sheet:
        txt = line.txt

        inchar: bool = False
        out = []
        for char in line.txt:
            if char == ' ':
                inchar = False

            if char == '|':
                inchar = False

            if char == '#':
                inchar = True

            if inchar == False:
                pass
                # out = out + char;
            if inchar == True:
                char = '.'
                # out = out + "."

            out.append(char)

        line.txt_processed = "".join(out)
        line.asm_bytes = ascii_to_atari_hex(out)

    return sheet

def convert_line_to_m65(asm_bytes: list[str]) -> str:
    txt = ", ".join(asm_bytes)
    return " .BYTE " + txt


def convert_sheet_do_m65(sheet: list[Chrome]) -> list[str]:
    out = []

    for line in sheet:
        out.append(";; >" + line.txt_processed + "<")

    for line in sheet:
        txt = ", ".join(line.asm_bytes)
        out.append(" .BYTE " + txt)

    return out


def render_populated_sheet_preview() -> list[str]:
    label_lookup = {label.key: label.ascii for label in labels}
    out: list[str] = []

    for line in get_sheet():
        rendered = list(line.txt)
        idx = 0

        while idx < len(line.txt):
            if line.txt[idx] == '#':
                key = line.txt[idx + 1:idx + 4]
                if key not in label_lookup:
                    raise Exception(f"Unknown label key '{key}' in sheet preview")

                value = label_lookup[key]
                end_idx = idx + 4

                while end_idx < len(rendered) and rendered[end_idx] == ' ':
                    end_idx += 1

                field_width = end_idx - idx
                fitted_value = value[:field_width].ljust(field_width)

                for value_idx, char in enumerate(fitted_value):
                    rendered[idx + value_idx] = char

                idx = end_idx
                continue

            idx += 1

        out.append(";; FULL >" + "".join(rendered) + "<")

    return out

sheet2 = convert_sheet_do_m65(get_sheet_for_screen())
labels = get_labels()

def make_key_full(key: str) -> str:
    return f"LABEL_{key}_F"


def build_message_section() -> list[str]:
    out: list[str] = []

    out.append(';; FULLY POPULATED SCREEN PREVIEW')
    out.extend(render_populated_sheet_preview())
    out.append('')
    out.append('MESSAGE')
    out.extend(sheet2)
    out.append('MESSAGE_END')
    out.append('MESSAGE_LEN = MESSAGE_END - MESSAGE')
    out.append('')

    return out


def build_label_full_section() -> list[str]:
    out: list[str] = []

    out.append('LABEL_LOOKUP_FULL')
    for label in labels:
        out.append(f"{make_key_full(label.key)}")
        out.append(' .BYTE $' + f"{label.length:02X} ; Length")
        out.append(' .BYTE $' + f"{label.screen_row:02X} ; row")
        out.append(' .BYTE $' + f"{label.screen_col:02X} ; col")
        out.append('; Rendered Text: ' + label.ascii)
        out.append(convert_line_to_m65(label.asm_bytes))

    return out


def build_label_pointer_sections() -> tuple[list[str], list[str]]:
    high_lines: list[str] = ['LABEL_LOOKUP_HIGH']
    low_lines: list[str] = ['LABEL_LOOKUP_LOW']

    for label in labels:
        high_lines.append(f"LABEL_{label.key}_H .BYTE >{make_key_full(label.key)}")
        low_lines.append(f"LABEL_{label.key}_L .BYTE <{make_key_full(label.key)}")

    return high_lines, low_lines


def build_output() -> str:
    out: list[str] = []

    message_section = build_message_section()
    label_full_section = build_label_full_section()
    label_high_section, label_low_section = build_label_pointer_sections()

    out.extend(message_section)
    out.extend(label_full_section)
    out.extend(label_high_section)
    out.extend(label_low_section)

    return '\n'.join(out) + '\n'


def main() -> None:
    with open(ASM_FILE_NAME, 'w', encoding='utf-8') as file:
        file.write(build_output())


if __name__ == '__main__':
    main()

