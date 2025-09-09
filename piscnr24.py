#!/usr/bin/env python3
"""
PiScnr24 - Flight Tracker
Copyright (c) 2024 [Your Name]

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to
Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
"""

import sys
import math
import socket
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, 
                             QPushButton, QProgressBar, QGroupBox, QGridLayout, 
                             QTextEdit, QFrame, QHeaderView, 
                             QSpinBox, QDoubleSpinBox, QDialog,
                             QScrollArea)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPixmap
from utilities.overhead import Overhead
from utilities.lookup import get_airport_name, get_airline_name
import time
import os
import json

# Import configuration
try:
    from config import *
except ImportError:
    # Default values if config file is missing
    GUI_REFRESH_INTERVAL = 5
    GUI_WINDOW_WIDTH = 1200
    GUI_WINDOW_HEIGHT = 800
    MAX_FLIGHT_LOOKUP = 10
    MIN_ALTITUDE = 0
    MAX_ALTITUDE = 40000
    ZONE_HOME = {"tl_y": 62.61, "tl_x": -13.07, "br_y": 49.71, "br_x": 3.46}
    LOCATION_HOME = [37.563653, -122.250361, 6371]
    DEFAULT_LATITUDE = 37.563653
    DEFAULT_LONGITUDE = -122.250361
    DEFAULT_RADIUS_KM = 10
    DEFAULT_RANGE_MILES = 2
    RETRIES = 3
    RATE_LIMIT_DELAY = 1
    LIGHT_THEME = {
        "primary": "#4CAF50",
        "primary_hover": "#45a049",
        "primary_pressed": "#3d8b40",
        "background": "#f0f0f0",
        "text_primary": "#2c3e50",
        "text_secondary": "#7f8c8d",
        "border": "#cccccc",
        "table_header": "#e0e0e0",
        "table_alternate": "#f8f8f8",
        "main_window": "#f0f0f0",
        "group_box": "#ffffff",
        "group_box_border": "#cccccc",
        "button": "#4CAF50",
        "button_hover": "#45a049",
        "button_pressed": "#3d8b40",
        "input_bg": "#ffffff",
        "input_border": "#cccccc",
        "input_focus": "#4CAF50",
        "label": "#2c3e50",
        "logo_text": "#6c757d",
        "frame": "#ffffff",
        "frame_border": "#ddd",
        "frame_hover": "#f8f9fa",
        "flight_card": "#ffffff",
        "flight_card_border": "#ddd",
        "flight_card_hover": "#f8f9fa",
        "flight_card_text": "#2c3e50",
        "scroll_area": "#f0f0f0",
        "scroll_area_widget": "#ffffff"
    }
    DARK_THEME = {
        "primary": "#3498db",
        "primary_hover": "#2980b9",
        "primary_pressed": "#21618c",
        "background": "#2c3e50",
        "text_primary": "#ecf0f1",
        "text_secondary": "#bdc3c7",
        "border": "#7f8c8d",
        "table_header": "#34495e",
        "table_alternate": "#2c3e50",
        "main_window": "#2c3e50",
        "group_box": "#34495e",
        "group_box_border": "#34495e",
        "button": "#3498db",
        "button_hover": "#2980b9",
        "button_pressed": "#21618c",
        "input_bg": "#34495e",
        "input_border": "#7f8c8d",
        "input_focus": "#3498db",
        "label": "#ecf0f1",
        "logo_text": "#ecf0f1",
        "frame": "#34495e",
        "frame_border": "#7f8c8d",
        "frame_hover": "#2c3e50",
        "flight_card": "#34495e",
        "flight_card_border": "#7f8c8d",
        "flight_card_hover": "#2c3e50",
        "flight_card_text": "#ecf0f1",
        "scroll_area": "#2c3e50",
        "scroll_area_widget": "#34495e"
    }
    THEME_COLORS = LIGHT_THEME

