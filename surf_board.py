#!/usr/bin/python

import surf
import sys

dev=surf.SURF()
dev.identify()
dev.clock(dev.internalClock())
dev.default_dac()
dev.default_timing()
