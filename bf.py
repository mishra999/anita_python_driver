import struct
import sys
import time

#
# This is the Bitfield (bf) module
# surf.py, tisc.py and spi.py need to import this module

# Bitfield manipulation. Note that ordering
# can be Python (smallest first) or Verilog
# (largest first) for easy compatibility
#

class bf(object):
    def __init__(self, value=0):
        self._d = int(value)
    
    # def __getitem__(self, index):
    #     # print(index)
    #     return (self._d >> index) & 1
    
    # def __setitem__(self, index,value):
    #     value = (value & 1) << index
    #     mask = (1)<<index
    #     self._d = (self._d & ~mask) | value
    
    def __getitem__(self, index):
        # print(range)
        if isinstance(index, int):
            return (self._d >> index) & 1 # process index as an integer
        elif isinstance(index, slice):
            # start, end = index.indices(len((self._d & (((1)<<(31+1))-1))[index]))    # index is a slice
             # process slice
            start = index.start
            end = index.stop
            if start > end:
                tmp = end
                end = start
                start = tmp
            mask = (((1)<<(end+1))-1) >> start
            return (self._d >> start) & mask
    
    def __setitem__(self, index, value):
        if isinstance(index, int):
            value = (value & 1) << index
            mask = (1)<<index
            self._d = (self._d & ~mask) | value
        elif isinstance(index, slice):
            start = index.start
            end = index.stop
            if start > end:
                tmp = end
                end = start
                start = tmp
            mask = (((1)<<(end+1))-1) >> start
            value = (value & mask) << start
            mask = mask << start
            self._d = (self._d & ~mask) | value
            return (self._d >> start) & mask
    
    def __int__(self):
        return self._d