class GPSFilter:
    """Class to handle GPS coordinate filtering"""
    def __init__(self, lat=37.563653, lon=-122.250361, radius_km=100):
        self.lat = lat
        self.lon = lon
        self.radius_km = radius_km
        self.earth_radius_km = 6371
    
    def set_coordinates(self, lat, lon, radius_km):
        """Update GPS coordinates and radius"""
        self.lat = lat
        self.lon = lon
        self.radius_km = radius_km
    
    def calculate_distance(self, flight_lat, flight_lon):
        """Calculate distance between two GPS coordinates using Haversine formula"""
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(flight_lat), math.radians(flight_lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return self.earth_radius_km * c
    
    def is_within_bounds(self, flight_lat, flight_lon):
        """Check if flight is within the specified radius"""
        distance = self.calculate_distance(flight_lat, flight_lon)
        within_bounds = distance <= self.radius_km
        return within_bounds


class GPSCoordinatesPopup(QDialog):
    """Popup window for GPS coordinates settings"""
    
    def __init__(self, current_gps_filter, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GPS Coordinates Settings")
        self.setModal(True)
        # Optimize size for 800x480 screen - use about 80% of screen space
        self.resize(640, 380)
        self.current_gps_filter = current_gps_filter
        self.parent_window = parent
        
        # Apply theme-aware styling
        self.apply_popup_theme()
        
        # Create layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # Add title
        title_label = QLabel("GPS Filter Settings")
        title_label.setObjectName("popupTitle")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Create form layout for GPS inputs
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setSpacing(10)
        
        # Row 1: Latitude and Longitude
        lat_label = QLabel("Latitude:")
        lat_label.setObjectName("popupLabel")
        form_layout.addWidget(lat_label, 0, 0)
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setObjectName("popupInput")
        self.lat_input.setRange(-90, 90)
        self.lat_input.setValue(current_gps_filter.lat)
        self.lat_input.setDecimals(6)
        self.lat_input.setMinimumWidth(150)
        form_layout.addWidget(self.lat_input, 0, 1)
        
        lon_label = QLabel("Longitude:")
        lon_label.setObjectName("popupLabel")
        form_layout.addWidget(lon_label, 0, 2)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setObjectName("popupInput")
        self.lon_input.setRange(-180, 180)
        self.lon_input.setValue(current_gps_filter.lon)
        self.lon_input.setDecimals(6)
        self.lon_input.setMinimumWidth(150)
        form_layout.addWidget(self.lon_input, 0, 3)
        
        # Row 2: Radius and Altitude Filter
        radius_label = QLabel("Radius:")
        radius_label.setObjectName("popupLabel")
        form_layout.addWidget(radius_label, 1, 0)
        self.range_input = QSpinBox()
        self.range_input.setObjectName("popupInput")
        self.range_input.setRange(1, 1000)
        # Convert km to miles for display
        range_miles = int(current_gps_filter.radius_km * 0.621371)
        self.range_input.setValue(range_miles)
        self.range_input.setSuffix(" miles")
        self.range_input.setMinimumWidth(120)
        form_layout.addWidget(self.range_input, 1, 1)
        
        alt_label = QLabel("Min Altitude:")
        alt_label.setObjectName("popupLabel")
        form_layout.addWidget(alt_label, 1, 2)
        self.altitude_filter_input = QSpinBox()
        self.altitude_filter_input.setObjectName("popupInput")
        self.altitude_filter_input.setRange(0, 50000)
        self.altitude_filter_input.setValue(100)  # Default 100 feet
        self.altitude_filter_input.setSuffix(" feet")
        self.altitude_filter_input.setMinimumWidth(120)
        form_layout.addWidget(self.altitude_filter_input, 1, 3)
        
        main_layout.addWidget(form_widget)
        
        # Add some help text
        help_label = QLabel("Set your location and filter radius to see flights in your area.\nHigher altitudes filter out ground traffic.")
        help_label.setObjectName("popupHelp")
        help_label.setWordWrap(True)
        help_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(help_label)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setObjectName("popupCancelButton")
        button_layout.addWidget(cancel_button)
        
        button_layout.addStretch()
        
        # Apply button
        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self.accept)
        apply_button.setObjectName("popupApplyButton")
        apply_button.setDefault(True)
        button_layout.addWidget(apply_button)
        
        main_layout.addLayout(button_layout)
        
    def get_settings(self):
        """Return the GPS settings from the dialog"""
        return {
            'latitude': self.lat_input.value(),
            'longitude': self.lon_input.value(),
            'range_miles': self.range_input.value(),
            'altitude_filter': self.altitude_filter_input.value()
        }
    
    def apply_popup_theme(self):
        """Apply theme-aware styling to the GPS popup"""
        # Determine if parent is using dark mode
        is_dark_mode = getattr(self.parent_window, 'is_dark_mode', False)
        
        if is_dark_mode:
            # Dark theme for popup
            self.setStyleSheet("""
                QDialog {
                    background-color: #2c3e50;
                    color: #ecf0f1;
                }
                QLabel#popupTitle {
                    font-size: 16px;
                    font-weight: bold;
                    color: #ecf0f1;
                    margin-bottom: 10px;
                }
                QLabel#popupLabel {
                    color: #ecf0f1;
                    font-weight: normal;
                }
                QLabel#popupHelp {
                    font-size: 11px;
                    color: #bdc3c7;
                    margin: 10px;
                }
                QDoubleSpinBox#popupInput, QSpinBox#popupInput {
                    background-color: #34495e;
                    color: #ecf0f1;
                    border: 1px solid #7f8c8d;
                    border-radius: 3px;
                    padding: 4px;
                    selection-background-color: #3498db;
                }
                QDoubleSpinBox#popupInput:focus, QSpinBox#popupInput:focus {
                    border: 2px solid #3498db;
                }
                QPushButton#popupApplyButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 120px;
                }
                QPushButton#popupApplyButton:hover {
                    background-color: #2980b9;
                }
                QPushButton#popupApplyButton:pressed {
                    background-color: #21618c;
                }
                QPushButton#popupCancelButton {
                    background-color: #7f8c8d;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QPushButton#popupCancelButton:hover {
                    background-color: #95a5a6;
                }
                QPushButton#popupCancelButton:pressed {
                    background-color: #6c7b7d;
                }
            """)
        else:
            # Light theme for popup
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #2c3e50;
                }
                QLabel#popupTitle {
                    font-size: 16px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 10px;
                }
                QLabel#popupLabel {
                    color: #2c3e50;
                    font-weight: normal;
                }
                QLabel#popupHelp {
                    font-size: 11px;
                    color: #666666;
                    margin: 10px;
                }
                QDoubleSpinBox#popupInput, QSpinBox#popupInput {
                    background-color: #ffffff;
                    color: #2c3e50;
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    padding: 4px;
                    selection-background-color: #4CAF50;
                }
                QDoubleSpinBox#popupInput:focus, QSpinBox#popupInput:focus {
                    border: 2px solid #4CAF50;
                }
                QPushButton#popupApplyButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 120px;
                }
                QPushButton#popupApplyButton:hover {
                    background-color: #45a049;
                }
                QPushButton#popupApplyButton:pressed {
                    background-color: #3d8b40;
                }
                QPushButton#popupCancelButton {
                    background-color: #f5f5f5;
                    color: #2c3e50;
                    border: 1px solid #cccccc;
                    padding: 8px 20px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QPushButton#popupCancelButton:hover {
                    background-color: #e9ecef;
                    border-color: #aaa;
                }
                QPushButton#popupCancelButton:pressed {
                    background-color: #dee2e6;
                }
            """)


class RawDataPopup(QDialog):
    """Popup window to display raw flight data"""
    
    def __init__(self, flight_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Raw Flight Data")
        self.setModal(True)
        self.resize(600, 400)
        self.parent_window = parent
        
        # Apply theme-aware styling
        self.apply_popup_theme()
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add title
        title_label = QLabel(f"Raw Data for Flight: {flight_data.get('callsign', 'Unknown')}")
        title_label.setObjectName("popupTitle")
        layout.addWidget(title_label)
        
        # Add raw data text area
        self.raw_data_text = QTextEdit()
        self.raw_data_text.setReadOnly(True)
        self.raw_data_text.setFont(QFont("Courier", 9))
        self.raw_data_text.setObjectName("rawDataText")
        
        # Format the raw data as JSON
        formatted_data = json.dumps(flight_data, indent=2, default=str)
        self.raw_data_text.setPlainText(formatted_data)
        
        layout.addWidget(self.raw_data_text)
        
        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setObjectName("popupCloseButton")
        layout.addWidget(close_button)
    
    def apply_popup_theme(self):
        """Apply theme-aware styling to the Raw Data popup"""
        # Determine if parent is using dark mode
        is_dark_mode = getattr(self.parent_window, 'is_dark_mode', False)
        
        if is_dark_mode:
            # Dark theme for popup
            self.setStyleSheet("""
                QDialog {
                    background-color: #2c3e50;
                    color: #ecf0f1;
                }
                QLabel#popupTitle {
                    font-size: 14px;
                    font-weight: bold;
                    color: #ecf0f1;
                    margin-bottom: 10px;
                }
                QTextEdit#rawDataText {
                    background-color: #34495e;
                    color: #ecf0f1;
                    border: 1px solid #7f8c8d;
                    border-radius: 4px;
                    selection-background-color: #3498db;
                }
                QPushButton#popupCloseButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton#popupCloseButton:hover {
                    background-color: #2980b9;
                }
                QPushButton#popupCloseButton:pressed {
                    background-color: #21618c;
                }
            """)
        else:
            # Light theme for popup
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #2c3e50;
                }
                QLabel#popupTitle {
                    font-size: 14px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 10px;
                }
                QTextEdit#rawDataText {
                    background-color: #f8f9fa;
                    color: #2c3e50;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    selection-background-color: #4CAF50;
                }
                QPushButton#popupCloseButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton#popupCloseButton:hover {
                    background-color: #45a049;
                }
                QPushButton#popupCloseButton:pressed {
                    background-color: #3d8b40;
                }
            """)


