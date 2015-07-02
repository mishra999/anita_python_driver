import ocpci
import struct
import sys
import time
#import surf
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

class PicoBlaze: #no changes from the copy in the tisc.py class
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

##Shouldn't need to rework the SPI class
class SPI: #SPI = serial peripheral interface
    map = { 'SPI_CtrlReg'    : 0x00030,
            'SPI_StatusReg'  : 0x00034,
            'SPI_WR'         : 0x00038,
            'SPI_ExtCtrlReg' : 0x0003C }
    
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
        val = bf(self.dev.read(self.base + self.map['SPI_CtrlReg']))
        val[6] = 1;
        val[3] = 0;
        val[2] = 0;
        self.dev.write(self.base + self.map['SPI_CtrlReg'], int(val))

    def command(self, device, command, dummy_bytes, num_read_bytes, data_in = [] ):
        self.dev.spi_cs(device, 1)
        self.dev.write(self.base + self.map['SPI_WR'], command)
        for dat in data_in:
            self.dev.write(self.base + self.map['SPI_WR'], dat)
        for i in range(dummy_bytes):
            self.dev.write(self.base + self.map['SPI_WR'], 0x00)
        # Empty the read FIFO.
        while not (self.dev.read(self.base + self.map['SPI_StatusReg']) & self.bits['RFEMPTY']):
            self.dev.read(self.base + self.map['SPI_WR'])
        rdata = []
        for i in range(num_read_bytes):
            self.dev.write(self.base + self.map['SPI_WR'], 0x00)
            rdata.append(self.dev.read(self.base + self.map['SPI_WR']))
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
        
class SURF(ocpci.Device):
    map = { 'SURF_Dev'      	: 0x00000,
            'SURF_Ver'      	: 0x00004,
			'SURF_IntStatus' 	: 0x00008, 
			'SURF_IntMask' 		: 0x0000C, 
			'SURF_PPSSel' 		: 0x00010, 
			'SURF_Reset' 		: 0x00014, 
			'SURF_LED' 		: 0x00018, 
			'SURF_ClkSel' 		: 0x0001C,  ##this is a clock
			'SURF_PllCtrl' 		: 0x00020,  ##this is a clock, PLL = phase locked loop 
            		'spi_cs'     		: 0x00024,  ##this is the spiss variable in the firmware doc 
            		'spi_base'   		: 0x00030,
			}

    def __init__(self, path="/sys/class/uio/uio0"):
        ocpci.Device.__init__(self, path, 1*1024*1024)
        self.spi = SPI(self, self.map['spi_base'])

    def __repr__(self):
        return "<SURF at %s>" % self.path

    def __str__(self):
        return "SURF (@%s)" % self.path
    
    def spi_cs(self, device, state):
        # We only have 1 SPI device.
        val = bf(self.read(self.map['spi_cs']))
        val[device] = state
        self.write(self.map['spi_cs'], int(val))
		
				
    def led(self, arg):
	    self.led_unusedbits = "0000"                 
	    #self.led_VALUE_list = [0]*12  #array so that we can change values, setting all to zero initially 
	    self.led_KEY_list = [1]*12    #array so that we can change values, setting all to one initially
	    print "LED function works!"
            print "  "
            #self.led = bf(self.read(self.map['SURF_LED']))
	    if arg == "all off":
		self.led_off()                             # call the function for turning LED's off 
	    elif arg == "all on":
		self.led_on()                             # call the function for turning LED's on 
	    elif arg == "release":
		self.led_release()                        # call function for releasing LED (we stop controlling it)
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
	if value == 0:
	    led_VALUE_list = [1]*12
	if value == 1:
	    led_VALUE_list = [0]*12
        led_current = bf(self.read(self.map['SURF_LED']))
	#print "led_current type is: %s " % (type(led_current))
	x = "{0:b}".format(led_current[31:0])
	print x
        print "the type of x is: %s" % (type(x))
        print " " 
        #led_VALUE_list = led_current[11:0]
	print led_VALUE_list
        led_VALUE_list[led_num] = value
        led_VALUE_string = self.list_to_string(led_VALUE_list)
        led_KEY_string = self.list_to_string(self.led_KEY_list)
        led_full_string = self.led_unusedbits + led_KEY_string + self.led_unusedbits + led_VALUE_string 
        print "current LED values in binary: " + led_full_string
        self.write(self.map['SURF_LED'],int(led_full_string,base=2))
			

    def led_off(self):
	self.write(self.map['SURF_LED'],0x0fff0000)
            		

    def led_on(self):
	self.write(self.map['SURF_LED'],0x0fff0fff)           
            

    def led_release(self):
	self.write(self.map['SURF_LED'],0x00000000)  
       
			
    def status(self):
       		clocksel = bf(self.read(self.map['SURF_ClkSel']))
		pullctrl = bf(self.read(self.map['SURF_PllCtrl']))
		int_status = bf(self.read(self.map['SURF_IntStatus']))
		int_mask = bf(self.read(self.map['SURF_IntMask']))
		led = bf(self.read(self.map['SURF_LED']))
       		print "Clock Status: LAB4 Clock is %s (SURF_ClkSel[1] = %d)" % ("enabled" if clocksel[1] else "not enabled", clocksel[1])
		print "            : LAB4 Driving Clock is %s (SURF_ClkSel[0] = %d)" % ("TURF Clock" if clocksel[0] else "FPGA Clock", clocksel[0])
        	print "            : FPGA Driving Clock is %s (SURF_ClkSel[2] = %d)" % ("TURF Clock" if clocksel[2] else "Local Clock", clocksel[2])
		print " Int Status : %8.8x" % (self.read(self.map['SURF_IntStatus']) & 0xFFFFFFFF)
		print " LED        : Internal value %3.3x, Key value %3.3x" % (led[11:0], led[27:16])
		print " Full LED   : %8.8x" % (self.read(self.map['SURF_LED']) & 0xFFFFFFFF)
		print " Int Mask   : %8.8x" % (self.read(self.map['SURF_IntMask']) & 0xFFFFFFFF)
		
		
		
		
    def identify(self):
        ident = bf(self.read(self.map['SURF_Dev']))
        ver = bf(self.read(self.map['SURF_Ver']))
        print "Identification Register: %x (%c%c%c%c)" % (int(ident),ident[31:24],ident[23:16],ident[15:8],ident[7:0])
        print "Version Register: %d.%d.%d compiled %d/%d" % (ver[15:12], ver[11:8], ver[7:0], ver[28:24], ver[23:16])
