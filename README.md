# anita-python
Python testing libraries for ANITA.

To build in this directory:

python setup.py build_ext --inplace

This is all pretty standard Python stuff, so Google should answer
any questions.

Using is as simple as:

import tisc
dev = tisc.TISC()
dev.identify()
dev.status()
dev.gprogram(0, "my_glitc_code.bit")
dev.GA.identify()

etc.

The initial device also takes a possible UIO path if multiple devices are
present, e.g.:
dev = tisc.TISC("/sys/class/uio/uio1")

 
