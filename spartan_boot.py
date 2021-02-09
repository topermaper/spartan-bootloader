import spidev
import argparse
import logging
import json
import sys
import time
import binascii
import RPi.GPIO



def parseArgs():
    parser = argparse.ArgumentParser(description='Loads user program to XC6SLX25 memory')
    parser.add_argument(
        '-s', '--clock_speed',
        dest='clock_speed',
        type=int, default=1000000,
        help='Clock speed Hz'
    )
    parser.add_argument('-p', '--programfile',
        dest='program_file',
        required=True,
        type=str,
        help='File to load'
    )
    parser.add_argument('-c', '--cfgfile',
        dest='cfg_file',
        required=True,
        type=str,
        help='File to load'
    )
    parser.add_argument(
            '-d', '--debug',
            help="Print lots of debugging statements",
            action="store_const",
            dest="loglevel",
            const=logging.DEBUG,
            default=logging.WARNING,
        )
    parser.add_argument(
            '-v', '--verbose',
            help="Be verbose",
            action="store_const",
            dest="loglevel",
            const=logging.INFO,
        )
    
    return parser.parse_args()



class SpartanBootLoader(object):


    def __init__(self, program_file, cfg_file, log_level='WARNING'):
        super()
        self.program_file = program_file
        self.cfg_file     = cfg_file

        logging.basicConfig(level=log_level)


    def parseCfgFile(self):
        try:
            logging.debug('Reading configuration file: {}'.format(self.cfg_file))
            with open(self.cfg_file) as cf:
                self._cfg = json.load(cf)
        except OSError:
            logging.error("Could not open/read config file {}".format(self.cfg_file))
            sys.exit(1)


    def parseProgramFile(self):
        try:
            logging.debug('Reading program file: {}'.format(self.program_file))
            with open(self.program_file,'rb') as pf:
                self._pf_stream = bytearray(pf.read())
        except OSError:
            logging.error("Could not open/read program file {}".format(self.program_file))
            sys.exit(1)


    def loadProgram(self):

        try:
            spi_bus          = self._cfg['spi']['bus']
            spi_device       = self._cfg['spi']['device']
            spi_clock_speed  = self._cfg['spi']['clock_speed']

            init_b    = self._cfg['pin_mapping']['init_b']
            program_b = self._cfg['pin_mapping']['program_b']

            logging.debug("Configurating bus SPI-{}".format(str(spi_bus)))

            # We may have to trick the driver, https://www.raspberrypi.org/forums/viewtopic.php?t=178629
            spi = spidev.SpiDev(spi_bus, spi_device)

            # SPI mode
            # MSB - Clock is low when idle
            # LSB - Data sampled on the raising edge and shifted out on the falling edge
            spi.mode = 0b00
            spi.max_speed_hz = spi_clock_speed

        except Exception as ex:
            logging.error("Could not initialize SPI: {}".format(ex))
            sys.exit(1)

        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setwarnings(False)
        RPi.GPIO.setup(init_b, RPi.GPIO.OUT)
        RPi.GPIO.setup(program_b, RPi.GPIO.OUT)

        # Start loading sequence
        RPi.GPIO.output(program_b, 0)
        time.sleep(0.01)
        RPi.GPIO.output(init_b, 0)
        time.sleep(0.01)
        RPi.GPIO.output(program_b, 1)
        time.sleep(0.01)
        RPi.GPIO.output(init_b, 1)
        time.sleep(0.01)

        logging.debug("Loading bytestream --> {} <--".format(binascii.hexlify(self._pf_stream)))

        # Send bytestream
        spi.writebytes2(self._pf_stream)

        logging.info("Bytestream loaded")
        sys.exit(0)


    def main(self):
        self.parseCfgFile()
        self.parseProgramFile()
        self.loadProgram()



if __name__ == "__main__":
    # Default log level
    args = parseArgs()
    bootloader = SpartanBootLoader(program_file=args.program_file, cfg_file=args.cfg_file, log_level=args.loglevel)
    bootloader.main()