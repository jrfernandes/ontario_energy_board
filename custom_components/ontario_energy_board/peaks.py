"""Time-of-use peak period rules for Ontario electricity.

This module is deliberately free of Home Assistant imports: every function here
is pure, taking an explicit timezone-aware ``datetime`` rather than reading the
clock. That makes the rules directly testable without a Home Assistant
instance, and keeps the sensor a thin adapter over them.

All callers must pass a datetime already localised to the Ontario timezone.
"""

from collections.abc import Container
from datetime import UTC, date, datetime, timedelta

from .const import (
    SECTOR_ELECTRICITY,
    STATE_MID_PEAK,
    STATE_NO_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_MID_PEAK,
    STATE_ULO_OFF_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OVERNIGHT,
)

SUMMER_FIRST_MONTH = 5
SUMMER_FIRST_DAY = 1
SUMMER_LAST_MONTH = 10
SUMMER_LAST_DAY = 31


def is_summer(moment: datetime) -> bool:
    """Whether the summer schedule applies, observed from May 1st to Oct 31st."""

    return (
        date(moment.year, SUMMER_FIRST_MONTH, SUMMER_FIRST_DAY)
        <= moment.date()
        <= date(moment.year, SUMMER_LAST_MONTH, SUMMER_LAST_DAY)
    )


def is_off_peak_day(moment: datetime, holidays: Container[date]) -> bool:
    """Whether the date falls on a weekend or an observed Ontario holiday."""

    return moment.weekday() >= 5 or moment.date() in holidays


def tou_active_peak(moment: datetime, holidays: Container[date]) -> str:
    """Find the active Time-of-Use peak for a given moment.

    According to OEB, weekends and holidays are 24-hour off-peak periods.
    During summer (observed from May 1st to Oct 31st), the morning and evening
    periods are mid-peak, and the afternoon is on-peak. This flips during winter
    time, where morning and evening are on-peak and afternoons are mid-peak.
    """

    if is_off_peak_day(moment, holidays):
        return STATE_OFF_PEAK

    hour = moment.hour

    if (7 <= hour < 11) or (17 <= hour < 19):
        return STATE_MID_PEAK if is_summer(moment) else STATE_ON_PEAK
    if 11 <= hour < 17:
        return STATE_ON_PEAK if is_summer(moment) else STATE_MID_PEAK

    return STATE_OFF_PEAK


def ulo_active_peak(moment: datetime, holidays: Container[date]) -> str:
    """Find the active Ultra-Low Overnight peak for a given moment.

    According to OEB, ULO nighttime rates apply every day. On weekends and
    holidays, daytime is off-peak. On weekdays, late afternoon and early
    evening is on-peak. The rest is mid-peak.

    ULO prices and periods are the same all year round.
    """

    hour = moment.hour

    if hour < 7 or hour >= 23:
        return STATE_ULO_OVERNIGHT

    if is_off_peak_day(moment, holidays):
        return STATE_ULO_OFF_PEAK

    if 16 <= hour < 21:
        return STATE_ULO_ON_PEAK

    return STATE_ULO_MID_PEAK


def active_peak(
    moment: datetime,
    holidays: Container[date],
    *,
    energy_sector: str,
    ulo_enabled: bool,
) -> str:
    """Find the active peak for a moment, given the sector and rate plan.

    Natural gas has no peak periods, so it always reports ``no_peak``.
    """

    if energy_sector != SECTOR_ELECTRICITY:
        return STATE_NO_PEAK

    if ulo_enabled:
        return ulo_active_peak(moment, holidays)

    return tou_active_peak(moment, holidays)


# A Time-of-Use off-peak stretch runs from Friday evening to Monday morning,
# and a holiday adjoining a weekend extends it further. Eight days clears any
# run of statutory holidays Ontario can produce, and the search is cheap.
MAX_LOOKAHEAD_HOURS = 8 * 24


def _next_hour(moment: datetime) -> datetime:
    """The following hour boundary, correct across daylight saving changes.

    Adding to a zone-aware datetime directly does wall-clock arithmetic and
    keeps the old offset, which drifts by an hour twice a year. Going through
    UTC keeps it to a true hour.
    """
    return (moment.astimezone(UTC) + timedelta(hours=1)).astimezone(moment.tzinfo)


def next_peak_change(
    moment: datetime,
    holidays: Container[date],
    *,
    energy_sector: str,
    ulo_enabled: bool,
) -> tuple[datetime, str] | None:
    """When the peak next changes, and what it changes to.

    Returns None where there is nothing to look forward to, which is any
    sector without peak periods.

    Peaks only ever change on the hour, so only hour boundaries are tested.
    """
    if energy_sector != SECTOR_ELECTRICITY:
        return None

    current = active_peak(
        moment, holidays, energy_sector=energy_sector, ulo_enabled=ulo_enabled
    )

    probe = moment.replace(minute=0, second=0, microsecond=0)

    for _ in range(MAX_LOOKAHEAD_HOURS):
        probe = _next_hour(probe)
        upcoming = active_peak(
            probe, holidays, energy_sector=energy_sector, ulo_enabled=ulo_enabled
        )

        if upcoming != current:
            return probe, upcoming

    return None
