import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from custom_components.ontario_energy_board.const import (
    STATE_NO_PEAK,
)
from custom_components.ontario_energy_board.sensor import OntarioEnergyBoardSensor

TESTING_ENTITY_ID = "Union Gas (South) [Natural Gas]"


@pytest.fixture
def mock_coordinator():
    return Mock()


@pytest.fixture
def sensor(mock_coordinator):
    return OntarioEnergyBoardSensor(mock_coordinator, TESTING_ENTITY_ID, None)


@pytest.mark.parametrize(
    "current_date, expected_summer",
    [
        (datetime(2024, 5, 1, 0, 0, 0), True),  # Summer date
        (datetime(2024, 11, 1, 0, 0, 0), False),  # Winter date
    ],
)
def test_is_summer(sensor, current_date, expected_summer):
    with patch(
        "custom_components.ontario_energy_board.sensor.as_local",
        return_value=current_date,
    ):
        assert sensor.is_summer == expected_summer


def test_tou_active_peak(sensor):
    with patch.object(sensor.coordinator, "energy_sector", "natural_gas"):
        assert sensor.tou_active_peak == STATE_NO_PEAK


def test_ulo_active_peak(sensor):
    with patch.object(sensor.coordinator, "energy_sector", "natural_gas"):
        assert sensor.tou_active_peak == STATE_NO_PEAK


def test_active_peak_tou(sensor):
    with patch.object(sensor.coordinator, "energy_sector", "natural_gas"):
        assert sensor.tou_active_peak == STATE_NO_PEAK


def test_active_peak_ulo(sensor):
    with patch.object(sensor.coordinator, "energy_sector", "natural_gas"):
        assert sensor.tou_active_peak == STATE_NO_PEAK
