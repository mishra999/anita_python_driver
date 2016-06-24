#!/bin/bash

sudo dd if=/sys/class/uio/uio0/device/config of=config_bkp bs=256 count=1
echo "PCI saved."
hold=' '
printf "Reprogram now: press 'SPACE' to continue or 'CTRL+C' to exit : "
tty_state=$(stty -g)
stty -icanon
until [ -z "${hold#$in}" ] ; do
    in=$(dd bs=1 count=1 </dev/tty 2>/dev/null)
done
stty "$tty_state"
sudo dd of=/sys/class/uio/uio0/device/config if=config_bkp bs=256 count=1
echo "PCI restored."

