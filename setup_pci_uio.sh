echo "  "
echo "  "
echo "Setting up the PCI..."
echo "  "
sudo modprobe uio_pci_generic
echo "  " 
sudo bash -c "echo 10ee ff01 > /sys/bus/pci/drivers/uio_pci_generic/new_id"
echo "10ee f01 has been assigned the uio_pci_generic driver"
sudo bash -c "echo 10ee ff00 > /sys/bus/pci/drivers/uio_pci_generic/new_id"
echo "10ee f00 has been assigned the uio_pci_generic driver"
sudo chmod 666 /sys/class/uio/uio0/device/resource0
echo "permission changed on resource0"
sudo chmod 666 /sys/class/uio/uio0/device/resource1
echo "permission changed on resource 1"
sudo chmod 666 /dev/uio0
echo "permission changed on /dev/uio0"
echo "  "
echo "  "
echo "PCI set-up complete" 
echo "  "
echo "  "
