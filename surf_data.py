import surf
import numpy as np
import matplotlib.pyplot as plt
import time
#import h5py
import matplotlib
import matplotlib.pyplot as plt
matplotlib.rc('xtick', labelsize=14)
matplotlib.rc('ytick', labelsize=14)

class SurfData:
    def __init__(self):
        self.dev=surf.SURF()
        self.pedestals=np.zeros((4096, 12), dtype=np.int)

    def start(self):
        self.dev.labc.run_mode(0)
        self.dev.labc.reset_fifo()
        self.dev.labc.testpattern_mode(0)
        self.dev.labc.run_mode(1)
        
    #def pedestals(lab, num_runs=100):   
    def log(self, lab, numevent=12, filename='test.dat', save=True, subtract_ped=True):
        self.start()
        time.sleep(1)
        data=[]
        for i in range(0, numevent):
            data.append(self.dev.log_lab(lab, force_trig=True))
            time.sleep(0.005)

        if subtract_ped:
            self.load_ped()
            for i in range(0, len(data)):
                    for j in range(0, len(data[0][0])):
                        for k in range(0, len(data[0])):
                            datbuf = (np.bitwise_and(data[i][k][j], 0xC000) >> 14)
                            data[i][k][j] = np.bitwise_and(data[i][k][j], 0x0FFF)-self.pedestals[j+datbuf*1024][k]

        if save:
            with open(filename, 'w') as filew:
                for i in range(0, len(data)):
                    for j in range(0, len(data[0][0])):
                        '''
                        for k in range(0, 2*len(data[0])):
                            if k & 1 and not subtract_ped:
                                filew.write(str(np.bitwise_and(data[i][int(k/2)-1/2][j], 0x0FFF)))
                            elif k & 1:
                                filew.write(str(pdata[i][int(k/2)-1/2][j]))
                            else:
                                filew.write(str((np.bitwise_and(data[i][int(k/2)][j], 0xC000)) >> 14) )
                            filew.write('\t')
                        '''
                        for k in range(0, len(data[0])):
                                filew.write(str(data[i][k][j]))
                                filew.write('\t')

                        filew.write('\n')
        return data

    def pedestal_run(self, numruns=80, filename='peds.dat', save=True):
        self.start()
        time.sleep(1)

        data = self.log(15, numruns, save=False, subtract_ped=False)
        ped_data=np.zeros((4096, 12), dtype=np.int)

        for i in range(0, len(data)):
            for j in range(0, 1024):
                for k in range(0, len(data[0])):
                    ped_data[j+(i%4)*1024,k] += np.bitwise_and(data[i][k][j], 0x0FFF)
        
        ped_data[:,:] /= (numruns / 4)

        if save:
            with open(filename, 'w') as filew:
                for j in range(0, 4096):
                    for k in range(0, 12):
                        filew.write(str(ped_data[j,k]))
                        filew.write('\t')
                    filew.write('\n')

#        self.pedestals=ped_data
        return ped_data

    def load_ped(self, fromfile='peds.dat'):
        
        with open(fromfile, 'r') as filer:
            peds=[x.strip().split('\t') for x in filer]

        for i in range(len(peds)):
            for j in range(len(peds[0])):
                self.pedestals[i][j]=peds[i][j]

    def pedestal_scan(self, start=0, stop=4096, incr=100, filename='pedscan.dat', save=True):

        scan_ped=[]
        scan_val=[]
        
        for val in range(start, stop, incr):
            self.dev.i2c.set_vped(val, eeprom=False)
            pedestals = self.pedestal_run(12, save=False)
            scan_ped.append(pedestals)
            scan_val.append(val)

        scan_ped =np.array(scan_ped)

        if save:
            with open(filename, 'w') as filew:
                for j in range(0, len(scan_val)):
                    filew.write(str(scan_val[j]))
                    filew.write('\t')
                    for k in range(0, 12):
                        for cell in range(0, 4096):
                            filew.write(str(scan_ped[j][cell][k]))
                            filew.write('\t')
                    filew.write('\n')

        return scan_val, scan_ped

    def read_ped_scan(self, lab, firstcell, cells=1, lo=0, hi=20,filename='pedscan.dat',
                      fit_order=3, plot=False):

        with open(filename, 'r') as filer:
            pedscan=[x.strip().split('\t') for x in filer]

        pedscan=np.array(pedscan, dtype=int)
        params=[]
        print pedscan[int(lo),0]/2
        print pedscan[int(hi),0]/2
        for cell in range(firstcell, firstcell+cells):
            index=int(cell+lab*4096+1)
            fitx = pedscan[int(lo):int(hi),0]
            fity = pedscan[int(lo):int(hi),index]
            params.append(np.polyfit(fitx, fity, deg=fit_order))
            linefit=np.poly1d(params[int(cell-firstcell)])
        
            if plot:
                f, (a0, a1) = plt.subplots(2,1, gridspec_kw={'height_ratios':[3,1]})
           
                a0.plot(pedscan[:,0]/2,pedscan[:,index], 'o')
                a0.plot(pedscan[:,0]/2, linefit(pedscan[:,0]))
                a0.plot([1250, 1250], [-500, 4300], '--', color='black')
                a0.set_ylim([-100, 4200])
                a0.set_ylabel('LAB4 output code', size=16)
           
                a1.plot(pedscan[:,0]/2, pedscan[:,index]-linefit(pedscan[:,0]),'o')
                a1.plot([1250, 1250], [-500, 500], '--', color='black')
                a1.set_ylim([-150, 300])
                a1.set_ylabel('Fit res., ADC counts', size=16)
                a1.set_xlabel('DAC pedestal voltage [mV]', size=16)
                
                f.show()

        return params

                 

