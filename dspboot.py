import spidev
import argparse
import logging
import json
import sys
import time
import RPi.GPIO
import pigpio

CE0=5
CE1=6
MISO=13
MOSI=19
SCLK=12

#|  17 | OUT  | High  | SPI1_CE1_DSP   |
#|  18 | OUT  | High  | SPI1_CE0_FPGA  |
#|  19 | ALT4 | Low   | SPI1_CE1_MISO  |
#|  20 | ALT4 | Low   | SPI1_CE1_MOSI  |
#|  21 | ALT4 | Low   | SPI1_CE1_SCLK  |







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

            self._pf_stream = raw_file

            '''
            # A 0-255 range integer is converted to bit sequence: 45 --> 00101101
            # Bits are inverted: 00101101 > 10110100
            # Converted back to integer 10110100 --> 180
            m2l = lambda n: bytes([int('{:08b}'.format(n)[::-1], 2)])

            counter = 0
            for b in raw_file:
                print(counter)
                self._pf_stream += m2l(b)
                counter+=1
            '''


        except OSError:
            logging.error("Could not open/read program file {}".format(self.program_file))
            sys.exit(1)



    def loadProgramSpiDev(self):

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


    def loadProgramBitBanging(self):

        logging.info("Configurating bitbanging SPI with config file '{}':".format(self.cfg_file))

        try:
            baudrate = self._cfg['spi']['baudrate']
            cs       = self._cfg['pin_mapping']['cs']
            reset    = self._cfg['pin_mapping']['reset']
            miso     = self._cfg['pin_mapping']['miso']
            mosi     = self._cfg['pin_mapping']['mosi']
            sclk     = self._cfg['pin_mapping']['sclk']
            print(1)

            logging.info("\tbaudrate = {}".format(baudrate))
            logging.info("\tcs       = GPIO{}".format(cs))
            logging.info("\treset    = GPIO{}".format(reset))
            logging.info("\tmiso     = GPIO{}".format(miso))
            logging.info("\tmosi     = GPIO{}".format(mosi))
            logging.info("\tsclk     = GPIO{}".format(sclk))
            
            pi = pigpio.pi()
            print(2)
            if not pi.connected:
                exit()
            print(3)

            pi.bb_spi_open(
                CS   = cs,
                MISO = miso,
                MOSI = mosi,
                SCLK = sclk,
                baud = baudrate,
                spi_flags = 3
            )
            print(4)
        except Exception as ex:
            logging.error("Could not initialize SPI: {}".format(ex))
            pi.bb_spi_close(cs)
            sys.exit(1)

        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setwarnings(False)
        RPi.GPIO.setup(reset, RPi.GPIO.OUT)
        #RPi.GPIO.setup(cs, RPi.GPIO.OUT)

        # Start loading sequence
        RPi.GPIO.output(reset, 0)
        time.sleep(0.05)
        RPi.GPIO.output(reset, 1)
        time.sleep(0.05)
        #RPi.GPIO.output(cs, 0)
        time.sleep(0.05)

        logging.info("Loading bytestream ...")

        start_time = time.time()

        print(len(self._pf_stream))
        print(type(self._pf_stream))
        stream = list(self._pf_stream)

        print(stream[:100])

        # Send bytestream
        buffer_size = 4096

        #count, data = pi.bb_spi_xfer(self._cfg['pin_mapping']['cs'], stream[:4096]) 

        for i in range(0,len(stream),buffer_size):
            print("sending chunk {} - {}".format(str(i),str(i+buffer_size)))
            count, data = pi.bb_spi_xfer(self._cfg['pin_mapping']['cs'], stream[i:i+buffer_size]) 

        end_time = time.time()

        logging.info("Bytestream loaded at {} baud in {:.3f} sec.".format(baudrate,end_time-start_time))


        pi.bb_spi_close(self._cfg['pin_mapping']['cs'])
        pi.stop()

        sys.exit(0)



    def main(self):
        self.parseCfgFile()
        self.parseProgramFile()
        #self.loadProgramSpiDev()
        self.loadProgramBitBanging()



if __name__ == "__main__":
    args = parseArgs()
    logging.basicConfig(level=args.loglevel)

    bootloader = DSPBootLoader(program_file=args.program_file, cfg_file=args.cfg_file)
    bootloader.main()

