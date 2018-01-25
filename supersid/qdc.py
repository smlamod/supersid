# AJS
#
# 20180102
# Read files, Get signal strength values, Create qdc file, Average strength values
from __future__ import print_function   # use the new Python 3 'print' function
from os import path
try:
    input = raw_input  # this is Python 2 raw_input now to be used like input in Python 3
except NameError:
    pass    # already Python 3
from time import gmtime, strftime

from sidfile import SidFile
from config import FILTERED, RAW, CALL_SIGN, FREQUENCY, SID_FORMAT, SUPERSID_FORMAT


class Qdc():
    def __init__(self, controller, read_file=None):
        self.controller = controller
        self.config = controller.config
        self.sid_file = SidFile(sid_params = self.config)

    def qdc_format(self, stations, filename='', log_type=FILTERED, extended = False):
        """ One file per station. """
        filenames = []
        for station in stations:       
            my_filename = self.config.data_path + (filename or self.sid_file.get_sid_filename(station['call_sign']))
            filenames.append(my_filename)
            self.sid_file.write_data_sid(station, my_filename, log_type, extended=extended, bema_wing=self.config["bema_wing"])
        return filenames