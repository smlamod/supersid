import glob
import csv

class Qdc2():
    def __init__(self,controller):#, controller):
        #self.controller = controller
        #self.config = controller.config
        #self.sid_file = SidFile(sid_params = self.config)

        
        file1 = open('../Data/MAPUA-SIDpi_NWC_2017-12-16.csv','rb')
        file2 = open('../Data/MAPUA-SIDpi_NWC_2017-12-01.csv','rb')
        file3 = open('../Data/MAPUA-SIDpi_NDT_2017-12-16.csv','rb')
        appended = open('../Data/QDC/appended.csv','wb')
        rdr = csv.reader(file1)
        rdr1 = csv.reader(file2)
        rdr2 = csv.reader(file3)
        writer = csv.writer(appended)

        for x in range(0,20):
            rdr.next()
            rdr1.next()
            rdr2.next()
    
        for row in rdr:
            row1=rdr1.next()
            row2=rdr2.next()   
            row.append(row1[1])
            row.append(row2[1])

            val = float(row[1])
            val1 = float(row1[1])
            val2 = float (row2[1])
            qdc = (val + val1 + val2)/3
            qdcrow = str(qdc)
    
            row.append(qdcrow)
            writer.writerow(row)

        file1.close()
        file2.close()
        file3.close()
        appended.close()
