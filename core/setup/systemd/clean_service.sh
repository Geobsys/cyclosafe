#!/bin/bash

if [ "$EUID" -ne 0 ]; then
  echo This script must be run as root. Use sudo
  exit 1
fi

sudo rm /etc/systemd/system/cyclosafed.service
sudo rm /etc/systemd/system/gpiod.service

systemctl stop cyclosafed.service gpiod.service
systemctl disable cyclosafed.service gpiod.service
systemctl daemon-reload
systemctl reset-failed