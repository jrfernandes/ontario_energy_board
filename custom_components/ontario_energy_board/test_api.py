from datetime import datetime

import aiohttp
import pytest_asyncio

from .api import OntarioEnergyBoard
from .const import STATE_MID_PEAK, STATE_OFF_PEAK, STATE_ON_PEAK

energy_company = (
    "Newmarket-Tay Power Distribution Ltd.-For Newmarket-Tay Power Main Rate Zone"
)


@pytest_asyncio.fixture
async def oeb():
    async with aiohttp.ClientSession() as websession:
        yield OntarioEnergyBoard(energy_company, websession)


def test_active_peak_with_summer_weekday(oeb, mocker):
    test_hours = {
        STATE_OFF_PEAK: [0, 3, 6, 19, 23],
        STATE_ON_PEAK: [11, 14, 16],
        STATE_MID_PEAK: [7, 10, 17, 18],
    }
    test_dates = [
        datetime(2020, 5, 1),
        datetime(2021, 8, 18),
        datetime(2022, 10, 31),
    ]

    for test_date in test_dates:
        for expected_peak, hours in test_hours.items():
            for test_hour in hours:
                mocker.patch(
                    "ontario_energy_board.api.as_local",
                    return_value=test_date.replace(hour=test_hour),
                )
                assert oeb.active_peak == expected_peak


def test_active_peak_with_winter_weekday(oeb, mocker):
    test_hours = {
        STATE_OFF_PEAK: [0, 3, 6, 19, 23],
        STATE_MID_PEAK: [11, 14, 16],
        STATE_ON_PEAK: [7, 10, 17, 18],
    }
    test_dates = [
        datetime(2021, 2, 11),
        datetime(2021, 4, 30),
        datetime(2021, 11, 1),
    ]

    for test_date in test_dates:
        for expected_peak, hours in test_hours.items():
            for test_hour in hours:
                mocker.patch(
                    "ontario_energy_board.api.as_local",
                    return_value=test_date.replace(hour=test_hour),
                )
                assert oeb.active_peak == expected_peak


def test_active_peak_with_non_holiday_weekend(oeb, mocker):
    for test_hour in (6, 8, 12, 18, 20):
        mocker.patch(
            "ontario_energy_board.api.as_local",
            return_value=datetime(2022, 2, 12, test_hour, 0, 0),
        )
        assert oeb.active_peak == STATE_OFF_PEAK


def test_active_peak_with_holiday_weekday(oeb, mocker):
    for test_hour in (6, 8, 12, 18, 20):
        mocker.patch(
            "ontario_energy_board.api.as_local",
            return_value=datetime(2022, 4, 15, test_hour, 0, 0),
        )
        assert oeb.active_peak == STATE_OFF_PEAK


def test_active_peak_with_holiday_weekend(oeb, mocker):
    for test_hour in (6, 8, 12, 18, 20):
        mocker.patch(
            "ontario_energy_board.api.as_local",
            return_value=datetime(2022, 1, 2, test_hour, 0, 0),
        )
        assert oeb.active_peak == STATE_OFF_PEAK

        mocker.patch(
            "ontario_energy_board.api.as_local",
            return_value=datetime(2022, 1, 1, test_hour, 0, 0),
        )
        assert oeb.active_peak == STATE_OFF_PEAK
