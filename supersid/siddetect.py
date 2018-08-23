"""
Detect class, implements a running statistical control limits to detect sudden/abrupt
changes in the signal stregths of the monitored frequencies
Algorithm is based from Control Charts by Shewhart 1931

SML
20180821
"""

from __future__ import print_function   # use the new Python 3 'print' function
from os import path
from datetime import datetime, timedelta
import itertools
import numpy

class Detect():
    def __init__(self,controller):
        self.controller = controller
        self.config = controller.config
        self.sid_file = controller.logger.sid_file
  
        self.control_header()

        self.sidbuffer = []     # window
        self.uplimit = []       # of len(sid)
        self.dnlimit = []
        self.minibreach = []
        self.breach = []
        

        self.limit_alloc()
        self.buffer_alloc()
        

    def window_append(self,signal_strengths):
        """ Fixed window buffer append, pushes at the bottom truncates on top """
        for bfr, sig in itertools.izip(self.sidbuffer,signal_strengths):
            bfr.append(sig)            
            _ = bfr.pop(0)

    def compute_limits(self,current_index):
        """ Function that computes for the limits and logs breaches """
        for upl, dnl, bfr, bx, bmx in itertools.izip(self.uplimit,self.dnlimit,self.sidbuffer,self.breach, self.minibreach):
            sidmean = numpy.mean(bfr)
            
            bx[current_index] = numpy.nan

            if numpy.isnan(sidmean):
                upl[current_index] = numpy.nan
                dnl[current_index] = numpy.nan
                
            else:
                sidstd = numpy.std(bfr)
                ul = sidmean + self.k*sidstd
                dl = sidmean - self.k*sidstd
                upl[current_index] = ul
                dnl[current_index] = dl

                newbuffer = bfr[-1]
                if (newbuffer >= ul or newbuffer <= dl) and newbuffer != 0.0:
                    bx[current_index] = newbuffer
                    bmx.append([self.sid_file.timestamp[current_index],newbuffer])

    def control_header(self):
        """ Parse detection parameters """
        if 'window' in self.config:
            self.n = int(self.config['window'])

        if 'k_distance' in self.config:
            self.k = float(self.config['k_distance'])

        if 'data_path2' in self.config:
            self.data_path = self.config['data_path2']

    def buffer_alloc(self):
        """ Allocate buffer window """
        for stations in self.sid_file.stations:
            self.sidbuffer.append(self.n*[numpy.nan])        

    def limit_alloc(self):
        """ Rest limits and breach log, invokesd at new day """
        self.uplimit = []
        self.dnlimit = []
        self.minibreach = [] 
        self.breach = []
        for stations in self.sid_file.stations:         
            self.minibreach.append([])
            self.breach.append(((24*3600)/self.sid_file.LogInterval)*[numpy.nan])
            self.uplimit.append(((24*3600)/self.sid_file.LogInterval)*[numpy.nan])
            self.dnlimit.append(((24*3600)/self.sid_file.LogInterval)*[numpy.nan])

    def write_breach(self,filename):
        """ Writes detected anomalies to disk """
        try:
            filename = self.data_path + filename
            sys.stdout.write("Saving  %s" % filename,)
            with open(filename,'wt') as fout:
                print(self.controller.logger.sid_file.create_header(True,'raw'),file=fout,end="")

                for row in numpy.transpose(self.breach):
                    floats_as_strings = ["%.15f" % x for x in row]
                    print(", ".join(floats_as_strings), file=fout)

                sys.stdout.write("\t[OK]")
                return True
        except IOError:
            sys.stdout.write("[ERROR]")
            return False       
            
        



        

