#!/bin/bash

rm yahtzee.65o
rm scores/strings.m65

( cd scores/; ./scores.py )
#../code/atasm -xd2.atr -gfile.lst  ./yahtzee.m65 && ../code/atari800 yahtzee.65o
../code/atasm -xd2.atr ./yahtzee.m65 && ../code/atari800 yahtzee.65o

