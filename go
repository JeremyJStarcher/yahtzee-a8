#!/bin/bash
set -e

cd venv
./runit
cd ..

rm -f yahtzee.65o
rm -f codegen/strings.m65
rm -f a8*

#../code/atasm -xd2.atr -g/tmp/file.lst  ./yahtzee.m65 && ../code/atari800 yahtzee.65o
./codegen/scores.py && ../code/atasm -xd2.atr -g/tmp/file.lst  ./yahtzee.m65 && ../code/atari800 yahtzee.65o

