import ocpci
import struct
import sys

#
# Bitfield manipulation. Note that ordering
# can be Python (smallest first) or Verilog
# (largest first) for easy compatibility
#

class bf(object):
    def __init__(self, value=0):
        self._d = int(value)
    
    def __getitem__(self, index):
        return (self._d >> index) & 1
    
    def __setitem__(self,index,value):
        value = (value & 1L)<<index
        mask = (1L)<<index
        self._d = (self._d & ~mask) | value
    
    def __getslice__(self, start, end):
        if start > end:
            tmp = end
            end = start
            start = tmp
        mask = (((1L)<<(end+1))-1) >> start
        return (self._d >> start) & mask
    
    def __setslice__(self, start, end, value):
        if start > end:
            tmp = end
            end = start
            start = tmp
        mask = (((1L)<<(end+1))-1) >> start
        value = (value & mask) << start
        mask = mask << start
        self._d = (self._d & ~mask) | value
        return (self._d >> start) & mask
    
    def __int__(self):
        return self._d

class GLITC:
    map = { 'ident'        : 0x000000,
            'ver'          : 0x000004,
            'settings_sc'  : 0x000178,
            'settings_pb'  : 0x00017C,
            'phasescan_pb' : 0x000058}
            
    def __init__(self, dev, base):
        self.dev = dev
        self.base = base
        
    def identify(self):
        ident = bf(self.read(self.map['ident']))
        ver = bf(self.read(self.map['ver']))
        print "Identification Register: %x (%c%c%c%c)" % (int(ident),ident[31:24],ident[23:16],ident[15:8],ident[7:0])
        print "Version Register: %d.%d.%d compiled %d/%d" % (ver[15:12], ver[11:8], ver[7:0], ver[28:24], ver[23:16])

    def pbprogram(self, addr, path):
        print "Programming PicoBlaze through register %8.8x" % addr
        oldctrl = bf(self.read(addr))
        # 'addr' points to the BRAM control register
        ctrl = bf(0)
        # set processor_reset
        ctrl[31] = 1
        self.write(addr, int(ctrl))
        # enable BRAM WE
        ctrl[30] = 1
        bramaddr=0
        with open(path,"rb") as f:        
            for line in f:
                instr = int(line, 16)
                if bramaddr == 0:
                    print "PicoBlaze address 0 (reset) instruction: %8.8x" % instr
                ctrl[17:0] = instr
                ctrl[27:18] = bramaddr
                self.write(addr, int(ctrl))
                bramaddr = bramaddr + 1
                if bramaddr > 1023:
                    break
        print oldctrl[31]
        if oldctrl[31] == 1:
            print "Leaving PicoBlaze in reset."
        else:
            print "Pulling PicoBlaze out of reset."
            ctrl = 0
            self.write(addr, int(ctrl))
        print "PicoBlaze address 0 (reset) readback: %8.8x" % (self.read(addr) & 0xFFFFFFFF)        

    def read(self, addr):
        return self.dev.read(addr + self.base)
    
    def write(self, addr, value):
        self.dev.write(addr + self.base, value)
        
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
            'READ'       : 0x03 ,
            'FASTREAD'   : 0x0B ,
            'PP'         : 0x02 ,
            'SE'         : 0xD8 ,
            'BE'         : 0xC7 }
    
    bits = { 'SPIF'      : 0x80,
             'WCOL'      : 0x40,
             'WFFULL'    : 0x08,
             'WFEMPTY'   : 0x04,
             'RFFULL'    : 0x02,
             'RFEMPTY'   : 0x01 }
    
    def __init__(self, dev, base):
        self.dev = dev
        self.base = base
        val = bf(self.dev.read(self.base + self.map['SPCR']))
        val[6] = 1;
        val[3] = 0;
        val[2] = 0;
        self.dev.write(self.base + self.map['SPCR'], int(val))

    def command(self, device, command, dummy_bytes, num_read_bytes, data_in = [] ):
        self.dev.spi_cs(device, 1)
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
        self.dev.spi_cs(device, 0)    
        return rdata
    
    def identify(self, device=0):
        res = self.command(device, self.cmd['RES'], 3, 1)
        print "Electronic Signature: 0x%x" % res[0]
        res = self.command(device, self.cmd['RDID'], 0, 3)
        print "Manufacturer ID: 0x%x" % res[0]
        print "Device ID: 0x%x 0x%x" % (res[1], res[2])

    def read(self, address, length=1, device=0):
        data_in = []
        data_in.append((address >> 16) & 0xFF)
        data_in.append((address >> 8) & 0xFF)
        data_in.append(address & 0xFF)
        res = self.command(device, self.cmd['READ'], 0, length, data_in)
        return res        
        
