import argparse
import logging
import json
import sys
import time
import RPi.GPIO
import pigpio
import signal
from multiprocessing import Process



def parseArgs():
    parser = argparse.ArgumentParser(description="Loads user program to ADSP-21489's")

    parser.add_argument('-p0', '--program_0',
        dest='program_file_0',
        required=False,
        default=False,
        type=str,
        help='File to load in DSP-0'
    )
    parser.add_argument('-p1', '--program_1',
        dest='program_file_1',
        required=False,
        default=False,
        type=str,
        help='File to load in DSP-1'
    )
    parser.add_argument('-p2', '--program_2',
        dest='program_file_2',
        required=False,
        default=False,
        type=str,
        help='File to load in DSP-2'
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

    def __init__(self, args):
        logging.basicConfig(format='%(asctime)s - DSPBOOT - %(message)s', level=args.loglevel)
        logging.info("Initializing ...")

        self.cfg_file = args.cfg_file
        self.args = args

        # BB_SPI_OPEN channels opened list
        self._cs_open = set()

    def parseCfgFile(self):
        try:
            logging.debug('Reading configuration file: {}'.format(self.cfg_file))
            with open(self.cfg_file) as cf:
                self._cfg = json.load(cf)
        except OSError:
            logging.error("Could not open/read config file {}".format(self.cfg_file))
            sys.exit(1)

    def resetDevices(self):
        # Reset is chained and affects all DSP's
        reset = self._cfg["dsp_reset"]

        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setwarnings(False)

        # set up GPIO output channel
        RPi.GPIO.setup(reset, RPi.GPIO.OUT)

        # Reset device
        RPi.GPIO.output(reset, 0)
        time.sleep(0.01)
        RPi.GPIO.output(reset, 1)
        time.sleep(0.01)


    def manage_ctrlC(self, *args):
        logging.debug("SIGINT received. Closing children processes")
        # Give 1 second so the children can finish
        time.sleep(1)
        # If you have multiple event processing processes, set each Event.
        self.process1.terminate()
        self.process2.terminate()

        logging.debug("Cleaning up GPIO's")
        RPi.GPIO.cleanup()

        sys.exit(0)

   
    def startMultiprocessing(self):

        self.resetDevices()

        try:
            self.process1 = Process(target=self.doSPI1, args=(self.args.program_file_0,))
            self.process2 = Process(target=self.doSPI2, args=([self.args.program_file_1, self.args.program_file_2],))

            # Manage Ctrl_C keyboard event 
            signal.signal(signal.SIGINT, self.manage_ctrlC)

            self.process1.start()
            self.process2.start()

            self.process1.join()
            self.process2.join()

        except Exception as e:
            logging.error("Something went wrong:{}".format(e))

        RPi.GPIO.cleanup()
        sys.exit(0)


    def doSPI1(self, program_file):
        logging.debug("SPI-1 thread started ...")
        if program_file != False:
            stream = self.parseProgramFile(program_file)
            self.loadProgramBitBanging(spi=str(1), cs=str(0), stream=stream)
        else:
            logging.info("Nothing to load in SPI-1 DSP")


    def doSPI2(self, program_files):
        logging.debug("SPI-2 thread started ...")

        self.stream = [False] * 2
        for i in range(len(program_files)):
            if program_files[i] != False:
                stream = self.parseProgramFile(program_files[i])
                self.loadProgramBitBanging(spi=str(2), cs=str(i), stream=stream)
            else:
                logging.info("Nothing to load in SPI-2 DSP")


    def parseProgramFile(self, program_file):

        try:
            logging.debug('Reading program file: {}'.format(program_file))

            with open(program_file,'rb') as pf:
                stream = pf.read()
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
                stream += m2l(b)
            '''
        except OSError:
            logging.error("Could not open/read program file {}".format(program_file))
            sys.exit(1)

        return stream


    def sigintHandler(self, *args):
        logging.debug("CTRL + C received - Cleaning up ...")

        for cs in self._cs_open:
            try:
                # It gets stuck in the following command.
                # I don't know why yet
                self.pi.bb_spi_close(cs)
                logging.debug("CS={} pigpio closed".format(cs))
            except Exception as e:
                pass

        self.pi.stop()
        logging.debug("pgpio stopped")


    def loadProgramBitBanging(self, spi, cs, stream):

        logging.info("Configuring bitbanging SPI-{} cs{}:".format(spi, cs))

        # Add handler for SIGINT signal
        signal.signal(signal.SIGINT, self.sigintHandler)

        self.pi = pigpio.pi()
        if not self.pi.connected:
            logging.error("pigpiod not connected")
            self.pi.stop()
            return

        try:
            baudrate    = self._cfg["spi"][spi]['baudrate']
            miso        = self._cfg["spi"][spi]['miso']
            mosi        = self._cfg["spi"][spi]['mosi']
            sclk        = self._cfg["spi"][spi]['sclk']
            buffer_size = self._cfg["spi"][spi]['buffer_size']
            cs          = self._cfg["spi"][spi]["cs"][cs]

            logging.info("\tbuffer size = {} bytes".format(buffer_size))
            logging.info("\tbaudrate    = {}".format(baudrate))
            logging.info("\tcs          = GPIO{}".format(cs))
            logging.info("\tmiso        = GPIO{}".format(miso))
            logging.info("\tmosi        = GPIO{}".format(mosi))
            logging.info("\tsclk        = GPIO{}".format(sclk))

            # If program is not closed properly connection could not be opened
            # We attempt to close previous connections so bootloader doesn't fail
            try:
                self.pi.bb_spi_close(cs)
                logging.warning("Previous bb_spi connection found CS={}. It has been closed.".format(cs))
            except Exception as e:
                pass

            # Use spi mode 3
            # http://abyz.me.uk/rpi/pigpio/python.html#bb_spi_open
            self.pi.bb_spi_open(
                CS   = cs,
                MISO = miso,
                MOSI = mosi,
                SCLK = sclk,
                baud = baudrate,
                spi_flags = 3
            )

            self._cs_open.add(cs)

        except Exception as ex:
            logging.error("Could not initialize SPI: {}".format(ex))
            return

        logging.info("Loading DSP program - {} bytes ...".format(len(stream)))

        start_time = time.time()

        # Send bytestream
        try:
            for i in range(0,len(stream),buffer_size):
                logging.debug("\tSending chunk {} - {}".format(str(i),str(min(i+buffer_size, len(stream)))))
                count, data = self.pi.bb_spi_xfer(cs, stream[i:i+buffer_size])
        except Exception as e:
            logging.error('Error loading data: {}'.format(e))
            self.pi.bb_spi_close(self._cs_open.pop())
            pi.stop()
            return

        end_time = time.time()
        logging.info("DSP program loaded at {} baud in {:.3f} sec.".format(baudrate,end_time-start_time))

        self.pi.bb_spi_close(self._cs_open.pop())
        self.pi.stop()


    def main(self):
        self.parseCfgFile()
        self.startMultiprocessing()
        sys.exit(0)


if __name__ == "__main__":
    args = parseArgs()

    bootloader = DSPBootLoader(args = args)
    bootloader.main()

