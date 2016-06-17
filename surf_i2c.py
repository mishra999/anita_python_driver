import i2c
from bf import *
import numpy as np
import time

'''
06-2016
Written to clean up the main surf.py module;
moved all i2c bus overhead to this module: surf_i2c.py
Includes functions to manage SURF dac, ioexpander, and RFP ADCs
'''

class SURFi2c:
    '''
    base map of the i2c cores in the fpga:
    '''
    i2c_map = {'DAC'                 : 0x00,
               'RFP_0'               : 0x20,
               'RFP_1'               : 0x40,
               'RFP_2'               : 0x60,
               'RFP_3'               : 0x80}

    def __init__(self, dev, base):
        self.dac = i2c.I2C(dev, base + self.i2c_map['DAC'], 0x60)
	self.ioexpander = i2c.I2C(dev, base + self.i2c_map['DAC'], 0x20)
        '''
        12 RFP circuits on 4 i2c buses. Slave address set by ADDR pin connection:
        GND: 1001000
        VDD: 1001001
        SDA: 1001010 (not used)
        SCL: 1001011 
        '''
        self.rfp = []
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_0'], 0x49) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_0'], 0x48) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_0'], 0x4B) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_1'], 0x49) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_1'], 0x48) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_1'], 0x4B) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_2'], 0x49) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_2'], 0x48) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_2'], 0x4B) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_3'], 0x49) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_3'], 0x48) )
        self.rfp.append(i2c.I2C(dev, base + self.i2c_map['RFP_3'], 0x4B) ) 

    def set_vped(self, value):
        val=bf(value)
        dac_bytes=[0x5E, (0x8<<4) | (val[11:8]), val[7:0]]
        self.dac.write_seq(dac_bytes)

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
            time.sleep(0.5) #time delay required! (can be better handled, surely)

    def read_dac(self):
        self.dac.start(read_mode=True)
        dac_bytes=self.dac.read_seq(24)
        print "Reading from MCP4728..."
        print "DAC channel A (RFP_VPED_0):  register is set to 0x{0:x}, EEPROM is set to 0x{0:x}".format(
            (dac_bytes[1] & 0xF) << 8 | dac_bytes[2], (dac_bytes[4] & 0xF) << 8 | dac_bytes[5] ) 
        print "DAC channel B (RFP_VPED_1):  register is set to 0x{0:x}, EEPROM is set to 0x{0:x}".format(
            (dac_bytes[7] & 0xF) << 8 | dac_bytes[8], (dac_bytes[10] & 0xF) << 8 | dac_bytes[11] ) 
        print "DAC channel C (RFP_VPED_2):  register is set to 0x{0:x}, EEPROM is set to 0x{0:x}".format(
            (dac_bytes[13] & 0xF) << 8 | dac_bytes[14], (dac_bytes[16] & 0xF) << 8 | dac_bytes[17] )
        print "DAC channel D (VPED)      :  register is set to 0x{0:x}, EEPROM is set to 0x{0:x}".format(
            (dac_bytes[19] & 0xF) << 8 | dac_bytes[20], (dac_bytes[22] & 0xF) << 8 | dac_bytes[23] ) 
