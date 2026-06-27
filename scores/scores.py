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
    unicode: str
    asm_bytes: list[str] = field(default_factory=list)
    length: int = 0
    screen_row: int = -1
    screen_col: int = -1

    def __post_init__(self):
        self.asm_bytes = ascii_to_atari_hex(self.unicode)
        self.length = len(self.unicode)

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

@dataclass
class LabelPosition:
    """Represents a label's position on screen with its name, row, and column."""
    name: str
    screen_row: int
    screen_col: int

class LabelExtractor:
    """Extracts labels from ASCII art and returns their positions."""

    LABEL_PATTERN = re.compile(r'#(\w+)')

    def __init__(self, atariUnicodeArt_lines: list[str]):
        self.atariUnicodeArt_lines = atariUnicodeArt_lines

    def extract_labels(self) -> list[LabelPosition]:
        """
        Extract all labels from the ASCII art lines.
        Returns a list of LabelPosition objects containing name, row, and column.
        """
        labels = []

        for row_idx, line in enumerate(self.atariUnicodeArt_lines):
            for match in self.LABEL_PATTERN.finditer(line):
                label_name = match.group(1)
                col_idx = match.start()

                labels.append(LabelPosition(
                    name=label_name,
                    screen_row=row_idx,
                    screen_col=col_idx
                ))

        return labels


def getScreenAsciiArt() -> list[str]:
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
    " | ♥♣♦♠  | #GTT         #SGT  | ♥♣♦♠  | ",
    " └───────┴────────────────────┴───────┘ ",
  ]

  return lines

def replaceTemplate(orig, newt, idx):
    a = list(orig)
    t = list(newt)

    length = min(len(newt), len(orig))

    for i in range(length):
        if i + idx >= len(orig):
            break
        a[i + idx] = t[i]

    return "".join(a)

def getLabelText() -> TextCollection:
    """Define all labels with their display text."""

    label_collections = TextCollection()

    def add_it(it: LabelText | ScoreText):
        if isinstance(it, LabelText):
            label_collections.screenLabels.append(it)
        elif isinstance(it, ScoreText):
            label_collections.screenScores.append(it)
        else:
            raise ValueError(f"Unknown label type: {type(it)}")

    # Left column labels
    add_it(LabelText('L1C', 'Aces'))        # Left column labels

    add_it(ScoreText('S1C'))
    add_it(LabelText('L2C', 'Twos'))
    add_it(ScoreText('S2C'))
    add_it(LabelText('L3C', 'Threes'))
    add_it(ScoreText('S3C'))
    add_it(LabelText('L4C', 'Fours'))
    add_it(ScoreText('S4C'))
    add_it(LabelText('L5C', 'Fives'))
    add_it(ScoreText('S5C'))
    add_it(LabelText('L6C', 'Sixes'))
    add_it(ScoreText('S6C'))
    add_it(LabelText('LTS', 'Top Score'))
    add_it(ScoreText('STS'))
    add_it(LabelText('LTB', 'Upper Bonus'))
    add_it(ScoreText('STB'))
    add_it(LabelText('LUT', 'Upper Total'))
    add_it(ScoreText('SUT'))

    # Right column labels
    add_it(LabelText('L3K', '3 of a Kind'))
    add_it(ScoreText('S3K'))
    add_it(LabelText('L4K', '4 of a Kind'))
    add_it(ScoreText('S4K'))
    add_it(LabelText('LFH', 'Full House'))
    add_it(ScoreText('SFH'))
    add_it(LabelText('LSS', 'S Straight'))
    add_it(ScoreText('SSS'))
    add_it(LabelText('LLS', 'L Straight'))
    add_it(ScoreText('SLS'))
    add_it(LabelText('L5K', '5 of a Kind'))
    add_it(ScoreText('S5K'))
    add_it(LabelText('LCH', 'Chance'))
    add_it(ScoreText('SCH'))
    add_it(LabelText('L5B', '5K Bonus'))
    add_it(ScoreText('S5B'))
    add_it(LabelText('LLT', 'Lower Total'))
    add_it(ScoreText('SLT'))

    # Bottom labels
    add_it(LabelText('GTT', 'Grand Total'))
    add_it(ScoreText('SGT'))

    return label_collections


def getScreenFrame() -> TextCollection:
    atariUnicodeArt_lines = getScreenAsciiArt()

    ex = LabelExtractor(atariUnicodeArt_lines=atariUnicodeArt_lines)
    labelCollection = ex.extract_labels()

    labelTextInfo = getLabelText()

    combinedList = labelTextInfo.screenLabels + labelTextInfo.screenScores

    for li, label in enumerate(labelCollection):

        record = next((z for z in combinedList if z.key == label.name), None)

        if record:
            record.screen_col = label.screen_col
            record.screen_row = label.screen_row

        for ai, txt in enumerate(atariUnicodeArt_lines):
            if label.screen_row == ai:
                replacement = "." * (len(record.key) +1)

                # if isinstance(record, LabelText):
                #     replacement = record.unicode

                if record is None:
                  raise ValueError(f"Unknown screen placeholder #{label.name}")

                if label.screen_row < 0 or label.screen_col < 0:
                  raise ValueError(f"Label {label.key} was never placed")

                atariUnicodeArt_lines[ai] = replaceTemplate(txt, replacement, label.screen_col)

    atariUnicodeArt = "".join(atariUnicodeArt_lines)
    label = LabelText("MAIN", atariUnicodeArt)
    label.screen_col = 0
    label.screen_row = 0

    ret: TextCollection = TextCollection(screenFrame=label, screenLabels=labelTextInfo.screenLabels, screenScores=labelTextInfo.screenScores)

    return ret

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
    textCollection = getScreenFrame()

    with open(ASM_FILE_NAME, 'w', encoding='utf-8') as file:

        allLabels = textCollection.screenLabels + [textCollection.screenFrame]

        out = createLabelTextRegion("TITLE", allLabels)
        file.write("\n".join(out))


if __name__ == '__main__':
    main()
