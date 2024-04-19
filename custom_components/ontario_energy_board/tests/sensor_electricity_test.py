import pytest
from unittest.mock import Mock, patch
from datetime import date, datetime
from custom_components.ontario_energy_board.const import (
    STATE_MID_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_MID_PEAK,
    STATE_ULO_OFF_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OVERNIGHT,
)
from custom_components.ontario_energy_board.sensor import OntarioEnergyBoardSensor

TESTING_ENTITY_ID = "Newmarket-Tay Power Distribution Ltd.-For Newmarket-Tay Power Main Rate Zone (RESIDENTIAL) [Electricity]"
TIME_OF_USE_SCENARIOS = [
    (
        datetime(2024, 5, 1),
        range(11, 17),
        [],
        STATE_ON_PEAK,
    ),  # Summer, weekday, on-peak
    (
        datetime(2024, 5, 1),
        list(range(7, 11)) + list(range(17, 19)),
        [],
        STATE_MID_PEAK,
    ),  # Summer, weekday, mid-peak
    (
        datetime(2024, 5, 1),
        list(range(0, 7)) + list(range(19, 24)),
        [],
        STATE_OFF_PEAK,
    ),  # Summer, weekday, off-peak
    (datetime(2024, 5, 4), range(24), [], STATE_OFF_PEAK),  # Summer, weekend, off-peak
    (
        datetime(2024, 7, 1),
        range(24),
        [date(2024, 7, 1)],
        STATE_OFF_PEAK,
    ),  # Summer, holiday, off-peak
    (
        datetime(2024, 1, 1),
        list(range(7, 11)) + list(range(17, 19)),
        [],
        STATE_ON_PEAK,
    ),  # Winter, weekday, on-peak
    (
        datetime(2024, 1, 1),
        range(11, 17),
        [],
        STATE_MID_PEAK,
    ),  # Winter, weekday, mid-peak
    (
        datetime(2024, 1, 1),
        list(range(0, 7)) + list(range(19, 24)),
        [],
        STATE_OFF_PEAK,
    ),  # Winter, weekday, off-peak
    (datetime(2024, 11, 2), range(24), [], STATE_OFF_PEAK),  # Winter, weekend, off-peak
    (
        datetime(2024, 12, 25),
        range(24),
        [date(2024, 12, 25)],
        STATE_OFF_PEAK,
    ),  # Winter, holiday, off-peak
]
ULTRA_LOW_OVERNIGHT_SCENARIOS = [
    (datetime(2024, 1, 1), range(16, 21), [], STATE_ULO_ON_PEAK),  # Weekday, on-peak
    (
        datetime(2024, 1, 1),
        list(range(7, 16)) + list(range(21, 23)),
        [],
        STATE_ULO_MID_PEAK,
    ),  # Weekday, mid-peak
    (
        datetime(2024, 1, 1),
        list(range(0, 7)) + list(range(23, 24)),
        [],
        STATE_ULO_OVERNIGHT,
    ),  # Weekday, off-peak
    (datetime(2024, 1, 6), range(7, 23), [], STATE_ULO_OFF_PEAK),  # Weekend, off-peak
    (
        datetime(2024, 1, 6),
        list(range(0, 7)) + list(range(23, 24)),
        [],
        STATE_ULO_OVERNIGHT,
    ),  # Weekend, ulo-peak
    (
        datetime(2024, 12, 25),
        range(7, 23),
        [date(2024, 12, 25)],
        STATE_ULO_OFF_PEAK,
    ),  # Winter, holiday, off-peak
    (
        datetime(2024, 12, 25),
        list(range(0, 7)) + list(range(23, 24)),
        [date(2024, 12, 25)],
        STATE_ULO_OVERNIGHT,
    ),  # Winter, holiday, off-peak
]


@pytest.fixture
def mock_coordinator():
    return Mock()


@pytest.fixture
def sensor(mock_coordinator):
    return OntarioEnergyBoardSensor(mock_coordinator, TESTING_ENTITY_ID)


@pytest.mark.parametrize(
    "current_date, expected_summer",
    [
        (datetime(2024, 6, 1, 0, 0, 0), True),  # Summer date
        (datetime(2024, 11, 1, 0, 0, 0), False),  # Winter date
    ],
)
def test_is_summer(sensor, current_date, expected_summer):
    with patch(
        "custom_components.ontario_energy_board.sensor.as_local",
        return_value=current_date,
    ):
        assert sensor.is_summer == expected_summer


@pytest.mark.parametrize(
    "test_date, test_hours, ontario_holidays, expected_peak_state",
    TIME_OF_USE_SCENARIOS,
)
def test_tou_active_peak(
    sensor, test_date, test_hours, ontario_holidays, expected_peak_state
):
    for test_hour in test_hours:
        with patch(
            "custom_components.ontario_energy_board.sensor.as_local",
            return_value=test_date.replace(hour=test_hour),
        ):
            with patch.object(sensor.coordinator, "ontario_holidays", ontario_holidays):
                assert sensor.tou_active_peak == expected_peak_state


@pytest.mark.parametrize(
    "test_date, test_hours, ontario_holidays, expected_peak_state",
    ULTRA_LOW_OVERNIGHT_SCENARIOS,
)
def test_ulo_active_peak(
    sensor, test_date, test_hours, ontario_holidays, expected_peak_state
):
    for test_hour in test_hours:
        with patch(
            "custom_components.ontario_energy_board.sensor.as_local",
            return_value=test_date.replace(hour=test_hour),
        ):
            with patch.object(sensor.coordinator, "ontario_holidays", ontario_holidays):
                assert sensor.ulo_active_peak == expected_peak_state


@pytest.mark.parametrize(
    "test_date, test_hours, ontario_holidays, expected_peak_state",
    TIME_OF_USE_SCENARIOS,
)
def test_active_peak_tou(
    sensor, test_date, test_hours, ontario_holidays, expected_peak_state
):
    for test_hour in test_hours:
        with patch(
            "custom_components.ontario_energy_board.sensor.as_local",
            return_value=test_date.replace(hour=test_hour),
        ):
            with patch.object(sensor.coordinator, "ontario_holidays", ontario_holidays):
                with patch.object(sensor.coordinator, "ulo_enabled", False):
                    assert sensor.active_peak == expected_peak_state


@pytest.mark.parametrize(
    "test_date, test_hours, ontario_holidays, expected_peak_state",
    ULTRA_LOW_OVERNIGHT_SCENARIOS,
)
def test_active_peak_ulo(
    sensor, test_date, test_hours, ontario_holidays, expected_peak_state
):
    for test_hour in test_hours:
        with patch(
            "custom_components.ontario_energy_board.sensor.as_local",
            return_value=test_date.replace(hour=test_hour),
        ):
            with patch.object(sensor.coordinator, "ontario_holidays", ontario_holidays):
                with patch.object(sensor.coordinator, "ulo_enabled", True):
                    assert sensor.active_peak == expected_peak_state
