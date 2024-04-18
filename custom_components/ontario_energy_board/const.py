"""Constants for the Ontario Energy Board integration."""

from datetime import timedelta

DOMAIN = "ontario_energy_board"

CONF_ENERGY_COMPANY = "energy_company"
CONF_ULO_ENABLED = "ulo_enabled"

ENERGY_SECTORS = ["electricity", "natural_gas"]

ELECTRICITY_RATES_URL = "https://www.oeb.ca/_html/calculator/data/BillData.xml"
NATURAL_GAS_RATES_URL = "https://www.oeb.ca/_html/calculator/data/GasBillData.xml"

ELECTRICITY_RATE_UNIT_OF_MEASURE = "CA $/kWh"
NATURAL_GAS_RATE_UNIT_OF_MEASURE = "CA ¢/m³"

REFRESH_RATES_INTERVAL = timedelta(days=1)
SCAN_INTERVAL = timedelta(minutes=1)

XML_KEY_MAPPINGS = {
    "electricity": {
        "Dist": "distributor_name",
        "Class": "rate_class",
        "YEAR": "rate_year",
        "ET1": "tier_threshold",
        "RPP1": "lower_tier_price",
        "RPP2": "higher_tier_price",
        "SC": "monthly_fixed_charge",
        "DC": "distribution_variable_charge",
        "GA_RR_NONRPP": "global_adjustment_rate_rider",
        "Net": "retail_transmission_network_rate",
        "Conn": "retail_transmission_connection_rate",
        "WMSR": "wholesale_market_service_charge",
        "RRRP": "rural_remote_rate_protection",
        "SSS": "standard_supply_service_charge",
        "LF": "loss_factor",
        "GST": "harmonized_sales_tax",
        "EOffP": "time_of_use_off_peak_usage",
        "EMidP": "time_of_use_mid_peak_usage",
        "EOnP": "time_of_use_on_peak_usage",
        "RPPOffP": "time_of_use_off_peak_price",
        "RPPMidP": "time_of_use_mid_peak_price",
        "RPPOnP": "time_of_use_on_peak_price",
        "PBGA": "global_adjustment",
        "Rebate": "ontario_electricity_rebate",
        "OFC": "other_fixed_charges",
        "VC": "distribution_volumetric_charge",
        "OC": "other_volumetric_charges",
        "DRP": "distribution_rate_protection",
        "DRC": "debt_retirement_charge",
        "DRP_Rate": "distribution_rate_protection_rate",
        "ULO_onp": "ultra_low_overnight_on_peak_rate",
        "ULO_onp_period": "ultra_low_overnight_on_peak_period",
        "ULO_weekendoffp": "ultra_low_overnight_weekend_off_peak_rate",
        "ULO_weekendoffp_period": "ultra_low_overnight_weekend_off_peak_period",
        "ULO_midp": "ultra_low_overnight_mid_peak_rate",
        "ULO_midp_period": "ultra_low_overnight_mid_peak_period",
        "ULO_overnight": "ultra_low_overnight_overnight_rate",
        "ULO_overnight_period": "ultra_low_overnight_overnight_period",
    },
    "natural_gas": {
        "Dist": "distributor_name",
        "SA": "service_area",
        "RC": "rate_class",
        "ED": "effective_date",
        "MC": "monthly_charge",
        "DT1Low": "delivery_tier_1_start",
        "DT1High": "delivery_tier_1_end",
        "DT2Low": "delivery_tier_2_start",
        "DT2High": "delivery_tier_2_end",
        "DT3Low": "delivery_tier_3_start",
        "DT3High": "delivery_tier_3_end",
        "DT4Low": "delivery_tier_4_start",
        "DT4High": "delivery_tier_4_end",
        "DT5Low": "delivery_tier_5_start",
        "DT5High": "delivery_tier_5_end",
        "DCT1": "delivery_charge_tier_1",
        "DCT2": "delivery_charge_tier_2",
        "DCT3": "delivery_charge_tier_3",
        "DCT4": "delivery_charge_tier_4",
        "DCT5": "delivery_charge_tier_5",
        "DCPA": "delivery_charge_price_adjustment",
        "SC": "storage_charge",
        "SCPA": "storage_charge_price_adjustment",
        "CM": "gas_supply_charge",
        "CMPA": "gas_supply_charge_price_adjustment",
        "TC": "transportation_charge",
        "TCPA": "transportation_charge_price_adjustment",
        "FedCC": "federal_carbon_charge",
        "FacCC": "facility_carbon_charge",
        "GST": "harmonized_sales_tax",
        "Jan": "january",
        "Feb": "february",
        "Mar": "march",
        "Apr": "april",
        "May": "may",
        "Jun": "june",
        "Jul": "july",
        "Aug": "august",
        "Sep": "september",
        "Oct": "october",
        "Nov": "november",
        "Dec": "december",
    },
}

STATE_MID_PEAK = "mid_peak"
STATE_ON_PEAK = "on_peak"
STATE_OFF_PEAK = "off_peak"
STATE_NO_PEAK = "no_peak"
STATE_NO_PEAK_RATE = "no_peak_rate"
STATE_ULO_MID_PEAK = "ulo_mid_peak"
STATE_ULO_ON_PEAK = "ulo_on_peak"
STATE_ULO_OFF_PEAK = "ulo_off_peak"
STATE_ULO_OVERNIGHT = "ulo_overnight"

XML_KEY_OFF_PEAK_RATE = "RPPOffP"
XML_KEY_MID_PEAK_RATE = "RPPMidP"
XML_KEY_ON_PEAK_RATE = "RPPOnP"
XML_KEY_ULO_OVERNIGHT_RATE = "ULO_overnight"
XML_KEY_ULO_OFF_PEAK_RATE = "ULO_weekendoffp"
XML_KEY_ULO_MID_PEAK_RATE = "ULO_midp"
XML_KEY_ULO_ON_PEAK_RATE = "ULO_onp"
