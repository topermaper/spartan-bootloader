#!/bin/bash

BOOTLOADER_PATH=/home/pi/dev/spartan-bootloader

python3 spartanboot.py -p ${BOOTLOADER_PATH}/bin_examples/FPGA-clock50mhz.bin -c spartan.json --debug
python3 dspboot.py -p ${BOOTLOADER_PATH}/bin_examples/DSP-LED-blink5.dat -c dsp.json --debug