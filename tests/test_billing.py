"""Tests for the Ontario electricity bill arithmetic.

These run without Home Assistant. The numbers below are not invented: they come
from the Ontario Energy Board's own bill calculator at
oeb.ca/_html/calculator/billcalc.php, and from a real Newmarket-Tay Power
residential bill. If the formula drifts, these fail.
"""

import pytest

from custom_components.ontario_energy_board.billing import (
    marginal_rate,
    tax_and_rebate_multiplier,
    volumetric_rate,
)

# Newmarket-Tay Power Distribution Ltd. - Newmarket-Tay Rate Zone, RESIDENTIAL,
# as published in BillData.xml, under the attribute names the parser produces.
NT_POWER = {
    "loss_factor": 1.0383,
    "monthly_fixed_charge": 38.24,
    "distribution_variable_charge": 0.0039,
    "retail_transmission_network_rate": 0.013,
    "retail_transmission_connection_rate": 0.0099,
    "wholesale_market_service_charge": 0.0047,
    "rural_remote_rate_protection": 0.0006,
    "standard_supply_service_charge": 0.25,
    "other_fixed_charges": 3.48,
    "harmonized_sales_tax": 0.13,
    "ontario_electricity_rebate": 0.235,
    "time_of_use_on_peak_price": 0.203,
    "time_of_use_mid_peak_price": 0.157,
    "time_of_use_off_peak_price": 0.098,
}

SERVICE_CHARGE = NT_POWER["monthly_fixed_charge"]
SUPPLY_SERVICE_CHARGE = NT_POWER["standard_supply_service_charge"]

# The calculator's own defaults: 700 kWh split 64% off, 18% mid, 18% on peak.
CALCULATOR_USAGE = {
    "time_of_use_off_peak_price": 700 * 0.64,
    "time_of_use_mid_peak_price": 700 * 0.18,
    "time_of_use_on_peak_price": 700 * 0.18,
}
# What it reported for that run.
CALCULATOR_ELECTRICITY = 89.26
CALCULATOR_DELIVERY = 61.03
CALCULATOR_REGULATORY = 4.10
CALCULATOR_SUBTOTAL = 154.39
CALCULATOR_HST = 20.07
CALCULATOR_REBATE = 36.28
CALCULATOR_TOTAL = 138.18


def _bill_variable_charges(usage: dict[str, float]) -> float:
    """Everything on the bill that scales with consumption, before tax."""
    return sum(
        kwh * volumetric_rate(NT_POWER, NT_POWER[price_key])
        for price_key, kwh in usage.items()
    )


def test_variable_charges_match_the_official_calculator():
    """Delivery and regulatory, less their fixed parts, as the OEB computes them."""
    fixed = SERVICE_CHARGE + SUPPLY_SERVICE_CHARGE
    expected = CALCULATOR_ELECTRICITY + CALCULATOR_DELIVERY + CALCULATOR_REGULATORY

    assert _bill_variable_charges(CALCULATOR_USAGE) == pytest.approx(
        expected - fixed, abs=0.02
    )


def test_total_matches_the_official_calculator():
    subtotal = (
        SERVICE_CHARGE
        + SUPPLY_SERVICE_CHARGE
        + _bill_variable_charges(CALCULATOR_USAGE)
    )

    assert subtotal == pytest.approx(CALCULATOR_SUBTOTAL, abs=0.02)
    assert subtotal * tax_and_rebate_multiplier(NT_POWER) == pytest.approx(
        CALCULATOR_TOTAL, abs=0.02
    )


def test_hst_applies_before_the_rebate_is_taken_off():
    """Both apply to the same subtotal, so they add rather than compound.

    Compounding them, (1 - rebate) x (1 + HST), gives 0.8645 and understates
    every charge by about 3.5%.
    """
    assert tax_and_rebate_multiplier(NT_POWER) == pytest.approx(0.895)

    assert pytest.approx(CALCULATOR_HST, abs=0.01) == CALCULATOR_SUBTOTAL * 0.13
    assert pytest.approx(CALCULATOR_REBATE, abs=0.01) == CALCULATOR_SUBTOTAL * 0.235


def test_other_fixed_charges_are_not_billed():
    """OFC is published but not charged, and including it overstates the bill.

    This is the trap: the field looks like a fixed charge alongside the service
    charge, but the calculator's own total is only reproduced by leaving it out.
    """
    without_ofc = (
        SERVICE_CHARGE
        + SUPPLY_SERVICE_CHARGE
        + _bill_variable_charges(CALCULATOR_USAGE)
    )
    with_ofc = without_ofc + NT_POWER["other_fixed_charges"]

    assert without_ofc == pytest.approx(CALCULATOR_SUBTOTAL, abs=0.02)
    assert with_ofc != pytest.approx(CALCULATOR_SUBTOTAL, abs=0.02)
    assert with_ofc - CALCULATOR_SUBTOTAL == pytest.approx(
        NT_POWER["other_fixed_charges"], abs=0.02
    )


def test_global_adjustment_is_excluded():
    """PBGA and the rate rider apply to customers off the regulated price plan.

    A regulated customer's global adjustment is already inside their price, so
    counting these again would inflate every reading substantially.
    """
    with_global_adjustment = dict(NT_POWER, global_adjustment=0.03904)

    assert volumetric_rate(with_global_adjustment, 0.098) == volumetric_rate(
        NT_POWER, 0.098
    )


@pytest.mark.parametrize(
    "price_key, expected",
    [
        ("time_of_use_off_peak_price", 0.1208),
        ("time_of_use_mid_peak_price", 0.1756),
        ("time_of_use_on_peak_price", 0.2184),
    ],
)
def test_marginal_rate_per_period(price_key, expected):
    """Delivery is flat per kWh, so it weighs far more on a cheap kWh."""
    assert marginal_rate(NT_POWER, NT_POWER[price_key]) == pytest.approx(
        expected, abs=0.0001
    )


def test_marginal_rate_exceeds_the_commodity_rate_most_at_off_peak():
    off_peak = NT_POWER["time_of_use_off_peak_price"]
    on_peak = NT_POWER["time_of_use_on_peak_price"]

    off_peak_uplift = marginal_rate(NT_POWER, off_peak) / off_peak
    on_peak_uplift = marginal_rate(NT_POWER, on_peak) / on_peak

    assert off_peak_uplift > on_peak_uplift
    assert off_peak_uplift == pytest.approx(1.23, abs=0.01)


def test_missing_rate_is_unknown_rather_than_an_error():
    assert marginal_rate(NT_POWER, None) is None


def test_empty_oeb_fields_are_treated_as_zero():
    """Distributors that do not levy a charge ship an empty element."""
    sparse = dict(NT_POWER, distribution_variable_charge="", debt_retirement_charge="")

    assert volumetric_rate(sparse, 0.098) == pytest.approx(
        volumetric_rate(NT_POWER, 0.098) - NT_POWER["distribution_variable_charge"]
    )
