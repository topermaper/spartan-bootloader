import spidev
import argparse
import logging
import json
import sys
import time
import RPi.GPIO



def parseArgs():
    parser = argparse.ArgumentParser(description='Loads user program to ADSP-21489 memory')

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
            default=logging.INFO
        )
    
    return parser.parse_args()



class DSPBootLoader(object):


    def __init__(self, program_file, cfg_file, log_level=logging.DEBUG):
        super()
        self.program_file = program_file
        self.cfg_file     = cfg_file


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
            self._pf_stream = bytes()
            with open(self.program_file,'rb') as pf:
                raw_file = pf.read()

            # A 0-255 range integer is converted to bit sequence: 45 --> 00101101
            # Bits are inverted: 00101101 > 10110100
            # Converted back to integer 10110100 --> 180
            m2l = lambda n: bytes([int('{:08b}'.format(n)[::-1], 2)])

            counter = 0
            for b in raw_file:
                print(counter)
                self._pf_stream += m2l(b)
                counter+=1


        except OSError:
            logging.error("Could not open/read program file {}".format(self.program_file))
            sys.exit(1)


    def loadProgram(self):

        try:
            spi_bus          = self._cfg['spi']['bus']
            spi_device       = self._cfg['spi']['device']
            spi_clock_speed  = self._cfg['spi']['clock_speed']

            reset = self._cfg['pin_mapping']['reset']
            cs    = self._cfg['pin_mapping']['cs']

            logging.info("Configurating bus SPI-{} with config file '{}'".format(str(spi_bus),self.cfg_file))
            spi = spidev.SpiDev(spi_bus, spi_device)

            # SPI mode 3 - b'11'
            # MSB - Clock is low high
            # LSB - Data sampled on the falling edge and shifted out on the raising edge
            spi.mode = self._cfg['spi']['mode']
            spi.max_speed_hz = spi_clock_speed

        except Exception as ex:
            logging.error("Could not initialize SPI: {}".format(ex))
            sys.exit(1)

        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setwarnings(False)
        RPi.GPIO.setup(reset, RPi.GPIO.OUT)
        RPi.GPIO.setup(cs, RPi.GPIO.OUT)

        # Start loading sequence

        RPi.GPIO.output(reset, 0)
        time.sleep(0.01)
        RPi.GPIO.output(reset, 1)
        time.sleep(0.01)
        RPi.GPIO.output(cs, 0)
        time.sleep(0.01)

        logging.info("Loading bytestream ...")

        start_time = time.time()

        # Send bytestream
        spi.writebytes2(self._pf_stream)

        end_time = time.time()

        logging.info("Bytestream loaded at {:.3f}Mhz in {:.3f} sec.".format(spi_clock_speed/1000000,end_time-start_time))
        sys.exit(0)


    def main(self):
        self.parseCfgFile()
        self.parseProgramFile()
        self.loadProgram()



if __name__ == "__main__":
    args = parseArgs()
    print(args.loglevel)
    logging.basicConfig(level=args.loglevel)

    bootloader = DSPBootLoader(program_file=args.program_file, cfg_file=args.cfg_file)
    bootloader.main()