class FlightDataThread(QThread):
    """Thread for fetching flight data from FlightRadar24"""
    data_updated = pyqtSignal(list)
    status_updated = pyqtSignal(str)
    
    def __init__(self, gps_filter=None):
        super().__init__()
        self.gps_filter = gps_filter or GPSFilter()
        self.overhead = Overhead(self.gps_filter)
        self.gps_filter_enabled = True
        self.running = True
        
    def run(self):
        while self.running:
            self.overhead.grab_data()
            
            # Wait for data to be processed
            while not self.overhead.new_data and self.running:
                time.sleep(0.5)
                
            if self.running:
                data = self.overhead.data
                
                # Filter data based on GPS coordinates (if enabled)
                if self.gps_filter_enabled:
                    try:
                        filtered_data = []
                        total_flights = len(data)
                        flights_with_gps = 0
                        flights_in_bounds = 0
                        
                        sample_coords = []
                        all_coords = []
                        for flight in data:
                            # Check if flight has GPS coordinates
                            if 'latitude' in flight and 'longitude' in flight:
                                flights_with_gps += 1
                                lat = flight['latitude']
                                lon = flight['longitude']
                                
                                # Store all coordinates for debugging
                                all_coords.append((lat, lon))
                                
                                # Store sample coordinates for debugging
                                if len(sample_coords) < 5:
                                    sample_coords.append(f"({lat:.3f}, {lon:.3f})")
                                
                                # Check if flight is within bounds
                                # Set current flight number for debug output
                                self.gps_filter._current_flight_num = flight.get('callsign', 'Unknown')
                                if self.gps_filter.is_within_bounds(lat, lon):
                                    flights_in_bounds += 1
                                    filtered_data.append(flight)
                            else:
                                # If no GPS coordinates, include the flight anyway
                                filtered_data.append(flight)
                        
                        
                        data = filtered_data
                        # Debug information
                        sample_str = ", ".join(sample_coords) if sample_coords else "None"
                        range_miles = self.gps_filter.radius_km * 0.621371
                        debug_msg = f"GPS Filter: {total_flights} total, {flights_with_gps} with GPS, {flights_in_bounds} in bounds (Center: {self.gps_filter.lat:.3f}, {self.gps_filter.lon:.3f}, Range: {range_miles:.1f} miles) [Sample: {sample_str}]"
                        self.status_updated.emit(debug_msg)
                        
                    except Exception as e:
                        # If filtering fails, use original data
                        self.status_updated.emit(f"GPS filter error: {str(e)}")
                        pass
                else:
                    # GPS filtering disabled, use all data
                    self.status_updated.emit(f"GPS filter disabled - showing all {len(data)} flights")
                
                self.data_updated.emit(data)
                self.status_updated.emit(f"Found {len(data)} flights")
                
            # Wait before next update
            time.sleep(GUI_REFRESH_INTERVAL)
            
    def stop(self):
        self.running = False

class FlightTrackerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.gps_filter = GPSFilter(DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_RADIUS_KM)
        self.is_dark_mode = True  # Start with dark mode
        self.is_fullscreen = True  # Track fullscreen state
        self.init_ui()
        self.init_data_thread()
        
        # Show initial GPS filter settings
        # Initialize footer
        
    def get_local_ip(self):
        """Get the local IP address of the device"""
        try:
            # Create a socket and connect to a remote server to determine local IP
            # This doesn't actually send data, just determines which interface to use
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        except Exception:
            # Fallback methods if the above fails
            try:
                # Try getting hostname and resolving it
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
                # Avoid returning 127.0.0.1
                if ip_address.startswith('127.'):
                    return "IP: Not Available"
                return ip_address
            except Exception:
                return "IP: Not Available"
    
    def refresh_ip_address(self):
        """Refresh the IP address display"""
        try:
            current_ip = self.get_local_ip()
            self.ip_address_label.setText(f"IP: {current_ip}")
        except Exception:
            self.ip_address_label.setText("IP: Not Available")
        
    def init_ui(self):
        self.setWindowTitle("PiScnr24 - See what is above you!")
        # Optimize window size for Raspberry Pi screen (800x480)
        self.setGeometry(0, 0, 800, 480)
        
        # Set application style using theme colors
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {THEME_COLORS['background']};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {THEME_COLORS['border']};
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QHeaderView::section {{
                background-color: {THEME_COLORS['table_header']};
                padding: 5px;
                border: 1px solid {THEME_COLORS['border']};
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {THEME_COLORS['primary']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME_COLORS['primary_hover']};
            }}
            QPushButton:pressed {{
                background-color: {THEME_COLORS['primary_pressed']};
            }}
            QProgressBar {{
                border: 2px solid {THEME_COLORS['border']};
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {THEME_COLORS['primary']};
                border-radius: 3px;
            }}
        """)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - minimize spacing and margins for maximum flight info space
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)  # Minimal margins
        main_layout.setSpacing(5)  # Minimal spacing between sections
        
        # Compact Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        header_layout.setSpacing(8)  # Tight spacing between elements
        
        # Compact Logo
        logo_label = QLabel()
        logo_path = os.path.join("assets", "PiScnr24.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                # Smaller logo for compact header (max height 35px)
                scaled_pixmap = pixmap.scaled(140, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                # Compact text fallback
                logo_label.setText("PiScnr24")
                logo_label.setFont(QFont("Arial", 16, QFont.Bold))
                logo_label.setStyleSheet("color: #2c3e50; margin: 2px;")
        else:
            # Compact text fallback
            logo_label.setText("PiScnr24")
            logo_label.setFont(QFont("Arial", 16, QFont.Bold))
            logo_label.setStyleSheet("color: #2c3e50; margin: 2px;")
        
        # Minimal logo styling
        logo_label.setStyleSheet("background-color: transparent; border: none; margin: 2px;")
        logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        
        # Compact GPS Settings Button
        self.gps_button = QPushButton("SET HOME")
        self.gps_button.clicked.connect(self.open_gps_settings)
        self.gps_button.setStyleSheet("padding: 4px 8px; min-width: 80px; font-size: 12px;")
        header_layout.addWidget(self.gps_button)
        
        # Store altitude filter value
        self.altitude_filter_feet = 100  # Default 100 feet
        
        # Compact Theme Toggle Button
        self.theme_button = QPushButton("LIGHT")
        self.theme_button.setFixedSize(50, 25)  # Wider for text labels
        self.theme_button.setStyleSheet("""
            QPushButton {
                font-size: 9px;
                border: 1px solid #ddd;
                border-radius: 12px;
                background-color: #f8f9fa;
                padding: 1px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.theme_button.clicked.connect(self.toggle_theme_button)
        header_layout.addWidget(self.theme_button)
        
        # Compact Refresh Button
        self.refresh_button = QPushButton("↻")
        self.refresh_button.clicked.connect(self.manual_refresh)
        self.refresh_button.setFixedSize(30, 25)  # Small circular button
        self.refresh_button.setStyleSheet("padding: 2px; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self.refresh_button)
        
        # Compact Quit Button
        self.quit_button = QPushButton("✕")
        self.quit_button.clicked.connect(self.close_application)
        self.quit_button.setFixedSize(30, 25)  # Small circular button
        self.quit_button.setToolTip("Exit PiScnr24")
        header_layout.addWidget(self.quit_button)
        
        # Initialize theme button and apply theme
        self.update_theme_button()
        self.update_quit_button()
        self.apply_theme()
        
        main_layout.addLayout(header_layout)
        
        # Progress bar (hidden, minimal space when visible)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(3)  # Very thin progress bar
        main_layout.addWidget(self.progress_bar)
        
        # Main content - Maximized flight information section
        main_panel = self.create_combined_flight_panel()
        main_layout.addWidget(main_panel, 1)  # Give maximum stretch factor
        
        # Apply theme to scroll area after it's created
        if hasattr(self, 'flight_scroll_area'):
            self.refresh_scroll_area_theme()
        
        # Compact Footer
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(5, 2, 5, 2)  # Minimal footer margins
        footer_layout.setSpacing(10)
        
        # Left side - Last update
        self.last_update_label = QLabel("Last update: Never")
        self.last_update_label.setStyleSheet("color: #7f8c8d; font-size: 9px; margin: 0px; padding: 2px;")
        footer_layout.addWidget(self.last_update_label)
        
        footer_layout.addStretch()
        
        # Right corner - IP Address
        self.ip_address_label = QLabel(f"IP: {self.get_local_ip()}")
        self.ip_address_label.setStyleSheet("color: #7f8c8d; font-size: 9px; margin: 0px; padding: 2px; font-weight: bold;")
        self.ip_address_label.setAlignment(Qt.AlignRight)
        self.ip_address_label.setToolTip("Current local IP address of this device")
        footer_layout.addWidget(self.ip_address_label)
               
        main_layout.addLayout(footer_layout)
        
    def create_combined_flight_panel(self):
        """Create a maximized card-based flight display"""
        group_box = QGroupBox("Flights")  # Shorter title
        layout = QVBoxLayout(group_box)
        layout.setContentsMargins(3, 15, 3, 3)  # Minimal margins, space for title
        layout.setSpacing(0)  # No spacing between elements
        
        # Create maximized scroll area for flight cards with enhanced scrolling
        scroll_area = QScrollArea()
        scroll_area.setObjectName("flightScrollArea")  # Set object name for theme targeting
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # Always show vertical scroll bar
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameStyle(QScrollArea.NoFrame)  # Remove frame for more space
        
        # Create container widget for cards
        self.cards_container = QWidget()
        self.cards_container.setObjectName("cardsContainer")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(3)  # Tight spacing between cards
        self.cards_layout.setContentsMargins(3, 3, 3, 3)  # Minimal margins
        
        scroll_area.setWidget(self.cards_container)
        layout.addWidget(scroll_area)
        
        # Store reference to scroll area for theme updates
        self.flight_scroll_area = scroll_area
        
        return group_box
    
    def create_flight_card(self, flight):
        """Create a compact card for a single flight optimized for small screens"""
        card = QWidget()
        card.setObjectName("flightCard")
        card.setMaximumHeight(135)  # Further increased height for even larger fonts
        
        # Compact main layout for the card
        main_layout = QHBoxLayout(card)
        main_layout.setSpacing(8)  # Tighter spacing
        main_layout.setContentsMargins(5, 3, 5, 3)  # Minimal margins
        
        # Left side - Compact Logo
        logo_widget = QLabel()
        logo_widget.setStyleSheet("background-color: transparent;")
        logo_widget.setAlignment(Qt.AlignCenter)
        
        # Load airline logo (smaller)
        callsign = flight.get('callsign', '')
        if len(callsign) >= 3:
            airline_code = callsign[:3]
            logo_widget, _ = self.create_compact_logo_widget(airline_code)
        else:
            logo_widget.setText("N/A")
            logo_widget.setObjectName("logoWidget")
            logo_widget.setFixedSize(40, 25)  # Smaller default logo
        
        main_layout.addWidget(logo_widget)
        
        # Center - Compact Flight info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)  # Minimal spacing
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Large callsign for better readability
        callsign = flight.get('callsign', 'N/A')
        callsign_label = QLabel(callsign)
        callsign_label.setStyleSheet("font-size: 26px; font-weight: bold; margin: 0px;")
        info_layout.addWidget(callsign_label)
        
        # Large route (airport codes only)
        origin = flight.get('origin', 'N/A')
        destination = flight.get('destination', 'N/A')
        route_label = QLabel(f"{origin} → {destination}")
        route_label.setStyleSheet("font-size: 20px; margin: 0px;")
        info_layout.addWidget(route_label)
        
        # Larger aircraft type
        aircraft_label = QLabel(flight.get('plane', 'N/A'))
        aircraft_label.setObjectName("secondaryText")
        aircraft_label.setStyleSheet("font-size: 18px; margin: 0px;")
        info_layout.addWidget(aircraft_label)
        
        main_layout.addLayout(info_layout)
        
        # Right side - Compact Flight data in two columns
        data_widget = QWidget()
        data_layout = QHBoxLayout(data_widget)
        data_layout.setSpacing(8)
        data_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left data column
        left_data = QVBoxLayout()
        left_data.setSpacing(1)
        left_data.setContentsMargins(0, 0, 0, 0)
        
        # Altitude (large)
        altitude = flight.get('altitude', 0)
        altitude_text = f"{altitude:,}ft" if altitude else 'N/A'
        altitude_label = QLabel(altitude_text)
        altitude_label.setStyleSheet("font-size: 20px; font-weight: bold; margin: 0px;")
        left_data.addWidget(altitude_label)
        
        # Vertical Speed (larger)
        vspeed = flight.get('vertical_speed', 0)
        vspeed_text = f"{vspeed:,}fpm" if vspeed else 'N/A'
        vspeed_label = QLabel(vspeed_text)
        vspeed_label.setObjectName("secondaryText")
        vspeed_label.setStyleSheet("font-size: 16px; margin: 0px;")
        left_data.addWidget(vspeed_label)
        
        data_layout.addLayout(left_data)
        
        # Right data column  
        right_data = QVBoxLayout()
        right_data.setSpacing(1)
        right_data.setContentsMargins(0, 0, 0, 0)
        
        # Distance (large)
        distance = self.calculate_distance(flight)
        if distance:
            distance_miles = distance * 0.621371
            distance_text = f"{distance_miles:.1f}mi"
        else:
            distance_text = 'N/A'
        distance_label = QLabel(distance_text)
        distance_label.setStyleSheet("font-size: 20px; font-weight: bold; margin: 0px;")
        right_data.addWidget(distance_label)
        
        # Speed (larger)
        speed = flight.get('speed', 0)
        speed_text = f"{speed}kts" if speed else 'N/A'
        speed_label = QLabel(speed_text)
        speed_label.setObjectName("secondaryText")
        speed_label.setStyleSheet("font-size: 16px; margin: 0px;")
        right_data.addWidget(speed_label)
        
        data_layout.addLayout(right_data)
        main_layout.addWidget(data_widget)
        
        # Make card clickable
        card.mousePressEvent = lambda event: self.on_card_clicked(flight)
        card.setCursor(Qt.PointingHandCursor)
        
        return card
    
    def on_card_clicked(self, flight):
        """Handle flight card click"""
        # Show raw data popup
        popup = RawDataPopup(flight, self)
        popup.exec_()
        
    def init_data_thread(self):
        """Initialize the data fetching thread"""
        self.data_thread = FlightDataThread(self.gps_filter)
        self.data_thread.data_updated.connect(self.update_flight_data)
        self.data_thread.status_updated.connect(self.update_status)
        self.data_thread.start()
        
    def update_flight_data(self, flight_data):
        """Update the flight cards with new data"""
        # Get altitude filter from stored value
        altitude_filter_feet = self.altitude_filter_feet
        
        # Filter out flights below the specified altitude
        filtered_flights = []
        for flight in flight_data:
            altitude = flight.get('altitude', 0)
            if altitude >= altitude_filter_feet:  # Only include flights at or above the specified altitude
                filtered_flights.append(flight)
        
        # Clear existing cards
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        # Create cards for flights, but limit to 3 visible at once for better readability
        # The scroll area will handle showing more flights through scrolling
        for flight in filtered_flights:
            card = self.create_flight_card(flight)
            self.cards_layout.addWidget(card)
        
        # Add stretch to push cards to top
        self.cards_layout.addStretch()
        
        # Update flight count (show both total and filtered)
        total_flights = len(flight_data)
        filtered_count = len(filtered_flights)
        
        # Update last update time
        from datetime import datetime
        self.last_update_label.setText(f"Last update: {datetime.now().strftime('%H:%M:%S')} | Found {filtered_count} flights (filtered from {total_flights})")
        
        # Store current flight data for selection handling
        self.current_flight_data = filtered_flights
        
    def calculate_distance(self, flight):
        """Calculate distance from home location using GPS coordinates"""
        try:
            # Calculate distance if GPS coordinates are available
            if 'latitude' in flight and 'longitude' in flight:
                lat = flight['latitude']
                lon = flight['longitude']
                return self.gps_filter.calculate_distance(lat, lon)
            
            return None
        except:
            return None
    
    def create_logo_widget(self, airline_code):
        """Create a logo widget for the table"""
        logo_widget = QLabel()
        logo_widget.setObjectName("logoWidget")  # Add object name for theme targeting
        logo_widget.setAlignment(Qt.AlignCenter)
        logo_height = 0  # Default height
        
        if airline_code:
            try:
                logo_path = os.path.join("assets", "airline_logos", f"airline_logo_{airline_code}.png")
                if not os.path.exists(logo_path):
                    logo_path = os.path.join("assets", "airline_logos", f"airline_logo_{airline_code}.gif")
                
                if os.path.exists(logo_path):
                    pixmap = QPixmap(logo_path)
                    if not pixmap.isNull():
                        # Scale pixmap to reasonable size while maintaining aspect ratio
                        # Maximum height of 120px, width scales proportionally
                        scaled_pixmap = pixmap.scaled(300, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_widget.setPixmap(scaled_pixmap)
                        logo_height = scaled_pixmap.height()
                        # Set widget size to match scaled pixmap with generous padding
                        logo_widget.setFixedSize(scaled_pixmap.width() + 30, scaled_pixmap.height() + 30)
                        # Force transparent background after setting pixmap
                        logo_widget.setStyleSheet("background-color: transparent; border: none;")
                    else:
                        logo_widget.setText("N/A")
                        logo_height = 20  # Default height for text
                        logo_widget.setFixedSize(60, 40)
                else:
                    logo_widget.setText("N/A")
                    logo_height = 20  # Default height for text
                    logo_widget.setFixedSize(60, 40)
            except Exception as e:
                logo_widget.setText("N/A")
                logo_height = 20  # Default height for text
                logo_widget.setFixedSize(60, 40)
        else:
            logo_widget.setText("N/A")
            logo_height = 20  # Default height for text
            logo_widget.setFixedSize(60, 40)
        
        return logo_widget, logo_height
    
    def create_compact_logo_widget(self, airline_code):
        """Create a compact logo widget for flight cards"""
        logo_widget = QLabel()
        logo_widget.setObjectName("logoWidget")
        logo_widget.setAlignment(Qt.AlignCenter)
        logo_height = 0
        
        if airline_code:
            try:
                logo_path = os.path.join("assets", "airline_logos", f"airline_logo_{airline_code}.png")
                if not os.path.exists(logo_path):
                    logo_path = os.path.join("assets", "airline_logos", f"airline_logo_{airline_code}.gif")
                
                if os.path.exists(logo_path):
                    pixmap = QPixmap(logo_path)
                    if not pixmap.isNull():
                        # Compact logo size for flight cards
                        scaled_pixmap = pixmap.scaled(65, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_widget.setPixmap(scaled_pixmap)
                        logo_height = scaled_pixmap.height()
                        # Set compact widget size
                        logo_widget.setFixedSize(65, 35)
                        logo_widget.setStyleSheet("background-color: transparent; border: none;")
                    else:
                        logo_widget.setText("N/A")
                        logo_height = 15
                        logo_widget.setFixedSize(55, 35)
                else:
                    logo_widget.setText("N/A")
                    logo_height = 15
                    logo_widget.setFixedSize(55, 35)
            except Exception as e:
                logo_widget.setText("N/A")
                logo_height = 15
                logo_widget.setFixedSize(55, 35)
        else:
            logo_widget.setText("N/A")
            logo_height = 15
            logo_widget.setFixedSize(55, 35)
        
        return logo_widget, logo_height
    
    def open_gps_settings(self):
        """Open GPS settings popup"""
        popup = GPSCoordinatesPopup(self.gps_filter, self)
        popup.altitude_filter_input.setValue(self.altitude_filter_feet)  # Set current altitude filter
        
        if popup.exec_() == QDialog.Accepted:
            settings = popup.get_settings()
            self.apply_gps_filter_from_settings(settings)
    
    def apply_gps_filter_from_settings(self, settings):
        """Apply GPS coordinate filter from settings dictionary"""
        try:
            lat = settings['latitude']
            lon = settings['longitude']
            range_miles = settings['range_miles']
            self.altitude_filter_feet = settings['altitude_filter']
            
            # Convert miles to kilometers for the GPS filter
            range_km = range_miles * 1.60934
            
            self.gps_filter.set_coordinates(lat, lon, range_km)
            
            # Update the data thread's GPS filter
            if hasattr(self, 'data_thread'):
                self.data_thread.gps_filter = self.gps_filter
            
            # Update the overhead's GPS filter
            if hasattr(self, 'overhead'):
                self.overhead.gps_filter = self.gps_filter
            
            # Trigger a manual refresh to apply the filter
            self.manual_refresh()
            
        except Exception as e:
            # GPS filter error - silently continue
            pass
    
    def apply_gps_filter(self):
        """Legacy method - now opens GPS settings popup"""
        self.open_gps_settings()
    
    def update_status(self, status):
        """Update the footer"""
        # Don't update the last update label with status messages
        # The timestamp should only be updated when new data arrives
        pass
        
        
    def manual_refresh(self):
        """Manually trigger a data refresh"""
        self.last_update_label.setText("Last update: Manual refresh requested...")
        # Refresh IP address as well in case network configuration has changed
        self.refresh_ip_address()
        # This would need to be implemented to force a refresh
        
    def toggle_theme_button(self):
        """Toggle between light and dark mode using button"""
        self.is_dark_mode = not self.is_dark_mode
        self.update_theme_button()
        self.apply_theme()
        
    def update_theme_button(self):
        """Update the compact theme button icon and styling"""
        if self.is_dark_mode:
            self.theme_button.setText("DARK")
            self.theme_button.setStyleSheet("""
                QPushButton {
                    font-size: 9px;
                    border: 1px solid #7f8c8d;
                    border-radius: 12px;
                    background-color: #34495e;
                    color: #ecf0f1;
                    padding: 1px;
                }
                QPushButton:hover {
                    background-color: #2c3e50;
                    border-color: #3498db;
                }
                QPushButton:pressed {
                    background-color: #1a252f;
                }
            """)
        else:
            self.theme_button.setText("LIGHT")
            self.theme_button.setStyleSheet("""
                QPushButton {
                    font-size: 9px;
                    border: 1px solid #ddd;
                    border-radius: 12px;
                    background-color: #f8f9fa;
                    color: #2c3e50;
                    padding: 1px;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #3498db;
                }
                QPushButton:pressed {
                    background-color: #dee2e6;
                }
            """)
        
    def refresh_scroll_area_theme(self):
        """Force refresh the scroll area theme after theme changes"""
        if hasattr(self, 'flight_scroll_area'):
            # Get current theme colors
            if self.is_dark_mode:
                bg_color = DARK_THEME['scroll_area']
                widget_bg_color = DARK_THEME['scroll_area_widget']
            else:
                bg_color = LIGHT_THEME['scroll_area']
                widget_bg_color = LIGHT_THEME['scroll_area_widget']
            
            # Clear any existing styles first
            self.flight_scroll_area.setStyleSheet("")
            if self.flight_scroll_area.viewport():
                self.flight_scroll_area.viewport().setStyleSheet("")
            if hasattr(self, 'cards_container'):
                self.cards_container.setStyleSheet("")
            
            # Apply aggressive style directly to the scroll area
            scroll_style = f"""
                QScrollArea#flightScrollArea {{
                    background: {bg_color} !important;
                    background-color: {bg_color} !important;
                    border: none !important;
                }}
                QScrollArea#flightScrollArea * {{
                    background: {bg_color} !important;
                    background-color: {bg_color} !important;
                }}
            """
            
            self.flight_scroll_area.setStyleSheet(scroll_style)
            
            # Also apply to viewport directly with more specific styles
            if self.flight_scroll_area.viewport():
                viewport_style = f"""
                    * {{
                        background: {bg_color} !important;
                        background-color: {bg_color} !important;
                    }}
                """
                self.flight_scroll_area.viewport().setStyleSheet(viewport_style)
            
            # Apply to cards container as well
            if hasattr(self, 'cards_container'):
                container_style = f"""
                    QWidget#cardsContainer {{
                        background: {bg_color} !important;
                        background-color: {bg_color} !important;
                    }}
                """
                self.cards_container.setStyleSheet(container_style)
            
            # Force refresh
            self.flight_scroll_area.update()
            self.flight_scroll_area.repaint()
            
    def apply_theme(self):
        """Apply the current theme to the application"""
        if self.is_dark_mode:
            # Dark theme colors from config
            theme = DARK_THEME
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: {theme['main_window']};
                    color: {theme['text_primary']};
                }}
                QGroupBox {{
                    font-weight: bold;
                    border: 2px solid {theme['group_box_border']};
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding-top: 10px;
                    background-color: {theme['group_box']};
                    color: {theme['text_primary']};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    background-color: {theme['main_window']};
                }}
                QPushButton {{
                    background-color: {theme['button']};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {theme['button_hover']};
                }}
                QPushButton:pressed {{
                    background-color: {theme['button_pressed']};
                }}
                QDoubleSpinBox, QSpinBox {{
                    background-color: {theme['input_bg']};
                    color: {theme['text_primary']};
                    border: 1px solid {theme['input_border']};
                    border-radius: 3px;
                    padding: 4px;
                }}
                QDoubleSpinBox:focus, QSpinBox:focus {{
                    border: 2px solid {theme['input_focus']};
                    background-color: {theme['main_window']};
                }}
                QDoubleSpinBox::up-button, QSpinBox::up-button {{
                    background-color: {theme['input_border']};
                    border: 1px solid {theme['input_border']};
                    border-radius: 2px;
                }}
                QDoubleSpinBox::down-button, QSpinBox::down-button {{
                    background-color: {theme['input_border']};
                    border: 1px solid {theme['input_border']};
                    border-radius: 2px;
                }}
                QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {{
                    background-color: {theme['input_focus']};
                }}
                QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
                    background-color: {theme['input_focus']};
                }}
                QLabel {{
                    color: {theme['label']};
                }}
                QLabel#logoWidget {{
                    background-color: transparent !important;
                    color: {theme['logo_text']};
                    font-size: 14px;
                    border: none !important;
                }}
                QFrame {{
                    background-color: {theme['frame']};
                    border: 1px solid {theme['frame_border']};
                    border-radius: 4px;
                    margin: 1px;
                    padding: 3px;
                }}
                QFrame:hover {{
                    border-color: {theme['input_focus']};
                    background-color: {theme['frame_hover']};
                }}
                QWidget#flightCard {{
                    background-color: {theme['flight_card']};
                    border: 1px solid {theme['flight_card_border']};
                    border-radius: 4px;
                    margin: 1px;
                    padding: 3px;
                    color: {theme['flight_card_text']};
                }}
                QWidget#flightCard * {{
                    border: none !important;
                    background: transparent !important;
                }}
                QWidget#flightCard:hover {{
                    background-color: {theme['flight_card_hover']};
                }}
                QWidget#flightCard QLabel {{
                    color: {theme['flight_card_text']} !important;
                    border: none !important;
                    background: transparent !important;
                    margin: 0px;
                    padding: 0px;
                }}
                QWidget#flightCard QLabel#secondaryText {{
                    color: {theme['text_secondary']} !important;
                    border: none !important;
                    background: transparent !important;
                    margin: 0px;
                    padding: 0px;
                }}
                QScrollArea {{
                    background-color: {theme['scroll_area']};
                    border: none;
                }}
                QScrollArea#flightScrollArea {{
                    background-color: {theme['scroll_area']};
                    border: none;
                }}
                QScrollArea QWidget {{
                    background-color: {theme['scroll_area_widget']};
                }}
                QWidget#cardsContainer {{
                    background-color: {theme['scroll_area']};
                }}
                QSlider::groove:horizontal {{
                    border: 1px solid {theme['input_border']};
                    height: 8px;
                    background: {theme['input_bg']};
                    border-radius: 4px;
                }}
                QSlider::handle:horizontal {{
                    background: {theme['input_focus']};
                    border: 1px solid {theme['button_hover']};
                    width: 18px;
                    margin: -2px 0;
                    border-radius: 9px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: {theme['button_hover']};
                }}
                QScrollBar:vertical {{
                    background: {theme['scroll_area']};
                    width: 20px;
                    border: 1px solid {theme['input_border']};
                    border-radius: 10px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {theme['input_focus']};
                    border: 1px solid {theme['button_hover']};
                    border-radius: 9px;
                    min-height: 30px;
                    margin: 1px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {theme['button_hover']};
                }}
                QScrollBar::handle:vertical:pressed {{
                    background: {theme['button_pressed']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    background: {theme['input_border']};
                    height: 20px;
                    border-radius: 10px;
                }}
                QScrollBar::add-line:vertical:hover, QScrollBar::sub-line:vertical:hover {{
                    background: {theme['input_focus']};
                }}
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                    background: {theme['text_primary']};
                    width: 8px;
                    height: 8px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: transparent;
                }}
            """)
        else:
            # Light theme colors from config
            theme = LIGHT_THEME
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: {theme['main_window']};
                }}
                QGroupBox {{
                    font-weight: bold;
                    border: 2px solid {theme['group_box_border']};
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding-top: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }}
                QPushButton {{
                    background-color: {theme['button']};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {theme['button_hover']};
                }}
                QPushButton:pressed {{
                    background-color: {theme['button_pressed']};
                }}
                QDoubleSpinBox, QSpinBox {{
                    background-color: {theme['input_bg']};
                    border: none;
                    border-radius: 3px;
                    padding: 4px;
                }}
                QLabel#logoWidget {{
                    background-color: transparent !important;
                    color: {theme['logo_text']};
                    font-size: 14px;
                    border: none !important;
                }}
                QFrame {{
                    background-color: {theme['frame']};
                    border: 1px solid {theme['frame_border']};
                    border-radius: 4px;
                    margin: 1px;
                    padding: 3px;
                }}
                QFrame:hover {{
                    border-color: {theme['input_focus']};
                    background-color: {theme['frame_hover']};
                }}
                QWidget#flightCard {{
                    background-color: {theme['flight_card']};
                    border: 1px solid {theme['flight_card_border']};
                    border-radius: 4px;
                    margin: 1px;
                    padding: 3px;
                    color: {theme['flight_card_text']};
                }}
                QWidget#flightCard * {{
                    border: none !important;
                    background: transparent !important;
                }}
                QWidget#flightCard:hover {{
                    background-color: {theme['flight_card_hover']};
                }}
                QWidget#flightCard QLabel {{
                    color: {theme['flight_card_text']} !important;
                    border: none !important;
                    background: transparent !important;
                    margin: 0px;
                    padding: 0px;
                }}
                QWidget#flightCard QLabel#secondaryText {{
                    color: {theme['text_secondary']} !important;
                    border: none !important;
                    background: transparent !important;
                    margin: 0px;
                    padding: 0px;
                }}
                QScrollArea {{
                    background-color: {theme['scroll_area']};
                    border: none;
                }}
                QScrollArea#flightScrollArea {{
                    background-color: {theme['scroll_area']};
                    border: none;
                }}
                QScrollArea QWidget {{
                    background-color: {theme['scroll_area_widget']};
                }}
                QWidget#cardsContainer {{
                    background-color: {theme['scroll_area']};
                }}
                QSlider::groove:horizontal {{
                    border: 1px solid {theme['border']};
                    height: 8px;
                    background: {theme['scroll_area']};
                    border-radius: 4px;
                }}
                QSlider::handle:horizontal {{
                    background: {theme['primary']};
                    border: 1px solid {theme['primary_hover']};
                    width: 18px;
                    margin: -2px 0;
                    border-radius: 9px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: {theme['primary_hover']};
                }}
                QScrollBar:vertical {{
                    background: {theme['scroll_area']};
                    width: 20px;
                    border: 1px solid {theme['border']};
                    border-radius: 10px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {theme['primary']};
                    border: 1px solid {theme['primary_hover']};
                    border-radius: 9px;
                    min-height: 30px;
                    margin: 1px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {theme['primary_hover']};
                }}
                QScrollBar::handle:vertical:pressed {{
                    background: {theme['primary_pressed']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    background: {theme['border']};
                    height: 20px;
                    border-radius: 10px;
                }}
                QScrollBar::add-line:vertical:hover, QScrollBar::sub-line:vertical:hover {{
                    background: {theme['primary']};
                }}
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                    background: {theme['text_primary']};
                    width: 8px;
                    height: 8px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: transparent;
                }}
            """)
        
        # Force refresh the scroll area theme
        self.refresh_scroll_area_theme()
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_F11 or event.key() == Qt.Key_Escape:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        if self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            self.is_fullscreen = True
    
    def update_quit_button(self):
        """Update the quit button styling based on current theme"""
        if self.is_dark_mode:
            self.quit_button.setStyleSheet("""
                QPushButton {
                    padding: 2px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #e74c3c;
                    border: 1px solid #7f8c8d;
                    border-radius: 12px;
                    background-color: #34495e;
                }
                QPushButton:hover {
                    background-color: #e74c3c;
                    color: white;
                    border-color: #e74c3c;
                }
                QPushButton:pressed {
                    background-color: #c0392b;
                }
            """)
        else:
            self.quit_button.setStyleSheet("""
                QPushButton {
                    padding: 2px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #e74c3c;
                    border: 1px solid #ddd;
                    border-radius: 12px;
                    background-color: #f8f9fa;
                }
                QPushButton:hover {
                    background-color: #e74c3c;
                    color: white;
                    border-color: #e74c3c;
                }
                QPushButton:pressed {
                    background-color: #c0392b;
                }
            """)
    
    def close_application(self):
        """Close the application safely"""
        # Stop the data thread if it exists
        if hasattr(self, 'data_thread'):
            self.data_thread.stop()
            self.data_thread.wait()
        # Close the main window
        self.close()
    
    def closeEvent(self, event):
        """Handle application close"""
        if hasattr(self, 'data_thread'):
            self.data_thread.stop()
            self.data_thread.wait()
        event.accept()

def main():
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='PiScnr24 - Flight Tracker')
    parser.add_argument('--fullscreen', '-f', action='store_true', 
                       help='Force fullscreen mode')
    parser.add_argument('--windowed', '-w', action='store_true', 
                       help='Force windowed mode (overrides auto-detection)')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("PiScnr24")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("PiScnr24")
    
    # Create and show the main window
    window = FlightTrackerGUI()
    
    # Determine display mode
    import platform
    is_raspberry_pi = platform.system() == "Linux" and "arm" in platform.machine().lower()
    
    if args.windowed:
        # Force windowed mode
        window.show()
    elif args.fullscreen or is_raspberry_pi:
        # Force fullscreen or auto-detect Raspberry Pi
        window.showFullScreen()
        window.is_fullscreen = True
    else:
        # Default windowed mode for other systems
        window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
