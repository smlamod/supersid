"""
Detect class, implements a running statistical control limits to detect sudden/abrupt
changes in the signal stregths of the monitored frequencies
Algorithm is based from Control Charts by Shewhart 1931

SML
20181213
"""

from __future__ import print_function   # use the new Python 3 'print' function
from os import path
from datetime import datetime, timedelta
import itertools
import numpy

class Detect():
    def __init__(self,controller):
        self.controller = controller
        self.version = "SML 1.0 20181213"
        self.config = controller.config
        self.sid_file = controller.logger.sid_file
  
        self.control_header()

        self.sidbuffer = []     # window
        self.uplimit = []       # of len(sid)
        self.dnlimit = []

        self.minibreach = []
        self.breach = []

        self.filtered = []

        # initial conditions of algorithm
        lenstations = len(self.sid_file.stations)
        self.prevs = lenstations*[0]
        self.prevq = lenstations*[0]
        self.n = 0

        self.limit_alloc()
        self.buffer_alloc()
        

    def window_append(self, signal_strengths):
        """ Fixed window buffer append, pushes at the bottom truncates on top """
        for bfr, sig in itertools.izip(self.sidbuffer, signal_strengths):
            bfr.append(sig)            
        

    def lowpassfilt(self, signal_strengths, current_index):
        """ Applies exponential smoothing to signal for detection """
        a = self.alpha
        i = current_index

        for sig, filt in itertools.izip(signal_strengths, self.filtered):
            if (a >= 1 and a <= 0) or self.n == 0:
                filt[i] = sig
            else:
                filt[i] = filt[i-1] + a * (sig - filt[i-1])


    def compute_limits(self, signal_strengths, current_index):
        """ Function that computes for the limits and logs breaches """
        self.window_append(signal_strengths)
        self.lowpassfilt(signal_strengths, current_index)

        if self.n < self.w:
            self.n += 1
            isFull = False
        else:
            isFull = True

        for prs, prq, upl, dnl, bfr, filt, bx, bmx in itertools.izip(self.prevs, self.prevq, self.uplimit, self.dnlimit, self.sidbuffer, self.filtered, self.breach, self.minibreach):

            if isFull:
                last = bfr.pop(0)   # first entry of buffer
            else:
                last = 0            # buffer is still incomplete default to 0
            
            new = bfr[-1]
            s = prs + new - last
            q = prq + new**2 - last**2

            mean = s/float(self.n)
            s2n = s**2/float(self.n)
            o2 = q - s2n

            if self.n > 1:
                o2 = o2/float(self.n - 1)

            std = numpy.std(o2)

            prs = s
            prq = q

            ul = mean + self.k*std
            dl = mean - self.k*std

            if dl <= 0:
                dl = 0.0

            upl[current_index] = ul
            dnl[current_index] = dl

            sig = filt[current_index]
            if (sig >= ul or sig <= dl) and sig != 0.0:
                
                bx[current_index] = sig
                bmx.append([self.sid_file.timestamp[current_index], sig])
                
        

    def control_header(self):
        """ Parse detection parameters """
        if 'window' in self.config:
            self.w = int(self.config['window'])

        if 'k_distance' in self.config:
            self.k = float(self.config['k_distance'])

        if 'alpha' in self.config:
            self.alpha = float(self.config['alpha'])

        if 'data_path2' in self.config:
            self.data_path = self.config['data_path2']

    def buffer_alloc(self):
        """ Allocate buffer window """
        for stations in self.sid_file.stations:
            self.sidbuffer.append(self.w*[numpy.nan])        

    def limit_alloc(self):
        """ Rest limits and breach log, invoked at new day """
        del self.uplimit[:]
        del self.dnlimit[:]

        del self.filtered[:]

        del self.minibreach[:] 
        del self.breach[:]

        for stations in self.sid_file.stations:         
            tmp = ((24*60*60)/self.sid_file.LogInterval)*[numpy.nan]
            tmp[0] = 0
            tmp[-1] = 0
            
            self.minibreach.append([])      
            self.breach.append(list(tmp))

            self.uplimit.append(list(tmp))
            self.filtered.append(list(tmp))
            self.dnlimit.append(list(tmp))
        

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
            
        



        

