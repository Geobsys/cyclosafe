#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Created on Mon Oct 26 2026
# Updated on Mon Oct 26 2026
#
# This file is part of Cyclosafe
# Copyright (c) 2026 GEOBSYS
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at:
# https://cecill.info/licences/Licence_CeCILL-B_V1-en.html

# Driver minimal pour la jauge de batterie TI BQ34Z100-G1 (I2C).
# Datasheet : https://www.ti.com/lit/ds/symlink/bq34z100-g1.pdf
# Technical reference : https://www.ti.com/lit/ug/sluubw5a/sluubw5a.pdf

import smbus

class BQ34Z100:

	BQ34Z100_I2C_ADDRESS = (0x55)

	# Standard data commands (mots de 16 bits little-endian, sauf SOC et MaxError sur 1 octet)
	_CMD_CONTROL = (0x00)
	_CMD_STATE_OF_CHARGE = (0x02)
	_CMD_MAX_ERROR = (0x03)
	_CMD_REMAINING_CAPACITY = (0x04)
	_CMD_FULL_CHARGE_CAPACITY = (0x06)
	_CMD_VOLTAGE = (0x08)
	_CMD_AVERAGE_CURRENT = (0x0A)
	_CMD_TEMPERATURE = (0x0C)
	_CMD_FLAGS = (0x0E)
	_CMD_CURRENT = (0x10)
	_CMD_FLAGS_B = (0x12)

	def __init__(self, bus = 1, addr = BQ34Z100_I2C_ADDRESS):
		self.i2cbus = smbus.SMBus(bus)
		self.i2c_addr = addr

	def _read_byte(self, cmd) -> int:
		return self.i2cbus.read_byte_data(self.i2c_addr, cmd)

	def _read_word(self, cmd) -> int:
		return self.i2cbus.read_word_data(self.i2c_addr, cmd)

	def _read_signed_word(self, cmd) -> int:
		value = self._read_word(cmd)
		if value & 0x8000:
			return value - 0x10000
		return value

	def get_state_of_charge(self) -> int:
		"""Etat de charge estimé par la jauge, en % (0-100)."""
		return self._read_byte(self._CMD_STATE_OF_CHARGE)

	def get_battery_state(self) -> float:
		return float(self.get_state_of_charge())

	def get_voltage_V(self) -> float:
		"""Tension du pack (nécessite une calibration du Voltage Divider de la jauge)."""
		return self._read_word(self._CMD_VOLTAGE) * 0.001

	def get_current_mA(self) -> int:
		"""Courant instantané, négatif en décharge."""
		return self._read_signed_word(self._CMD_CURRENT)

	def get_average_current_mA(self) -> int:
		return self._read_signed_word(self._CMD_AVERAGE_CURRENT)

	def get_power_mW(self) -> float:
		return self.get_voltage_V() * self.get_current_mA()

	def get_remaining_capacity_mAh(self) -> int:
		return self._read_word(self._CMD_REMAINING_CAPACITY)

	def get_full_charge_capacity_mAh(self) -> int:
		return self._read_word(self._CMD_FULL_CHARGE_CAPACITY)

	def get_temperature_C(self) -> float:
		# Temperature() est exprimée en 0.1 K
		return self._read_word(self._CMD_TEMPERATURE) * 0.1 - 273.15

	def get_flags(self) -> int:
		return self._read_word(self._CMD_FLAGS)

	def scan(self):
		try:
			self.i2cbus.read_byte_data(self.i2c_addr, self._CMD_STATE_OF_CHARGE)
			return True
		except:
			return False
