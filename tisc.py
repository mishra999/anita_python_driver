import ocpci
import struct
import sys
import time
from bf import *
import spi


class PicoBlaze:
    instr0_map = { (0x00>>1) : "LOAD",
                   (0x16>>1) : "STAR",
                   (0x02>>1) : "AND",
                   (0x04>>1) : "OR",
                   (0x06>>1) : "XOR",
                   (0x10>>1) : "ADD",
                   (0x12>>1) : "ADDCY",
                   (0x18>>1) : "SUB",
                   (0x1A>>1) : "SUBCY",
                   (0x0C>>1) : "TEST",
                   (0x0E>>1) : "TESTCY",
                   (0x1C>>1) : "COMPARE",
                   (0x1E>>1) : "COMPARECY" }
    instr1_map = { 0x06 : "SL0",
                   0x07 : "SL1",
                   0x04 : "SLX",
                   0x00 : "SLA",
                   0x02 : "RL",
                   0x0E : "SR0",
                   0x0F : "SR1",
                   0x0A : "SRX",
                   0x08 : "SRA",
                   0x0C : "RR",
                   0x80 : "HWBUILD"}
    instr2_map = { (0x08>>1) : "INPUT",
                   (0x2C>>1) : "OUTPUT",
                   (0x2E>>1) : "STORE",
                   (0x0A>>1) : "FETCH" }
    def __init__(self, dev, addr):
        self.dev = dev
        self.addr = addr

    def __repr__(self):
        return "<PicoBlaze in dev:%r at 0x%8.8x>" % (self.dev, self.addr)

    def __str__(self):
        return "PicoBlaze (@%8.8x)" % self.addr

    def read(self, addr = None):
        val = bf(self.dev.read(self.addr))
        oldval = val
        if addr is not None:
            val[27:18] = addr
            val[30] = 0
            self.dev.write(self.addr, int(val))
            val = bf(self.dev.read(self.addr))
            self.dev.write(self.addr, int(oldval))
        return "%3.3x: %s [%s]" % (val[27:18],self.decode(val[17:0]),"RESET" if val[31] else "RUNNING")

    def program(self, path):
        oldctrl = bf(self.dev.read(self.addr))
        # 'addr' points to the BRAM control register
        ctrl = bf(0)
        # set processor_reset
        ctrl[31] = 1
        self.dev.write(self.addr, int(ctrl))
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
                self.dev.write(self.addr, int(ctrl))
                bramaddr = bramaddr + 1
                if bramaddr > 1023:
                    break
        print oldctrl[31]
        if oldctrl[31] == 1:
            print "Leaving PicoBlaze in reset."
        else:
            print "Pulling PicoBlaze out of reset."
            ctrl = 0
            self.dev.write(self.addr, int(ctrl))
        print "PicoBlaze address 0 (reset) readback: %8.8x" % (self.dev.read(self.addr) & 0xFFFFFFFF)        
        
        
    @staticmethod
    def decode(val):
        instr = bf(val)
        instr0 = PicoBlaze.instr0_map.get(instr[17:13])
        if instr0 is not None:
            return "%s s%1.1X, %s" % ( instr0, instr[11:8], format(instr[7:0], 'X') if instr[12] else ("s%1.1X" % instr[7:4]))
        else:
            # Shift/rotate/hwbuild instructions.
            if instr[17:12] == 0x14:
                instr1 = PicoBlaze.instr1_map.get(instr[7:0])
                if instr1 is not None:
                    return "%s s%1.1X" % (instr1, instr[11:8])
                else:
                    return "Illegal instruction."
            # Jump/call instructions.
            elif instr[17:16] == 0x3 and instr[12] == 0:
                return "%s %s%s, %3.3x" % ( "JUMP" if instr[13] else "CALL", "N" if instr[14] else "", "C" if instr[15] else "Z", instr[11:0])
            elif instr[17:12] == 0x22 or instr[17:12] == 0x20:
                return "%s %3.3x" % ( "JUMP" if instr[13] else "CALL", instr[11:0] )
            elif instr[17:12] == 0x24 or instr[17:12] == 0x26:
                return "%s@ (s%1.1X,s%1.1X)" % ( "JUMP" if instr[13] else "CALL", instr[11:8], instr[7:4])
            # Return.
            # 11 0001
            # 11 0101
            # 11 1001
            # 11 1101
            elif instr[17:16] == 0x3 and instr[12:11] == 1:
                return "RETURN %s%s" % ( "N" if instr[14] else "", "C" if instr[15] else "Z")
            elif instr[17:12] == 0x25:
                return "RETURN"
            # In/out/store/fetch
            elif instr[17:13] == (0x08>>1) or instr[17:13] == (0x2C>>1) or instr[17:13] == (0x2E>>1) or instr[17:13] == (0x0A>>1):
                return "%s s%1.1X, %s" % ( PicoBlaze.instr2_map[instr[17:13]], instr[11:8], format(instr[7:0],'X') if instr[12] else ("(s%1.1X)"%instr[7:4]))
            elif instr[17:12] == 0x2B:
                return "OUTPUTK %2.2x, %2.2x" % (instr[11:4], instr[3:0])
            # Specialty
            elif instr[17:12] == 0x37:
                return "REGBANK %s" % ("B" if instr[0] else "A")
            elif instr[17:13] == (0x28>>1):
                return "%s%s%s" % ( "RETURNI " if instr[12] else "", "ENABLE" if instr[0] else "DISABLE", "" if instr[12] else " INTERRUPT")
            elif instr[17:12] == 0x21:
                return "LOAD&RETURN s%1.1X, %2.2X" % (instr[11:8], instr[7:0])

