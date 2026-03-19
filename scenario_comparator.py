"""
Compare multiple tax scenarios and return a unified table vs baseline (current situation).
"""

from __future__ import annotations

from typing import Any, Dict, List

from tax_calculator import calculate_federal_tax, get_standard_deduction
from user_profile import load_profile
from scenario_modeler import (
    model_str,
    model_cost_segregation,
    model_capital_gains_harvesting,
    model_401k_ira,
)


def _baseline_row() -> Dict[str, Any]:
    """Current situation: profile income, standard deduction, no scenario changes."""
    profile = load_profile()
    status = (profile.get("filing_status") or "single").lower()
    income = profile.get("annual_income")
    if income is None and profile.get("w2_data"):
        income = profile["w2_data"].get("box_1_wages")
    income = float(income) if income is not None else 0.0
    std_ded = get_standard_deduction(status)
    calc = calculate_federal_tax(income, status, None)
    taxable = calc["taxable_income"]
    tax = calc["tax_owed"]
    effective = float(calc["effective_tax_rate"].rstrip("%")) if calc.get("effective_tax_rate") else 0.0
    net_take_home = income - tax
    return {
        "scenario_name": "Baseline: current situation",
        "gross_income": round(income, 2),
        "total_deductions": round(calc["deduction"], 2),
        "taxable_income": round(taxable, 2),
        "estimated_tax": round(tax, 2),
        "effective_rate_pct": round(effective, 2),
        "net_take_home": round(net_take_home, 2),
        "tax_savings_vs_baseline": 0.0,
    }


def _scenario_to_row(name: str, result: Dict[str, Any], baseline_tax: float) -> Dict[str, Any]:
    """Map a single modeler result to comparison row; baseline_tax for savings delta."""
    ti = result.get("tax_impact") or {}
    inputs = result.get("inputs_used") or {}

    gross = ti.get("gross_income")
    deductions = ti.get("total_deductions")
    taxable = ti.get("taxable_income")
    tax_owed = ti.get("estimated_tax")

    if gross is None:
        gross = inputs.get("w2_income") or inputs.get("income") or 0
    if taxable is None or tax_owed is None or deductions is None:
        status = inputs.get("filing_status") or "single"
        std_ded = get_standard_deduction(status)
        gross_income = float(gross or 0)
        calc = calculate_federal_tax(gross_income, status, None)
        taxable = taxable or calc["taxable_income"]
        tax_owed = tax_owed or calc["tax_owed"]
        deductions = deductions or calc["deduction"]

    gross = float(gross or 0)
    taxable = float(taxable or 0)
    tax_owed = float(tax_owed or 0)
    deductions = float(deductions or 0)
    effective = (tax_owed / gross * 100) if gross > 0 else 0
    net_take_home = gross - tax_owed
    savings = max(0, baseline_tax - tax_owed)

    return {
        "scenario_name": name,
        "gross_income": round(gross, 2),
        "total_deductions": round(deductions, 2),
        "taxable_income": round(taxable, 2),
        "estimated_tax": round(tax_owed, 2),
        "effective_rate_pct": round(effective, 2),
        "net_take_home": round(net_take_home, 2),
        "tax_savings_vs_baseline": round(savings, 2),
    }


def _run_modeler(config: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch to the right modeler and return full result."""
    modeler = (config.get("modeler") or "").strip().lower()
    params = config.get("params") or {}

    if modeler == "str":
        return model_str(
            property_purchase_price=params.get("property_purchase_price"),
            gross_rental_income=params.get("gross_rental_income"),
            w2_income=params.get("w2_income"),
            average_stay_days=params.get("average_stay_days"),
            material_participation_hours=params.get("material_participation_hours"),
            annual_expenses=params.get("annual_expenses"),
            filing_status=params.get("filing_status"),
        )
    if modeler == "cost_seg" or modeler == "cost_segregation":
        return model_cost_segregation(
            property_value=params.get("property_value"),
            land_value=params.get("land_value"),
            marginal_tax_rate_pct=params.get("marginal_tax_rate_pct"),
            filing_status=params.get("filing_status"),
        )
    if modeler == "capital_gains":
        return model_capital_gains_harvesting(
            gains=params.get("gains"),
            losses=params.get("losses"),
            income=params.get("income"),
            filing_status=params.get("filing_status"),
        )
    if modeler == "401k" or modeler == "401k_ira":
        return model_401k_ira(
            income=params.get("income"),
            filing_status=params.get("filing_status"),
            age=params.get("age"),
            self_employment_income=params.get("self_employment_income"),
        )
    return {"error": f"Unknown modeler: {modeler}", "tax_impact": {}, "inputs_used": {}}


def compare_scenarios(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run multiple scenario configs and return a unified comparison table.

    Each scenario in scenarios[] should have: name, modeler (str|cost_seg|capital_gains|401k), params (dict).
    Returns: baseline row + one row per scenario with columns:
      scenario_name, gross_income, total_deductions, taxable_income, estimated_tax,
      effective_rate_pct, net_take_home, tax_savings_vs_baseline
    """
    baseline = _baseline_row()
    baseline_tax = baseline["estimated_tax"]
    rows = [baseline]

    for config in scenarios or []:
        name = config.get("name") or "Unnamed scenario"
        result = _run_modeler(config)
        if result.get("error"):
            rows.append({
                "scenario_name": name,
                "error": result["error"],
                "gross_income": None,
                "total_deductions": None,
                "taxable_income": None,
                "estimated_tax": None,
                "effective_rate_pct": None,
                "net_take_home": None,
                "tax_savings_vs_baseline": None,
            })
            continue
        # Build row from result; for STR/cost seg we need to derive taxable income and tax from scenario
        row = _scenario_to_row(name, result, baseline_tax)
        rows.append(row)

    # Mark best outcome (max net_take_home among valid rows)
    valid_rows = [r for r in rows if r.get("net_take_home") is not None]
    if valid_rows:
        best_net = max(r["net_take_home"] for r in valid_rows)
        for r in rows:
            r["is_best_outcome"] = r.get("net_take_home") == best_net

    return {
        "baseline": baseline,
        "comparison_table": rows,
        "scenarios_run": len(scenarios or []),
    }
