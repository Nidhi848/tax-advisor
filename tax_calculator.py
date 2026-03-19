"""2025 US Federal Income Tax Calculator."""

from typing import Optional

# 2025 IRS tax brackets: list of (upper_bound, rate) tuples.
# Each bracket applies to income from the previous upper_bound up to this one.
TAX_BRACKETS = {
    "single": [
        (11_925,        0.10),
        (48_475,        0.12),
        (103_350,       0.22),
        (197_300,       0.24),
        (250_525,       0.32),
        (626_350,       0.35),
        (float("inf"), 0.37),
    ],
    "married_jointly": [
        (23_850,        0.10),
        (96_950,        0.12),
        (206_700,       0.22),
        (394_600,       0.24),
        (501_050,       0.32),
        (751_600,       0.35),
        (float("inf"), 0.37),
    ],
    "head_of_household": [
        (17_000,        0.10),
        (64_850,        0.12),
        (103_350,       0.22),
        (197_300,       0.24),
        (250_500,       0.32),
        (626_350,       0.35),
        (float("inf"), 0.37),
    ],
}

# 2025 standard deductions
STANDARD_DEDUCTIONS = {
    "single":            15_000,
    "married_jointly":   30_000,
    "head_of_household": 22_500,
}

VALID_STATUSES = list(STANDARD_DEDUCTIONS.keys())


def _validate_status(filing_status: str) -> str:
    s = filing_status.lower()
    if s not in VALID_STATUSES:
        raise ValueError(
            f"Invalid filing status '{filing_status}'. "
            f"Must be one of: {VALID_STATUSES}"
        )
    return s


def get_standard_deduction(filing_status: str) -> int:
    """Return the 2025 standard deduction for the given filing status."""
    return STANDARD_DEDUCTIONS[_validate_status(filing_status)]


def get_tax_brackets(filing_status: str) -> list[dict]:
    """Return the 2025 federal income tax brackets for the given filing status."""
    brackets = TAX_BRACKETS[_validate_status(filing_status)]
    result = []
    lower = 0
    for upper, rate in brackets:
        result.append({
            "from": lower,
            "to": upper if upper != float("inf") else None,
            "rate_pct": f"{rate * 100:.0f}%",
        })
        lower = upper
    return result


def calculate_federal_tax(
    gross_income: float,
    filing_status: str,
    deductions: Optional[float] = None,
) -> dict:
    """
    Calculate estimated 2025 federal income tax.

    Steps:
      1. Subtract deduction from gross income → taxable income.
         Uses `deductions` if provided, else standard deduction.
      2. Apply progressive brackets to taxable income.

    Returns a dict with gross_income, deduction, taxable_income,
    tax_owed, effective_tax_rate, marginal_tax_rate, and bracket_breakdown.
    """
    status = _validate_status(filing_status)
    standard_deduction = STANDARD_DEDUCTIONS[status]
    deduction = deductions if deductions is not None else standard_deduction
    taxable_income = max(0.0, gross_income - deduction)

    brackets = TAX_BRACKETS[status]
    tax_owed = 0.0
    breakdown = []
    remaining = taxable_income
    lower = 0

    for upper, rate in brackets:
        if remaining <= 0:
            break
        income_in_bracket = min(remaining, upper - lower)
        tax_in_bracket = income_in_bracket * rate
        tax_owed += tax_in_bracket

        if income_in_bracket > 0:
            breakdown.append({
                "bracket_from": lower,
                "bracket_to": upper if upper != float("inf") else None,
                "rate": f"{rate * 100:.0f}%",
                "income_taxed": round(income_in_bracket, 2),
                "tax": round(tax_in_bracket, 2),
            })

        remaining -= income_in_bracket
        lower = upper

    effective_rate = (tax_owed / gross_income * 100) if gross_income > 0 else 0.0
    marginal_rate = breakdown[-1]["rate"] if breakdown else "0%"

    return {
        "gross_income": gross_income,
        "filing_status": status,
        "deduction": round(deduction, 2),
        "standard_deduction": standard_deduction,
        "taxable_income": round(taxable_income, 2),
        "tax_owed": round(tax_owed, 2),
        "effective_tax_rate": f"{effective_rate:.2f}%",
        "marginal_tax_rate": marginal_rate,
        "bracket_breakdown": breakdown,
    }
