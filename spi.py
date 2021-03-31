import struct
import sys
import time
import hexfile
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
        res = self.command(self.cmd['RES'], 3, 1)
        self.electronic_signature = res[0]
        res = self.command(self.cmd['RDID'], 0, 3)
        self.manufacturer_id = res[0]
        self.memory_type = res[1]
        self.memory_capacity = 2**res[2]        
        
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

    def status(self):
        res = self.command(self.cmd['RDSR'], 0, 1)
        return res[0]
    

    def identify(self):
        print "Electronic Signature: 0x%x" % self.electronic_signature
        print "Manufacturer ID: 0x%x" % self.manufacturer_id
        print "Memory Type: 0x%x Memory Capacity: %d bytes" % (self.memory_type, self.memory_capacity)
#        res = self.command(self.cmd['RES'], 3, 1)
#        print "Electronic Signature: 0x%x" % res[0]
#        res = self.command(self.cmd['RDID'], 0, 3)
#        print "Manufacturer ID: 0x%x" % res[0]
#        print "self.device ID: 0x%x 0x%x" % (res[1], res[2])


    def read(self, address, length):
        if self.memory_capacity > 2**24:
            data_in = []
            data_in.append((address >> 24) & 0xFF)
            data_in.append((address >> 16) & 0xFF)
            data_in.append((address >> 8) & 0xFF)
            data_in.append(address & 0xFF)
            result = self.command(self.cmd['4READ'], 0, length, data_in)
        else:
            data_in = []
            data_in.append((address >> 16) & 0xFF)
            data_in.append((address >> 8) & 0xFF)
            data_in.append(address & 0xFF)
            result = self.command(self.cmd['3READ'], 0, length, data_in)
	return result 

	
    def write_enable(self):
        enable = self.command(self.cmd["WREN"], 0, 0)
        trials = 0
        while trials < 10:
            res = self.status()
            if not res & 0x2:
                trials = trials + 1
            else:
                print "Write enable succeeded (%d)." % res
                break

    def write_disable(self):
        disable = self.command(self.cmd["WRDI"], 0, 0)
        res = self.status()
        if res & 0x2:
            print "Write disable failed (%d)!" % res

    def program_mcs(self, filename):
        f = hexfile.load(filename)
        # Figure out what sectors we need to erase.
        sector_size = 0
        total_size = 0
        page_size = 256
        if self.memory_capacity == 2**24:
            sector_size = 256*1024
            total_size = self.memory_capacity
        elif self.memory_capacity == 2**25:
            sector_size = 256*1024
            total_size = self.memory_capacity
        elif self.memory_capacity == 2**20:
            sector_size = 64*1024
            total_size = self.memory_capacity
        else:
            print "Don't know how to program flash with capacity %d" % self.memory_capacity
            return
        erase_sectors = [0]*(total_size/sector_size)
        sector_list = []
        for seg in f.segments:
            print "Segment %s starts at %d" % (seg, seg.start_address)
            start_sector = seg.start_address/sector_size
            print "This is sector %d" % start_sector
            if erase_sectors[start_sector] == 0:
                erase_sectors[start_sector] = 1
                sector_list.append(start_sector)
            end_address = seg.end_address
            end_sector = start_sector + 1
            while end_sector*sector_size < seg.end_address:
                if erase_sectors[end_sector] == 0:
                    erase_sectors[end_sector] = 1
                    sector_list.append(end_sector)
                end_sector = end_sector + 1
        for erase in sector_list:
            print "I think I should erase sector %d" % erase
            self.erase(erase*sector_size)
        for seg in f.segments:
            start = seg.start_address
            end = 0
            while start < seg.size:
                end = start + page_size
                if end > seg.end_address:
                    end = seg.end_address
                data = seg[start:end].data
                print "Programming %d-%d" % (start, end)
                self.page_program(start, data)
                start = end
                
        self.write_disable()
        print "Complete!"

    def page_program(self, address, data_write = []):
        self.write_enable()
        data_write.insert(0,(address & 0xFF))
        data_write.insert(0,((address>>8) & 0xFF))
        data_write.insert(0,((address>>16) & 0xFF))
        if self.memory_capacity > 2**24:
            data_write.insert(0,((address>>24) & 0xFF))
            self.command(self.cmd["4PP"],0,0,data_write)
        else:
            self.command(self.cmd["3PP"],0,0,data_write)
        res = self.status()
        trials = 0
        while trials < 10:
            res = self.status()
            if res & 0x1:
                break
            trials = trials + 1
        trials = 0
        while res & 0x1:
            res = self.status()
            trials = trials + 1

    def erase(self, address): 
	self.write_enable()
        if self.memory_capacity > 2**24:
            data = []
            data.append((address >> 24) & 0xFF)
            data.append((address >> 16) & 0xFF)
            data.append((address >> 8) & 0xFF)
            data.append((address & 0xFF))
            erase = self.command(self.cmd["4SE"], 0, 0, data)
        else:
            data = []
            data.append((address>>16) & 0xFF)
            data.append((address>>8) & 0xFF)
            data.append((address & 0xFF))
            erase = self.command(self.cmd["3SE"], 0, 0, data)
        res = self.status()
        print "Checking for erase start..."
        trials = 0
        while trials < 10:
            res = self.status()
            if res & 0x1:
                break
        print "Erase started. Waiting for erase complete..."
        trials = 0
        while res & 0x1:
            res = self.status()
            trials = trials + 1
        print "Erase complete after %d trials." % trials

    def write_bank_address(self, bank):
        if self.memory_capacity > 2**24:
            return
	bank_write = self.command(self.cmd["BRWR"], 0, 0, [ bank ])
	return bank_write 	
	

    def read_bank_address(self):
        if self.memory_capacity > 2**24:
            res = []
            res.append(0)
            return res
	bank_read = self.command(self.cmd["BRRD"], 0, 1)
	return bank_read
	
	
	
	
	
