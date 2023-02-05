# Ontario Energy Board integration
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![Tests](https://github.com/jrfernandes/ontario_energy_board/actions/workflows/pytest.yml/badge.svg)](https://github.com/jrfernandes/ontario_energy_board/actions/workflows/pytest.yml)
[![hacs validation](https://github.com/jrfernandes/ontario_energy_board/actions/workflows/hacs.yml/badge.svg)](https://github.com/jrfernandes/ontario_energy_board/actions/workflows/hacs.yml)
[![hassfest validation](https://github.com/jrfernandes/ontario_energy_board/actions/workflows/hassfest.yml/badge.svg)](https://github.com/jrfernandes/ontario_energy_board/actions/workflows/hassfest.yml)


This [Home Assistant](https://home-assistant.io/) component installs a sensor with the current energy rate and active peak for Ontario, Canada based companies, using the Ontario Energy Board's official open data inventory. Find out more at https://www.oeb.ca/open-data

![Preview](https://raw.githubusercontent.com/jrfernandes/ontario_energy_board/main/assets/sensor-preview.jpg)


# Installation

## HACS
1. Open integrations. 
1. Click "Explore + Download repositories"
1. Search for "Ontario Energy Board" and install the found integration.

## Manual
Clone or download the repo, and copy the "ontario_energy_board" folder in "custom_components" to the "custom_components" folder in home assistant. 


## Using the component

Once installed, use the UI to add the new component to your setup, or click on the button below:

[![AA](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=ontario_energy_board)


### Attributes

The sensor will include extra attributes for most of the available data from your energy supplier, enabling you to replicate your hydro bill if needed. @Digital-Ark [shared](https://github.com/jrfernandes/ontario_energy_board/issues/10#issuecomment-1242147422) this great [Google Sheets](https://docs.google.com/spreadsheets/d/14pV23ip7UQH6B72HYhsWEpsCbo_X1aII/) document containing the billing formula using the attributes extracted by this integration:

| Attribute                             | Unit        | Description                                                                |
|:--------------------------------------|:------------|:---------------------------------------------------------------------------|
| `energy_company`                      |             | Energy company name                                                        | 
| `off_peak_rate`                       | CA$/kWh     | Off-peak Rate                                                              |
| `mid_peak_rate`                       | CA$/kWh     | Mid-peak Rate                                                              |
| `on_peak_rate`                        | CA$/kWh     | On-peak Rate                                                               |
| `active_peak`                         |             | Active Peak                                                                |
| `season`                              |             | Current Season (`winter` or `summer`)                                      |
| `tier_threshold`                      | kWh         | Tier 1 Threshold                                                           |
| `tier_1`                              | CA$/kWh     | Tier 1 Rate                                                                |
| `tier_2`                              | CA$/kWh     | Tier 2 Rate                                                                |
| `service_charge`                      | CA$/30 days | Service Charge                                                             |
| `loss_adjustment_factor`              |             | Loss Adjustment Factor                                                     |
| `network_service_rate`                | CA$/kWh     | Retail Transmission Rate - Network Service Rate                            |
| `connection_service_rate`             | CA$/kWh     | Retail Transmission Rate - Line and Transformation Connection Service Rate |
| `wholesale_market_service_rate`       | CA$/kWh     | Wholesale Market Service Rate (WMSR) - including CBR                       |
| `rural_remote_rate_protection_charge` | CA$/kWh     | Rural or Remote Electricty Rate Protection Charge (RRRP)                   |
| `standard_supply_service`             | CA$/30 days | Standard Supply Service - Administrative Charge                            |
| `gst`                                 | %           | Goods & Services Tax (GST)                                                 |
| `rebate`                              | % rebate    | Ontario Electricity Rebate (OER)                                           |
| `one_time_fixed_charge`               |             | One-time Fixed Charge                                                      |
