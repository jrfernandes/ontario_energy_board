"""Ontario electricity bill arithmetic.

Pure functions, free of Home Assistant imports, so the arithmetic can be tested
directly. Verified line by line against the Ontario Energy Board's own bill
calculator at oeb.ca/_html/calculator/billcalc.php; `tests/test_billing.py`
pins that comparison.

An Ontario electricity bill is:

    electricity = sum of kWh in each period at that period's price
    delivery    = service charge
                + line losses on the cost of power
                + a rate rider per kWh
                + transmission on loss-adjusted kWh
    regulatory  = wholesale market service and rural rate protection on
                  loss-adjusted kWh, plus the standard supply service charge
    total       = (electricity + delivery + regulatory) x (1 + HST - rebate)

Two details are easy to get wrong, and both were caught by comparing against
the calculator rather than by reading the feed:

- HST applies to the subtotal *before* the Ontario Electricity Rebate is taken
  off, and the rebate applies to that same subtotal. They do not compound, so
  a variable charge is multiplied by (1 + HST - rebate), not by
  (1 - rebate) x (1 + HST).
- The "other fixed charges" field is not billed. Including it overstates
  delivery by exactly that amount.

The global adjustment fields are deliberately unused. PBGA and GA_RR_NONRPP
apply to customers who are not on the regulated price plan, whose name they
carry; for the Time-of-Use and Ultra-Low Overnight customers this integration
serves, the global adjustment is already inside the regulated price.
"""

from collections.abc import Mapping
from typing import Any


def _number(company_data: Mapping[str, Any], key: str, default: float) -> float:
    """Read a rate, treating an absent or empty OEB field as its default.

    Distributors that do not levy a charge ship an empty element for it.
    """
    value = company_data.get(key)

    return float(value) if isinstance(value, (int, float)) else default


def volumetric_rate(company_data: Mapping[str, Any], commodity_rate: float) -> float:
    """Everything charged per kWh at a given commodity price, before tax.

    Excludes the service charge and the standard supply service charge, which
    are billed per month and so cannot be expressed per kWh without knowing
    how much was used.
    """
    loss_factor = _number(company_data, "loss_factor", 1.0)

    per_kwh_on_loss_adjusted = (
        _number(company_data, "retail_transmission_network_rate", 0.0)
        + _number(company_data, "retail_transmission_connection_rate", 0.0)
        + _number(company_data, "wholesale_market_service_charge", 0.0)
        + _number(company_data, "rural_remote_rate_protection", 0.0)
    )

    return (
        commodity_rate * loss_factor
        + _number(company_data, "distribution_variable_charge", 0.0)
        + _number(company_data, "debt_retirement_charge", 0.0)
        + loss_factor * per_kwh_on_loss_adjusted
    )


def tax_and_rebate_multiplier(company_data: Mapping[str, Any]) -> float:
    """What a pre-tax charge is multiplied by to reach the amount billed.

    HST and the Ontario Electricity Rebate both apply to the same subtotal, so
    they add rather than compound.
    """
    return (
        1.0
        + _number(company_data, "harmonized_sales_tax", 0.0)
        - _number(company_data, "ontario_electricity_rebate", 0.0)
    )


def marginal_rate(
    company_data: Mapping[str, Any], commodity_rate: float | None
) -> float | None:
    """The all-in cost of one more kWh, tax and rebate included.

    This is the marginal rate, not the bill divided by consumption: the fixed
    monthly charges are excluded because they do not vary with use.
    """
    if commodity_rate is None:
        return None

    return volumetric_rate(company_data, commodity_rate) * tax_and_rebate_multiplier(
        company_data
    )
