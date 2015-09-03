import ocpci
import struct
import sys
import time
from bf import * 


#
# This is the spi module
# surf.py and tisc.py need to import this module
#

class SPI:
    map = { 'SPCR'       : 0x000000,
            'SPSR'       : 0x000004,
            'SPDR'       : 0x000008,
            'SPER'       : 0x00000C }
    
    cmd = { 'RES'        : 0xAB ,
            'RDID'       : 0x9F ,
            'WREN'       : 0x06 ,
            'WRDI'       : 0x04 ,
            'RDSR'       : 0x05 ,
            'WRSR'       : 0x01 ,
            '4READ'      : 0x13 , 
	    '3READ'      : 0x03 ,   
            'FASTREAD'   : 0x0B ,
            '4PP'        : 0x12 , 
	    '3PP'        : 0x02 , 
            '4SE'        : 0xDC , 
            '3SE'        : 0xD8 ,
            'BRRD'       : 0x16 , 
            'BRWR'       : 0x17 , 
            'BE'         : 0xC7 }
    
    bits = { 'SPIF'      : 0x80,
             'WCOL'      : 0x40,
             'WFFULL'    : 0x08,
             'WFEMPTY'   : 0x04,
             'RFFULL'    : 0x02,
             'RFEMPTY'   : 0x01 }
    
    def __init__(self, dev, base, device = 0):
        self.dev = dev
        self.base = base
        self.device = device 
        val = bf(self.dev.read(self.base + self.map['SPCR']))
        val[6] = 1;
        val[3] = 0;
        val[2] = 0;
        self.dev.write(self.base + self.map['SPCR'], int(val))

    def command(self, command, dummy_bytes, num_read_bytes, data_in = [] ):
        self.dev.spi_cs(self.device, 1)
        self.dev.write(self.base + self.map['SPDR'], command)
        for dat in data_in:
            self.dev.write(self.base + self.map['SPDR'], dat)
        for i in range(dummy_bytes):
            self.dev.write(self.base + self.map['SPDR'], 0x00)
        # Empty the read FIFO.
        while not (self.dev.read(self.base + self.map['SPSR']) & self.bits['RFEMPTY']):
            self.dev.read(self.base + self.map['SPDR'])
        rdata = []
        for i in range(num_read_bytes):
            self.dev.write(self.base + self.map['SPDR'], 0x00)
            rdata.append(self.dev.read(self.base + self.map['SPDR']))
        self.dev.spi_cs(self.device, 0)    
        return rdata
    
    def identify(self):
        res = self.command(self.cmd['RES'], 3, 1)
        print "Electronic Signature: 0x%x" % res[0]
        res = self.command(self.cmd['RDID'], 0, 3)
        print "Manufacturer ID: 0x%x" % res[0]
        print "self.device ID: 0x%x 0x%x" % (res[1], res[2])

    def read(self, address, length=1):
        data_in = []
        data_in.append((address >> 16) & 0xFF)
        data_in.append((address >> 8) & 0xFF)
	#data_in.append((address >> 8) & 0xFF) #added this line
        data_in.append(address & 0xFF)
        result = self.command(self.cmd['4READ'], 0, length, data_in)
	print len(result)
	print type(result)
	x = 0
	for i in range (0,65536):
            if result[i] == 0:
	        x += 1
	        print i
	
        print result 
	print "Number of zeros:" 
	print x

        
#Oindree found from datasheet:         
#
#The WEL bit must be set to 1 to enable program, write, or erase operations 
#as a means to provide protection against inadvertent changes to memory or register values. 
#The Write Enable (WREN) command execution sets the Write Enable Latch to a 1 to allow any program, 
#erase, or write commands to execute afterwards. The Write Disable (WRDI) command can be used to set the 
#Write Enable Latch to a 0 to prevent all program, erase, and write commands from execution. The WEL 
#bit is cleared to 0 at the end of any successful program, write, or erase operation. 
#Following a failed operation the WEL bit may remain set and should be cleared with a WRDI
#command following a CLSR command. After a power down/power up sequence, hardware reset, or software reset,
#the Write Enable Latch is set to a 0 
#The WRR command does not affect this bit.         
#		

    
	
    def write_enable(self):
        print "Inside function write_enable: command to make SPI flash write enabled" 
        #Need to execute WREN here
        #Call the function command which was written to send commands
        #arguments dummy_bytes = 0 and num_read_bytes = 0 I guess 
        enable = self.command(self.cmd["WREN"], 0, 0)
        return enable
        
        
    def write_disable(self):
        print "Inside function write_disable: command to make SPI flash write disabled" 
        #Need to execute WRDI here 
        #Call the function command which was written to send commands
        #arguments dummy_bytes = 0 and num_read_bytes = 0 I guess 
        disable = self.command(self.cmd["WRDI"], 0, 0)
        return disable
        
        
    def page_program(self, address = 0x1ffff00, data = []):
        print "Inside function program: command to program the SPI flash" 
	self.write_enable()
        #Need to execute PP here 
        #Call the function command which was written to send commands
        #arguments dummy_bytes = ? and num_read_bytes = ? 
	print hex(address)
	towrite = []
	towrite.append((address >> 24) & 0xFF)
	towrite.append((address >> 16) & 0xFF)
 	towrite.append((address >> 8) & 0xFF)
	towrite.append(address & 0xFF)
	# Magic python command to add data to the end of this list
	# Check that data is 256 bytes
	
        program = self.command(self.cmd["4PP"], 0, 0, data)
        length=len(data)
	for i in range(0,length):
	    print hex(data[i])
	print "hex is over"
	print data
	print "data is over"
	data = [] 
	return data 
	#return program


    def erase(self, address): 
	print "Inside function erase: command sector erase or SE to erase parts of SPI flash"
	erase = self.command(self.cmd["4SE"], 0, 0, [ address ])
	return erase


    def write_bank_address(self, bank):
	print "Inside function write_bank_address that writes the bank byte to 0 (3 byte) or 1 (4 byte)" 
	bank_write = self.command(self.cmd["BRWR"], 0, 0, [ bank ])
	return bank_write 	
	

    def read_bank_address(self):
	print "Inside function read_bank_address that reads the bank byte" 
	bank_read = self.command(self.cmd["BRRD"], 0, 1)
	return bank_read
	
	
	
	
	
