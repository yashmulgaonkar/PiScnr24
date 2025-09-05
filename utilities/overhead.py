#!/usr/bin/env python3
"""
PiScnr24 - Flight data fetching and processing utilities
Copyright (c) 2024 [Your Name]

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to
Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
"""

from FlightRadar24.api import FlightRadar24API
from threading import Thread, Lock
from time import sleep
import math

from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError
from urllib3.exceptions import MaxRetryError


try:
    # Attempt to load config data
    from config import MIN_ALTITUDE, MAX_ALTITUDE, RETRIES, RATE_LIMIT_DELAY, MAX_FLIGHT_LOOKUP, ZONE_HOME, LOCATION_HOME
except (ModuleNotFoundError, NameError, ImportError):
    # If there's no config data, use defaults
    MIN_ALTITUDE = 0  # feet
    MAX_ALTITUDE = 100000  # feet
    RETRIES = 3
    RATE_LIMIT_DELAY = 1
    MAX_FLIGHT_LOOKUP = 5
    ZONE_HOME = {"tl_y": 62.61, "tl_x": -13.07, "br_y": 49.71, "br_x": 3.46}
    LOCATION_HOME = [51.509865, -0.118092, 3958.8]

BLANK_FIELDS = ["", "N/A", "NONE"]


class Overhead:
    def __init__(self, gps_filter=None):
        self._api = FlightRadar24API()
        self._lock = Lock()
        self._data = []
        self._new_data = False
        self._processing = False
        self.gps_filter = gps_filter

    def grab_data(self):
        Thread(target=self._grab_data).start()

    def _grab_data(self):
        # Mark data as old
        with self._lock:
            self._new_data = False
            self._processing = True

        data = []

        # Grab flight details
        try:
            # Calculate bounds string from GPS coordinates and radius
            # Format: "north,south,west,east" (comma-separated float values)
            lat = self.gps_filter.lat
            lon = self.gps_filter.lon
            radius_km = self.gps_filter.radius_km
            
            # Convert radius from km to degrees (approximate)
            # 1 degree latitude ≈ 111 km
            # 1 degree longitude ≈ 111 km * cos(latitude)
            lat_delta = radius_km / 111.0
            lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
            
            # Calculate bounds
            north = lat + lat_delta
            south = lat - lat_delta
            west = lon - lon_delta
            east = lon + lon_delta
            
            # Format as string: "north,south,west,east"
            bounds_string = f"{north:.3f},{south:.3f},{west:.3f},{east:.3f}"
            
            flights = self._api.get_flights(bounds=bounds_string)

            # Sort flights by closest first
            flights = [
                f
                for f in flights
                if f.altitude < MAX_ALTITUDE and f.altitude > MIN_ALTITUDE
            ]
            # Sort flights by altitude (closest to ground first)
            flights = sorted(flights, key=lambda f: f.altitude)

            for flight in flights[:MAX_FLIGHT_LOOKUP]:
                retries = RETRIES

                while retries:
                    # Rate limit protection
                    sleep(RATE_LIMIT_DELAY)

                    # Grab and store details
                    try:
                        details = self._api.get_flight_details(flight)

                        # Get plane type
                        try:
                            plane = details["aircraft"]["model"]["text"]
                        except (KeyError, TypeError):
                            plane = ""

                        # Tidy up what we pass along
                        plane = plane if not (plane.upper() in BLANK_FIELDS) else ""

                        origin = (
                            flight.origin_airport_iata
                            if not (flight.origin_airport_iata.upper() in BLANK_FIELDS)
                            else ""
                        )

                        destination = (
                            flight.destination_airport_iata
                            if not (flight.destination_airport_iata.upper() in BLANK_FIELDS)
                            else ""
                        )

                        callsign = (
                            flight.callsign
                            if not (flight.callsign.upper() in BLANK_FIELDS)
                            else ""
                        )

                        data.append(
                            {
                                "plane": plane,
                                "origin": origin,
                                "destination": destination,
                                "vertical_speed": flight.vertical_speed,
                                "altitude": flight.altitude,
                                "callsign": callsign,
                                "latitude": flight.latitude,
                                "longitude": flight.longitude,
                            }
                        )
                        break

                    except (KeyError, AttributeError):
                        retries -= 1

            with self._lock:
                self._new_data = True
                self._processing = False
                self._data = data

        except (ConnectionError, NewConnectionError, MaxRetryError):
            self._new_data = False
            self._processing = False

    @property
    def new_data(self):
        with self._lock:
            return self._new_data

    @property
    def processing(self):
        with self._lock:
            return self._processing

    @property
    def data(self):
        with self._lock:
            self._new_data = False
            return self._data

    @property
    def data_is_empty(self):
        return len(self._data) == 0


# Main function
if __name__ == "__main__":

    o = Overhead()
    o.grab_data()
    while not o.new_data:
        sleep(1)

    # Data is available in o.data
