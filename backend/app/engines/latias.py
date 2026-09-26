"""
Latias Detection Engine:
Combines 3 core Level-0 techniques according to IWA/AWWA standards:
1. Component-based Water Audit (Loss = Inflow - Billed - Authorized Unbilled)
2. Minimum Night Flow (MNF) Analysis (2:00 AM - 4:00 AM)
3. Unavoidable Annual Real Losses (UARL) Baseline
"""

from typing import Dict, Any, List, Optional

def water_balance_loss(inflow_litres: float, billed_litres: float, authorized_unbilled_litres: float = 0.0) -> float:
    """Calculates gross water loss."""
    return max(0.0, inflow_litres - (billed_litres + authorized_unbilled_litres))

def mnf_loss_estimate(night_flow_litres: float, hours: float = 2.0, legitimate_night_use_factor: float = 0.15) -> float:
    """Estimates 24-hr leakage based on Minimum Night Flow (2 AM - 4 AM)."""
    if night_flow_litres <= 0:
        return 0.0
    net_night_loss_hourly = (night_flow_litres * (1.0 - legitimate_night_use_factor)) / hours
    return net_night_loss_hourly * 24.0

def unavoidable_annual_real_losses(pipe_length_km: float, connection_count: int, avg_pressure_bar: float) -> float:
    """
    IWA/AWWA Standard formula for UARL in Litres/day:
    UARL (L/day) = (18 * Lm + 0.80 * Nc + 25 * Lp) * P
    """
    pressure_head_meters = avg_pressure_bar * 10.197
    uarl_litres_per_day = (18.0 * pipe_length_km + 0.80 * connection_count + 25.0 * (0.015 * connection_count)) * pressure_head_meters
    return max(0.0, uarl_litres_per_day)

def calculate_dynamic_confidence(
    has_inflow: bool,
    has_billing: bool,
    has_mnf: bool,
    methods_count: int,
    readings_count: int = 1
) -> float:
    """Replaces hardcoded 0.7 confidence score with dynamic calculation."""
    score = 0.0
    if has_inflow and has_billing:
        score += 0.35
    if has_mnf:
        score += 0.15

    if methods_count >= 3:
        score += 0.3
    elif methods_count == 2:
        score += 0.2
    else:
        score += 0.1

    if readings_count >= 10:
        score += 0.2
    elif readings_count >= 3:
        score += 0.15
    else:
        score += 0.1

    return round(min(0.98, max(0.20, score)), 2)

def process_zone(
    zone_id: str,
    inflow_litres: float,
    billed_litres: float,
    night_flow_litres: Optional[float] = None,
    pipe_length_km: float = 10.0,
    connection_count: int = 500,
    avg_pressure_bar: float = 2.5,
    readings_count: int = 5
) -> Dict[str, Any]:
    """Wires all 3 detection techniques into a single audit report."""
    methods_run: List[str] = ["water_balance"]
    wb_loss = water_balance_loss(inflow_litres, billed_litres)

    # 1. UARL Baseline
    uarl_baseline = unavoidable_annual_real_losses(pipe_length_km, connection_count, avg_pressure_bar)
    methods_run.append("uarl")
    actionable_loss = max(0.0, wb_loss - uarl_baseline)

    # 2. MNF Analysis
    mnf_loss = 0.0
    if night_flow_litres is not None and night_flow_litres > 0:
        mnf_loss = mnf_loss_estimate(night_flow_litres)
        methods_run.append("mnf")

    final_loss_estimate = ((actionable_loss * 0.5) + (mnf_loss * 0.5)) if mnf_loss > 0 else actionable_loss

    # 3. Dynamic Confidence
    confidence = calculate_dynamic_confidence(
        has_inflow=(inflow_litres > 0),
        has_billing=(billed_litres > 0),
        has_mnf=(night_flow_litres is not None and night_flow_litres > 0),
        methods_count=len(methods_run),
        readings_count=readings_count
    )

    nrw_percentage = (wb_loss / inflow_litres * 100.0) if inflow_litres > 0 else 0.0
    if nrw_percentage >= 50.0:
        severity = "CRITICAL"
    elif nrw_percentage >= 35.0:
        severity = "HIGH"
    elif nrw_percentage >= 20.0:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    details = (
        f"Multi-method audit: Water Balance loss = {wb_loss:,.0f} L. "
        f"UARL baseline = {uarl_baseline:,.0f} L/day. "
        f"Actionable loss = {actionable_loss:,.0f} L. "
        f"MNF daily estimate = {mnf_loss:,.0f} L. "
        f"NRW = {nrw_percentage:.1f}%."
    )

    return {
        "zone_id": zone_id,
        "is_leak_detected": (wb_loss > uarl_baseline or mnf_loss > 0),
        "estimated_loss_litres": round(final_loss_estimate, 2),
        "total_water_balance_loss": round(wb_loss, 2),
        "uarl_baseline_litres": round(uarl_baseline, 2),
        "nrw_percentage": round(nrw_percentage, 2),
        "severity": severity,
        "confidence_score": confidence,
        "detection_methods": ",".join(methods_run),
        "details": details
    }

if __name__ == "__main__":
    test_res = process_zone("ZONE-TEST", inflow_litres=100000, billed_litres=45000, night_flow_litres=2500)
    print("Latias Engine Test Result:")
    print(test_res)