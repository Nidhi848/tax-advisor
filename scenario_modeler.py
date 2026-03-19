"""
Tax scenario modelers for Phase 4: STR, Cost Segregation, Capital Gains Harvesting, 401k/IRA.
All modelers accept parameters directly or fall back to user profile.
Return: inputs_used, calculation_steps, tax_impact, summary (plain English).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from tax_calculator import calculate_federal_tax
from user_profile import load_profile

# ---------------------------------------------------------------------------
# Constants (2024 where specified by requirements)
# ---------------------------------------------------------------------------

RESIDENTIAL_DEPRECIATION_YEARS = 27.5
STR_AVG_STAY_DAYS_THRESHOLD = 7
STR_MATERIAL_PARTICIPATION_HOURS = 750
MAGI_PASSIVE_LOSS_PHASEOUT = 150_000
BONUS_DEPRECIATION_PCT_2024 = 0.60

# 2024 LTCG brackets (taxable income thresholds)
LTCG_0_PCT_LIMIT = {
    "single": 44_625,
    "married_jointly": 89_250,
    "head_of_household": 59_750,
}
LTCG_20_PCT_THRESHOLD = {
    "single": 492_300,
    "married_jointly": 553_850,
    "head_of_household": 523_050,
}
ANNUAL_LOSS_OFFSET_LIMIT = 3_000

# 2024 401k / IRA
LIMIT_401K_2024 = 23_000
CATCH_UP_401K_2024 = 7_500
ROTH_PHASEOUT_SINGLE_2024 = (146_000, 161_000)
ROTH_PHASEOUT_MARRIED_2024 = (230_000, 240_000)
SEP_IRA_MAX_2024 = 69_000
SEP_IRA_PCT = 0.25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_or(
    key: str,
    override: Optional[float],
    default: Optional[float] = None,
) -> Optional[float]:
    p = load_profile()
    if override is not None:
        return float(override)
    v = p.get(key)
    if v is not None:
        return float(v)
    return default


def _profile_str(key: str, override: Optional[str]) -> Optional[str]:
    if override:
        return override
    return load_profile().get(key)


def _marginal_rate_pct(filing_status: str, taxable_income: float) -> float:
    """Return marginal rate as decimal (e.g. 0.22)."""
    calc = calculate_federal_tax(
        taxable_income + 100,
        filing_status,
        None,
    )
    calc_base = calculate_federal_tax(taxable_income, filing_status, None)
    extra_tax = calc["tax_owed"] - calc_base["tax_owed"]
    return extra_tax / 100.0


# ---------------------------------------------------------------------------
# 1. STR Modeler
# ---------------------------------------------------------------------------

STR_DISCLAIMER = (
    "STR loophole eligibility requires professional verification — "
    "material participation rules are strictly enforced by the IRS."
)


def model_str(
    property_purchase_price: Optional[float] = None,
    gross_rental_income: Optional[float] = None,
    w2_income: Optional[float] = None,
    average_stay_days: Optional[float] = None,
    material_participation_hours: Optional[float] = None,
    annual_expenses: Optional[float] = None,
    filing_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    STR (short-term rental) modeler: depreciation, net rental income/loss,
    STR loophole eligibility (avg stay < 7 days AND 750+ hours), passive loss rules, MAGI phaseout.
    """
    profile = load_profile()
    price = _profile_or("property_purchase_price", property_purchase_price) or 0.0
    gross_rental = _profile_or("gross_rental_income", gross_rental_income) or 0.0
    w2 = _profile_or("annual_income", w2_income)
    if w2 is None and profile.get("w2_data"):
        box1 = profile["w2_data"].get("box_1_wages")
        w2 = float(box1) if box1 is not None else None
    w2 = w2 or 0.0
    avg_stay = average_stay_days if average_stay_days is not None else 5.0  # assume STR
    hours = material_participation_hours if material_participation_hours is not None else 800.0
    expenses = annual_expenses if annual_expenses is not None else 0.0
    status = _profile_str("filing_status", filing_status) or "single"

    # Land typically 20%; building depreciable
    land_pct = 0.20
    building_value = price * (1 - land_pct)
    annual_depreciation = building_value / RESIDENTIAL_DEPRECIATION_YEARS
    net_rental_before_depreciation = gross_rental - expenses
    net_rental_income = net_rental_before_depreciation - annual_depreciation

    qualifies_avg_stay = avg_stay < STR_AVG_STAY_DAYS_THRESHOLD
    qualifies_material = hours >= STR_MATERIAL_PARTICIPATION_HOURS
    str_loophole_qualified = qualifies_avg_stay and qualifies_material
    magi = w2 + max(0, net_rental_before_depreciation)
    magi_exceeds_phaseout = magi > MAGI_PASSIVE_LOSS_PHASEOUT

    # Passive loss: cannot offset W-2 if not qualified or MAGI phaseout
    losses_passive = not str_loophole_qualified or magi_exceeds_phaseout
    rental_loss = -min(0, net_rental_income)
    rental_loss_offset_w2 = 0.0
    tax_savings = 0.0
    if str_loophole_qualified and not magi_exceeds_phaseout and net_rental_income < 0:
        rental_loss_offset_w2 = min(rental_loss, w2)
        marginal = _marginal_rate_pct(status, w2 + net_rental_income)
        tax_savings = rental_loss_offset_w2 * marginal

    steps = [
        {"step": "Building value (80% of purchase)", "value": round(building_value, 2)},
        {"step": "Annual depreciation (27.5-year schedule)", "value": round(annual_depreciation, 2)},
        {"step": "Net rental before depreciation", "value": round(net_rental_before_depreciation, 2)},
        {"step": "Net rental income (after depreciation)", "value": round(net_rental_income, 2)},
        {"step": "Average stay < 7 days?", "value": qualifies_avg_stay},
        {"step": "Material participation ≥ 750 hrs?", "value": qualifies_material},
        {"step": "STR loophole qualified?", "value": str_loophole_qualified},
        {"step": "MAGI exceeds $150k (phaseout)?", "value": magi_exceeds_phaseout},
        {"step": "Rental losses treated as passive?", "value": losses_passive},
        {"step": "Rental loss offsetting W-2 (if qualified)", "value": round(rental_loss_offset_w2, 2)},
        {"step": "Estimated tax savings from offset", "value": round(tax_savings, 2)},
    ]

    if net_rental_income < 0 and losses_passive:
        summary = (
            f"Rental shows a loss of ${abs(net_rental_income):,.0f}, but losses are passive "
            "(cannot offset W-2) because STR loophole criteria are not met or MAGI exceeds $150k."
        )
    elif str_loophole_qualified and tax_savings > 0:
        summary = (
            f"You may qualify for the STR loophole. Rental loss of ${rental_loss:,.0f} could offset "
            f"W-2 income; estimated tax savings: ${tax_savings:,.0f}. {STR_DISCLAIMER}"
        )
    else:
        summary = (
            f"Net rental income: ${net_rental_income:,.0f}. "
            f"STR loophole qualified: {str_loophole_qualified}. {STR_DISCLAIMER}"
        )

    gross_for_compare = w2 + gross_rental
    taxable_for_compare = max(0, w2 + net_rental_income)
    calc_compare = calculate_federal_tax(w2 + net_rental_income, status, None)
    from tax_calculator import get_standard_deduction
    std_ded = get_standard_deduction(status)

    return {
        "inputs_used": {
            "property_purchase_price": price,
            "gross_rental_income": gross_rental,
            "w2_income": w2,
            "average_stay_days": avg_stay,
            "material_participation_hours": hours,
            "annual_expenses": expenses,
            "filing_status": status,
        },
        "calculation_steps": steps,
        "tax_impact": {
            "annual_depreciation": round(annual_depreciation, 2),
            "net_rental_income": round(net_rental_income, 2),
            "str_loophole_qualified": str_loophole_qualified,
            "losses_passive": losses_passive,
            "magi_exceeds_150k": magi_exceeds_phaseout,
            "rental_loss_offsetting_w2": round(rental_loss_offset_w2, 2),
            "estimated_tax_savings": round(tax_savings, 2),
            "gross_income": round(gross_for_compare, 2),
            "total_deductions": round(std_ded, 2),
            "taxable_income": round(taxable_for_compare, 2),
            "estimated_tax": round(calc_compare["tax_owed"], 2),
        },
        "summary": summary,
        "disclaimer": STR_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# 2. Cost Segregation Modeler
# ---------------------------------------------------------------------------

COST_SEG_DISCLAIMER = (
    "Cost segregation estimates require a professional engineer study for IRS compliance."
)


def model_cost_segregation(
    property_value: Optional[float] = None,
    land_value: Optional[float] = None,
    marginal_tax_rate_pct: Optional[float] = None,
    filing_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cost segregation: reclassify 20-30% to 5-year, 10-15% to 7-year, 5-10% to 15-year.
    Apply 60% bonus depreciation (2024) to accelerated components.
    """
    profile = load_profile()
    total_value = _profile_or("property_value", property_value) or 0.0
    land = _profile_or("land_value", land_value)
    if land is None:
        land = total_value * 0.20
    building_value = max(0, total_value - land)
    status = _profile_str("filing_status", filing_status) or "single"
    income = profile.get("annual_income")
    if income is None and profile.get("w2_data"):
        income = profile["w2_data"].get("box_1_wages")
    income = float(income) if income is not None else 0.0

    # Estimate reclassification (midpoints: 25% 5-yr, 12.5% 7-yr, 7.5% 15-yr)
    pct_5yr = 0.25
    pct_7yr = 0.125
    pct_15yr = 0.075
    value_5 = building_value * pct_5yr
    value_7 = building_value * pct_7yr
    value_15 = building_value * pct_15yr
    remaining_straight = building_value * (1 - pct_5yr - pct_7yr - pct_15yr)
    standard_annual_sl = building_value / RESIDENTIAL_DEPRECIATION_YEARS

    # Year 1: bonus 60% on accelerated portions
    bonus_5 = value_5 * BONUS_DEPRECIATION_PCT_2024
    bonus_7 = value_7 * BONUS_DEPRECIATION_PCT_2024
    bonus_15 = value_15 * BONUS_DEPRECIATION_PCT_2024
    remaining_5 = value_5 - bonus_5
    remaining_7 = value_7 - bonus_7
    remaining_15 = value_15 - bonus_15
    # First-year straight-line on remaining (simplified: 1/5, 1/7, 1/15 of remainder)
    yr1_5 = bonus_5 + remaining_5 / 5
    yr1_7 = bonus_7 + remaining_7 / 7
    yr1_15 = bonus_15 + remaining_15 / 15
    yr1_remaining_sl = remaining_straight / RESIDENTIAL_DEPRECIATION_YEARS
    year1_total_depreciation = yr1_5 + yr1_7 + yr1_15 + yr1_remaining_sl

    additional_yr1_deduction = year1_total_depreciation - standard_annual_sl
    if marginal_tax_rate_pct is not None:
        rate = marginal_tax_rate_pct / 100.0
    else:
        rate = _marginal_rate_pct(status, income)
    tax_savings_yr1 = additional_yr1_deduction * rate

    steps = [
        {"step": "Building value (total - land)", "value": round(building_value, 2)},
        {"step": "Reclassified to 5-year property (25%)", "value": round(value_5, 2)},
        {"step": "Reclassified to 7-year property (12.5%)", "value": round(value_7, 2)},
        {"step": "Reclassified to 15-year property (7.5%)", "value": round(value_15, 2)},
        {"step": "Year 1 depreciation (cost seg)", "value": round(year1_total_depreciation, 2)},
        {"step": "Year 1 standard straight-line", "value": round(standard_annual_sl, 2)},
        {"step": "Additional Year 1 deduction", "value": round(additional_yr1_deduction, 2)},
        {"step": "Marginal rate used", "value": f"{rate*100:.0f}%"},
        {"step": "Estimated Year 1 tax savings", "value": round(tax_savings_yr1, 2)},
    ]

    summary = (
        f"Cost segregation could front-load ${additional_yr1_deduction:,.0f} in Year 1 deductions "
        f"vs standard depreciation, with estimated tax savings of ${tax_savings_yr1:,.0f}. "
        f"{COST_SEG_DISCLAIMER}"
    )

    # Comparison row: same income as baseline but extra deduction from cost seg
    income = profile.get("annual_income") or 0
    from tax_calculator import get_standard_deduction
    std_ded = get_standard_deduction(status)
    taxable_with_extra = max(0, income - std_ded - additional_yr1_deduction)
    calc_baseline = calculate_federal_tax(income, status, None)
    tax_with_seg = max(0, calc_baseline["tax_owed"] - tax_savings_yr1)

    return {
        "inputs_used": {
            "property_value": total_value,
            "land_value": land,
            "building_value": building_value,
            "filing_status": status,
        },
        "calculation_steps": steps,
        "tax_impact": {
            "year1_depreciation_cost_seg": round(year1_total_depreciation, 2),
            "year1_standard_straight_line": round(standard_annual_sl, 2),
            "additional_year1_deduction": round(additional_yr1_deduction, 2),
            "estimated_tax_savings_yr1": round(tax_savings_yr1, 2),
            "gross_income": round(income, 2),
            "total_deductions": round(std_ded + additional_yr1_deduction, 2),
            "taxable_income": round(taxable_with_extra, 2),
            "estimated_tax": round(tax_with_seg, 2),
        },
        "summary": summary,
        "disclaimer": COST_SEG_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# 3. Capital Gains Harvesting Modeler
# ---------------------------------------------------------------------------

def model_capital_gains_harvesting(
    gains: Optional[float] = None,
    losses: Optional[float] = None,
    income: Optional[float] = None,
    filing_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capital gains harvesting: LTCG rate (0/15/20%), net gain/loss, $3k ordinary offset, carryforward.
    """
    profile = load_profile()
    status = _profile_str("filing_status", filing_status) or "single"
    inc = _profile_or("annual_income", income)
    if inc is None and profile.get("w2_data"):
        inc = profile["w2_data"].get("box_1_wages")
        inc = float(inc) if inc is not None else None
    inc = inc or 0.0
    gains_val = (gains if gains is not None else 0.0) or 0.0
    losses_val = (losses if losses is not None else 0.0) or 0.0

    # Taxable income from profile (simplified: income - standard deduction)
    from tax_calculator import get_standard_deduction
    std_ded = get_standard_deduction(status)
    taxable_base = max(0, inc - std_ded)

    limit_0 = LTCG_0_PCT_LIMIT.get(status, LTCG_0_PCT_LIMIT["single"])
    limit_20 = LTCG_20_PCT_THRESHOLD.get(status, LTCG_20_PCT_THRESHOLD["single"])

    net_cg = gains_val - losses_val
    rate_pct = 0
    tax_on_gains = 0.0
    carryforward = 0.0
    ordinary_offset_used = 0.0
    if net_cg >= 0:
        # Net gain: taxable
        taxable_with_cg = taxable_base + net_cg
        if taxable_with_cg <= limit_0:
            rate_pct = 0
        elif taxable_with_cg <= limit_20:
            rate_pct = 15
        else:
            rate_pct = 20
        tax_on_gains = net_cg * (rate_pct / 100.0)
    else:
        # Net loss
        ordinary_offset_used = min(abs(net_cg), ANNUAL_LOSS_OFFSET_LIMIT)
        carryforward = abs(net_cg) - ordinary_offset_used

    # Near bracket threshold?
    taxable_for_threshold = taxable_base + net_cg
    near_0_to_15 = limit_0 - 5000 <= taxable_for_threshold <= limit_0 + 5000
    near_15_to_20 = limit_20 - 5000 <= taxable_for_threshold <= limit_20 + 5000

    steps = [
        {"step": "Taxable income (before gains/losses)", "value": round(taxable_base, 2)},
        {"step": "Long-term gains", "value": round(gains_val, 2)},
        {"step": "Long-term losses", "value": round(losses_val, 2)},
        {"step": "Net LTCG / (loss)", "value": round(net_cg, 2)},
        {"step": "Applicable LTCG rate", "value": f"{rate_pct}%" if net_cg >= 0 else "N/A"},
        {"step": "Tax on net gain", "value": round(tax_on_gains, 2)},
        {"step": "Ordinary income offset (max $3,000)", "value": round(ordinary_offset_used, 2)},
        {"step": "Loss carryforward", "value": round(carryforward, 2)},
        {"step": "Near 0%/15% bracket?", "value": near_0_to_15},
        {"step": "Near 15%/20% bracket?", "value": near_15_to_20},
    ]

    if net_cg >= 0:
        summary = (
            f"Net LTCG ${net_cg:,.0f} taxed at {rate_pct}%; estimated tax ${tax_on_gains:,.0f}. "
            + ("You are near a bracket threshold; harvesting could push you into a higher rate." if (near_0_to_15 or near_15_to_20) else "")
        )
    else:
        summary = (
            f"Net loss ${abs(net_cg):,.0f}. Up to $3,000 offsets ordinary income; "
            f"carryforward: ${carryforward:,.0f}."
        )

    from tax_calculator import get_standard_deduction
    std_ded = get_standard_deduction(status)
    taxable_with_cg = max(0, taxable_base + net_cg)
    # Tax = f(gross) where gross - std_ded = taxable_with_cg
    gross_for_tax = taxable_with_cg + std_ded
    calc_cg = calculate_federal_tax(gross_for_tax, status, None)
    tax_owed_scenario = calc_cg["tax_owed"]

    return {
        "inputs_used": {
            "gains": gains_val,
            "losses": losses_val,
            "income": inc,
            "filing_status": status,
        },
        "calculation_steps": steps,
        "tax_impact": {
            "net_capital_gain_loss": round(net_cg, 2),
            "ltcg_rate_pct": rate_pct if net_cg >= 0 else None,
            "tax_on_net_gain": round(tax_on_gains, 2),
            "ordinary_income_offset_used": round(ordinary_offset_used, 2),
            "carryforward": round(carryforward, 2),
            "near_bracket_threshold": near_0_to_15 or near_15_to_20,
            "gross_income": round(inc, 2),
            "total_deductions": round(std_ded, 2),
            "taxable_income": round(taxable_with_cg, 2),
            "estimated_tax": round(tax_owed_scenario, 2),
        },
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# 4. 401k / IRA Optimizer
# ---------------------------------------------------------------------------

def model_401k_ira(
    income: Optional[float] = None,
    filing_status: Optional[str] = None,
    age: Optional[int] = None,
    self_employment_income: Optional[float] = None,
) -> Dict[str, Any]:
    """
    401k: tax savings at $5k, $10k, $23k, catch-up if 50+.
    Roth: MAGI limits (single $146k–$161k, married $230k–$240k 2024); backdoor if over.
    SEP-IRA if self-employment: 25% of net SE income, max $69k 2024.
    """
    profile = load_profile()
    inc = _profile_or("annual_income", income)
    if inc is None and profile.get("w2_data"):
        inc = profile["w2_data"].get("box_1_wages")
        inc = float(inc) if inc is not None else None
    inc = inc or 0.0
    status = _profile_str("filing_status", filing_status) or "single"
    age_val = age if age is not None else profile.get("age")
    if age_val is not None:
        age_val = int(age_val)
    se_income = _profile_or("self_employment_income", self_employment_income) or 0.0

    from tax_calculator import get_standard_deduction
    std_ded = get_standard_deduction(status)
    taxable_before = max(0, inc - std_ded)
    marginal_rate = _marginal_rate_pct(status, taxable_before)

    contribution_levels = [5_000, 10_000, LIMIT_401K_2024]
    if age_val is not None and age_val >= 50:
        contribution_levels.append(LIMIT_401K_2024 + CATCH_UP_401K_2024)

    savings_at_levels = []
    for contrib in contribution_levels:
        if contrib > inc:
            continue
        new_taxable = max(0, taxable_before - contrib)
        tax_before = taxable_before * marginal_rate  # simplified
        tax_after = new_taxable * _marginal_rate_pct(status, new_taxable)
        # More accurate: full recalc
        calc_before = calculate_federal_tax(inc, status, std_ded)
        calc_after = calculate_federal_tax(inc - contrib, status, std_ded)
        savings = calc_before["tax_owed"] - calc_after["tax_owed"]
        savings_at_levels.append({"contribution": contrib, "tax_savings": round(savings, 2)})

    # Roth eligibility (MAGI ≈ income for simplicity)
    if status == "single":
        low, high = ROTH_PHASEOUT_SINGLE_2024
    else:
        low, high = ROTH_PHASEOUT_MARRIED_2024
    if inc < low:
        roth_eligible = True
        roth_note = "You qualify for direct Roth IRA contribution."
    elif inc <= high:
        roth_eligible = "phaseout"
        roth_note = f"MAGI in phaseout range (${low:,}-${high:,}); reduced contribution limit."
    else:
        roth_eligible = False
        roth_note = "Over MAGI limit for direct Roth; consider backdoor Roth IRA."

    sep_limit = 0.0
    if se_income > 0:
        sep_limit = min(se_income * SEP_IRA_PCT, SEP_IRA_MAX_2024)

    # Comparison row: assume max 401k contribution
    max_contrib = LIMIT_401K_2024 + (CATCH_UP_401K_2024 if (age_val and age_val >= 50) else 0)
    max_contrib = min(max_contrib, inc)
    calc_after = calculate_federal_tax(inc - max_contrib, status, None) if max_contrib > 0 else calculate_federal_tax(inc, status, None)

    steps = [
        {"step": "Current taxable income (approx)", "value": round(taxable_before, 2)},
        {"step": "Marginal rate", "value": f"{marginal_rate*100:.0f}%"},
        {"step": "Tax savings by 401k contribution", "value": savings_at_levels},
        {"step": "Roth IRA direct contribution", "value": roth_note},
        {"step": "SEP-IRA limit (if self-employed)", "value": round(sep_limit, 2) if se_income else "N/A"},
    ]

    summary = (
        f"401k contributions reduce AGI; at $23,000 you'd save approximately "
        f"${next((s['tax_savings'] for s in savings_at_levels if s['contribution'] == LIMIT_401K_2024), 0):,.0f} in federal tax. "
        f"{roth_note}"
        + (f" SEP-IRA limit: ${sep_limit:,.0f}." if sep_limit > 0 else "")
    )

    return {
        "inputs_used": {
            "income": inc,
            "filing_status": status,
            "age": age_val,
            "self_employment_income": se_income,
        },
        "calculation_steps": steps,
        "tax_impact": {
            "marginal_rate_pct": round(marginal_rate * 100, 1),
            "savings_by_contribution": savings_at_levels,
            "roth_eligible": roth_eligible,
            "roth_note": roth_note,
            "sep_ira_limit": round(sep_limit, 2) if se_income else None,
            "gross_income": round(inc, 2),
            "total_deductions": round(std_ded + max_contrib, 2),
            "taxable_income": round(calc_after["taxable_income"], 2),
            "estimated_tax": round(calc_after["tax_owed"], 2),
        },
        "summary": summary,
    }