class TISC(ocpci.Device):
    map = { 'ident'      : 0x000000,
            'ver'        : 0x000004,
            'clock'      : 0x000008,
            'spi_cs'     : 0x00000C,
            'spi_base'   : 0x000010,
            'glitc_ctrl' : 0x000040,
            'GA'         : 0x100000,
            'GB'         : 0x140000,
            'GC'         : 0x180000,
            'GD'         : 0x1C0000 }

    glitc_base           = 0x100000
    glitc_offset         = 0x040000

    glitc_init_bit         = 0x100
    glitc_prog_bit         = 0x1
    glitc_done_bit         =  0x10000
    glitc_config_done_bit  = 0x10

    def __init__(self, path="/sys/class/uio/uio0"):
        ocpci.Device.__init__(self, path, 2*1024*1024)
        self.spi = SPI(self, self.map['spi_base'])
        self.GA = GLITC(self, self.map['GA'])
        self.GB = GLITC(self, self.map['GB'])
        self.GC = GLITC(self, self.map['GC'])
        self.GD = GLITC(self, self.map['GD'])
        
    def spi_cs(self, device, state):
        # We only have 1 SPI device.
        val = bf(self.read(self.map['spi_cs']))
        val[device] = state
        self.write(self.map['spi_cs'], int(val))

    def status(self):
        gc = bf(self.read(self.map['glitc_ctrl']))
        for i in xrange(4):
            print "GLITC %c Status: INIT_B %s" % ( chr(ord('A')+i), "went high" if gc[8+i] else "did not go high")
            print "              : DONE %s" % ( "went high" if gc[16+i] else "did not go high")
            print "              : %s" % ( "is in normal mode" if gc[4+i] else "is in config mode")
            print ""
        clock = bf(self.read(self.map['clock']))
        print "Clock Status: Local Clock is %s (EN_LOCAL_CLK = %d)" % ("enabled" if clock[1] else "not enabled", clock[1])
        print "            :   SYS Clock is %s (SYSCLK_SEL = %d)" % ("Local Clock" if clock[0] else "TURF Clock", clock[0])

        
    def identify(self):
        ident = bf(self.read(self.map['ident']))
        ver = bf(self.read(self.map['ver']))
        print "Identification Register: %x (%c%c%c%c)" % (int(ident),ident[31:24],ident[23:16],ident[15:8],ident[7:0])
        print "Version Register: %d.%d.%d compiled %d/%d" % (ver[15:12], ver[11:8], ver[7:0], ver[28:24], ver[23:16])
        
    def gprogram(self, glitc, path):
        if glitc > 3 or glitc < 0:
            return
        with open(path,"rb") as f:
            header = "\x00\x09\x0F\xF0\x0F\xF0\x0F\xF0\x0F\xF0\x00"
            # First 11 bytes: header
            test = f.read(11)
            if header != test:
                print "Improper header in file %s." % path
                return
            version = struct.unpack(">H", f.read(2))[0]
            if version != 1:
                print "Improper file version: %d." % version
                return
            for x in xrange(4):
                tag = f.read(1)
                length = struct.unpack(">H", f.read(2))[0]
                string = f.read(length)
                if tag == 'a':
                    print "Filename: %s" % string
                elif tag == 'b':
                    print "Device name: %s" % string
                elif tag == 'c':
                    print "Date stamp: %s" % string
                elif tag == 'd':
                    print "Time stamp: %s" % string
                else:
                    print "Improper tag: %c" % tag
                    return
            btag = f.read(1)
            if btag != 'e':
                print "Improper bulk tag: %c" % btag
            length = struct.unpack(">I", f.read(4))[0]
            print "Bitstream length: %d" % length
            print "Issuing program request."
            tmp = self.read(self.map['glitc_ctrl'])
            tmp = tmp | (self.glitc_prog_bit<<glitc)
            self.write(self.map['glitc_ctrl'], tmp)
            for i in xrange(1000):
                if self.read(self.map['glitc_ctrl']) & (self.glitc_init_bit<<glitc):
                    break
            if i == 1000:
                print "INIT_B did not go high - program failed."
                return
            print "Initialization complete, INIT_B is high."
            i = 0
            next_check = 0
            while i < length:
                val = struct.unpack("<I", f.read(4))[0]
                val = ((val>>1) & 0x55555555L) | ((val & 0x55555555L) << 1)
                val = ((val>>2) & 0x33333333L) | ((val & 0x33333333L) << 2)
                val = ((val>>4) & 0x0F0F0F0FL) | ((val & 0x0F0F0F0FL) << 4)
                val = ((val>>8) & 0x00FF00FFL) | ((val & 0x00FF00FFL) << 8)
                val = ((val >> 16) & 0x0000FFFFL) | ((val & 0x0000FFFFL) << 16)
                self.write(self.glitc_base + self.glitc_offset*glitc, val)
                if i == next_check:
                    print "%d / %d" % (i , length)
                    next_check = next_check + (length/4)
                    next_check = next_check & ~0x3
                i = i + 4
            print "Bitstream load done - checking DONE bit."
            if not self.read(self.map['glitc_ctrl']) & (self.glitc_done_bit << glitc):
                print "Programming failed - DONE bit not high (%8.8x)" % self.read(self.map['glitc_ctrl'])
            else:
                tmp = self.read(self.map['glitc_ctrl'])
                tmp = tmp | (self.glitc_config_done_bit << glitc)
                self.write(self.map['glitc_ctrl'], tmp)
                print "Programming complete."
