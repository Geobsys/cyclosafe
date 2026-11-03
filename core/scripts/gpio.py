#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Crerated on Tue Aug 05 2025
# Updated on Mon Oct 26 2026
#
# This file is part of Cyclosafe
# Copyright (c) 2025 Nicolas Pirard @Anvently
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at:
# https://cecill.info/licences/Licence_CeCILL-B_V1-en.html

import os, time, sys, signal
import psutil
from bq34z100 import BQ34Z100
from gpiozero import Button
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

BTN_RST_GPIO = 20

OLED_I2C_PORT = 1
OLED_I2C_ADDRESS = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 32
OLED_LINE_HEIGHT = 11

button = Button(BTN_RST_GPIO, pull_up=None, active_state=False, bounce_time=0.1)

class BatteryException(Exception):
	pass

BUTTON_SHUTDOWN = 255
BATTERY_SHUTDOWN = 254

NBR_CELLS = 2
CHARGE_VOLTAGE = 4.2
MIN_VOLTAGE = 3

VOLTAGE_RANGE = CHARGE_VOLTAGE - MIN_VOLTAGE
BUS_CHARGE_VOLTAGE = NBR_CELLS * CHARGE_VOLTAGE
BATTERY_VOLTAGE_TRESHOLD = BUS_CHARGE_VOLTAGE - (NBR_CELLS * VOLTAGE_RANGE)

LOW_BATTERY_PERCENT = float(os.getenv("LOW_BATTERY_PERCENT", "0.2"))

LOW_STORAGE_TRESHOLD = int(os.getenv("LOW_STORAGE_TRESHOLD", "512"))

class GPIOController():
	def __init__(self):
		self.battery_percent = None
		self.battery_low = False
		self.storage_percent = None
		self.storage_free_gb = None
		self.storage_low = False
		self.recording = False
		self.heartbeat = False

		try:
			self.oled = ssd1306(i2c(port=OLED_I2C_PORT, address=OLED_I2C_ADDRESS), width=OLED_WIDTH, height=OLED_HEIGHT)
		except Exception as e:
			print(f"OLED init failed: {e}")
			self.oled = None

		self.gauge = BQ34Z100(1)

	def draw(self, lines):
		if not self.oled:
			return
		try:
			with canvas(self.oled) as draw:
				for i, line in enumerate(lines):
					draw.text((0, i * OLED_LINE_HEIGHT), line, fill="white")
				# Point clignotant indiquant que le script tourne toujours
				if self.heartbeat:
					draw.rectangle((OLED_WIDTH - 4, 1, OLED_WIDTH - 2, 3), fill="white")
		except Exception as e:
			print(f"OLED draw failed: {e}")

	def refresh_display(self):
		if self.battery_percent is None:
			battery = "BAT  --"
		else:
			battery = f"BAT  {self.battery_percent:d}%"
			if self.battery_low:
				battery += "  LOW"

		if self.storage_percent is None:
			storage = "SD   --"
		elif self.storage_low:
			storage = f"SD   {self.storage_percent:.0f}%  FULL"
		else:
			storage = f"SD   {self.storage_percent:.0f}%  {self.storage_free_gb:.1f}G free"

		recording = "REC  ON" if self.recording else "REC  OFF"

		self.draw([battery, storage, recording])

	def check_battery_state(self):
		if not self.gauge:
			return
		try:
			voltage = self.gauge.get_voltage_V()
			state_of_charge = self.gauge.get_state_of_charge()
		except:
			self.battery_percent = None
			return
		self.battery_percent = state_of_charge
		self.battery_low = state_of_charge < LOW_BATTERY_PERCENT * 100
		if voltage < BATTERY_VOLTAGE_TRESHOLD:
			raise BatteryException()

	def check_sd_card(self) -> bool:
		usage = psutil.disk_usage("/")
		mb_available = usage.free / 1024 / 1024
		self.storage_percent = usage.percent
		self.storage_free_gb = usage.free / 1024 / 1024 / 1024
		self.storage_low = mb_available < LOW_STORAGE_TRESHOLD
		return not self.storage_low

	def check_recording(self):
		# Le recording est lancé par la launch description via "ros2 bag record"
		recording = False
		for proc in psutil.process_iter(["cmdline"]):
			cmdline = proc.info["cmdline"] or []
			if "bag" in cmdline and "record" in cmdline and any(arg.endswith("ros2") for arg in cmdline):
				recording = True
				break
		self.recording = recording

	def cleanup(self, message = None):
		if not self.oled:
			return
		if message:
			# Le message reste affiché jusqu'à la coupure de l'alimentation
			self.heartbeat = False
			self.oled.persist = True
			self.draw(message)
		else:
			self.oled.cleanup()

	def routine(self):
		shutdown_type = 0
		try:
			count = 0
			while not button.is_pressed:
				if count % 40 == 0:
					self.check_battery_state()
				if count % 120 == 0:
					self.check_sd_card()
				if count % 8 == 0:
					self.check_recording()
				if count % 4 == 0:
					self.heartbeat = not self.heartbeat
					self.refresh_display()
				time.sleep(0.25)
				count += 1
			print("Shutting down...")
			shutdown_type = BUTTON_SHUTDOWN
			self.cleanup(["Shutting down..."])
		except BatteryException:
			shutdown_type = BATTERY_SHUTDOWN
			self.cleanup(["Battery empty", "Shutting down..."])

		return shutdown_type

gpio_controler = GPIOController()

def signal_handler(signum, frame):
	gpio_controler.cleanup()
	sys.exit(0)

def main(args=None):
	global gpio_controler

	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)
	shutdown_code = 0
	try:
		shutdown_code = gpio_controler.routine()
	except:
		pass

	sys.exit(shutdown_code)

if __name__ == '__main__':
	main()
