"""Valication script to ensure coverage of OEB data parameters.
"""

import sys
from custom_components.ontario_energy_board.const import (
    ELECTRICITY_RATES_URL,
    NATUR_GAS_RATES_URL,
    XML_KEY_MAPPINGS,
)
import requests
import xml.etree.ElementTree as ET

# Grab OEB data
electricity_data = requests.get(ELECTRICITY_RATES_URL)
natural_gas_data = requests.get(NATUR_GAS_RATES_URL)

# Parse the XML
electricity_data_tree = ET.fromstring(electricity_data.content)
natural_gas_data_tree = ET.fromstring(natural_gas_data.content)

# Excluded keys
excluded_keys = {
    "electricity": [],
    "natural_gas": [
        "Lic",
        "ExtID",
    ],  # Lic & ExtID - don't have any substantial importance
}

# Calculate the different in keys and create dictionary
key_differences = {}
for energy_type, data_tree in [
    ("electricity", electricity_data_tree),
    ("natural_gas", natural_gas_data_tree),
]:
    # Grab the respective energy keys
    energy_keys = [
        element.tag
        for element in data_tree.findall(
            "BillDataRow" if energy_type == "electricity" else "GasBillData"
        )[0]
    ]

    # Calculate the sectional difference
    missing_from_oeb = [
        item
        for item in (set(energy_keys) - set(XML_KEY_MAPPINGS[energy_type].keys()))
        if item not in excluded_keys[energy_type]
    ]
    const_leftover = [
        item
        for item in (set(XML_KEY_MAPPINGS[energy_type].keys()) - set(energy_keys))
        if item not in excluded_keys[energy_type]
    ]

    # Create the energy type if it doesn't exist
    if missing_from_oeb or const_leftover:
        key_differences[energy_type] = {}

    # Check if there is a delta and add  it to the key_differences
    if missing_from_oeb:
        # missing_from_oeb = property exists in OEB data, though doesn't exist locally (likely a new data point)
        key_differences[energy_type]["missing_from_oeb"] = missing_from_oeb

    if const_leftover:
        # const_leftover = property exists in local XML_KEY_MAPPINGS const, though doesn't exist in OEB data (likely a removed data point)
        key_differences[energy_type]["const_leftover"] = const_leftover

# If there are key differences, exit with a non-zero exit code to indicate failure
if key_differences:
    # Display the key differences in the pipeline and exist in error
    print("Key Differences: {}".format(key_differences))
    sys.exit(1)
else:
    # Display no differences
    print("No differences!")
