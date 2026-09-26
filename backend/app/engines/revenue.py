"""
Revenue & Payback Engine:
Calculates ROI, estimated payback periods, and financial impact.
"""

from typing import Dict, Any

DEFAULT_TARIFF_RATE = 0.005  # ₹ 0.005 per litre (₹ 5 per kilolitre)

def calculate_payback_period(
    daily_loss_litres: float,
    tariff_rate: float = DEFAULT_TARIFF_RATE,
    pipe_type: str = "cast_iron",
    pipe_age_years: int = 15,
    custom_repair_cost: float = None
) -> Dict[str, Any]:
    """Calculates payback period: Repair Cost ÷ Daily Revenue Loss."""
    if custom_repair_cost is not None and custom_repair_cost > 0:
        repair_cost = custom_repair_cost
    else:
        base_cost = 25000.0  # ₹ 25,000 mobilization base
        age_multiplier = 1.0 + (min(pipe_age_years, 40) * 0.02)
        type_multiplier = 1.3 if pipe_type.lower() in ["cast_iron", "di"] else 1.0
        repair_cost = round(base_cost * age_multiplier * type_multiplier, 2)

    daily_revenue_loss = round(daily_loss_litres * tariff_rate, 2)
    payback_days = round(repair_cost / daily_revenue_loss, 1) if daily_revenue_loss > 0 else 999.0

    return {
        "daily_loss_litres": round(daily_loss_litres, 2),
        "tariff_rate_per_litre": tariff_rate,
        "daily_revenue_loss": daily_revenue_loss,
        "estimated_repair_cost": repair_cost,
        "payback_period_days": payback_days
    }

def calculate_revenue_recovered(litres_saved: float, tariff_rate: float = DEFAULT_TARIFF_RATE) -> float:
    """Calculates rupees recovered from saved water."""
    return round(litres_saved * tariff_rate, 2)

if __name__ == "__main__":
    res = calculate_payback_period(daily_loss_litres=30467.25, tariff_rate=0.005)
    print("Revenue Engine Test Result:")
    print(res)