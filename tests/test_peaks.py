"""Tests for the pure peak-period rules.

These run without Home Assistant: the functions under test take an explicit
timezone-aware datetime, so every case is a plain function call. All moments are
built in America/Toronto, which is what the sensor localises to in production.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from holidays import country_holidays
import pytest

from custom_components.ontario_energy_board.const import (
    SECTOR_ELECTRICITY,
    SECTOR_NATURAL_GAS,
    STATE_MID_PEAK,
    STATE_NO_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_MID_PEAK,
    STATE_ULO_OFF_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OVERNIGHT,
)
from custom_components.ontario_energy_board.peaks import (
    active_peak,
    is_summer,
    tou_active_peak,
    ulo_active_peak,
)

ONTARIO = ZoneInfo("America/Toronto")

CANADA_DAY = date(2024, 7, 1)
CHRISTMAS = date(2024, 12, 25)


def at(day: date, hour: int) -> datetime:
    """Build an Ontario-local moment."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=ONTARIO)


# (date, hours, holidays, expected state)
TIME_OF_USE_SCENARIOS = [
    (date(2024, 5, 1), range(11, 17), [], STATE_ON_PEAK),  # Summer weekday on-peak
    (
        date(2024, 5, 1),
        [*range(7, 11), *range(17, 19)],
        [],
        STATE_MID_PEAK,
    ),  # Summer weekday mid-peak
    (
        date(2024, 5, 1),
        [*range(0, 7), *range(19, 24)],
        [],
        STATE_OFF_PEAK,
    ),  # Summer weekday off-peak
    (date(2024, 5, 4), range(24), [], STATE_OFF_PEAK),  # Summer weekend
    (date(2024, 7, 1), range(24), [CANADA_DAY], STATE_OFF_PEAK),  # Summer holiday
    (
        date(2024, 1, 1),
        [*range(7, 11), *range(17, 19)],
        [],
        STATE_ON_PEAK,
    ),  # Winter weekday on-peak
    (date(2024, 1, 1), range(11, 17), [], STATE_MID_PEAK),  # Winter weekday mid-peak
    (
        date(2024, 1, 1),
        [*range(0, 7), *range(19, 24)],
        [],
        STATE_OFF_PEAK,
    ),  # Winter weekday off-peak
    (date(2024, 11, 2), range(24), [], STATE_OFF_PEAK),  # Winter weekend
    (date(2024, 12, 25), range(24), [CHRISTMAS], STATE_OFF_PEAK),  # Winter holiday
]

ULTRA_LOW_OVERNIGHT_SCENARIOS = [
    (date(2024, 1, 1), range(16, 21), [], STATE_ULO_ON_PEAK),  # Weekday on-peak
    (
        date(2024, 1, 1),
        [*range(7, 16), *range(21, 23)],
        [],
        STATE_ULO_MID_PEAK,
    ),  # Weekday mid-peak
    (
        date(2024, 1, 1),
        [*range(0, 7), 23],
        [],
        STATE_ULO_OVERNIGHT,
    ),  # Weekday overnight
    (date(2024, 1, 6), range(7, 23), [], STATE_ULO_OFF_PEAK),  # Weekend daytime
    (
        date(2024, 1, 6),
        [*range(0, 7), 23],
        [],
        STATE_ULO_OVERNIGHT,
    ),  # Weekend overnight
    (
        date(2024, 12, 25),
        range(7, 23),
        [CHRISTMAS],
        STATE_ULO_OFF_PEAK,
    ),  # Holiday daytime
    (
        date(2024, 12, 25),
        [*range(0, 7), 23],
        [CHRISTMAS],
        STATE_ULO_OVERNIGHT,
    ),  # Holiday overnight
]


@pytest.mark.parametrize(
    "moment, expected",
    [
        (at(date(2024, 4, 30), 12), False),  # Day before summer starts
        (at(date(2024, 5, 1), 0), True),  # First moment of summer
        (at(date(2024, 10, 31), 23), True),  # Last moment of summer
        (at(date(2024, 11, 1), 0), False),  # First moment of winter
        (at(date(2024, 1, 15), 12), False),
    ],
)
def test_is_summer(moment, expected):
    assert is_summer(moment) is expected


@pytest.mark.parametrize("day, hours, holidays, expected", TIME_OF_USE_SCENARIOS)
def test_tou_active_peak(day, hours, holidays, expected):
    for hour in hours:
        assert tou_active_peak(at(day, hour), holidays) == expected, f"{day} {hour}:00"


@pytest.mark.parametrize(
    "day, hours, holidays, expected", ULTRA_LOW_OVERNIGHT_SCENARIOS
)
def test_ulo_active_peak(day, hours, holidays, expected):
    for hour in hours:
        assert ulo_active_peak(at(day, hour), holidays) == expected, f"{day} {hour}:00"


@pytest.mark.parametrize("day, hours, holidays, expected", TIME_OF_USE_SCENARIOS)
def test_active_peak_uses_tou_when_ulo_disabled(day, hours, holidays, expected):
    for hour in hours:
        assert (
            active_peak(
                at(day, hour),
                holidays,
                energy_sector=SECTOR_ELECTRICITY,
                ulo_enabled=False,
            )
            == expected
        )


