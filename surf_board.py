import surf
import sys

sys.path.insert(0, '/home/anita/astroparticlelab/')

def do():
    dev=surf.SURF()
    print 'identify:'
    dev.identify()
    print 'path:', dev.path
    dev.labc.run_mode(0)
    dev.i2c.default_config()
    dev.clock(dev.internalClock)
    dev.labc.default()
    dev.set_phase(2)
#    dev.labc.automatch_phab()
    dev.status()
    return dev
