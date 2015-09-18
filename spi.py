import ocpci
import struct
import sys
import time
from bf import * 


#
# This is the spi module
# surf.py and tisc.py need to import this module
#

#It appears that the SPI flash can dump the FIFO faster than we can write to it
#But we did not confirm whether this is due to python speed or actually the SPI being fast enough

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
	x = 0 
	for dat in data_in:
	    self.dev.write(self.base + self.map['SPDR'], dat)
	    val = bf(self.map['SPSR'])
	    x+=1
            if val[6] == 1:
	        return x 	
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
	

    def test_wcol(self, size):
	print "Inside function test_wcol: function to test if we are trying to send too many bytes at a time" 
	self.write_enable()
	data = [] 
	for i in range(size):
	    data.append(0x00) 
	self.command(self.cmd['RES'],0,0,data)
	
    
    def identify(self):
        res = self.command(self.cmd['RES'], 3, 1)
        print "Electronic Signature: 0x%x" % res[0]
        res = self.command(self.cmd['RDID'], 0, 3)
        print "Manufacturer ID: 0x%x" % res[0]
        print "self.device ID: 0x%x 0x%x" % (res[1], res[2])


    def read(self, address, length):
        data_in = []
        data_in.append((address >> 24) & 0xFF)
        data_in.append((address >> 16) & 0xFF)
	data_in.append((address >> 8) & 0xFF)
        data_in.append(address & 0xFF)
        result = self.command(self.cmd['4READ'], 0, length, data_in)
	return result 

	
    def write_enable(self):
        print "Inside function write_enable: command to make SPI flash write enabled" 
        enable = self.command(self.cmd["WREN"], 0, 0)
        return enable
        
        
    def write_disable(self):
        print "Inside function write_disable: command to make SPI flash write disabled" 
        disable = self.command(self.cmd["WRDI"], 0, 0)
        return disable


    def program(self, address, datafilename):
        print "Inside function program"
        self.write_enable()
        if type(datafilename) != str:
            return "data filename must be a string!"   
        datafile = open(datafilename)
        data = datafile.read()
	print data 
	num_eightbit = len(data)/8
	eightbit = [] 
        for i in range(0,len(data),8):
	    eightbit.append(data[i:i+8])
	print "eightbit is:"
	print eightbit
	for i in range(len(eightbit)-1):
	    eightbit[i] = int(("0b" + eightbit[i]),2)
	print "eightbit turned into ints is:"
	print eightbit
        #self.page_program(address, eightbit)          
       
        
        
    def page_program(self, address, data = []):
        print "Inside function page_program: command to program the SPI flash" 
	self.write_enable()
	print hex(address)
	data.append((address >> 24) & 0xFF)
	data.append((address >> 16) & 0xFF)
 	data.append((address >> 8) & 0xFF)
	data.append(address & 0xFF)
	self.command(self.cmd["4PP"], 0, 0, data)

    ''' 
	for i in range(256):
	    data.append(0x00)
	if (len(data)-4) != 256:
	    print "something wrong with data length!"
	    print data
	else:
	    print len(data)
            print data
       
        length=len(data)
	hex_data= []
	for i in range(0,length):
	    hex_data.append(hex(data[i]))
	print hex_data

     '''

    def erase(self, address): 
	print "Inside function erase: command sector erase or SE to erase parts of SPI flash"
	self.write_enable()
	data = []
	data.append((address >> 24) & 0xFF)
	data.append((address >> 16) & 0xFF)
	data.append((address >> 8) & 0xFF)
	data.append((address & 0xFF))
	erase = self.command(self.cmd["4SE"], 0, 0, data)


    def write_bank_address(self, bank):
	print "Inside function write_bank_address that writes the bank byte to 0 (3 byte) or 1 (4 byte)" 
	bank_write = self.command(self.cmd["BRWR"], 0, 0, [ bank ])
	return bank_write 	
	

    def read_bank_address(self):
	print "Inside function read_bank_address that reads the bank byte" 
	bank_read = self.command(self.cmd["BRRD"], 0, 1)
	return bank_read
	
	
	
	
	
