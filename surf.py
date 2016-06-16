import ocpci
import struct
import sys
import time
from bf import *   # imports the module bf, and creates references in the current namespace to all public objects defined by bf
import spi
import i2c
import picoblaze
import numpy as np
import surf_calibrations

class LAB4_Controller:
        map = { 'CONTROL'			: 0x00000,
                'SHIFTPRESCALE'		        : 0x00004,
		'RDOUTPRESCALE'		        : 0x00008,
		'WILKDELAY'			: 0x0000C,
		'WILKMAX'			: 0x00010,
		'TPCTRL'			: 0x00014,
		'L4REG'				: 0x00018,
                'PHASECMD'                      : 0x00020,
                'PHASEARG'                      : 0x00024,
                'PHASERES'                      : 0x00028,
                'PHASEZERO'                     : 0x0002C,
                'PHASEPB'                       : 0x0003C,
		'TRIGGER'			: 0x00054,
                'READOUT'                       : 0x00058,
                'pb'				: 0x0007C,
                }
        amon = { 'Vbs'                      : 0,
                 'Vbias'                    : 1,
                 'Vbias2'                   : 2,
                 'CMPbias'                  : 3,
                 'VadjP'                    : 4,
                 'Qbias'                    : 5,
                 'ISEL'                     : 6,
                 'VtrimT'                   : 7,
                 'VadjN'                    : 8,
                 }
        tmon = {'A1'                        : 0,
                'B1'                        : 1,
                'A2'                        : 2,
                'B2'                        : 3,
                'SSPout'                    : 68,
                'SSTout'                    : 100,
                'PHASE'                     : 4,
                'PHAB'                      : 5,
                'SSPin'                     : 6,
                'WR_STRB'                   : 7,
                }
                
	def __init__(self, dev, base):
		self.dev = dev
		self.base = base
                self.pb = picoblaze.PicoBlaze(self, self.map['pb'])
                self.phasepb = picoblaze.PicoBlaze(self,self.map['PHASEPB'])

        def automatch_phab(self, lab):
            labs = []
            if lab == 15:
                labs = range(12)
            else:
                labs = [lab]
            # Find our start point.
            sync_edge = self.scan_edge(12, 1)
            print "Found sync edge: %d" % sync_edge
            for i in labs:
                # Find our PHAB sampling point.
                self.set_tmon(i, self.tmon['WR_STRB'])
                wr_edge = self.scan_edge(i, 1, sync_edge)
                print "Found WR_STRB edge on LAB%d: %d" % (lab, wr_edge)
                self.set_tmon(i, self.tmon['PHAB'])
                phab = self.scan_value(i, wr_edge) & 0x01
                while phab != 1:
                    print "LAB%d wrong PHAB phase, resetting." % i
                    self.clr_phase(i)
                    phab = self.scan_value(i, wr_edge) & 0x01
                
        def autotune_vadjn(self, lab):
            self.set_tmon(lab, self.tmon['A1'])
            vadjn = 1640
            delta = 20            
            self.l4reg(lab, 3, vadjn)            
            width = self.scan_width(lab, 64)
            oldwidth = width
            print "Trial: vadjn %d width %f" % ( vadjn, width)
            while abs(width-840) > 0.5:
                if (width < 840):
                    if (oldwidth > 840):
                        delta = delta/2
                        if delta < 1:
                            delta = 1
                    vadjn -= delta
                else:
                    if (oldwidth < 840):
                        delta = delta/2
                        if delta < 1:
                            delta = 1
                    vadjn += delta
                oldwidth = width
                self.l4reg(lab, 3, vadjn)
                width = self.scan_width(lab, 64)
                print "Trial: vadjn %d width %f" % ( vadjn, width)
            return vadjn            
                
        def scan_free(self):
            self.write(self.map['PHASECMD'], 0x01)
            
        def scan_width(self, lab, trials=1):
            self.write(self.map['PHASEARG'], lab)
            res = 0
            for i in xrange(trials):
                self.write(self.map['PHASECMD'], 0x02)
                val = self.read(self.map['PHASECMD'])
                while val != 0x00:
                    val = self.read(self.map['PHASECMD'])
                res += self.read(self.map['PHASERES'])                
            return res/(trials*1.0)

        def scan_value(self,lab,position):
            if position > 4479:
                print "Position must be 0-4479."
                return None
            val = bf(0)                
            val[15:0] = position
            val[19:16] = lab
            self.write(self.map['PHASEARG'], int(val))
            self.write(self.map['PHASECMD'], 0x03)
            res = self.read(self.map['PHASECMD'])
            while res != 0x00:
                res = self.read(self.map['PHASECMD'])
            return self.read(self.map['PHASERES'])
        
        def scan_edge(self,lab, pos=0, start=0):
            val = bf(0)
            val[15:0] = start
            val[24] = pos
            val[19:16] = lab
            self.write(self.map['PHASEARG'], int(val))
            self.write(self.map['PHASECMD'], 0x04)
            ret=self.read(self.map['PHASECMD'])
            while ret != 0x00:
                ret = self.read(self.map['PHASECMD'])
            return self.read(self.map['PHASERES'])
        
        def set_amon(self, lab, value):
            self.l4reg(lab, 12, value)

        def set_tmon(self, lab, value):
            self.l4reg(lab, 396, value)
            
        def clr_phase(self, lab):
            self.l4reg(lab, 396, self.tmon['PHAB']+128)
            self.l4reg(lab, 396, self.tmon['PHAB'])

	def start(self):
		ctrl = bf(self.read(self.map['CONTROL']))
		while not ctrl[2]:
			ctrl[1] = 1
			self.write(self.map['CONTROL'], int(ctrl))
			ctrl = bf(self.read(self.map['CONTROL']))

	def stop(self):
 		ctrl = bf(self.read(self.map['CONTROL']))
		while ctrl[2]:
			ctrl[1] = 0
			self.write(self.map['CONTROL'], int(ctrl))
			ctrl = bf(self.read(self.map['CONTROL']))
        '''
        send software trigger
        '''
	def force_trigger(self):
		self.write(self.map['TRIGGER'], 2)
        '''
        clear all registers on LAB
        '''
        def reg_clr(self):
            ctrl = bf(self.read(self.map['CONTROL']))
            if ctrl[1]:
                print 'cannot issue REG_CLR: LAB4 in run mode'
                return 1
            else:
                self.write(0, 0xFFF0000)
                self.write(0, 0)
                return 0
        '''
        reset FIFO on FPGA, which holds LAB4 data
        '''
        def fifo_reset(self, force=False):
            ctrl = bf(self.read(self.map['CONTROL']))
            if ctrl[1] and not force:
                print 'cannot reset FIFO: LAB4 in run mode'
                return 1
            else:
                rdout = bf(self.read(self.map['READOUT']))
                rdout[2] = 1
                self.write(self.map['READOUT'], rdout) 
                return 0
        '''
        enables LAB run mode (sample+digitize+readout)
        '''    
        def run_mode(self, enable=True):
            ctrl = bf(self.read(self.map['CONTROL']))
            if enable:
                ctrl[1] = 1
                self.write(self.map['CONTROL'], ctrl)
            else:
                ctrl[1] = 0
                self.write(self.map['CONTROL'], ctrl)
        '''
        enable serial test-pattern data on output
        '''
        def testpattern_mode(self, enable=True):     #when enabled, SELany bit is 0
            rdout = bf(self.read(self.map['READOUT']))
            if enable:
                rdout[4] = 0 
                self.write(self.map['READOUT'], rdout)
            else:
                rdout[4] = 1
                self.write(self.map['READOUT'], rdout)

        '''
        set serial data test-pattern (12 bits)
        '''
        def testpattern(self, lab4, pattern=0xBA6):
            self.l4reg(lab4, 13, pattern)
            return [lab4, pattern]
        
        def read(self, addr):
		return self.dev.read(addr + self.base)
    
	def write(self, addr, value):
		self.dev.write(addr + self.base, value)                
                
	def l4reg(self, lab, addr, value, verbose=False):
		ctrl = bf(self.read(self.map['CONTROL']))
		if ctrl[1]:  #should be checking ctrl[2], which indicates run-mode. but not working 6/9
                    print 'LAB4_Controller is running, cannot update registers.' 
                    return
		user = bf(self.read(self.map['L4REG']))
		if user[31]:
                    print 'LAB4_Controller is still processing a register?' 
                    return
		user[11:0] = value
		user[23:12] = addr
		user[27:24] = lab
		user[31] = 1
                if verbose:
                    print 'Going to write 0x%X' % user 
		self.write(self.map['L4REG'], int(user))
		while not user[31]:
                        user = bf(self.read(self.map['L4REG']))

        def default(self, lab4=15):
                '''DAC default values'''
                self.l4reg(lab4, 0, 1024)      #PCLK-1=0 : Vboot 
                self.l4reg(lab4, 1, 1024)      #PCLK-1=1 : Vbsx
                self.l4reg(lab4, 2, 1024)      #PCLK-1=2 : VanN
                cals = surf_calibrations.read_vadjn(self.dev.dna())
                if cals == None:
                    print "Using default VadjN of 1640."
                    self.l4reg(lab4, 3, 1640)
                else:
                    if lab4 == 15:
                        for i in xrange(12):
                            self.l4reg(i,3,cals[i])
                    else:
                        self.l4reg(lab4, 3, cals[lab4])
                self.l4reg(lab4, 4, 1024)      #PCLK-1=4 : Vbs 
                self.l4reg(lab4, 5, 1100)      #PCLK-1=5 : Vbias 
                self.l4reg(lab4, 6, 950)       #PCLK-1=6 : Vbias2 
                self.l4reg(lab4, 7, 1024)      #PCLK-1=7 : CMPbias 
                self.l4reg(lab4, 8, 2700)      #PCLK-1=8 : VadjP 
                self.l4reg(lab4, 9, 1000)      #PCLK-1=9 : Qbias 
                self.l4reg(lab4, 10, 2780)     #PCLK-1=10 : ISEL 
                self.l4reg(lab4, 11, 4090)     #PCLK-1=11 : VtrimT 
                self.l4reg(lab4, 16, 0)        #patrick said to add 6/9
                
                for i in range (0, 128):       #PCLK-1=<255:383> : dTrim DACS
                        self.l4reg(lab4, i+256, 0)
                
                '''timing register default values'''        
                self.l4reg(lab4, 384, 95)      #PCLK-1=384 : wr_strb_le 
                self.l4reg(lab4, 385, 0)       #PCLK-1=385 : wr_strb_fe 
                self.l4reg(lab4, 386, 120)     #PCLK-1=386 : sstoutfb 
                self.l4reg(lab4, 387, 0)       #PCLK-1=387 : wr_addr_sync 
                self.l4reg(lab4, 388, 38)      #PCLK-1=388 : tmk_s1_le  
                self.l4reg(lab4, 389, 86)      #PCLK-1=389 : tmk_s1_fe 
                self.l4reg(lab4, 390, 120)     #PCLK-1=390 : tmk_s2_le 
                self.l4reg(lab4, 391, 20)      #PCLK-1=391 : tmk_s2_fe
                self.l4reg(lab4, 392, 35)      #PCLK-1=392 : phase_le -- was 45 6/8
                self.l4reg(lab4, 393, 75)      #PCLK-1=393 : phase_fe -- was 85 6/8
                self.l4reg(lab4, 394, 92)      #PCLK-1=394 : sspin_le
                self.l4reg(lab4, 395, 10)      #PCLK-1=395 : sspin_fe

                '''default test pattern'''
                self.l4reg(lab4, 13, 0xBA6)    #PCLK-1=13  : LoadTPG
                
