import surf
import sys

def do():
    dev=surf.SURF()
    print 'identify:'
    dev.identify()
    print 'path:', dev.path
    dev.labc.run_mode(0)
    dev.clock(dev.internalClock)
    dev.labc.default()
    
    dev.status()
    return dev