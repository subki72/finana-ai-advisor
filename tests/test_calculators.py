"""Unit tests for deterministic personal finance calculators."""

from __future__ import annotations

import math

import pytest

from src.calculators import (
    assess_mortgage_affordability,
    calculate_budget_50_30_20,
    calculate_emergency_fund,
)


def test_calculate_budget_50_30_20_returns_expected_split() -> None:
    """Verify standard 50/30/20 allocation on a clean monthly income."""
    # Arrange
    monthly_income = 10_000_000.0

    # Act
    result = calculate_budget_50_30_20(monthly_income)

    # Assert
    assert result.monthly_income == 10_000_000.0
    assert result.needs == 5_000_000.0
    assert result.wants == 3_000_000.0
    assert result.savings == 2_000_000.0
    assert result.needs_pct == 50.0
    assert result.wants_pct == 30.0
    assert result.savings_pct == 20.0


def test_calculate_budget_50_30_20_rounds_fractional_amounts() -> None:
    """Verify two-decimal rounding on fractional income amounts."""
    # Arrange & Act
    result = calculate_budget_50_30_20(1234.56)

    # Assert
    assert result.needs == 617.28
    assert result.wants == 370.37
    assert result.savings == 246.91


@pytest.mark.parametrize("bad_income", [0, -5000.0, math.nan, math.inf, True])
def test_calculate_budget_50_30_20_rejects_invalid_income(bad_income: object) -> None:
    """Reject zero, negative, non-finite, or boolean income values."""
    with pytest.raises(ValueError, match="monthly_income"):
        calculate_budget_50_30_20(bad_income)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("stability", "dependents", "expected_months"),
    [
        ("stable", 0, 3),
        ("stable", 1, 5),
        ("variable", 1, 8),
        ("freelance", 0, 9),
        ("freelance", 4, 12),
    ],
)
def test_calculate_emergency_fund_scales_and_caps_between_3_and_12_months(
    stability: str,
    dependents: int,
    expected_months: int,
) -> None:
    """Verify emergency fund coverage scales by stability/dependents and caps at 12."""
    # Arrange
    monthly_expenses = 4_000_000.0

    # Act
    result = calculate_emergency_fund(
        monthly_expenses=monthly_expenses,
        dependents=dependents,
        income_stability=stability,
    )

    # Assert
    assert result.recommended_months == expected_months
    assert result.minimum_target == 12_000_000.0
    assert result.recommended_target == expected_months * 4_000_000.0
    assert str(expected_months) in result.rationale


def test_calculate_emergency_fund_rejects_invalid_inputs() -> None:
    """Reject negative expenses, out-of-range dependents, and unknown stability labels."""
    with pytest.raises(ValueError, match="monthly_expenses"):
        calculate_emergency_fund(0.0)
    with pytest.raises(ValueError, match="dependents"):
        calculate_emergency_fund(2_000_000.0, dependents=-1)
    with pytest.raises(ValueError, match="dependents"):
        calculate_emergency_fund(2_000_000.0, dependents=21)
    with pytest.raises(ValueError, match="income_stability"):
        calculate_emergency_fund(2_000_000.0, income_stability="unknown")


def test_assess_mortgage_affordability_affordable_verdict() -> None:
    """Classify mortgage with <=30% combined DSR as affordable."""
    # Arrange & Act
    result = assess_mortgage_affordability(
        monthly_income=20_000_000.0,
        existing_monthly_debt=500_000.0,
        principal=400_000_000.0,
        annual_rate_pct=6.0,
        tenure_years=15,
    )

    # Assert
    assert result.verdict == "affordable"
    assert result.dsr_pct <= 30.0
    assert result.monthly_installment == pytest.approx(3_375_427.32, rel=1e-4)
    assert result.total_monthly_debt == pytest.approx(3_875_427.32, rel=1e-4)
    assert result.max_recommended_installment == 5_500_000.0


def test_assess_mortgage_affordability_stretched_and_unaffordable_verdicts() -> None:
    """Classify 30-40% DSR as stretched and >40% DSR as unaffordable."""
    # Arrange & Act
    stretched = assess_mortgage_affordability(
        monthly_income=10_000_000.0,
        existing_monthly_debt=1_000_000.0,
        principal=300_000_000.0,
        annual_rate_pct=6.0,
        tenure_years=15,
    )
    unaffordable = assess_mortgage_affordability(
        monthly_income=8_000_000.0,
        existing_monthly_debt=2_000_000.0,
        principal=500_000_000.0,
        annual_rate_pct=8.0,
        tenure_years=15,
    )

    # Assert
    assert stretched.verdict == "stretched"
    assert 30.0 < stretched.dsr_pct <= 40.0
    assert unaffordable.verdict == "unaffordable"
    assert unaffordable.dsr_pct > 40.0


def test_assess_mortgage_affordability_zero_interest_edge_case() -> None:
    """Handle zero percent interest rate without division by zero."""
    # Arrange & Act
    result = assess_mortgage_affordability(
        monthly_income=10_000_000.0,
        existing_monthly_debt=0.0,
        principal=120_000_000.0,
        annual_rate_pct=0.0,
        tenure_years=10,
    )

    # Assert
    assert result.monthly_installment == 1_000_000.0
    assert result.dsr_pct == 10.0
    assert result.verdict == "affordable"


def test_assess_mortgage_affordability_rejects_invalid_bounds() -> None:
    """Reject out-of-range tenure, rate, negative debt, and non-positive principal."""
    with pytest.raises(ValueError, match="tenure_years"):
        assess_mortgage_affordability(10_000_000, 0, 100_000_000, 5.0, 0)
    with pytest.raises(ValueError, match="annual_rate_pct"):
        assess_mortgage_affordability(10_000_000, 0, 100_000_000, 105.0, 10)
    with pytest.raises(ValueError, match="existing_monthly_debt"):
        assess_mortgage_affordability(10_000_000, -1, 100_000_000, 5.0, 10)
    with pytest.raises(ValueError, match="principal"):
        assess_mortgage_affordability(10_000_000, 0, 0, 5.0, 10)
