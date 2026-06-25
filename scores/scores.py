#!/usr/bin/env python3

ASM_FILE_NAME = "strings.m65"

from dataclasses import dataclass
from typing import Optional

@dataclass
class Chrome:
    name: str
    col: int
    row: int
    txt: str


def get_sheet() -> list[Chrome]:
    sheet = [
        Chrome('L00', 0,  0, "-------------| FIVE DICE |------------"),
        Chrome('L01', 0,  1, "ACES       #1C##   | 3 OF KIND  #3K## "),
        Chrome('L02', 0,  2, "TWOS       #2C##   | 4 OF KIND  #4K## "),
        Chrome('L03', 0,  3, "THREES     #3C##   | FULL HOUSE #FH## "),
        Chrome('L04', 0,  4, "FOURS      #4C##   | S STRAIGHT #SS## "),
        Chrome('L05', 0,  5, "FIVES      #5C##   | L STRAIGHT #LS## "),
        Chrome('L06', 0,  6, "SIXES      #6C##   | 5 OF KIND  #5K## "),
        Chrome('L07', 0,  7, "TOP SCORE  #TS##   | CHANCE     #CH## "),
        Chrome('L08', 0,  8, "BONUS      #TB##   | 5K BONUS   #5B## "),
        Chrome('L09', 0,  9, "TOTAL      #UT##   | TOTAL      #LT## "),
        Chrome('L10', 0, 10, "          GRAND TOTAL  #GT##          "),
    ]
    return sheet

def get_sheet_for_screen() -> list[Chrome]:
    sheet = get_sheet();

    for line in sheet:
        txt = line.txt

        inchar: bool = False
        out = ''
        for char in line.txt:
            if char == ' ':
                inchar = False
            
            if char == '#':
                inchar = True

            if inchar == False:
                out = out + char;
            if inchar == True:
                out = out + "."

        line.txt = out

    return sheet

def convert_sheet_do_m65(sheet: list[Chrome]) -> list[str]:
    out = [ '.BYTE "' + line.txt + '",' for line in sheet]
    return out;


sheet = get_sheet_for_screen()
sheet2 = convert_sheet_do_m65(sheet)

with open(ASM_FILE_NAME, 'w') as file:
    file.write('\n'.join(sheet2))

print(sheet2)