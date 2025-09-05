#!/usr/bin/env python3
"""
PiScnr24 - Airport and Airline lookup utilities
Copyright (c) 2024 [Your Name]

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to
Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
"""


from .airports_data import AIRPORTS
from .airlines_data import AIRLINES

def get_airport_name(airport_code):
    """
    Get full airport name from IATA code
    
    Args:
        airport_code (str): 3-letter IATA airport code (e.g., 'SFO')
    
    Returns:
        str: Full airport name (e.g., 'San Francisco International Airport')
             or the code itself if not found
    """
    if not airport_code or len(airport_code) != 3:
        return airport_code
    
    airport_code = airport_code.upper()
    airport = AIRPORTS.get(airport_code)
    
    if airport:
        return airport['name']
    else:
        return airport_code


def get_airline_name(airline_code):
    """
    Get airline name from ICAO code
    
    Args:
        airline_code (str): 3-letter ICAO airline code (e.g., 'AAL')
    
    Returns:
        str: Airline name (e.g., 'American Airlines')
             or the code itself if not found
    """
    if not airline_code or len(airline_code) != 3:
        return airline_code
    
    airline_code = airline_code.upper()
    airline = AIRLINES.get(airline_code)
    
    if airline:
        return airline['name']
    else:
        return airline_code




# Test the functions
if __name__ == "__main__":
    # Test airport lookups
    assert get_airport_name('SFO') != 'SFO'  # Should return full name
    assert get_airport_name('YUL') != 'YUL'  # Should return full name
    assert get_airport_name('LAX') != 'LAX'  # Should return full name
    
    # Test airline lookups
    assert get_airline_name('AAL') != 'AAL'  # Should return full name
    assert get_airline_name('UAL') != 'UAL'  # Should return full name
    
    # All tests passed
    