@pytest.mark.parametrize(
    "day, hours, holidays, expected", ULTRA_LOW_OVERNIGHT_SCENARIOS
)
def test_active_peak_uses_ulo_when_enabled(day, hours, holidays, expected):
    for hour in hours:
        assert (
            active_peak(
                at(day, hour),
                holidays,
                energy_sector=SECTOR_ELECTRICITY,
                ulo_enabled=True,
            )
            == expected
        )


@pytest.mark.parametrize("ulo_enabled", [True, False])
def test_natural_gas_never_has_a_peak(ulo_enabled):
    """Gas has no time-of-use periods regardless of the rate plan."""
    for hour in range(24):
        assert (
            active_peak(
                at(date(2024, 1, 15), hour),
                [],
                energy_sector=SECTOR_NATURAL_GAS,
                ulo_enabled=ulo_enabled,
            )
            == STATE_NO_PEAK
        )


def test_ulo_overnight_wins_over_holiday():
    """Overnight applies every day, including holidays and weekends."""
    assert ulo_active_peak(at(CHRISTMAS, 2), [CHRISTMAS]) == STATE_ULO_OVERNIGHT


def test_tou_boundaries_are_half_open():
    """Boundary hours belong to the period that starts on them."""
    weekday = date(2024, 1, 15)  # A Monday in winter

    assert tou_active_peak(at(weekday, 6), []) == STATE_OFF_PEAK
    assert tou_active_peak(at(weekday, 7), []) == STATE_ON_PEAK
    assert tou_active_peak(at(weekday, 11), []) == STATE_MID_PEAK
    assert tou_active_peak(at(weekday, 17), []) == STATE_ON_PEAK
    assert tou_active_peak(at(weekday, 19), []) == STATE_OFF_PEAK


def test_ulo_boundaries_are_half_open():
    weekday = date(2024, 1, 15)  # A Monday

    assert ulo_active_peak(at(weekday, 6), []) == STATE_ULO_OVERNIGHT
    assert ulo_active_peak(at(weekday, 7), []) == STATE_ULO_MID_PEAK
    assert ulo_active_peak(at(weekday, 16), []) == STATE_ULO_ON_PEAK
    assert ulo_active_peak(at(weekday, 21), []) == STATE_ULO_MID_PEAK
    assert ulo_active_peak(at(weekday, 23), []) == STATE_ULO_OVERNIGHT


def test_peaks_follow_local_time_across_dst():
    """A UTC instant maps to different peaks either side of the DST switch.

    17:00 UTC is 12:00 in Ontario during EST and 13:00 during EDT. Both fall in
    the winter mid-peak window, but the same clock hour must be derived from
    local time, never from UTC.
    """
    winter_utc = datetime(2024, 1, 15, 17, tzinfo=ZoneInfo("UTC"))
    summer_utc = datetime(2024, 7, 15, 17, tzinfo=ZoneInfo("UTC"))

    winter_local = winter_utc.astimezone(ONTARIO)
    summer_local = summer_utc.astimezone(ONTARIO)

    assert winter_local.hour == 12
    assert summer_local.hour == 13

    assert tou_active_peak(winter_local, []) == STATE_MID_PEAK
    assert tou_active_peak(summer_local, []) == STATE_ON_PEAK


def test_dst_spring_forward_hour_is_handled():
    """On the spring-forward day the 2am hour does not exist locally."""
    # 06:30 UTC on 2024-03-10 is 01:30 EST; 07:30 UTC is 03:30 EDT.
    before = datetime(2024, 3, 10, 6, 30, tzinfo=ZoneInfo("UTC")).astimezone(ONTARIO)
    after = datetime(2024, 3, 10, 7, 30, tzinfo=ZoneInfo("UTC")).astimezone(ONTARIO)

    assert before.hour == 1
    assert after.hour == 3

    # Sunday, so both are off-peak, but the lookup must not raise.
    assert tou_active_peak(before, []) == STATE_OFF_PEAK
    assert tou_active_peak(after, []) == STATE_OFF_PEAK
    assert ulo_active_peak(before, []) == STATE_ULO_OVERNIGHT
    assert ulo_active_peak(after, []) == STATE_ULO_OVERNIGHT


def test_real_ontario_holidays_are_recognised():
    """Guard the holidays configuration the sensor builds in production."""
    ontario_holidays = country_holidays(
        "CA", subdiv="ON", observed=True, categories={"public", "optional"}
    )

    # Family Day is an Ontario-specific statutory holiday.
    family_day = date(2024, 2, 19)
    assert family_day in ontario_holidays
    assert tou_active_peak(at(family_day, 12), ontario_holidays) == STATE_OFF_PEAK

    # Boxing Day is in the "optional" category and must be included.
    boxing_day = date(2024, 12, 26)
    assert boxing_day in ontario_holidays

    # A plain working Monday must not be treated as a holiday.
    assert date(2024, 1, 15) not in ontario_holidays
