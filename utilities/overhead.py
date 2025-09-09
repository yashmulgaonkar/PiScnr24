#!/usr/bin/env python3
"""
PiScnr24 - Flight data fetching and processing utilities
Copyright (c) 2024 [Your Name]

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to
Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
"""

from threading import Thread, Lock
from time import sleep
import math
import ssl
import urllib3
import platform

from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError
from urllib3.exceptions import MaxRetryError

# Disable SSL warnings and certificate verification for Windows
if platform.system() == "Windows":
    import urllib3
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # Disable SSL warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Create unverified HTTPS context
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Monkey patch requests to disable SSL verification
    original_request = requests.Session.request
    def patched_request(self, method, url, **kwargs):
        kwargs['verify'] = False
        return original_request(self, method, url, **kwargs)
    requests.Session.request = patched_request
    
    # Also patch the main requests functions
    original_get = requests.get
    original_post = requests.post
    
    def patched_get(*args, **kwargs):
        kwargs['verify'] = False
        return original_get(*args, **kwargs)
    
    def patched_post(*args, **kwargs):
        kwargs['verify'] = False
        return original_post(*args, **kwargs)
    
    requests.get = patched_get
    requests.post = patched_post
    
    print("🔓 SSL verification disabled for Windows compatibility")
else:
    print("🔒 Using standard SSL verification (non-Windows platform)")

# Import FlightRadar24API after SSL patches are applied (if any)
from FlightRadar24.api import FlightRadar24API

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
        print("🚀 Starting data grab...")
        # Mark data as old
        with self._lock:
            self._new_data = False
            self._processing = True

        data = []

        # Grab flight details
        try:
            print(f"🌍 GPS Filter: lat={self.gps_filter.lat}, lon={self.gps_filter.lon}, radius={self.gps_filter.radius_km}km")
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
            # print(f"📍 Calculated bounds: {bounds_string}")  # Uncomment for detailed debugging
            
            print("🌐 Calling FlightRadar24 API...")
            flights = self._api.get_flights(bounds=bounds_string)
            print(f"✈️ Found {len(flights)} flights from API")

            # Sort flights by closest first
            flights = [
                f
                for f in flights
                if f.altitude < MAX_ALTITUDE and f.altitude > MIN_ALTITUDE
            ]
            # Sort flights by altitude (closest to ground first)
            flights = sorted(flights, key=lambda f: f.altitude)
            # print(f"🔍 Processing up to {MAX_FLIGHT_LOOKUP} flights (filtered from {len(flights)} total)")  # Uncomment for detailed debugging

            for flight in flights[:MAX_FLIGHT_LOOKUP]:
                retries = RETRIES

                while retries:
                    # Rate limit protection
                    sleep(RATE_LIMIT_DELAY)

                    # Grab and store details
                    try:
                        details = self._api.get_flight_details(flight)

                        # DEBUG: Print available fields to understand API response structure
                        # Uncomment these lines if you need to debug the API response structure:
                        # print(f"🔍 Available flight detail keys: {details.keys()}")
                        # if 'time' in details:
                        #     print(f"⏰ Time data: {details['time']}")
                        # if 'status' in details:
                        #     print(f"📊 Status data: {details['status']}")

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

                        # Extract timing and status information for on-time indicator
                        flight_status = ""
                        delay_minutes = 0
                        on_time_status = "Unknown"
                        scheduled_departure = ""
                        actual_departure = ""
                        
                        try:
                            # Try to extract timing information from details
                            # FlightRadar24 API typically provides time data in 'time' or 'status' sections
                            if 'time' in details:
                                time_data = details['time']
                                if 'scheduled' in time_data and 'departure' in time_data['scheduled']:
                                    scheduled_departure = time_data['scheduled']['departure']
                                if 'real' in time_data and 'departure' in time_data['real']:
                                    actual_departure = time_data['real']['departure']
                                
                                # Calculate delay if we have both scheduled and actual times
                                if scheduled_departure and actual_departure:
                                    # Convert to timestamps and calculate delay
                                    import datetime
                                    try:
                                        sched_time = datetime.datetime.fromtimestamp(scheduled_departure)
                                        actual_time = datetime.datetime.fromtimestamp(actual_departure)
                                        delay_seconds = (actual_time - sched_time).total_seconds()
                                        delay_minutes = int(delay_seconds / 60)
                                        
                                        # Determine on-time status
                                        if delay_minutes <= 15:  # Within 15 minutes is considered on-time
                                            on_time_status = "On Time"
                                        elif delay_minutes <= 60:
                                            on_time_status = f"Delayed {delay_minutes}m"
                                        else:
                                            hours = delay_minutes // 60
                                            remaining_minutes = delay_minutes % 60
                                            on_time_status = f"Delayed {hours}h {remaining_minutes}m"
                                    except (ValueError, TypeError):
                                        on_time_status = "Unknown"
                            
                            # Try to get flight status from status field
                            if 'status' in details and 'text' in details['status']:
                                flight_status = details['status']['text']
                                # Map common status codes to on-time indicators
                                status_lower = flight_status.lower()
                                if 'on time' in status_lower or 'scheduled' in status_lower:
                                    on_time_status = "On Time"
                                elif 'delayed' in status_lower:
                                    on_time_status = "Delayed"
                                elif 'cancelled' in status_lower or 'canceled' in status_lower:
                                    on_time_status = "Cancelled"
                        
                        except (KeyError, TypeError, AttributeError):
                            # If we can't get timing data, fall back to basic status
                            on_time_status = "Unknown"

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
                                "ground_speed": flight.ground_speed,
                                "on_time_status": on_time_status,
                                "delay_minutes": delay_minutes,
                                "flight_status": flight_status,
                                "scheduled_departure": scheduled_departure,
                                "actual_departure": actual_departure,
                            }
                        )
                        # print(f"✅ Added flight data for {callsign}")  # Uncomment for detailed debugging
                        break

                    except (KeyError, AttributeError):
                        retries -= 1

            print(f"🏁 Data grab complete! Collected {len(data)} flights")
            with self._lock:
                self._new_data = True
                self._processing = False
                self._data = data

        except (ConnectionError, NewConnectionError, MaxRetryError) as e:
            print(f"❌ Network error in API call: {e}")
            self._new_data = False
            self._processing = False
        except Exception as e:
            print(f"❌ Unexpected error in API call: {e}")
            import traceback
            traceback.print_exc()
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
