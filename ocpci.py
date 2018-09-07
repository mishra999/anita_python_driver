import ocpci_uio
import ocpci_vfio
import sys

# Create a few global objects for convenience.
# The 'backend' object stores the module we're using for a backend.
# The 'Device' object stores the class we're currently using as a Device.
#
# If you want to use a different backend, just do ocpci.set_backend(ocpci.ocpci_vfio)
# before anything else.

this = sys.modules[__name__]
this.backend = ocpci_uio
this.Device = ocpci_uio.Device

def set_backend(classname):
    this.backend = classname
    this.Device = classname.Device
