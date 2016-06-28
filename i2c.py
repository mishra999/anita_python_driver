'''
06-2016 
Class to manage the OpenCores I2C controller core
'''

class I2C:
    map = {'PREL'    : 0x00,
           'PREH'    : 0x04,
           'CTR'     : 0x08,
           'TX'      : 0x0C,
           'RX'      : 0x0C,
           'CR'      : 0x10,
           'SR'      : 0x10  }

    cmd = {'STA'     : 0x80,  # generate (repeated) start condition
           'STO'     : 0x40,  # generate stop condition
           'RD'      : 0x20,  # read from slave
           'WR'      : 0x10,  # write to slave
           'NACK'    : 0x08 } # NACK 

    stat = {'RXACK'  : 0x80,  # received acknowledge from slave
            'TIP'    : 0x02 } # transfer-in-progress
    
    def __init__(self, dev, base, slave_addr, prescaler=0x41, enable_core=True):
        self.dev = dev
        self.base = base
        self.address = slave_addr
        #prescaler = sys_clk / (5* scl) - 1 
        self.dev.write(self.base + self.map['PREL'], (prescaler & 0xFF))
        self.dev.write(self.base + self.map['PREH'], ((prescaler >> 8) & 0xFF))
        if enable_core:
            self.dev.write(self.base + self.map['CTR'], 0x80)
        else:
            print 'you probably meant to enable the i2c core'

    '''
    transfer-in-progress loop
    '''
    def poll_tip(self, timeout=None):
        while(self.dev.read(self.base + self.map['SR']) & self.stat['TIP']):
            pass

    '''
    check ACK/NACK
    '''
    def check_ack(self):
        if (self.dev.read(self.base + self.map['SR']) & self.stat['RXACK']):
            raise Exception('No ACK from slave address: 0x{0:x}'.format(self.address))
    '''
    start transaction, mode=1 for read, 0 for write
    ''' 
    def start(self, read_mode=False): 
        addr = self.address << 1
        addr = addr | read_mode
        self.dev.write(self.map['TX'] + self.base, addr)  #send data to tx register
        self.dev.write(self.map['CR'] + self.base, self.cmd['STA'] | self.cmd['WR'])
        self.poll_tip()
        self.check_ack()

    '''
    write a byte of data to slave device
    ''' 
    def write(self, data, last_byte=False):
        self.dev.write(self.map['TX'] + self.base, data & 0xFF)
        cr_cmd=self.cmd['WR']
        if last_byte:
            cr_cmd = cr_cmd | self.cmd['STO']
        self.dev.write(self.map['CR'] + self.base, cr_cmd)
        self.poll_tip()
        self.check_ack()

    '''
    read a byte of data from slave device
    '''
    def read(self, last_byte=False):
        cr_cmd = self.cmd['RD']
        if last_byte:
            cr_cmd = cr_cmd | self.cmd['STO'] | self.cmd['NACK']  #send stop + NACK

        self.dev.write(self.map['CR'] + self.base, cr_cmd)
        self.poll_tip()

        return self.dev.read(self.map['RX'] + self.base)

    '''
    write a byte sequence, data ==> list of bytes...[byte0, byte1, byte2, ...]
    '''     
    def write_seq(self, data):
        self.start()
        for i, byte in enumerate(data):
            if i == len(data)-1:
                self.write(data[i], last_byte=True)
            else:
                self.write(data[i])
    '''
    read a byte sequence, specify number of bytes
    '''     
    def read_seq(self, num_bytes):
        seq = []
        self.start(read_mode=True)
        while len(seq) < (num_bytes - 1):
            seq.append(self.read())
        seq.append(self.read(last_byte=True))
        return seq            