class GLITC:
    map = { 'ident'          : 0x000000,
            'ver'            : 0x000004,
            'control'        : 0x000008,
            'DPCTRL0'        : 0x000080,
            'DPCTRL1'        : 0x000084,
            'DPTRAINING'     : 0x000088,
            'DPCOUNTER'      : 0x00008C,
            'DPIDELAY'       : 0x000090,
            'RDINPUT'        : 0x000100,
            'RDCTRL'         : 0x000104,
            'settings_dac'   : 0x000140,
            'settings_atten' : 0x000160,
            'settings_sc'    : 0x000178,
            'settings_pb'    : 0x00017C,
            'phasescan_pb'   : 0x000058,
            'GICTRL0'        : 0x000180,
            'GICTRL1'        : 0x000184,
            'GITRAIN'        : 0x000188,
            'GIDELAY'        : 0x00018C}
            
    def __init__(self, dev, base):
        self.dev = dev
        self.base = base
        self.settings_pb = PicoBlaze(self, self.map['settings_pb'])
        self.phasescan_pb = PicoBlaze(self, self.map['phasescan_pb'])
        
    def __repr__(self):
        return "<GLITC in dev:%r at 0x%8.8x>" % (self.dev, self.base)

    def __str__(self):
        return "GLITC (@%8.8x)" % self.base

    def status(self):
        ctrl = bf(self.read(self.map['control']))
        print "Clock status (%8.8x)   : SYSCLK = REFCLK%s" % (int(ctrl)&0xFFFFFFFF, "" if ctrl[0] else "x6.5")
        print "                          : 6.5x MMCM is %spowered down" % ("" if ctrl[1] else "not ")
        print "                          : MMCMs are %sin reset" % ("" if ctrl[2] else "not ")
        ctrl = bf(self.read(self.map['DPCTRL0']))
        print "Datapath status (%8.8x): FIFO is %senabled" % (int(ctrl)&0xFFFFFFFF, "" if ctrl[1] else "not ")
        print "                          : DELAYCTRL is %sready" % ("" if ctrl[4] else "not ")
        print "                          : Datapath inputs are %senabled" % ("not " if ctrl[5] else "")
        ctrl = bf(self.read(self.map['DPCTRL1']))
        print "VCDL status (%8.8x)    : REFCLK R0, CH0 is %s" % (int(ctrl)&0xFFFFFFFF, "high" if ctrl[16] else "low")
        print "                          : REFCLK R0, CH1 is %s" % ("high" if ctrl[17] else "low")
        print "                          : REFCLK R0, CH2 is %s" % ("high" if ctrl[18] else "low")
        print "                          : REFCLK R1, CH0 is %s" % ("high" if ctrl[19] else "low")
        print "                          : REFCLK R1, CH1 is %s" % ("high" if ctrl[20] else "low")
        print "                          : REFCLK R1, CH2 is %s" % ("high" if ctrl[21] else "low")
        print "                          : R0 VCDL is %srunning" % ("" if ctrl[29] else "not ")
        print "                          : R1 VCDL is %srunning" % ("" if ctrl[31] else "not ")
        ctrl = bf(self.read(self.map['DPTRAINING']))
        print "Training status (%8.8x): Training is %s" % (int(ctrl)&0xFFFFFFFF, "off" if ctrl[31] else "on")
        print "                          : Training is in %s view" % ("sample" if ctrl[29] else "signal")
        print "                          : Training latch is %senabled" % ("" if ctrl[28] else "not ")

    def datapath_input_ctrl(self, enable):
        val = bf(self.read(self.map['DPCTRL0']))
        if enable == 0:
            val[5] = 1
        else:
            val[5] = 0
        print "Going to write %8.8x" % int(val)
        self.write(self.map['DPCTRL0'], int(val))

    def datapath_initialize(self):
        self.datapath_input_ctrl(1)
        # Do something here about checking polarity
        # of REFCLK. Turn off VCDL first, then
        # check polarity, invert if needed, and restart.
        self.vcdl(0, 1)
        self.vcdl(1, 1)
        # Maybe do something here about autotuning?
        self.fifo_ctrl(0)
        self.serdes_reset()
        self.fifo_reset()
        self.fifo_ctrl(1)
        
    def serdes_reset(self):
        val = bf(self.read(self.map['DPCTRL0']))
        val[2] = 1
        self.write(self.map['DPCTRL0'], int(val))
    
    def fifo_reset(self):
        val = bf(self.read(self.map['DPCTRL0']))
        val[0] = 1
        self.write(self.map['DPCTRL0'], int(val))
        
    def fifo_ctrl(self, en):
        val = bf(self.read(self.map['DPCTRL0']))
        val[1] = en
        self.write(self.map['DPCTRL0'], int(val))

    def vcdl_pulse(self, channel):
        if channel > 1:
            print "Illegal RITC channel (%d)" % channel
            return
        val = bf(self.read(self.map['DPCTRL1']))
        if channel == 0:
            val[28] = 1
        else:
            val[30] = 1
        self.write(self.map['DPCTRL1'], int(val))
        
    def vcdl(self, channel, value = None):
        if channel > 1:
            print "Illegal RITC channel (%d)" % channel
            return None
        if value is None:
            val = bf(self.read(self.map['DPCTRL1']))
            if channel == 0:
                return 1 if val[29] else 0
            else:
                return 1 if val[31] else 0
        else:
            val = bf(self.read(self.map['DPCTRL1']))
            if channel == 0:
                val[29] = value
            else:
                val[31] = value
            self.write(self.map['DPCTRL1'], int(val))
            return value

    def counters(self):
        val = bf(0)
        for i in range(6):
            val[19:16] = i
            self.write(self.map['DPCOUNTER'], int(val))
            time.sleep(0.1)
            v2 = bf(self.read(self.map['DPCOUNTER']))
            print "Channel %d: %d" % (i, v2[15:0])

    def train_latch_ctrl(self, en):
        val = bf(self.read(self.map['DPTRAINING']))
        val[28] = en
        self.write(self.map['DPTRAINING'], int(val))
            
    def training_ctrl(self, en):
        val = bf(self.read(self.map['DPTRAINING']))
        if en == 0:
            val[31] = 1
        else:
            val[31] = 0
        self.write(self.map['DPTRAINING'], int(val))
        
    def train_read(self, channel, bit_or_sample, sample_view=0):
        val = bf(self.read(self.map['DPTRAINING']))
        smp = bf(bit_or_sample)
        val[28] = 1
        val[29] = sample_view
        val[19:16] = smp[3:0]
        val[23] = smp[4]
        val[22:20] = channel
        self.write(self.map['DPTRAINING'], int(val))
        v2 = bf(self.read(self.map['DPTRAINING']))
        return v2[7:0]

    def eye_autotune_all(self):
        for i in (0,1,2,4,5,6):
            for j in xrange(12):
                self.eye_autotune(i,j)
    
    # I should believe in exceptions, really I should.
    def eye_autotune(self, channel, bit, verbose=1):
        eyevars = self.eye_scan(channel, bit, verbose)
        if eyevars[0] == 0:
            print "eye_autotune error: eye start not found (%2.2x %2.2x %2.2x)" % eyevars
            return -1
        elif eyevars[2] != 0x2B and eyevars[2] != 0x95 and eyevars[2] != 0xCA and eyevars[2] != 0x65:
            print "eye_autotune error: unknown value in eye (%2.2x %2.2x %2.2x)" % eyevars
            return -1
        eyecenter = (eyevars[1] + eyevars[0])/2
        self.delay(channel, bit, int(eyecenter))
        bitslip_count = 0
        if eyevars[2] == 0x2B:
            bitslip_count = 2
        elif eyevars[2] == 0x95:
            bitslip_count = 1
        elif eyevars[2] == 0x65:
            bitslip_count = 3
        if verbose == 1:
            print "eye_autotune: setting to delay %d" % eyecenter
            print "eye_autotune: bitslipping %d time%s" % ( bitslip_count, ("" if bitslip_count == 1 else "s"))
        for i in xrange(bitslip_count):
            self.bitslip(channel, bit)
        return bitslip_count
    
    def eye_scan(self, channel, bit, verbose=1):
        val = bf(self.read(self.map['DPTRAINING']))
        val[22:20] = channel
        val[19:16] = bit
        val[28] = 1
        val[29] = 0
        self.write(self.map['DPTRAINING'], int(val))
        old_train = 0
        stable_count = 0
        eye_start = 0
        eye_stop = 0
        found_eye_start = 0
        looking_for_stop = 0
        train_in_eye = 0
        for i in xrange(32):
            self.delay(channel, bit, i)
            new_train = self.train_read(channel, bit)
            if i==0:
                old_train = new_train
            else:
                if new_train == old_train:
                    stable_count = stable_count + 1
                    if stable_count > 9:
                        if found_eye_start == 0:
                            eye_start = i-stable_count
                            found_eye_start = 1
                            train_in_eye = new_train
                else:
                    stable_count = 0
                    if found_eye_start == 1:
                        eye_stop = i
                        break
                old_train = new_train
        if verbose == 1:
            print "Ch%2.2d Bit %2.2d Eye scan: (%2.2d - %2.2d) [%2.2X]" % (channel, bit, eye_start, eye_stop, train_in_eye)
        return (eye_start, eye_stop, train_in_eye)
    
    def delay(self, channel, bit, value):
        val = bf(0)
        val[7:0] = value
        val[19:16] = bit
        val[22:20] = channel
        val[31] = 1
        self.write(self.map['DPIDELAY'], int(val))
    
    def bitslip(self, channel, bit):
        val = bf(self.read(self.map['DPTRAINING']))
        val[22:20] = channel
        val[19:16] = bit
        val[30] = 1
        self.write(self.map['DPTRAINING'], int(val))
        
    def rdac(self, ritc, channel, value = None):
        if ritc > 1:
            print "Illegal RITC channel %d" % ritc
            return None
        if channel > 32:
            print "Illegal RITC DAC channel %d" % channel
            return None
        if value is None:
            print "RITC DAC readback not supported yet"
            return None
        else:
            val = bf(0x0)
            val[11:0] = value
            val[17:12] = channel
            val[18] = ritc
            self.write(self.map['RDINPUT'], int(val))
            self.write(self.map['RDCTRL'], 0x1)
            val = bf(self.read(self.map['RDCTRL']))
            while val[1]:
                print "Loader busy, waiting..."
                val = bf(self.read(self.map['RDCTRL']))
    
    def identify(self):
        ident = bf(self.read(self.map['ident']))
        ver = bf(self.read(self.map['ver']))
        print "Identification Register: %x (%c%c%c%c)" % (int(ident),ident[31:24],ident[23:16],ident[15:8],ident[7:0])
        print "Version Register: %d.%d.%d compiled %d/%d" % (ver[15:12], ver[11:8], ver[7:0], ver[28:24], ver[23:16])

    def read(self, addr):
        return self.dev.read(addr + self.base)
    
    def write(self, addr, value):
        self.dev.write(addr + self.base, value)

    def dac(self, channel, value = None):
        if channel > 8:
            print "Illegal DAC channel (%d)" % channel
            return None
        if value is None:
            return self.read(self.map['settings_dac'] + channel*4)
        else:
            value = value & 0xFFF
            if value > 2000:
                print "DAC value is too high (%d)!" % value
                return None
            print "Writing %8.8x to DAC %d" % ( value, channel)
            self.write(self.map['settings_dac'] + channel*4, value)
            return value

    def dac_mv(self, channel, value = None):
        if channel > 8:
            print "Illegal DAC channel (%d)" % channel
            return None
        if value is None:
            return int(self.read(self.map['settings_dac']+channel*4)*2500/4095)
        else:
            value = int(value*4095./2500.) & 0xFFF
            print "Writing %8.8x to DAC %d" % (value, channel)
            self.write(self.map['settings_dac'] + channel*4, value)
            return int(value*4095./2500.)
            
    def atten(self, channel, value = None):
        if value is None:
            return self.read(self.map['settings_atten'] + channel*4)
        else:
            value = value & 0x1F
            self.write(self.map['settings_atten'] + channel*4, value)
            return value
        
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
        self.spi = spi.SPI(self, self.map['spi_base'])
        self.GA = GLITC(self, self.map['GA'])
        self.GB = GLITC(self, self.map['GB'])
        self.GC = GLITC(self, self.map['GC'])
        self.GD = GLITC(self, self.map['GD'])

    def __repr__(self):
        return "<TISC at %s>" % self.path

    def __str__(self):
        return "TISC (@%s)" % self.path
    
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
