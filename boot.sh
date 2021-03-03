#!/bin/bash

BOOTLOADER_PATH=/home/pi/dev/spartan-bootloader

python3 spartanboot.py -p ${BOOTLOADER_PATH}/bin_examples/led_alldsp_clock.bin -c spartan.json --debug
python3 dspboot.py -c dsp.json -p0 bin_examples/DSP-LED-blink5.dat -p1 bin_examples/DSP-LED-blink5.dat -p2 bin_examples/DSP-LED-blink5.dat --debug