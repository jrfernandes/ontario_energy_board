"""Constants for the Ontario Energy Board integration."""

DOMAIN = "ontario_energy_board"

CONF_ENERGY_COMPANY = "energy_company"

RATES_URL = "https://www.oeb.ca/_html/calculator/data/BillData.xml"

RATE_UNIT_OF_MEASURE = "CA$/kWh"

REFRESH_RATES_IN_MINUTES = 60 * 24

STATE_MID_PEAK = "mid_peak"
STATE_ON_PEAK = "on_peak"
STATE_OFF_PEAK = "off_peak"

XML_KEY_OFF_PEAK_RATE = "RPPOffP"
XML_KEY_MID_PEAK_RATE = "RPPMidP"
XML_KEY_ON_PEAK_RATE = "RPPOnP"
