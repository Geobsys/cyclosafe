#!/bin/bash
# Created on Tue Aug 05 2025
# Updated on Tue Nov 03 2026
#
#  This file is part of Cyclosafe
# Copyright (c) 2025 Nicolas Pirard @Anvently
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at:
# https://cecill.info/licences/Licence_CeCILL-B_V1-en.html

function color() {
  if [ "$#" -ne 2 ] ; then
    echo "[ERROR] color <color-name> <text> expected two arguments, but got $#" >&2
    return 1
  fi

  local -r colorName="$1"
  local -r message="$2"

  local colorCode="0;37"
  case "${colorName,,}" in
    black          ) colorCode='0;30' ;;
    red            ) colorCode='0;31' ;;
    green          ) colorCode='0;32' ;;
    yellow         ) colorCode='0;33' ;;
    blue           ) colorCode='0;34' ;;
    magenta        ) colorCode='0;35' ;;
    cyan           ) colorCode='0;36' ;;
    white          ) colorCode='0;37' ;;
    bright_black   ) colorCode='0;90' ;;
    bright_red     ) colorCode='0;91' ;;
    bright_green   ) colorCode='0;92' ;;
    bright_yellow  ) colorCode='0;93' ;;
    bright_blue    ) colorCode='0;94' ;;
    bright_magenta ) colorCode='0;95' ;;
    bright_cyan    ) colorCode='0;96' ;;
    bright_white   ) colorCode='0;97' ;;
    gray           ) colorCode='0;90' ;;
    *              ) colorCode='0;37' ;;
  esac

  echo -e "\e[${colorCode}m${message}\e[0m"
}

function info() {
  echo "$(color green '[INFO]')" "$1"
}

function error() {
  echo "$(color red '[ERROR]')" "$1" >&2
}

function warning() {
  echo "$(color yellow '[WARNING]')" "$1"
}

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P )
cd "$parent_path" || exit 1

if [ "$EUID" -eq 0 ]; then
  error "This script must be run as normal user."
  exit 1
fi

info "Please log in"
sudo -v || exit 1

if ! uname -a | grep -q rpi; then
  error "This device does not appear to be a raspberry pi"
  exit 1
fi

if [ -n "$SUDO_USER" ]; then
  USERNAME="$SUDO_USER"
fi

HOME=$(eval echo "~$USERNAME")
source .env

mkdir -p "$CYCLOSAFE_RECORD"
mkdir -p "$CYCLOSAFE_LOGS"

if ! grep -q "ipv6.disable=1" /boot/firmware/cmdline.txt; then
  info "Updating boot config files."
  sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.backup
  sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.backup
  sudo tee -a /boot/firmware/cmdline.txt < ./cmdline.txt > /dev/null
  sudo tee -a /boot/firmware/config.txt < ./config.txt > /dev/null
  info "--- Boot config was backed up and updated. You must reboot the raspberry pi before making any further installation."
  exit 0
fi

if ! [ -f /opt/ros/jazzy/setup.bash ]; then
  info "No ROS2 installation detected. Installing."
  # ROS_VARIANT (desktop / ros-base) can be set in .env
  if ! ROS_VARIANT="${ROS_VARIANT:-desktop}" ./ros_install.sh || ! [ -f /opt/ros/jazzy/setup.bash ]; then
    error "ROS2 installation failed."
    exit 1
  fi
fi

info "Sourcing ROS2"

source /opt/ros/jazzy/setup.bash

cd "$CYCLOSAFE_WORKSPACE" || exit 1

info "Installing dependencies"

# On Trixie, rosdep can't map ROS keys (std_msgs, sensor_msgs, ...) to ros-jazzy-*
# and falls back to Debian's ROS 1 packages (libstd-msgs-dev, ...), which then
# shadow the ROS 2 ones and break the build. So: every key that exists as a
# ros-jazzy-* package is installed from apt directly and skipped in rosdep.
ros_pkgs=()
skip_keys=()
while read -r key; do
  [ -z "$key" ] && continue
  candidate="ros-jazzy-${key//_/-}"
  if apt-cache show "$candidate" > /dev/null 2>&1; then
    ros_pkgs+=("$candidate")
    skip_keys+=("$key")
  fi
done < <(rosdep keys --ignore-src --from-paths src 2>/dev/null | sort -u)

if [ ${#ros_pkgs[@]} -ne 0 ]; then
  if ! sudo apt-get install -y "${ros_pkgs[@]}"; then
    warning "Some ros-jazzy-* dependency failed to install"
  fi
fi

if ! rosdep install -ry --ignore-src --from-paths src --skip-keys "${skip_keys[*]}"; then
  warning "Some ROS package dependency failed to install"
fi

# Debian ROS 1 packages shadow ROS 2 message packages in CMake: refuse to build with them
ros1_pkgs=$(dpkg-query -W -f '${db:Status-Abbrev} ${Package}\n' \
  libstd-msgs-dev libsensor-msgs-dev libgeometry-msgs-dev libroscpp-core-dev 2>/dev/null \
  | awk '$1 == "ii" {print $2}')
if [ -n "$ros1_pkgs" ]; then
  error "Debian ROS 1 packages are installed and will break the ROS 2 build: $(echo $ros1_pkgs)"
  error "Remove them with: sudo apt remove $(echo $ros1_pkgs)"
  exit 1
fi

info "Installing OLED screen driver"

if ! sudo pip install --break-system-packages luma.oled; then
  warning "Failed to install luma.oled, the OLED screen will not work"
fi

info "Installing GPS time synchronisation dependencies"

if ! sudo apt-get install -y gpsd gpsd-clients pps-tools chrony python3-gps; then
  warning "Failed to install gpsd/chrony, GPS node and time synchronisation will not work"
fi

info "Building ROS packages"

if ! colcon build --symlink-install --parallel-workers=2; then
  warning "Build errors detected. Check build output for any fatal error."
  warning "You can use cy_core_build (after sourcing cyclosafe_environment) to retry the build."
fi

cd "$parent_path" || exit 1

systemctl status cyclosafed.service > /dev/null
if [ $? -eq 4 ]; then
  info "Setting up cyclosafe services"
  ./systemd/setup_services.sh
fi

info "Installation is done. Make sure no error or warning show up in the logs."
info "You can source cyclosafe environment using : source $CYCLOSAFE_WORKSPACE/setup/.bashrc"
info "You can enable environment at startup using : echo 'source $CYCLOSAFE_WORKSPACE/setup/.bashrc' >> ~/.bashrc"
info "To start cyclosafe recordings you can use: sudo systemctl start cyclosafed.service"
