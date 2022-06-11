"""Constants for the Ontario Energy Board integration."""
from datetime import date, timedelta

DOMAIN = "ontario_energy_board"

CONF_ENERGY_COMPANY = "energy_company"

ENERGY_SECTORS=['electricity', 'natural_gas']

ELECTRICITY_RATES_URL = "https://www.oeb.ca/_html/calculator/data/BillData.xml"
NATUR_GAS_RATES_URL = "https://www.oeb.ca/_html/calculator/data/GasBillData.xml"

ELECTRICITY_RATE_UNIT_OF_MEASURE = "CA $/kWh"
NATURAL_GAS_RATE_UNIT_OF_MEASURE = "CA ¢/m³"

REFRESH_RATES_INTERVAL = timedelta(days=1)
SCAN_INTERVAL = timedelta(minutes=1)

STATE_MID_PEAK = "mid_peak"
STATE_ON_PEAK = "on_peak"
STATE_OFF_PEAK = "off_peak"
STATE_NO_PEAK = "no_peak"

XML_KEY_OFF_PEAK_RATE = "RPPOffP"
XML_KEY_MID_PEAK_RATE = "RPPMidP"
XML_KEY_ON_PEAK_RATE = "RPPOnP"