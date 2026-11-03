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

# Affiche en continu les mesures de la jauge de batterie BQ34Z100-G1.

import time
from bq34z100 import BQ34Z100

def main():
	gauge = BQ34Z100(1)

	while not gauge.scan():
		time.sleep(2)

	while True:
		print ("Voltage            : %.3f V" % gauge.get_voltage_V())
		print ("Current            : %d mA" % gauge.get_current_mA())
		print ("Average current    : %d mA" % gauge.get_average_current_mA())
		print ("Power              : %.f mW" % gauge.get_power_mW())
		print ("State of charge    : %d %%" % gauge.get_state_of_charge())
		print ("Remaining capacity : %d / %d mAh" % (gauge.get_remaining_capacity_mAh(), gauge.get_full_charge_capacity_mAh()))
		print ("Temperature        : %.1f °C" % gauge.get_temperature_C())
		print ("Flags              : 0x%04X" % gauge.get_flags())
		print ()
		time.sleep(1)

if __name__ == "__main__":
	main()
