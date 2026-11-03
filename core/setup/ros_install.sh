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
  echo "$(color white '[INFO]')" "$1"
}

function error() {
  echo "$(color red '[ERROR]')" "$1" >&2
}

function warning() {
  echo "$(color yellow '[WARNING]')" "$1"
}

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# ROS 2 variant (desktop, ros-base, ...). ros-base is enough for a headless device.
ROS_VARIANT="${ROS_VARIANT:-desktop}"

# ROS 2 Jazzy for Debian / Raspberry Pi OS Trixie (arm64): rospian APT repository
ROSPIAN_URL="https://rospian.github.io/rospian-repo"
ROSPIAN_KEYRING="/usr/share/keyrings/rospian-archive-keyring.gpg"
ROSPIAN_LIST="/etc/apt/sources.list.d/rospian.list"

# Extra system packages. Installed one by one so a single missing package
# (e.g. not available on this Debian release) doesn't block all the others.
APT_DEPS=(cmake curl libopencv-dev python3-pip python3-opencv python3-numpy python3-smbus python3-pigpiod python3-picamera2)
PIP_DEPS=(vcstool colcon-common-extensions mcap-ros2-support)

# ---------------------------------------------------------------------------
# Install functions
# ---------------------------------------------------------------------------

function install_ros() {
  info "Installing ros-jazzy-$ROS_VARIANT from the rospian APT repository"

  sudo apt-get update
  sudo apt-get upgrade -y
  sudo apt-get install -y curl gnupg ca-certificates || return 1

  if ! [ -f "$ROSPIAN_KEYRING" ]; then
    local tmpkey
    tmpkey=$(mktemp) || return 1
    if ! curl -fsSL "$ROSPIAN_URL/public/rospian-archive-keyring.asc" -o "$tmpkey"; then
      error "Failed to download rospian signing key"
      rm -f "$tmpkey"
      return 1
    fi
    gpg --dearmor < "$tmpkey" | sudo tee "$ROSPIAN_KEYRING" > /dev/null
    rm -f "$tmpkey"
  fi

  echo "deb [arch=arm64 signed-by=$ROSPIAN_KEYRING] $ROSPIAN_URL trixie-jazzy main" \
    | sudo tee "$ROSPIAN_LIST" > /dev/null

  sudo apt-get update || return 1
  if ! sudo apt-get install -y "ros-jazzy-$ROS_VARIANT"; then
    error "Failed to install ros-jazzy-$ROS_VARIANT"
    return 1
  fi
}

# rosdep: use the apt package if available, else pip
function install_rosdep() {
  command -v rosdep > /dev/null && return 0
  info "Installing rosdep"
  local pkg
  for pkg in python3-rosdep python3-rosdep2; do
    if apt-cache show "$pkg" > /dev/null 2>&1; then
      sudo apt-get install -y "$pkg" && return 0
    fi
  done
  sudo pip install --break-system-packages rosdep
}

# ROS 2 Jazzy code generation (rosidl) needs empy 3.x; empy 4 breaks message builds
function install_empy() {
  local version
  version=$(python3 -c 'import em; print(em.__version__)' 2>/dev/null)
  if [[ "$version" == 3.* ]]; then
    info "empy $version already installed"
    return 0
  fi
  pip install --break-system-packages empy==3.3.4
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P )
cd "$parent_path" || exit 1

if [ "$EUID" -eq 0 ]; then
  error "This script must be run as normal user."
  exit 1
fi

info "Please log in"
sudo -v || exit 1

if [ "$(dpkg --print-architecture)" != "arm64" ]; then
  error "Unsupported architecture '$(dpkg --print-architecture)' (arm64 required)"
  exit 1
fi

codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
if [ "$codename" != "trixie" ]; then
  error "Unsupported OS release '$codename': Debian / Raspberry Pi OS Trixie required"
  exit 1
fi

if [ -f /opt/ros/jazzy/setup.bash ]; then
  info "Ros is already installed"
else
  info "-------------- Installing ROS2-Jazzy ----------------"
  install_ros || exit 1
fi

sudo apt-get clean
sudo apt-get autoclean
sudo apt-get autoremove -y
sudo rm -rf /usr/share/man/*
sudo rm -rf /usr/share/doc/*
sudo rm -rf /usr/share/info/*

if ! install_empy; then
  error "Failed to install empy"
  exit 1
fi

if ! sudo pip install --break-system-packages "${PIP_DEPS[@]}"; then
  error "Failed to install dependencies (${PIP_DEPS[*]})"
  exit 1
fi

if ! install_rosdep; then
  error "Failed to install rosdep"
  exit 1
fi

if ! [ -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
  sudo rosdep init
fi
rosdep update

sudo apt-get update
missing=()
for pkg in "${APT_DEPS[@]}"; do
  if ! sudo apt-get install -y "$pkg" > /dev/null 2>&1; then
    missing+=("$pkg")
  fi
done
if [ ${#missing[@]} -ne 0 ]; then
  error "Failed to install: ${missing[*]} (ROS core was installed)."
fi