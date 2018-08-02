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
from datetime import datetime, timedelta
import numpy
import sys

class Qdc():
    def __init__(self, controller, read_file=None):
        self.controller = controller
        self.config = controller.config
        self.data_path = '..\\aData\\'
        self.is_ok = False
        self._max_qdc = 3
        self._max_days = 30
        self.qdays = []

        self.load_files()
        

    def load_pickedfiles(self, filelist):
        """ Calculates QDC from given file list """
        params = self.controller.logger.sid_file.sid_params
        qdc_index = 0
        inData = []
        inDays = []

        #if type(filelist) is str:
        #    if filelist.find(',') >= 0:  # file1,file2,...,fileN given as script argument
        #        filelist = filelist.split(",")
        #    else:
        #        filelist = (filelist, )        

        for fstr in filelist:
            try: 
                with open(fstr, "rt") as fin:
                    lines = fin.readlines()
                    if not self.is_ok_station(fstr,lines):
                        continue                       
                    inDays.append(self.parse_utcstart(lines))

            except IOError:
                print ("- Could not compute qdc")
                inData = None
                self.is_ok = False
                return 

            inData.append(numpy.loadtxt(lines, dtype=float, comments='#', delimiter=",").transpose())
            inData[qdc_index][inData[qdc_index] == 0.0] = numpy.nan
            qdc_index += 1
           
        self.qdays = inDays
        self.get_avg(inData)        

    def load_files(self):
        """ Reads next available sidfile """
        params = self.controller.logger.sid_file.sid_params
        delta_day = 0
        qdc_index = 0
        inData = []
        inDays = []

        while qdc_index < self._max_qdc:
            delta_day += 1
            d = datetime.utcnow() - timedelta(days=delta_day)
            fstr = params.data_path + params['site_name'] + '{:_%Y-%m-%d.csv}'.format(d)
            try: 
                with open(fstr, "rt") as fin:                    
                    lines = fin.readlines()                
                    if not self.is_ok_station(fstr,lines):
                        continue                       
                    inDays.append('{:%Y-%m-%d}'.format(d))
            except IOError:                
                #print ("Skip:", fstr)                
                if delta_day > self._max_days:
                    print ("- Could not compute for qdc: expects {0} supersid files not older than {1} days".format(self._max_qdc,self._max_days))
                    inData = None
                    self.is_ok = False
                    return
                else:
                    continue
            inData.append(numpy.loadtxt(lines, dtype=float, comments='#', delimiter=",").transpose())
            inData[qdc_index][inData[qdc_index] == 0.0] = numpy.nan            
            qdc_index += 1
         
        self.qdays = inDays
        self.get_avg(inData)

    def parse_utcstart(self,lines):
        """ Fetches the UTC startime from lines """

        temp_d = lines[9]
        temp_d = temp_d.split('=',1)[-1]
        temp_d = temp_d.split(' ',1)[-1]
        temp_d = temp_d.split(' ',1)[0]
        return temp_d

    def is_ok_station(self,fstr,lines):
        """ Checks if read in sidfiles are valid """

        sys.stdout.write ("Reading {0}".format(fstr),)
        #Lines[13] has station list
        temp_station = lines[13]
        temp_station = temp_station.replace(" ", "")
        temp_station = temp_station.replace("\n", "")
        temp_station = temp_station.split('=',1)[-1]
        #temp_station = temp_station.split(',')
        if temp_station != self.controller.config['stations']:
            sys.stdout.write ("[\tBAD] inconsistent stations\n")
            return False         
        else:
            sys.stdout.write ("\t[OK]\n")
            return True

    def get_avg(self,inData):
        """ Calculates the nanmean of read supersid file data """
        self.qdcData = numpy.nanmean(inData, axis=0)        
        self.is_ok = True
        print("- QDC Loaded")    


    def write_qdc(self,filename):
        """ Writes computed QDC to disk """
        try:
            filename = self.data_path + filename
            sys.stdout.write("Saving  %s" % filename,)
            with open(filename,'wt') as fout:
                print(self.controller.logger.sid_file.create_header(True,'filtered'),file=fout,end="")
                print('# Days Averaged = ' + ','.join(self.qdays), file=fout, end="")
                for row in numpy.transpose(self.qdcData):
                    floats_as_strings = ["%.15f" % x for x in row]
                    print(", ".join(floats_as_strings), file=fout)

                sys.stdout.write("\t[OK]")
        except IOError:
            sys.stdout.write("[ERROR]")
            return False
