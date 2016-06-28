import surf
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
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
    def log(self, lab, numevent, filename='temp.dat', save=True, subtract_ped=True, unwrap=True):
        self.start()
        time.sleep(1)
        data=[]
        for i in range(0, numevent):
            data.append(self.dev.log_lab(lab, samples=1024, force_trig=True))
            time.sleep(0.002)
            if i%5==0:
                sys.stdout.write('logging event...{:}\r'.format(i))
                sys.stdout.flush()
        sys.stdout.write('\n')

        if subtract_ped:
            self.load_ped()

        for i in range(numevent):
            for k in range(0, len(data[0])):
                end_of_buf_flag=-1
                for j in range(0, len(data[0][0])):
                    datbuf = (data[i][k][j] & 0xC000) >> 14
                    while(((data[i][k][j] & 0x2000) >> 13) and (end_of_buf_flag < 0)):
                        end_of_buf_flag=j
                    data[i][k][j] = (data[i][k][j] & 0x0FFF)-self.pedestals[j+datbuf*1024][k]

                if unwrap and (end_of_buf_flag > 0):
                    data[i][k][:] = np.roll(data[i][k][:], end_of_buf_flag)

        if save:
            sys.stdout.write('saving to file...{:}\n'.format(filename))

            with open(filename, 'w') as filew:
                for i in range(numevent):
                    for j in range(0, len(data[0][0])):
                       
                        for k in range(0, len(data[0])):
                                filew.write(str(data[i][k][j]))
                                filew.write('\t')

                        filew.write('\n')
        return data

    def pedestal_run(self, numruns=40, filename='peds.dat', save=True):

        self.start()
        time.sleep(0.2)

        if (numruns % 4) > 0:
            print 'pedestal run requires numruns be a multiple of 4'
            return 1

        data = self.log(15, numruns, save=False, subtract_ped=False)
        ped_data=np.zeros((4096, 12), dtype=np.int)
        
        for i in range(0, len(data)):
            for j in range(0, 1024):
                for k in range(0, len(data[0])):
                    ped_data[j+(i%4)*1024,k] += (data[i][k][j] & 0x0FFF)
        
        #ped_data = np.transpose(np.sum(np.bitwise_and(np.array(data).reshape((numruns/4, 12, 4096)), 0x0FFF), axis=0))
        ped_data /= (numruns / 4)

        print ped_data.shape
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
            sys.stdout.write('pedestal level is...{:}\r'.format(val))
            sys.stdout.flush()
            self.dev.i2c.set_vped(val, eeprom=False)
            pedestals = self.pedestal_run(16, save=False)
            scan_ped.append(pedestals)
            scan_val.append(val)

        sys.stdout.write('\n')
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

    def read_ped_scan(self, lab, firstcell=0, cells=1, lo=0, hi=20,filename='pedscan.dat',
                      fit=True, fit_order=3, plot=False, plot_color='green'):

        with open(filename, 'r') as filer:
            pedscan=[x.strip().split('\t') for x in filer]

        pedscan=np.array(pedscan, dtype=int)

        if fit==False:
            return pedscan
        
        params=[]
        print pedscan[int(lo),0]/2
        print pedscan[int(hi),0]/2

        cell_stack=np.zeros(128)

        for cell in range(firstcell, firstcell+cells):
            index=int(cell+lab*4096+1)
            fitx = pedscan[int(lo):int(hi),0]
            fity = pedscan[int(lo):int(hi),index]
            params.append(np.polyfit(fitx, fity, deg=fit_order))
            linefit=np.poly1d(params[int(cell-firstcell)])

            cell_stack[cell % 128] += params[int(cell-firstcell)][0]
        
            if plot:
                f, (a0, a1) = plt.subplots(2,1, gridspec_kw={'height_ratios':[3,1]})
           
                a0.plot(pedscan[:,0]/2,pedscan[:,index], 'o', color=plot_color)
                a0.plot(pedscan[:,0]/2, linefit(pedscan[:,0]))
                a0.set_ylim([-100, 4200])
                a0.set_ylabel('LAB4 output code', size=16)
           
                a1.plot(pedscan[:,0]/2, pedscan[:,index]-linefit(pedscan[:,0]),'o')
                a1.set_ylim([-150, 300])
                a1.set_ylabel('Fit res., ADC counts', size=16)
                a1.set_xlabel('DAC pedestal voltage [mV]', size=16)
                
                return f

        return params, cell_stack

                 

