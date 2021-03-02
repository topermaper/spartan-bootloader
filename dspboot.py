import argparse
import logging
import json
import sys
import time
import RPi.GPIO
import pigpio



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
        logging.basicConfig(format='DSPBOOT %(asctime)s %(message)s',level=args.loglevel)
        logging.info("Initializing ...")
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

            with open(self.program_file,'rb') as pf:
                self._stream = pf.read()

            # DSP program needs bytes to be inverted before sending them
            #
            # A 0-255 integer representing a byte is converted to bit sequence: 45 --> 00101101
            # Bits are inverted: 00101101 > 10110100
            # Converted back to integer 10110100 --> 180
            # This can be done with the following commented code but it's slow
            # so it will be done during the build
            '''   
            m2l = lambda n: bytes([int('{:08b}'.format(n)[::-1], 2)])

            for b in raw_stream:
                self._stream += m2l(b)
            '''

        except OSError:
            logging.error("Could not open/read program file {}".format(self.program_file))
            sys.exit(1)


    def loadProgramBitBanging(self):

        logging.info("Configuring bitbanging SPI with config file '{}':".format(self.cfg_file))

        try:
            baudrate    = self._cfg['spi']['baudrate']
            cs          = self._cfg['pin_mapping']['cs']
            reset       = self._cfg['pin_mapping']['reset']
            miso        = self._cfg['pin_mapping']['miso']
            mosi        = self._cfg['pin_mapping']['mosi']
            sclk        = self._cfg['pin_mapping']['sclk']
            buffer_size = self._cfg['spi']['buffer_size']

            logging.info("\tbuffer size = {} bytes".format(buffer_size))
            logging.info("\tbaudrate    = {}".format(baudrate))
            logging.info("\tcs          = GPIO{}".format(cs))
            logging.info("\treset       = GPIO{}".format(reset))
            logging.info("\tmiso        = GPIO{}".format(miso))
            logging.info("\tmosi        = GPIO{}".format(mosi))
            logging.info("\tsclk        = GPIO{}".format(sclk))

            
            pi = pigpio.pi()

            if not pi.connected:
                sys.exit(1)

            # Use spi mode 3
            # http://abyz.me.uk/rpi/pigpio/python.html#bb_spi_open
            pi.bb_spi_open(
                CS   = cs,
                MISO = miso,
                MOSI = mosi,
                SCLK = sclk,
                baud = baudrate,
                spi_flags = 3
            )

        except Exception as ex:
            logging.error("Could not initialize SPI: {}".format(ex))
            sys.exit(1)

        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setwarnings(False)
        RPi.GPIO.setup(reset, RPi.GPIO.OUT)

        # Reset device
        RPi.GPIO.output(reset, 0)
        time.sleep(0.01)
        RPi.GPIO.output(reset, 1)
        time.sleep(0.01)

        logging.info("Loading DSP program - {} bytes ...".format(len(self._stream)))

        start_time = time.time()

        # Send bytestream
        buffer_size = self._cfg['spi']['buffer_size']

        try:
            for i in range(0,len(self._stream),buffer_size):
                logging.debug("\tSending chunk {} - {}".format(str(i),str(min(i+buffer_size, len(self._stream)))))
                count, data = pi.bb_spi_xfer(cs, self._stream[i:i+buffer_size])
        except:
            pi.bb_spi_close(cs)
            pi.stop()
            sys.exit(1)

        end_time = time.time()

        logging.info("DSP program loaded at {} baud in {:.3f} sec.".format(baudrate,end_time-start_time))

        pi.bb_spi_close(cs)
        pi.stop()

        sys.exit(0)


    def main(self):
        self.parseCfgFile()
        self.parseProgramFile()
        self.loadProgramBitBanging()


if __name__ == "__main__":
    args = parseArgs()

    bootloader = DSPBootLoader(program_file=args.program_file, cfg_file=args.cfg_file)
    bootloader.main()

