import surf
import sys

def do():
    dev=surf.SURF()
    print 'identify:'
    dev.identify()
    print 'path:', dev.path
    dev.clock(dev.internalClock)
    dev.labc.default()
    
    dev.status()
    return dev