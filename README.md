# Ontario Energy Board integration
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This [Home Assistant](https://home-assistant.io/) component installs a sensor with the current energy rate and active peak for Ontario, Canada based companies, using the Ontario Energy Board's official open data inventory. Find out more at https://www.oeb.ca/open-data


# Installation

## HACS
1. Go to any of the integrations section.
1. Click on the 3 dots in the top right corner.
1. Select "Custom repositories"
1. Add the URL `https://github.com/jrfernandes/ontario_energy_board`
1. Select the "Integrations" category.
1. Click the "ADD" button to use the custom repository.
1. Click "Explore + Download repositories"
1. Search for "Ontario Energy Board" and install the found integration.

## Manual
For this, it is highly recomended to use the "Samba share" add-on (you will need to enable advanced mode in your user profile).

Clone or download the repo, and copy the "ontario_energy_board" folder in "custom_components" to the "custom_components" folder in home assistant. 


## Using the component

Once installed, use the UI to add the new component to your setup.
