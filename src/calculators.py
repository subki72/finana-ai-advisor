"""Pure, deterministic personal finance calculators for Finana AI Advisor."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

NEEDS_RATIO = 0.50
WANTS_RATIO = 0.30
SAVINGS_RATIO = 0.20

MIN_EMERGENCY_MONTHS = 3
MAX_EMERGENCY_MONTHS = 12
DEPENDENTS_MONTH_STEP = 2
MAX_DEPENDENTS = 20

STABILITY_BASE_MONTHS: dict[str, int] = {
    "stable": 3,
    "variable": 6,
    "freelance": 9,
}

HEALTHY_DSR_PCT = 30.0
STRETCHED_DSR_PCT = 40.0
MONTHS_PER_YEAR = 12
MAX_MORTGAGE_TENURE_YEARS = 40
MAX_ANNUAL_RATE_PCT = 100.0

AffordabilityVerdict = Literal["affordable", "stretched", "unaffordable"]


@dataclass(frozen=True)
class BudgetAllocation:
    """50/30/20 monthly budget breakdown."""

    monthly_income: float
    needs: float
    wants: float
    savings: float
    needs_pct: float = 50.0
    wants_pct: float = 30.0
    savings_pct: float = 20.0


@dataclass(frozen=True)
class EmergencyFundRecommendation:
    """Recommended emergency fund coverage target based on household risk profile."""

    monthly_expenses: float
    dependents: int
    income_stability: str
    recommended_months: int
    minimum_target: float
    recommended_target: float
    rationale: str


@dataclass(frozen=True)
class MortgageAssessment:
    """Mortgage installment and Debt Service Ratio (DSR) affordability assessment."""

    monthly_installment: float
    existing_monthly_debt: float
    total_monthly_debt: float
    dsr_pct: float
    max_recommended_installment: float
    verdict: AffordabilityVerdict
    rationale: str


def _require_finite_number(value: float, field_name: str, *, allow_zero: bool = False) -> float:
    """Validate that an input numeric value is finite and within sign constraints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a numeric value.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be a finite number.")
    if allow_zero and numeric < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    if not allow_zero and numeric <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return numeric


def calculate_budget_50_30_20(monthly_income: float) -> BudgetAllocation:
    """Compute a deterministic 50/30/20 personal budget allocation.

    Args:
        monthly_income: Net monthly take-home income (must be finite and > 0).

    Returns:
        `BudgetAllocation` with needs (50%), wants (30%), and savings (20%).

    Raises:
        ValueError: If `monthly_income` is non-finite or <= 0.
    """
    income = _require_finite_number(monthly_income, "monthly_income", allow_zero=False)
    return BudgetAllocation(
        monthly_income=round(income, 2),
        needs=round(income * NEEDS_RATIO, 2),
        wants=round(income * WANTS_RATIO, 2),
        savings=round(income * SAVINGS_RATIO, 2),
    )


def calculate_emergency_fund(
    monthly_expenses: float,
    dependents: int = 0,
    income_stability: str = "stable",
) -> EmergencyFundRecommendation:
    """Calculate recommended emergency fund buffer between 3 and 12 months.

    Args:
        monthly_expenses: Essential monthly living expenses (must be > 0).
        dependents: Number of financial dependents (0..20).
        income_stability: One of `"stable"`, `"variable"`, or `"freelance"`.

    Returns:
        `EmergencyFundRecommendation` detailing target coverage and rationale.

    Raises:
        ValueError: If any argument is outside accepted domain bounds.
    """
    expenses = _require_finite_number(monthly_expenses, "monthly_expenses", allow_zero=False)
    if isinstance(dependents, bool) or not isinstance(dependents, int):
        raise ValueError("dependents must be an integer.")
    if not (0 <= dependents <= MAX_DEPENDENTS):
        raise ValueError(f"dependents must be between 0 and {MAX_DEPENDENTS}.")

    normalized_stability = income_stability.strip().lower() if isinstance(income_stability, str) else ""
    if normalized_stability not in STABILITY_BASE_MONTHS:
        valid = sorted(STABILITY_BASE_MONTHS)
        raise ValueError(f"income_stability must be one of {valid}.")

    base_months = STABILITY_BASE_MONTHS[normalized_stability]
    raw_months = base_months + (dependents * DEPENDENTS_MONTH_STEP)
    recommended_months = min(MAX_EMERGENCY_MONTHS, max(MIN_EMERGENCY_MONTHS, raw_months))

    minimum_target = round(expenses * MIN_EMERGENCY_MONTHS, 2)
    recommended_target = round(expenses * recommended_months, 2)
    rationale = (
        f"Based on {normalized_stability} income (base {base_months} months) and "
        f"{dependents} dependent(s), a {recommended_months}-month reserve is recommended "
        f"(capped at {MAX_EMERGENCY_MONTHS} months)."
    )
    return EmergencyFundRecommendation(
        monthly_expenses=round(expenses, 2),
        dependents=dependents,
        income_stability=normalized_stability,
        recommended_months=recommended_months,
        minimum_target=minimum_target,
        recommended_target=recommended_target,
        rationale=rationale,
    )


