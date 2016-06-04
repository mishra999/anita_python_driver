import ocpci
import struct
import sys
import time
from bf import *   # imports the module bf, and creates references in the current namespace to all public objects defined by bf
import spi
import picoblaze

class LAB4_Controller:
	map = { 'CONTROL'			: 0x00000,
			'SHIFTPRESCALE'		: 0x00004,
			'RDOUTPRESCALE'		: 0x00008,
			'WILKDELAY'			: 0x0000C,
			'WILKMAX'			: 0x00010,
			'TPCTRL'			: 0x00014,
			'L4REG'				: 0x00018,
			'TRIGGER'			: 0x00054,
			'pb'				: 0x0007C,
		   }

	def __init__(self, dev, base):
		self.dev = dev
		self.base = base

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

	def force_trigger(self):
		self.write(self.map['TRIGGER'], 2)

    def read(self, addr):
        return self.dev.read(addr + self.base)
    
    def write(self, addr, value):
        self.dev.write(addr + self.base, value)

	def l4reg(self, lab, addr, value):
		ctrl = bf(self.read(self.map['CONTROL']))
		if ctrl[2]:
			print 'LAB4_Controller is running, cannot update registers.'
			return
		user = bf(self.read(self.map['L4REG']))
		if user[31]:
			print 'LAB4_Controller is still processing a register?'
			return
		user[11:0] = value
		user[23:12] = addr
		user[27:24] = lab
		self.write(self.map['L4REG']), int(user))
		while not user[31]:
			user = bf(self.read(self.map['L4REG']))
					        
class SURF(ocpci.Device):
    map = { 'IDENT'             : 0x00000,
            'VERSION'           : 0x00004,
            'INTCSR'    		: 0x00008,
            'INTMASK'      		: 0x0000C,
            'PPSSEL'       		: 0x00010,
            'RESET'        		: 0x00014,
            'LED'          		: 0x00018,
            'CLKSEL'       		: 0x0001C,      ## this is a clock
            'PLLCTRL'      		: 0x00020,      ## this is a clock, PLL = phase locked loop 
            'SPICS'             : 0x00024,      ## this is the spiss variable in the firmware doc 
            'SPI_BASE'          : 0x00030,
           }

    def __init__(self, path="/sys/class/uio/uio0"):
        ocpci.Device.__init__(self, path, 1*1024*1024)
        self.spi = spi.SPI(self, self.map['SPI_BASE'])
		
    def __repr__(self):
        return "<SURF at %s>" % self.path

    def __str__(self):
        return "SURF (@%s)" % self.path
    
    def spi_cs(self, device, state):
        # We only have 1 SPI device.
        val = bf(self.read(self.map['SPICS']))
        val[device] = state
        self.write(self.map['SPICS'], int(val))
		
				
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
       
			
    def status(self):
        clocksel = bf(self.read(self.map['CLKSEL']))
        pullctrl = bf(self.read(self.map['PLLCTRL']))
        int_status = bf(self.read(self.map['INTCSR']))
        int_mask = bf(self.read(self.map['INTMASK']))
        led = bf(self.read(self.map['LED']))
        print "Clock Status: LAB4 Clock is %s (CLKSEL[1] = %d)" % ("enabled" if clocksel[1] else "not enabled", clocksel[1])
        print "            : LAB4 Driving Clock is %s (CLKSEL[0] = %d)" % ("TURF Clock" if clocksel[0] else "FPGA Clock", clocksel[0])
        print "            : FPGA Driving Clock is %s (CLKSEL[2] = %d)" % ("TURF Clock" if clocksel[2] else "Local Clock", clocksel[2])
        print " Int Status : %8.8x" % (self.read(self.map['INTCSR']) & 0xFFFFFFFF)
        print " LED        : Internal value %3.3x, Key value %3.3x" % (led[11:0], led[27:16])
        print " Full LED   : %8.8x" % (self.read(self.map['LED']) & 0xFFFFFFFF)
        print " Int Mask   : %8.8x" % (self.read(self.map['INTMASK']) & 0xFFFFFFFF)
		
		
		
		
    def identify(self):
        ident = bf(self.read(self.map['IDENT']))
        ver = bf(self.read(self.map['VERSION']))
        print "Identification Register: %x (%c%c%c%c)" % (int(ident),ident[31:24],ident[23:16],ident[15:8],ident[7:0])
        print "Version Register: %d.%d.%d compiled %d/%d" % (ver[15:12], ver[11:8], ver[7:0], ver[28:24], ver[23:16])
