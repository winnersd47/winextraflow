"""Investment Calculator API — compound interest, trading projections, 3-level strategy.

Based on Investology methodology:
- Level 1: Savings (6-8% annual)
- Level 2: Investments (15% annual, fund market)
- Level 3: Trading/Crypto (15-50% monthly potential)

Key principles:
- Save 10%+ of all income
- Initial capital: 30,000 RUB minimum
- Monthly additions: 5,000+ RUB
- Reinvest all profits (compound effect)
- Diversify across all 3 levels
"""

import math
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


class CompoundCalcRequest(BaseModel):
    initial_capital: float = 30000  # RUB
    monthly_addition: float = 5000  # RUB
    annual_rate: float = 15  # %
    years: int = 5


class TradingProjectionRequest(BaseModel):
    initial_capital: float = 30000
    monthly_return_pct: float = 15  # % per month (trading)
    months: int = 12
    reinvest: bool = True  # reinvest profits


class ThreeLevelRequest(BaseModel):
    monthly_income: float = 50000  # monthly salary
    savings_pct: float = 10  # % to save
    savings_rate: float = 7  # annual % for savings
    invest_rate: float = 15  # annual % for investments
    trading_rate: float = 15  # monthly % for trading
    trading_allocation_pct: float = 30  # % of savings goes to trading
    years: int = 5


@router.post("/compound")
async def compound_calculator(
    data: CompoundCalcRequest,
    user: User = Depends(get_current_user),
):
    """Compound interest calculator with monthly additions."""
    monthly_rate = data.annual_rate / 100 / 12
    months = data.years * 12

    # Calculate month by month
    balance = data.initial_capital
    timeline = [{"month": 0, "balance": round(balance, 2), "total_invested": data.initial_capital}]
    total_invested = data.initial_capital

    for m in range(1, months + 1):
        balance = balance * (1 + monthly_rate) + data.monthly_addition
        total_invested += data.monthly_addition
        if m % 12 == 0 or m == months:
            timeline.append({
                "month": m,
                "year": m // 12,
                "balance": round(balance, 2),
                "total_invested": round(total_invested, 2),
                "profit": round(balance - total_invested, 2),
                "profit_pct": round((balance / total_invested - 1) * 100, 1),
            })

    return {
        "initial": data.initial_capital,
        "monthly_addition": data.monthly_addition,
        "annual_rate": data.annual_rate,
        "years": data.years,
        "final_balance": round(balance, 2),
        "total_invested": round(total_invested, 2),
        "total_profit": round(balance - total_invested, 2),
        "roi_pct": round((balance / total_invested - 1) * 100, 1),
        "timeline": timeline,
    }


@router.post("/trading-projection")
async def trading_projection(
    data: TradingProjectionRequest,
    user: User = Depends(get_current_user),
):
    """Trading projection with monthly returns and reinvestment."""
    balance = data.initial_capital
    timeline = [{"month": 0, "balance": round(balance, 2)}]

    for m in range(1, data.months + 1):
        profit = balance * data.monthly_return_pct / 100
        if data.reinvest:
            balance += profit
        timeline.append({
            "month": m,
            "balance": round(balance, 2),
            "monthly_profit": round(profit, 2),
            "cumulative_pct": round((balance / data.initial_capital - 1) * 100, 1),
        })

    return {
        "initial": data.initial_capital,
        "monthly_return_pct": data.monthly_return_pct,
        "months": data.months,
        "reinvest": data.reinvest,
        "final_balance": round(balance, 2),
        "total_profit": round(balance - data.initial_capital, 2),
        "roi_pct": round((balance / data.initial_capital - 1) * 100, 1),
        "timeline": timeline,
    }


@router.post("/three-level-strategy")
async def three_level_strategy(
    data: ThreeLevelRequest,
    user: User = Depends(get_current_user),
):
    """3-level financial strategy: Savings + Investments + Trading.

    Based on Investology methodology:
    - Level 1: Savings (safety cushion, 6-8% annual)
    - Level 2: Investments (fund market, 15% annual)
    - Level 3: Trading (crypto, 15-50% monthly)
    """
    monthly_savings = data.monthly_income * data.savings_pct / 100
    monthly_to_trading = monthly_savings * data.trading_allocation_pct / 100
    monthly_to_invest = monthly_savings - monthly_to_trading

    months = data.years * 12

    # Level 1: Savings account (first 6 months go to safety cushion)
    savings_rate_monthly = data.savings_rate / 100 / 12
    savings = 0

    # Level 2: Investment fund
    invest_rate_monthly = data.invest_rate / 100 / 12
    investments = 0

    # Level 3: Trading
    trading_rate_monthly = data.trading_rate / 100
    trading = 0

    timeline = []
    total_contributed = 0

    for m in range(1, months + 1):
        total_contributed += monthly_savings

        # First 6 months: everything to savings (safety cushion)
        if m <= 6:
            savings = (savings + monthly_savings) * (1 + savings_rate_monthly)
        else:
            savings = savings * (1 + savings_rate_monthly)
            investments = (investments + monthly_to_invest) * (1 + invest_rate_monthly)
            trading = (trading + monthly_to_trading) * (1 + trading_rate_monthly)

        total = savings + investments + trading

        if m % 6 == 0 or m == months:
            timeline.append({
                "month": m,
                "year": round(m / 12, 1),
                "savings": round(savings, 2),
                "investments": round(investments, 2),
                "trading": round(trading, 2),
                "total": round(total, 2),
                "contributed": round(total_contributed, 2),
                "profit": round(total - total_contributed, 2),
            })

    total = savings + investments + trading

    return {
        "monthly_income": data.monthly_income,
        "monthly_savings": round(monthly_savings, 2),
        "monthly_to_invest": round(monthly_to_invest, 2),
        "monthly_to_trading": round(monthly_to_trading, 2),
        "years": data.years,
        "levels": {
            "savings": {"balance": round(savings, 2), "rate": data.savings_rate, "purpose": "Safety cushion"},
            "investments": {"balance": round(investments, 2), "rate": data.invest_rate, "purpose": "Long-term growth"},
            "trading": {"balance": round(trading, 2), "rate": data.trading_rate * 12, "purpose": "Active income"},
        },
        "total_balance": round(total, 2),
        "total_contributed": round(total_contributed, 2),
        "total_profit": round(total - total_contributed, 2),
        "roi_pct": round((total / total_contributed - 1) * 100, 1) if total_contributed > 0 else 0,
        "timeline": timeline,
    }
