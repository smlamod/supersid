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

from datetime import datetime, timedelta
import numpy

class Qdc():
    def __init__(self, controller, read_file=None):
        self.controller = controller
        self.config = controller.config
        #self.sid_file = SidFile(sid_params = self.config)
        self._max_qdc = 3
        self._max_days = 30
        self.load_files()

    def load_pickedfiles(self, filelist):
        """ Calculates QDC from given file list """
        params = self.controller.logger.sid_file.sid_params
        qdc_index = 0

        if type(filelist) is str:
            if filelist.find(',') >= 0:  # file1,file2,...,fileN given as script argument
                filelist = filelist.split(",")
            else:
                filelist = (filelist, )

        inData = [None] * len(filelist)

        for sid_file in filelist:
            try: 
                with open(sid_file, "rt") as fin:
                    lines = fin.readlines()
            except IOError:
                return False

            inData[qdc_index] = numpy.loadtxt(lines, dtype=float, comments='#', delimiter=",").transpose()
            inData[qdc_index][inData[qdc_index] == 0.0] = numpy.nan
            print ("Reading {0} ".format(sid_file))
            qdc_index += 1
            
        self.qdcData = numpy.nanmean(inData, axis=0)
        print("QDC Loaded")
        

    def load_files(self):
        """ Reads next available sidfile """
        params = self.controller.logger.sid_file.sid_params
        delta_day = 0
        qdc_index = 0
        inData = [None] * self._max_qdc


        while qdc_index < self._max_qdc:
            delta_day += 1
            d = datetime.utcnow() - timedelta(days=delta_day)
            fstr = params.data_path + params['site_name'] + '{:_%Y-%m-%d.csv}'.format(d)
            try: 
                with open(fstr, "rt") as fin:
                    lines = fin.readlines()
            except IOError:                
                #print ("Skip:", fstr)                
                if delta_day > self._max_days:
                    print ("Could not compute for qdc")
                    inData = None
                    return
                else:
                    continue
            inData[qdc_index] = numpy.loadtxt(lines, dtype=float, comments='#', delimiter=",").transpose()
            inData[qdc_index][inData[qdc_index] == 0.0] = numpy.nan
            print ("Reading {0} ".format(fstr))
            qdc_index += 1
                
        self.qdcData = numpy.nanmean(inData, axis=0)
        print("QDC Loaded")
        