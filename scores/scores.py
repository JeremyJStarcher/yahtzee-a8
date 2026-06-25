#!/usr/bin/env python3

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


from dataclasses import dataclass
from typing import Optional

@dataclass
class Chrome:
    name: str
    col: int
    row: int
    txt: str

@dataclass
class ScreenLabel:
    key: str
    value: str

def get_sheet_old() -> list[Chrome]:
    sheet = [
        Chrome('L00', 0,  0, " ┌────────────┤ FIVE DICE ├───────────┐ "),
        Chrome('L01', 0,  1, " |ACES       #S1C#  |3 OF KIND  #S3K# | "),
        Chrome('L02', 0,  2, " |TWOS       #S2C#  |4 OF KIND  #S4K# | "),
        Chrome('L03', 0,  3, " |THREES     #S3C#  |FULL HOUSE #SFH# | "),
        Chrome('L04', 0,  4, " |FOURS      #S4C#  |S STRAIGHT #SSS# | "),
        Chrome('L05', 0,  5, " |FIVES      #S5C#  |L STRAIGHT #SLS# | "),
        Chrome('L06', 0,  6, " |SIXES      #S6C#  |5 OF KIND  #S5K# | "),
        Chrome('L07', 0,  7, " |TOP SCORE  #STS#  |CHANCE     #SCH# | "),
        Chrome('L08', 0,  8, " |BONUS      #STB#  |5K BONUS   #S5B# | "),
        Chrome('L09', 0,  9, " |TOTAL      #SUT#  |TOTAL      #SLT# | "),
        Chrome('L09', 0,  9, " ├───────┬──────────┴─────────┬───────┤ "),
        Chrome('L10', 0, 10, " | ♥♣♦♠  | Grand Total  #GT## | ␛↑␛↓␛←␛→  | "),
        Chrome('L09', 0,  9, " └───────┴────────────────────┴───────┘ "),
    ]
    return sheet

def get_sheet() -> list[Chrome]:
    sheet = [
        Chrome('L00', 0,  0, " ┌────────────┤ FIVE DICE ├───────────┐ "),
        Chrome('L01', 0,  1, " |#L1C######  #S1C# |#L3K###### #S3K# | "),
        Chrome('L02', 0,  2, " |#L2C######  #S2C# |#L4K###### #S4K# | "),
        Chrome('L03', 0,  3, " |#L3C######  #S3C# |#LFH###### #SFH# | "),
        Chrome('L04', 0,  4, " |#L4C######  #S4C# |#LSS###### #SSS# | "),
        Chrome('L05', 0,  5, " |#L5C######  #S5C# |#LLS###### #SLS# | "),
        Chrome('L06', 0,  6, " |#L6C######  #S6C# |#L5K###### #S5K# | "),
        Chrome('L07', 0,  7, " |#LTS######  #STS# |#LCH###### #SCH# | "),
        Chrome('L08', 0,  8, " |#LTB######  #STB# |#L5B###### #S5B# | "),
        Chrome('L09', 0,  9, " |#LUT######  #SUT# |#LLT###### #SLT# | "),
        Chrome('L09', 0,  9, " ├───────┬──────────┴─────────┬───────┤ "),
        Chrome('L10', 0, 10, " | ♥♣♦♠  | #GTT#######  #SGT# | ␛↑␛↓␛←␛→  | "),
        Chrome('L09', 0,  9, " └───────┴────────────────────┴───────┘ "),
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
        ScreenLabel('LSS', 'Small Straight'),
        ScreenLabel('SSS', num),
        ScreenLabel('LLS', 'Large Straight'),
        ScreenLabel('SLS', num),
        ScreenLabel('L5K', '5 of a Kind'),
        ScreenLabel('S5K', num),
        ScreenLabel('LCH', 'Chance'),
        ScreenLabel('SCH', num),
        ScreenLabel('L5B', '5 Kind Bonus'),
        ScreenLabel('S5B', num),
        ScreenLabel('LLT', 'Lower Total'),
        ScreenLabel('SLT', num),

        ScreenLabel('GTT', 'Grand Total'),
        ScreenLabel('SGT', num),
    ]
    return out;

def get_sheet_for_screen() -> list[Chrome]:
    sheet = get_sheet();

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

            try:
                idx = ATASCII.index(char)
            except ValueError:
                print(f"Warning: character '{char}' is not ATASCII")


            hex = '$' + f"{idx:02X}"

            out.append(hex)
        

        line.txt = out

    return sheet

def convert_sheet_do_m65(sheet: list[Chrome]) -> list[str]:
    out = []
    for line in sheet:
        txt = ",".join(line.txt)
        out.append(" .BYTE " + txt)

    return out;

sheet = get_sheet_for_screen()
sheet2 = convert_sheet_do_m65(sheet)

labels = get_labels()

with open(ASM_FILE_NAME, 'w') as file:
    file.write('MESSAGE\n')
    file.write('\n'.join(sheet2))
    file.write('\n')
    file.write('MESSAGE_END\n')
    file.write('MESSAGE_LEN = MESSAGE_END - MESSAGE\n\n')

# print(sheet2)