def _validate_mortgage_inputs(
    monthly_income: float,
    existing_monthly_debt: float,
    principal: float,
    annual_rate_pct: float,
    tenure_years: int,
) -> tuple[float, float, float, float, int]:
    """Validate and normalize numeric inputs for mortgage affordability analysis."""
    income = _require_finite_number(monthly_income, "monthly_income", allow_zero=False)
    existing_debt = _require_finite_number(existing_monthly_debt, "existing_monthly_debt", allow_zero=True)
    loan_principal = _require_finite_number(principal, "principal", allow_zero=False)
    rate_pct = _require_finite_number(annual_rate_pct, "annual_rate_pct", allow_zero=True)
    if rate_pct > MAX_ANNUAL_RATE_PCT:
        raise ValueError(f"annual_rate_pct must be <= {MAX_ANNUAL_RATE_PCT}.")
    if isinstance(tenure_years, bool) or not isinstance(tenure_years, int):
        raise ValueError("tenure_years must be an integer.")
    if not (1 <= tenure_years <= MAX_MORTGAGE_TENURE_YEARS):
        raise ValueError(f"tenure_years must be between 1 and {MAX_MORTGAGE_TENURE_YEARS}.")
    return income, existing_debt, loan_principal, rate_pct, tenure_years


def _compute_annuity_installment(principal: float, annual_rate_pct: float, tenure_years: int) -> float:
    """Compute monthly mortgage installment using fixed-rate annuity math."""
    total_months = tenure_years * MONTHS_PER_YEAR
    if annual_rate_pct == 0.0:
        return principal / total_months
    monthly_rate = (annual_rate_pct / 100.0) / MONTHS_PER_YEAR
    compound_factor = (1.0 + monthly_rate) ** total_months
    return principal * (monthly_rate * compound_factor) / (compound_factor - 1.0)


def assess_mortgage_affordability(
    monthly_income: float,
    existing_monthly_debt: float,
    principal: float,
    annual_rate_pct: float,
    tenure_years: int,
) -> MortgageAssessment:
    """Evaluate mortgage monthly installment and Debt Service Ratio (DSR).

    Uses the standard fixed-rate annuity formula and evaluates combined debt
    service against conservative 30% (healthy) and 40% (stress) income ceilings.

    Args:
        monthly_income: Net monthly income (> 0).
        existing_monthly_debt: Sum of existing monthly debt installments (>= 0).
        principal: Financed mortgage principal (> 0).
        annual_rate_pct: Annual interest rate percentage in [0, 100].
        tenure_years: Loan term in years (1..40).

    Returns:
        `MortgageAssessment` containing installment, DSR %, verdict, and rationale.

    Raises:
        ValueError: If inputs fail domain validation.
    """
    income, existing_debt, loan_principal, rate_pct, years = _validate_mortgage_inputs(
        monthly_income, existing_monthly_debt, principal, annual_rate_pct, tenure_years
    )
    installment = _compute_annuity_installment(loan_principal, rate_pct, years)
    total_debt = existing_debt + installment
    dsr_pct = (total_debt / income) * 100.0
    max_installment = max(0.0, (income * (HEALTHY_DSR_PCT / 100.0)) - existing_debt)
    verdict, rationale = _classify_dsr(dsr_pct, max_installment)

    return MortgageAssessment(
        monthly_installment=round(installment, 2),
        existing_monthly_debt=round(existing_debt, 2),
        total_monthly_debt=round(total_debt, 2),
        dsr_pct=round(dsr_pct, 2),
        max_recommended_installment=round(max_installment, 2),
        verdict=verdict,
        rationale=rationale,
    )


def _classify_dsr(dsr_pct: float, max_recommended_installment: float) -> tuple[AffordabilityVerdict, str]:
    """Classify DSR percentage into a clear affordability verdict and rationale."""
    if dsr_pct <= HEALTHY_DSR_PCT:
        return (
            "affordable",
            f"Combined DSR of {dsr_pct:.2f}% stays within the {HEALTHY_DSR_PCT:.0f}% healthy ceiling.",
        )
    if dsr_pct <= STRETCHED_DSR_PCT:
        return (
            "stretched",
            (
                f"Combined DSR of {dsr_pct:.2f}% exceeds the {HEALTHY_DSR_PCT:.0f}% healthy target; "
                f"recommended installment ceiling is {max_recommended_installment:.2f} per month."
            ),
        )
    return (
        "unaffordable",
        (
            f"Combined DSR of {dsr_pct:.2f}% breaches the {STRETCHED_DSR_PCT:.0f}% stress limit; "
            f"reduce principal or tenure so installment stays under {max_recommended_installment:.2f}."
        ),
    )
