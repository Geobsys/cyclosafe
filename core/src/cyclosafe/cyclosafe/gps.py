# Created on Tue Aug 05 2025
# Updated on Mon Oct 26 2026
#
#  This file is part of Cyclosafe
# Copyright (c) 2025 Nicolas Pirard @Anvently
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at:
# https://cecill.info/licences/Licence_CeCILL-B_V1-en.html

import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rcl_interfaces.msg import ParameterDescriptor
from cyclosafe_interfaces.msg import NavSatInfo
from sensor_msgs.msg import NavSatStatus
import gps

"""
Le port série du GPS est lu exclusivement par gpsd (qui fournit aussi l'heure à chrony).
Ce noeud est un client gpsd : il lit les rapports JSON TPV (position, vitesse) et SKY (satellites, DOP).

TPV.mode : 0 = inconnu, 1 = pas de fix, 2 = fix 2D, 3 = fix 3D
SKY.satellites[].gnssid : 0 = GPS, 1 = SBAS, 2 = Galileo, 3 = BeiDou, 5 = QZSS, 6 = GLONASS
"""

GNSSID_TO_SERVICE = {
	0: NavSatStatus.SERVICE_GPS,
	2: NavSatStatus.SERVICE_GALILEO,
	3: NavSatStatus.SERVICE_COMPASS,
	6: NavSatStatus.SERVICE_GLONASS,
}

RETRY_PERIOD = 10.0

class GPSPublisher(Node):

	def __init__(self):
		super().__init__('gps')
		self.declare_parameter('host', '127.0.0.1', ParameterDescriptor(description="gpsd host"))
		self.declare_parameter('gpsd_port', '2947', ParameterDescriptor(description="gpsd port"))
		self.declare_parameter('period', 1.0, ParameterDescriptor(description="Publishing period in seconds"))
		self.declare_parameter('start_time', 0.0, ParameterDescriptor(description="Time to be used as the beginning of the simulation. Float value of seconds since epoch."))
		self.host = self.get_parameter('host').get_parameter_value().string_value
		self.gpsd_port = self.get_parameter('gpsd_port').get_parameter_value().string_value
		self.period = self.get_parameter('period').get_parameter_value().double_value

		self.latitude = float('NaN')
		self.longitude = float('NaN')
		self.altitude = float('NaN')
		self.hdop = float('NaN')
		self.pdop = float('NaN')
		self.ground_speed = float('NaN') # km/h
		self.active_sat = 0
		self.status = NavSatStatus(status=NavSatStatus.STATUS_NO_FIX, service=0)

		self.session = None
		self.pub = self.create_publisher(NavSatInfo, 'gps', 10)
		self.timer = self.create_timer(self.period, self.routine)

	def connect(self):
		self.session = gps.gps(host=self.host, port=self.gpsd_port, mode=gps.WATCH_ENABLE | gps.WATCH_JSON)
		self.get_logger().info(f"connected to gpsd on {self.host}:{self.gpsd_port}")
		self.timer.timer_period_ns = int(self.period * 1000 * 1000 * 1000)

	def routine(self):
		try:
			if not self.session:
				self.connect()
			# Lit tous les rapports reçus depuis le dernier appel sans bloquer
			while self.session.waiting(0):
				if self.session.read() != 0:
					raise ConnectionError("connection to gpsd lost")
				self.parse(self.session.data)
			self.publish()

		except Exception as e:
			self.get_logger().error(f"Failed to read from gpsd: {str(e)}\nRetrying...")
			self.timer.timer_period_ns = int(RETRY_PERIOD * 1000 * 1000 * 1000)
			if self.session:
				self.session.close()
			self.session = None

	def parse(self, report):
		report_class = report.get('class')
		if report_class == 'TPV':
			if report.get('mode', 0) >= 2:
				self.status.status = NavSatStatus.STATUS_FIX
				self.latitude = report.get('lat', float('NaN'))
				self.longitude = report.get('lon', float('NaN'))
				self.altitude = report.get('altMSL', report.get('alt', float('NaN')))
				speed = report.get('speed') # m/s
				self.ground_speed = speed * 3.6 if speed is not None else float('NaN')
			else:
				self.status.status = NavSatStatus.STATUS_NO_FIX
				self.latitude = float('NaN')
				self.longitude = float('NaN')
				self.altitude = float('NaN')
				self.ground_speed = float('NaN')
		elif report_class == 'SKY':
			# gpsd peut envoyer des SKY partiels : ne mettre à jour que les champs présents
			if 'hdop' in report:
				self.hdop = report['hdop']
			if 'pdop' in report:
				self.pdop = report['pdop']
			satellites = report.get('satellites')
			if satellites is not None:
				used = [sat for sat in satellites if sat.get('used')]
				self.active_sat = len(used)
				self.status.service = 0
				for sat in used:
					self.status.service |= GNSSID_TO_SERVICE.get(sat.get('gnssid'), 0)
			elif 'uSat' in report:
				self.active_sat = report['uSat']

	def publish(self):
		msg = NavSatInfo(
			latitude=self.latitude, longitude = self.longitude, altitude = self.altitude,
			hdop = self.hdop, pdop = self.pdop,
			ground_speed = self.ground_speed, actives_sat = self.active_sat, status = self.status
		)
		msg.header.stamp = self.get_clock().now().to_msg()
		self.get_logger().debug(
			f"lat={msg.latitude},\
lon={msg.longitude},\
alt={self.altitude},\
speed={self.ground_speed},\
actives={self.active_sat},\
hdop={self.hdop},\
pdop={self.pdop}")
		self.pub.publish(msg)


def main(args=None):
	try:
		rclpy.init(args=args)
		sensor_publisher = GPSPublisher()
		rclpy.spin(sensor_publisher)

	except (KeyboardInterrupt, ExternalShutdownException):
		pass


if __name__ == '__main__':
	main()
