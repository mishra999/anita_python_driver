# anita-python
Written by Patrick Allison
Python testing libraries for ANITA. This contains only the common functions - the OCPCI classes,
the bitfield class, the SPI class, and the PicoBlaze class. Device scripts should derive from the
ocpci.Device class.

Note that ocpci.Device isn't actually a class, it's just an attribute in the ocpci namespace.
By default, it's the ocpci_uio.Device class, however it can be switched to the vfio device by
using `ocpci.set_backend(ocpci.ocpci_vfio)`.

To build in this directory:

```
python setup.py build_ext --inplace
```

Using the UIO backend requires assigning the uio_pci_generic driver to the device, via
(assuming 10ee ff01 is the PCI vendor and device ID respectively)

```
sudo bash -c "echo 10ee ff01 > /sys/bus/pci/drivers/uio_pci_generic/new_id"
```

Using the VFIO backend requires assigning the vfio-pci driver to the device, via

```
sudo bash -c "echo 10ee ff01 > /sys/bus/pci/drivers/vfio-pci/new_id"
```

Example scripts are available (which also set permissions correctly afterwards so root access
isn't needed) as setup_pci_uio.sh and setup_pci_vfio.sh.

Note that when using the VFIO backend, there's about a one second stall when opening the device.
This is under investigation but seems harmless.

## High speed readout (DMA access)

To read out data at high speed, DMA transfers are needed. These are only available using
the VFIO backend, and require changing user limits on the amount of locked memory.

To find out the current limit, do `ulimit -l` - the number returned is in kB, typically
64 by default.

To increase this limit, on Debian, edit /etc/security/limits.conf and add a line similar to

```
anita            -       memlock         16384
```

Then log out, and back in. `ulimit -l` should show the new limit.

## New instructions to set up VFIO
1. vi /etc/modules-load.d/loadmodules.conf
Add these modules:
  vfio,
  vfio_iommu_type1,
  vfio_pci

2. echo "options vfio_iommu_type1 allow_unsafe_interrupts=1" > /etc/modprobe.d/iommu_unsafe_interrupts.conf
   echo "options kvm ignore_msrs=1" > /etc/modprobe.d/kvm.conf

3. echo "options vfio-pci ids=10ee:ff00"> /etc/modprobe.d/vfio.conf




