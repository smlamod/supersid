#!/usr/bin/python
""" supersid.py
    version 1.3
    Segregation MVC

    SuperSID class is the Controller.
    First, it reads the .cfg file specified on the command line (unique accepted parameter) or in ../Config
    Then it creates its necessary elements:
    - Model: Logger, Sampler
    - Viewer: Viewer
    using the parameters read in the .cfg file
    Finally, it launches an infinite loop to wait for events:
    - User input (graphic or text)
    - Timer for sampling
    - <still missing> network management with client-server protocol

"""
from __future__ import print_function   # use the new Python 3 'print' function
import os.path
import argparse

# matplotlib ONLY used in Controller for its PSD function, not for any graphic
from matplotlib.mlab import psd as mlab_psd

# SuperSID Package classes
from sidtimer import SidTimer
from sampler import Sampler
from config import Config
from logger import Logger
from datetime import datetime

from qdc import Qdc
from siddetect import Detect

    # @s SuperSid() is startup class
    # Config Class is used to Parse the cfg file
    # Loggger Class 

class SuperSID():
    '''
    This is the main class which creates all other objects.
    In CMV pattern, this is the Controller.
    '''
    running = False  # class attribute to indicate if the SID application is running

    def __init__(self, config_file='', read_file=None):
        self.version = "EG 1.4 20150801"
        self.timer = None
        self.sampler = None
        self.viewer = None
        
        # Read Config file here
        print(datetime.utcnow())
        print("Reading supersid.cfg ...", end='')
        # this script accepts a .cfg file as optional argument else we default
        # so that the "historical location" or the local path are explored
        self.config = Config(config_file or "supersid.cfg")
        # once the .cfg read, some sanity checks are necessary
        self.config.supersid_check()
        if not self.config.config_ok:
            print("ERROR:", self.config.config_err)
            exit(1)
        else:
            print(self.config.filenames) # good for debugging: what .cfg file(s) were actually read
        self.config["supersid_version"] = self.version

        # Create Logger - Logger will read an existing file if specified as -r|--read script argument
        self.logger = Logger(self, read_file)
        if 'utc_starttime' not in self.config:
            self.config['utc_starttime'] = self.logger.sid_file.sid_params["utc_starttime"]


        #S Calculate Quiet Day curves - Will read applicable files to be averaged
        self.qdc = Qdc(self)
        self.detect = Detect(self)

        # Create the viewer based on the .cfg specification (or set default):
        # Note: the list of Viewers can be extended provided they implement the same interface
        if self.config['viewer'] == 'wx':
            # GUI Frame to display real-time VLF Spectrum based on wxPython
            # # special case: 'wx' module might not be installed (text mode only) nor even available (python 3)
            try:
                from wxsidviewer import wxSidViewer
                self.viewer = wxSidViewer(self)
                wx_imported = True
            except ImportError:
                print("'wx' module not imported.")
                wx_imported = False
        elif self.config['viewer'] == 'tk':
            # GUI Frame to display real-time VLF Spectrum based on tkinter (python 2 and 3)
            from tksidviewer import tkSidViewer
            self.viewer = tkSidViewer(self)
        elif self.config['viewer'] == 'text':
            # Lighter text version a.k.a. "console mode"
            from textsidviewer import textSidViewer
            self.viewer = textSidViewer(self)
        else:
            print("ERROR: Unknown viewer", self.config['viewer'])
            exit(2)

        # Assign desired psd function for calculation after capture
        # currently: using matplotlib's psd
        if (self.config['viewer'] == 'wx' and wx_imported) or self.config['viewer'] == 'tk':
            self.psd = self.viewer.get_psd  # calculate psd and draw result in one call
        else:
            self.psd = mlab_psd             # calculation only

        # calculate Stations' buffer_size
        self.buffer_size = int(24*60*60 / self.config['log_interval'])

        # Create Sampler to collect audio buffer (sound card or other server)
        self.sampler = Sampler(self, audio_sampling_rate = self.config['audio_sampling_rate'], NFFT = 1024);
        if not self.sampler.sampler_ok:
            self.close()
            exit(3)
        else:
            self.sampler.set_monitored_frequencies(self.config.stations);

        # Link the logger.sid_file.data buffers to the config.stations
        for ibuffer, station  in enumerate(self.config.stations):
            station['raw_buffer'] =  self.logger.sid_file.data[ibuffer]

        # Create Timer
        self.viewer.status_display("Waiting for Timer ... ")
        self.timer = SidTimer(self.config['log_interval'], self.on_timer)


    def clear_all_data_buffers(self):
        """Clear the current memory buffers and pass to the next day"""
        self.logger.sid_file.clear_buffer(next_day = True)

    def on_timer(self):
        """Callback function triggered by SidTimer every 'log_interval' seconds"""
        # current_index is the position in the buffer calculated from current UTC time
        current_index = self.timer.data_index
        utc_now = self.timer.utc_now

        # Get new data and pass them to the View
        message = "%s  [%d]  Capturing data..." % (self.timer.get_utc_now(), current_index)
        self.viewer.status_display(message, level=1)
        signal_strengths = []
        try:
            data = self.sampler.capture_1sec()  # return a list of 1 second signal strength
            Pxx, freqs = self.psd(data, self.sampler.NFFT, self.sampler.audio_sampling_rate)
            
            self.Pxx = Pxx
            self.freqs = freqs

            for binSample in self.sampler.monitored_bins:
                signal_strengths.append(Pxx[binSample])
        except IndexError as idxerr:
            print("Index Error:", idxerr)
            print("Data len:", len(data))
        except TypeError as err_te:
            print("Warning:", err_te)

        # ensure that one thread at the time accesses the sid_file's' buffers
        with self.timer.lock:
            # do we need to save some files (hourly) or switch to a new day?
            if self.timer.utc_now.minute == 0 and self.timer.utc_now.second < self.config['log_interval']:
                if self.config['hourly_save'] == 'YES':
                    fileName = "hourly_current_buffers.raw.ext.%s.csv" % (self.logger.sid_file.sid_params['utc_starttime'][:10])
                    self.save_current_buffers(filename=fileName, log_type='raw', log_format='supersid_extended')
                # a new day!
                if self.timer.utc_now.hour == 0:
                    # use log_type and log_format(s) requested by the user in the .cfg
                    for log_format in self.config['log_format'].split(','):
                        self.save_current_buffers(log_type=self.config['log_type'], log_format=log_format)
                    self.clear_all_data_buffers()

                    #S save todays data as yesterday
                    #self.qdc.yesterday = self.logger.sid_file.data
                    
                    #S calculate new qdc curve
                    self.qdc.load_files()

                    #S initialize limits
                    self.detect.limit_alloc()
                    self.viewer.axes2.cla()
            
            #S save latest buffer to detect window
            self.detect.window_append(signal_strengths)            
            self.detect.compute_limits(current_index)

            # Save signal strengths into memory buffers ; prepare message for status bar
            message = self.timer.get_utc_now() + "  [%d]  " % current_index
            for station, strength in zip(self.config.stations, signal_strengths):
                station['raw_buffer'][current_index] = strength
                message +=  station['call_sign'] + "=%f " % strength
            self.logger.sid_file.timestamp[current_index] = utc_now

        # end of this thread/need to handle to View to display captured data & message
        # print(data[19800])
        self.viewer.status_display(message, level=2)

    def save_current_buffers(self, filename='', log_type='raw', log_format = 'both'):
        ''' Save buffer data from logger.sid_file

            log_type = raw or filtered
            log_format = sid_format|sid_extended|supersid_format|supersid_extended|both|both_extended'''
        filenames = []
        if log_format.startswith('both') or log_format.startswith('sid'):
            fnames = self.logger.log_sid_format(self.config.stations, '', log_type=log_type, extended=log_format.endswith('extended')) # filename is '' to ensure one file per station
            filenames += fnames
        if log_format.startswith('both') or log_format.startswith('supersid'):
            fnames = self.logger.log_supersid_format(self.config.stations, filename, log_type=log_type, extended=log_format.endswith('extended'))
            filenames += fnames
        return filenames

    def on_close(self):
        self.close()

    def run(self, wx_app = None):
        """Start the application as infinite loop accordingly to need"""
        self.__class__.running = True
        self.viewer.run()

    def close(self):
        """Call all necessary stop/close functions of children objects"""
        self.__class__.running = False
        if self.sampler:
            self.sampler.close()
        if self.timer:
            self.timer.stop()
        if self.viewer:
            self.viewer.close()

    def about_app(self):
        """return a text indicating various information on the app, incl, versions"""
        msg = """This program is designed to detect Sudden Ionosphere Disturbances (SID), \
which are caused by a blast of intense X-ray radiation when there is a Solar Flare on the Sun.\n\n""" + \
            "Controller: " + self.version + "\n" +  \
            "Sampler: " + self.sampler.version  + "\n"  \
            "Timer: " + self.timer.version  + "\n"  \
            "Config: " + self.config.version  + "\n"  \
            "Logger: " + self.logger.version  + "\n"  \
            "Sidfile: " + self.logger.sid_file.version  + "\n" + \
            "Viewer: " + self.viewer.version  + "\n"  + \
            "\n\nAuthor: Eric Gibert  ericgibert@yahoo.fr" +  \
            "\n\nVisit http://solar-center.stanford.edu/SID/sidmonitor/ for more information."
        return msg


#-------------------------------------------------------------------------------
def exist_file(x):
    """
    'Type' for argparse - checks that file exists but does not open.
    """
    if not os.path.isfile(x):
        raise argparse.ArgumentError("{0} does not exist".format(x))
    return x

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--read", dest="filename", required=False, type=exist_file,
                        help="Read raw file and continue recording")
    parser.add_argument('config_file', nargs='?', default='')
    args, unk = parser.parse_known_args()

    sid = SuperSID(config_file=args.config_file, read_file=args.filename)
    #sid = SuperSID("../Config/supersid.cfg", "../Data/MIT-PH_2018-07-24.csv")
    sid.run()
    sid.close()



