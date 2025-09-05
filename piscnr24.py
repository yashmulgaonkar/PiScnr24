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


class RawDataPopup(QDialog):
    """Popup window to display raw flight data"""
    
    def __init__(self, flight_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Raw Flight Data")
        self.setModal(True)
        self.resize(600, 400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add title
        title_label = QLabel(f"Raw Data for Flight: {flight_data.get('callsign', 'Unknown')}")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Add raw data text area
        self.raw_data_text = QTextEdit()
        self.raw_data_text.setReadOnly(True)
        self.raw_data_text.setFont(QFont("Courier", 9))
        self.raw_data_text.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6;")
        
        # Format the raw data as JSON
        formatted_data = json.dumps(flight_data, indent=2, default=str)
        self.raw_data_text.setPlainText(formatted_data)
        
        layout.addWidget(self.raw_data_text)
        
        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("padding: 5px 20px;")
        layout.addWidget(close_button)


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
        self.is_dark_mode = False  # Start with light mode
        self.init_ui()
        self.init_data_thread()
        
        # Show initial GPS filter settings
        # Initialize footer
        
    def init_ui(self):
        self.setWindowTitle("PiScnr24 - See what is above you!")
        self.setGeometry(100, 100, GUI_WINDOW_WIDTH, GUI_WINDOW_HEIGHT)
        
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
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Logo instead of text title
        logo_label = QLabel()
        logo_path = os.path.join("assets", "PiScnr24.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                # Scale logo to reasonable size (max height 60px, maintain aspect ratio)
                scaled_pixmap = pixmap.scaled(200, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                # Fallback to text if image loading fails
                logo_label.setText("PiScnr24")
                logo_label.setFont(QFont("Arial", 24, QFont.Bold))
                logo_label.setStyleSheet("color: #2c3e50; margin: 10px;")
        else:
            # Fallback to text if file doesn't exist
            logo_label.setText("PiScnr24")
            logo_label.setFont(QFont("Arial", 24, QFont.Bold))
            logo_label.setStyleSheet("color: #2c3e50; margin: 10px;")
        
        # Remove border and background from logo
        logo_label.setStyleSheet("background-color: transparent; border: none; margin: 10px;")
        logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        
        # GPS Controls
        gps_group = QGroupBox("GPS Coordinates")
        gps_layout = QVBoxLayout(gps_group)
        
        # Create 2x2 grid for inputs
        grid_layout = QGridLayout()
        
        # Row 1: Latitude and Longitude
        grid_layout.addWidget(QLabel("Latitude:"), 0, 0)
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setValue(DEFAULT_LATITUDE)
        self.lat_input.setDecimals(6)
        self.lat_input.setFixedWidth(120)
        grid_layout.addWidget(self.lat_input, 0, 1)
        
        grid_layout.addWidget(QLabel("Longitude:"), 0, 2)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)
        self.lon_input.setValue(DEFAULT_LONGITUDE)
        self.lon_input.setDecimals(6)
        self.lon_input.setFixedWidth(120)
        grid_layout.addWidget(self.lon_input, 0, 3)
        
        # Row 2: Radius and Altitude Filter
        grid_layout.addWidget(QLabel("Radius:"), 1, 0)
        self.range_input = QSpinBox()
        self.range_input.setRange(1, 1000)
        self.range_input.setValue(DEFAULT_RANGE_MILES)
        self.range_input.setSuffix(" miles")
        self.range_input.setFixedWidth(100)
        grid_layout.addWidget(self.range_input, 1, 1)
        
        grid_layout.addWidget(QLabel("Show flights above:"), 1, 2)
        self.altitude_filter_input = QSpinBox()
        self.altitude_filter_input.setRange(0, 50000)
        self.altitude_filter_input.setValue(100)  # Default 100 feet
        self.altitude_filter_input.setSuffix(" feet")
        self.altitude_filter_input.setFixedWidth(100)
        grid_layout.addWidget(self.altitude_filter_input, 1, 3)
        
        gps_layout.addLayout(grid_layout)
        
        # Apply GPS button
        self.apply_gps_button = QPushButton("Apply GPS Filter")
        self.apply_gps_button.clicked.connect(self.apply_gps_filter)
        gps_layout.addWidget(self.apply_gps_button)
        
        header_layout.addWidget(gps_group)
        
        # Theme Toggle Button
        self.theme_button = QPushButton("☀️")
        self.theme_button.setFixedSize(40, 30)
        self.theme_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                border: 2px solid #ddd;
                border-radius: 15px;
                background-color: #f8f9fa;
                padding: 2px;
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
        
        # Initialize theme button and apply theme
        self.update_theme_button()
        self.apply_theme()
        
        # Controls
        self.refresh_button = QPushButton("Refresh Now")
        self.refresh_button.clicked.connect(self.manual_refresh)
        header_layout.addWidget(self.refresh_button)
        
        main_layout.addLayout(header_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Main content - Combined flight table and details
        main_panel = self.create_combined_flight_panel()
        main_layout.addWidget(main_panel)
        
        # Footer
        footer_layout = QHBoxLayout()
        self.last_update_label = QLabel("Last update: Never")
        self.last_update_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        footer_layout.addWidget(self.last_update_label)
        footer_layout.addStretch()
               
        main_layout.addLayout(footer_layout)
        
    def create_combined_flight_panel(self):
        """Create a responsive card-based flight display"""
        group_box = QGroupBox("Flight Information")
        layout = QVBoxLayout(group_box)
        
        # Create scroll area for responsive cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create container widget for cards
        self.cards_container = QWidget()
        self.cards_container.setObjectName("cardsContainer")  # Add object name for theme targeting
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll_area.setWidget(self.cards_container)
        layout.addWidget(scroll_area)
        
        return group_box
    
    def create_flight_card(self, flight):
        """Create a responsive card for a single flight"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setObjectName("flightCard")  # Add object name for theme targeting
        
        # Main layout for the card
        main_layout = QHBoxLayout(card)
        main_layout.setSpacing(15)
        
        # Left side - Logo
        logo_widget = QLabel()
        logo_widget.setStyleSheet("background-color: transparent;")
        logo_widget.setAlignment(Qt.AlignCenter)
        
        # Load airline logo
        callsign = flight.get('callsign', '')
        if len(callsign) >= 3:
            airline_code = callsign[:3]
            logo_widget, _ = self.create_logo_widget(airline_code)
            # Logo size is already set in create_logo_widget
        else:
            # Default "N/A" logo
            logo_widget.setText("N/A")
            logo_widget.setObjectName("logoWidget")  # Add object name for theme targeting
            logo_widget.setFixedSize(60, 40)
        
        main_layout.addWidget(logo_widget)
        
        # Center - Flight info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # Callsign with airline name (large, bold)
        callsign = flight.get('callsign', 'N/A')
        if callsign != 'N/A' and len(callsign) >= 3:
            # Try to get airline name from first 3 characters
            airline_code = callsign[:3]
            airline_name = get_airline_name(airline_code)
            if airline_name != airline_code:  # If we found a match
                callsign_display = f"{callsign} ({airline_name})"
            else:
                callsign_display = callsign
        else:
            callsign_display = callsign
            
        callsign_label = QLabel(callsign_display)
        callsign_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        callsign_label.setWordWrap(True)  # Allow text wrapping for long airline names
        info_layout.addWidget(callsign_label)
        
        # Aircraft type
        aircraft_label = QLabel(flight.get('plane', 'N/A'))
        aircraft_label.setStyleSheet("font-size: 12px;")
        info_layout.addWidget(aircraft_label)
        
        # Route with full airport names
        origin = flight.get('origin', 'N/A')
        destination = flight.get('destination', 'N/A')
        
        # Get full airport names if codes are available
        if origin != 'N/A' and len(origin) == 3:
            origin_name = get_airport_name(origin)
            origin_display = f"{origin_name} ({origin})"
        else:
            origin_display = origin
            
        if destination != 'N/A' and len(destination) == 3:
            destination_name = get_airport_name(destination)
            destination_display = f"{destination_name} ({destination})"
        else:
            destination_display = destination
        
        route_label = QLabel(f"{origin_display} → {destination_display}")
        route_label.setStyleSheet("font-size: 12px;")
        route_label.setWordWrap(True)  # Allow text wrapping for long airport names
        info_layout.addWidget(route_label)
        
        main_layout.addLayout(info_layout)
        
        # Right side - Flight data
        data_layout = QVBoxLayout()
        data_layout.setSpacing(5)
        
        # Altitude
        altitude = flight.get('altitude', 0)
        altitude_text = f"{altitude:,} ft" if altitude else 'N/A'
        altitude_label = QLabel(f"Altitude: {altitude_text}")
        altitude_label.setStyleSheet("font-size: 11px;")
        data_layout.addWidget(altitude_label)
        
        # Vertical Speed
        vspeed = flight.get('vertical_speed', 0)
        vspeed_text = f"{vspeed:,} ft/min" if vspeed else 'N/A'
        vspeed_label = QLabel(f"V/Speed: {vspeed_text}")
        vspeed_label.setStyleSheet("font-size: 11px;")
        data_layout.addWidget(vspeed_label)
        
        # Distance
        distance = self.calculate_distance(flight)
        if distance:
            # Convert km to miles (1 km = 0.621371 miles)
            distance_miles = distance * 0.621371
            distance_text = f"{distance_miles:.1f} miles"
        else:
            distance_text = 'N/A'
        distance_label = QLabel(f"Distance: {distance_text}")
        distance_label.setStyleSheet("font-size: 11px;")
        data_layout.addWidget(distance_label)
        
        main_layout.addLayout(data_layout)
        
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
        # Get altitude filter from input field
        altitude_filter_feet = self.altitude_filter_input.value()
        
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
        
        # Create cards for each filtered flight
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
                        # Maximum height of 100px, width scales proportionally
                        scaled_pixmap = pixmap.scaled(250, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
    
    def apply_gps_filter(self):
        """Apply GPS coordinate filter"""
        try:
            lat = self.lat_input.value()
            lon = self.lon_input.value()
            range_miles = self.range_input.value()
            
            # Convert miles to kilometers for the GPS filter
            range_km = range_miles * 1.60934
            
            self.gps_filter.set_coordinates(lat, lon, range_km)
            
            # Update the data thread's GPS filter
            if hasattr(self, 'data_thread'):
                self.data_thread.gps_filter = self.gps_filter
            
            # Update the overhead's GPS filter
            if hasattr(self, 'overhead'):
                self.overhead.gps_filter = self.gps_filter
            
            # GPS filter applied successfully
            
            # Trigger a manual refresh to apply the filter
            self.manual_refresh()
            
        except Exception as e:
            # GPS filter error - silently continue
            pass
    
    def update_status(self, status):
        """Update the footer"""
        # Don't update the last update label with status messages
        # The timestamp should only be updated when new data arrives
        pass
        
        
    def manual_refresh(self):
        """Manually trigger a data refresh"""
        self.last_update_label.setText("Last update: Manual refresh requested...")
        # This would need to be implemented to force a refresh
        
    def toggle_theme_button(self):
        """Toggle between light and dark mode using button"""
        self.is_dark_mode = not self.is_dark_mode
        self.update_theme_button()
        self.apply_theme()
        
    def update_theme_button(self):
        """Update the theme button icon and styling"""
        if self.is_dark_mode:
            self.theme_button.setText("🌙")
            self.theme_button.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    border: 2px solid #7f8c8d;
                    border-radius: 15px;
                    background-color: #34495e;
                    color: #ecf0f1;
                    padding: 2px;
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
            self.theme_button.setText("☀️")
            self.theme_button.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    border: 2px solid #ddd;
                    border-radius: 15px;
                    background-color: #f8f9fa;
                    color: #2c3e50;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #3498db;
                }
                QPushButton:pressed {
                    background-color: #dee2e6;
                }
            """)
        
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
                    font-size: 10px;
                    border: none !important;
                }}
                QFrame {{
                    background-color: {theme['frame']};
                    border: 1px solid {theme['frame_border']};
                    border-radius: 8px;
                    margin: 5px;
                    padding: 10px;
                }}
                QFrame:hover {{
                    border-color: {theme['input_focus']};
                    background-color: {theme['frame_hover']};
                }}
                QFrame#flightCard {{
                    background-color: {theme['flight_card']};
                    border: 1px solid {theme['flight_card_border']};
                    border-radius: 8px;
                    margin: 5px;
                    padding: 10px;
                    color: {theme['flight_card_text']};
                }}
                QFrame#flightCard:hover {{
                    border-color: {theme['input_focus']};
                    background-color: {theme['flight_card_hover']};
                }}
                QFrame#flightCard QLabel {{
                    color: {theme['flight_card_text']} !important;
                }}
                QScrollArea {{
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
                    font-size: 10px;
                    border: none !important;
                }}
                QFrame {{
                    background-color: {theme['frame']};
                    border: 1px solid {theme['frame_border']};
                    border-radius: 8px;
                    margin: 5px;
                    padding: 10px;
                }}
                QFrame:hover {{
                    border-color: {theme['input_focus']};
                    background-color: {theme['frame_hover']};
                }}
                QFrame#flightCard {{
                    background-color: {theme['flight_card']};
                    border: 1px solid {theme['flight_card_border']};
                    border-radius: 8px;
                    margin: 5px;
                    padding: 10px;
                    color: {theme['flight_card_text']};
                }}
                QFrame#flightCard:hover {{
                    border-color: {theme['input_focus']};
                    background-color: {theme['flight_card_hover']};
                }}
                QFrame#flightCard QLabel {{
                    color: {theme['flight_card_text']} !important;
                }}
                QScrollArea {{
                    background-color: {theme['scroll_area']};
                    border: none;
                }}
                QScrollArea QWidget {{
                    background-color: {theme['scroll_area_widget']};
                }}
                QWidget#cardsContainer {{
                    background-color: {THEME_COLORS['background']};
                }}
                QSlider::groove:horizontal {{
                    border: 1px solid #ddd;
                    height: 8px;
                    background: #f0f0f0;
                    border-radius: 4px;
                }}
                QSlider::handle:horizontal {{
                    background: {THEME_COLORS['primary']};
                    border: 1px solid {THEME_COLORS['primary_hover']};
                    width: 18px;
                    margin: -2px 0;
                    border-radius: 9px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: {THEME_COLORS['primary_hover']};
                }}
            """)
        
    def closeEvent(self, event):
        """Handle application close"""
        if hasattr(self, 'data_thread'):
            self.data_thread.stop()
            self.data_thread.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("PiScnr24")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("PiScnr24")
    
    # Create and show the main window
    window = FlightTrackerGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
