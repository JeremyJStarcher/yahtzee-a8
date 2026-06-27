#!/bin/bash

rm yahtzee.65o
rm scores/strings.m65



./scores/scores.py && ../code/atasm -xd2.atr -g/tmp/file.lst  ./yahtzee.m65 && ../code/atari800 yahtzee.65o