class SURF(ocpci.Device):
    internalClock = 0
    externalClock = 1
    map = { 'IDENT'                     : 0x00000,
            'VERSION'                   : 0x00004,
            'INTCSR'    		: 0x00008,
            'INTMASK'      		: 0x0000C,
            'PPSSEL'       		: 0x00010,
            'RESET'        		: 0x00014,
            'LED'          		: 0x00018,
            'CLKSEL'       		: 0x0001C,      ## this is a clock
            'PLLCTRL'      		: 0x00020,      ## this is a clock, PLL = phase locked loop 
            'SPICS'                     : 0x00024,      ## this is the spiss variable in the firmware doc 
            'PHASESEL'                  : 0x00028,
            'DNA'                       : 0x0002C,
            'SPI_BASE'                  : 0x00030,
            'LAB4_CTRL_BASE'            : 0x10000,
	    'LAB4_ROM_BASE'             : 0x20000,      
            'RFP_BASE'                  : 0x30000,
           }

    i2c_periph = {'DAC'                 : 0x00,
                  'RFP_0'               : 0x20,
                  'RFP_1'               : 0x40,
                  'RFP_2'               : 0x60,
                  'RFP_3'               : 0x80}

    def __init__(self, path="/sys/class/uio/uio0"):
        ocpci.Device.__init__(self, path, 1*1024*1024)
        self.spi = spi.SPI(self, self.map['SPI_BASE'])
	self.labc = LAB4_Controller(self, self.map['LAB4_CTRL_BASE'])
	self.dac = i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['DAC'], 0x60)
	self.ioexpander = i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['DAC'], 0x20)
        '''
        12 RFP circuits on 4 i2c buses. Slave address set by ADDR pin connection:
        GND: 1001000
        VDD: 1001001
        SDA: 1001010 (not used)
        SCL: 1001011 
        '''
        self.rfp = []
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_0'], 0x49) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_0'], 0x48) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_0'], 0x4B) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_1'], 0x49) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_1'], 0x48) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_1'], 0x4B) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_2'], 0x49) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_2'], 0x48) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_2'], 0x4B) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_3'], 0x49) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_3'], 0x48) )
        self.rfp.append(i2c.I2C(self, self.map['RFP_BASE'] + self.i2c_periph['RFP_3'], 0x4B) ) 

        self.vped = 0x9C4
        
    def __repr__(self):
        return "<SURF at %s>" % self.path

    def __str__(self):
        return "SURF (@%s)" % self.path
    
    def spi_cs(self, device, state):
        # We only have 1 SPI device.
        val = bf(self.read(self.map['SPICS']))
        val[device] = state
        self.write(self.map['SPICS'], int(val))
		
    def set_phase(self, phase=0):
        #fix later
        self.write(self.map['PHASESEL'], phase)
        
    def led(self, arg):
        off_led_num = 14                     # initializing this to something while debugging 
        on_led_num = 14
        off_value = 2
        on_value = 2
        self.led_unusedbits = "0000"
        self.led_KEY_list = [1]*12    #array so that we can change values, setting all to one initially
        print "LED function works!"
        print "  "
        if arg == "all off":
            self.led_off()                             # call the function for turning LED's off
        elif arg == "all on":
            self.led_on()                              # call the function for turning LED's on
        elif arg == "release":
            self.led_release()                         # call function for releasing LED (we stop controlling it)
        elif arg == "one off":
            off_led_num = int(input("Enter number of LED you want to turn off: "))
            off_value = 0
            self.led_one(off_led_num,off_value)
        elif arg == "one on":
            on_led_num = int(input("Enter number of LED you want to turn on: "))
            on_value = 1
            self.led_one(on_led_num,on_value)
        else:
            print "Invalid argument! Your options are all off, all on, release, one off, one on" 
	

    def list_to_string(self,list):
        return "".join(map(str,list))

				
    def led_one(self,led_num,value):
        led_current = bf(self.read(self.map['LED']))
        led_current_binary = "{0:b}".format(led_current[31:0])                             # string containing current LED configuration in binary
        led_current_binary = "0000" + led_current_binary
        print "integer value of led_current_binary: " + str(int(led_current_binary,base=2))
        print led_num
        print value 
        print "current LED values in binary: " + led_current_binary                        # this string misses the first four zeros!
        print len(led_current_binary)
        print led_current_binary[0]
        print led_current_binary[15], led_current_binary[16]
        print led_current_binary[27] 
        print "the type of led_current_binary is: %s" % (type(led_current_binary))         # check it's a string!
        print " "       
        led_current_VALUE = led_current_binary[20:32]                                      # take last part of string to get just VALUES
        led_VALUE_list = list(led_current_VALUE)                                           # turn string into list so we can easily toggle its values
        print "The length of the array is %d" % (len(led_VALUE_list))	
        led_VALUE_list[led_num] = value                                                    # change the LED value that user wants to change 
        led_VALUE_string = self.list_to_string(led_VALUE_list)                             # turn list of LED values back into string 
        led_KEY_string = self.list_to_string(self.led_KEY_list)                            # turn list of LED key values to string 
        led_full_string = self.led_unusedbits + led_KEY_string + self.led_unusedbits + led_VALUE_string    # put the different strings together to get full LED configuration
        print "updated LED values in binary: " + led_full_string
        self.write(self.map['LED'],int(led_full_string,base=2))                       # write in this new configuration to see the change take place 	
        print "integer value of led_full_string: " + str(int(led_full_string,base=2))
        u= bf(self.read(self.map['LED']))
        y= "{0:b}".format(u[31:0])	
        print "after we change everyting: "+"0000" + y		
        print led_num
        print value 

    def led_off(self):
        self.write(self.map['LED'],0x0fff0000)
            		

    def led_on(self):
        self.write(self.map['LED'],0x0fff0fff)           
            

    def led_release(self):
        self.write(self.map['LED'],0x00000000)  

    def clock(self, source):
	clocksel = bf(self.read(self.map['CLKSEL']))
	pllctrl = bf(self.read(self.map['PLLCTRL']))
	if source == self.internalClock:
		# Enable LAB clock.
		clocksel[1] = 1
		# Use FPGA input.
		clocksel[0] = 0
		# Enable local clock.
		clocksel[2] = 0
		if pllctrl[1]:
			# Switch PLL to internal clock. Need to reset it.
			pllctrl[1] = 0
			pllctrl[0] = 1
			self.write(self.map['PLLCTRL'], int(pllctrl))
			pllctrl[0] = 0
			self.write(self.map['PLLCTRL'], int(pllctrl))
		self.write(self.map['CLKSEL'], int(clocksel))
	elif source == self.externalClock:
		# Enable LAB clock.
		clocksel[1] = 1
		# Use TURF input.
		clocksel[0] = 1
		# Disable local clock
		clocksel[2] = 1
		if not pllctrl[1]:
			# Switch PLL to external clock. Need to reset it.
			pllctrl[1] = 1
			pllctrl[0] = 1
			self.write(self.map['PLLCTRL'], int(pllctrl))
			pllctrl[0] = 0
			self.write(self.map['PLLCTRL'], int(pllctrl))
		self.write(self.map['CLKSEL'], int(clocksel))
			
    def status(self):
        clocksel = bf(self.read(self.map['CLKSEL']))
        pllctrl = bf(self.read(self.map['PLLCTRL']))
        int_status = bf(self.read(self.map['INTCSR']))
        int_mask = bf(self.read(self.map['INTMASK']))
        led = bf(self.read(self.map['LED']))
        labcontrol = bf(self.labc.read(self.labc.map['CONTROL']))
        labreadout = bf(self.labc.read(self.labc.map['READOUT']))
        print "Clock Status: LAB4 Clock is %s (CLKSEL[1] = %d)" % ("enabled" if clocksel[1] else "not enabled", clocksel[1])
        print "            : LAB4 Driving Clock is %s (CLKSEL[0] = %d)" % ("TURF Clock" if clocksel[0] else "FPGA Clock", clocksel[0])
	print "            : Local Clock is %s (CLKSEL[2] = %d)" % ("enabled" if not clocksel[2] else "not enabled", clocksel[2])
	print "            : FPGA System Clock PLL is %s (PLLCTRL[0] = %d/PLLCTRL[2] = %d)" % ("powered down" if pllctrl[2] else ("running" if not pllctrl[0] else "in reset"), pllctrl[0], pllctrl[2])
        print "            : FPGA System Clock is %s (PLLCTRL[1] = %d)" % ("TURF Clock" if pllctrl[1] else "Local Clock", pllctrl[1])
        print " Int Status : %8.8x" % (self.read(self.map['INTCSR']) & 0xFFFFFFFF)
        print " LED        : Internal value %3.3x, Key value %3.3x" % (led[11:0], led[27:16])
        print " Full LED   : %8.8x" % (self.read(self.map['LED']) & 0xFFFFFFFF)
        print " Int Mask   : %8.8x" % (self.read(self.map['INTMASK']) & 0xFFFFFFFF)
        print "**********************"
        print "LAB4 runmode: %s" % ("enabled" if labcontrol[1] else "not enabled")
        print "LAB4 testpat: %s" % ("enabled" if not labreadout[4] else "not enabled")


    ''' NOT DONE YET, will move i2c control to a class
    def readi2cexpander(self, address=0x4D):
        self.write(self.map['RFP_BASE']+12, 0x40) #address the device
        self.write(self.map['RFP_BASE']+16, 0x90) #start write to core
        while(self.read(self.map['RFP_BASE']+16) & 0x2):
                print 'waiting for TIP'
        if (self.read(self.map['RFP_BASE']+16) & 0x80):
                print 'error, no ACK'
                return 1
        self.write(self.map['RFP_BASE']+12, address) #send address to read (interupt status register=0x4d)
        self.write(self.map['RFP_BASE']+16, 0x10) #write to slave
        while(self.read(self.map['RFP_BASE']+16) & 0x2):
                print 'waiting for TIP'
        if (self.read(self.map['RFP_BASE']+16) & 0x80):
                print 'error, no ACK'
                return 1
        self.write(self.map['RFP_BASE']+12, 0x41) #address the device (+read bit)
        self.write(self.map['RFP_BASE']+16, 0x90) #start write to core
        while(self.read(self.map['RFP_BASE']+16) & 0x2):
                print 'waiting for TIP'
        if (self.read(self.map['RFP_BASE']+16) & 0x80):
                print 'error, no ACK'
                return 1
        self.write(self.map['RFP_BASE']+12, 0x68) #set RD, STO, and NACK
        print self.read(self.map['RFP_BASE']+12)
    def setupi2cexpander(self):
        config=[]
        config.append([0x40, 0x44, 0xFF])  #input latch register 0
        config.append([0x40, 0x45, 0xFF])  #input latch register 1
        config.append([0x40, 0x46, 0xFF])  #PU/PD enable register 0
        config.append([0x40, 0x47, 0xFF])  #PU/PD enable register 1
        config.append([0x40, 0x48, 0xFF])  #PU/PD selection register 0
        config.append([0x40, 0x49, 0xFF])  #PU/PD selection register 1
        for dac in range(0, len(config)):
                for i in range(0, len(config[dac])):
                        self.write(self.map['RFP_BASE']+12, config[dac][i])
                        if i==0:
                                self.write(self.map['RFP_BASE']+16, 0x90) #write to slave and start a write
                        elif i==len(config[dac])-1:
                                self.write(self.map['RFP_BASE']+16, 0x50) #write to slave and stop write
                        else:
                                self.write(self.map['RFP_BASE']+16, 0x10) #write to slave
                        while(self.read(self.map['RFP_BASE']+16) & 0x2):
                                print 'waiting for TIP'
                        if (self.read(self.map['RFP_BASE']+16) & 0x80):
                                print 'error, no ACK'
                                return dac*i+1
        return 0
    '''
    def set_vped(self, value=0x9C4):
        val=bf(value)
        dac_bytes=[0x5E, (0x8<<4) | (val[11:8]), val[7:0]]
        self.dac.write_seq(dac_bytes)
        self.vped=value  #update vped value

    def set_rfp_vped(self, value=[0x9C4, 0x800, 0xA00]):
        val0=bf(value[0])
        val1=bf(value[1])
        val2=bf(value[2])
        dac_bytes=[]
        dac_bytes.append([0x58, (0x8<<4) | (val0[11:8]), val0[7:0]])
        dac_bytes.append([0x5A, (0x8<<4) | (val1[11:8]), val1[7:0]])
        dac_bytes.append([0x5C, (0x8<<4) | (val2[11:8]), val2[7:0]])
        for i in range(0, len(dac_bytes)):
                self.dac.write_seq(dac_bytes[i])
            
    def read_fifo(self, lab, address=0): 		
        val = bf(self.read(self.map['LAB4_ROM_BASE']+(lab<<11)+address))
        sample0 = val[11:0]
        sample1 = val[27:16]
        #print 'LAB addr', lab, ', samples =', hex(sample0), hex(sample1)
        return sample0, sample1

    def log_lab(self, lab, samples=128, force_trig=False, save=False, filename=''):
        if save==True and len(filename)<=1:
                timestr=time.strftime('%Y%m%d-%H%M%S')
                filename= timestr+'_LAB'+str(lab)+'.dat'

        if force_trig:
                self.labc.force_trigger()
        labdata=np.zeros(samples)
        for i in range(0, int(samples), 2):
                labdata[i], labdata[i+1] = self.read_fifo(lab) 
               
        if save:
            np.savetxt(filename, labdata, delimiter=',')
        return labdata

    def scope_lab(self, lab, samples, force_trig=True, frames=1, refresh=0.1):
        import matplotlib.pyplot as plt
        plt.ion()
    
        x=np.arange(samples)
        for i in range(0, frames):
                fig=plt.figure(1)
                plt.clf()
                plot_data = self.log_lab(lab=lab, samples=samples, force_trig=True)
                #plot_data = np.sin(x+np.random.uniform(0,np.pi))+np.random.normal(0, .1)
                plt.plot(x, plot_data, '-')
                if i == (frames-1):
                        raw_input('press enter to close')
                        plt.close(fig)
                        plt.ioff()
                else:
                        plt.pause(refresh)
                  
    def identify(self):
        ident = bf(self.read(self.map['IDENT']))
        ver = bf(self.read(self.map['VERSION']))
        print "Identification Register: %x (%c%c%c%c)" % (int(ident),ident[31:24],ident[23:16],ident[15:8],ident[7:0])
        print "Version Register: %d.%d.%d compiled %d/%d" % (ver[15:12], ver[11:8], ver[7:0], ver[28:24], ver[23:16])
        print "Device DNA: %x" % self.dna()

    def dna(self):
        self.write(self.map['DNA'], 0x80000000)
        dnaval=0
        for i in xrange(57):
            val=self.read(self.map['DNA'])
            dnaval = (dnaval << 1) | val
        return dnaval