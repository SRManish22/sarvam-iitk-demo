"""
risk/engine.py — Risk management engine for Vyapar Copilot.

Implements:
- Fixed-fraction position sizing
- Risk:Reward ratio calculation
- SEBI margin estimation (simplified)
- Full pre-trade validation
"""

from __future__ import annotations


def calculate_position(
    capital: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float = 1.0,
) -> dict:
    """
    Fixed-fraction position sizing.

    Formula:
        risk_amount = capital * risk_pct / 100
        risk_per_share = |entry_price - stop_loss|
        quantity = floor(risk_amount / risk_per_share)
        capital_deployed = quantity * entry_price

    Args:
        capital: Total trading capital in INR.
        entry_price: Entry price per share.
        stop_loss: Stop-loss price per share.
        risk_pct: Percentage of capital to risk (default 1.0%).

    Returns:
        dict with: quantity, risk_amount, risk_per_share, max_loss, capital_deployed,
                   capital_deployed_pct.
    """
    if entry_price <= 0:
        return {"error": "Entry price must be positive"}
    if stop_loss <= 0:
        return {"error": "Stop-loss price must be positive"}
    if capital <= 0:
        return {"error": "Capital must be positive"}
    if risk_pct <= 0 or risk_pct > 100:
        return {"error": "risk_pct must be between 0 and 100"}

    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share == 0:
        return {"error": "Entry price and stop-loss cannot be equal"}

    risk_amount = capital * risk_pct / 100
    quantity = int(risk_amount / risk_per_share)

    if quantity == 0:
        return {
            "error": (
                f"Position size rounds to 0 shares. "
                f"Risk amount ₹{risk_amount:.2f} < risk per share ₹{risk_per_share:.2f}. "
                f"Increase capital or risk_pct, or widen stop-loss."
            )
        }

    capital_deployed = round(quantity * entry_price, 2)
    capital_deployed_pct = round(capital_deployed / capital * 100, 2)
    actual_max_loss = round(quantity * risk_per_share, 2)

    return {
        "quantity": quantity,
        "risk_per_share": round(risk_per_share, 2),
        "risk_amount": round(risk_amount, 2),
        "max_loss": actual_max_loss,
        "capital_deployed": capital_deployed,
        "capital_deployed_pct": capital_deployed_pct,
    }


def check_risk_reward(entry: float, stop_loss: float, target: float) -> dict:
    """
    Calculate and validate the Risk:Reward ratio for a trade.

    Formula:
        risk_points = |entry - stop_loss|
        reward_points = |target - entry|
        rr_ratio = reward_points / risk_points

    Args:
        entry: Entry price.
        stop_loss: Stop-loss price.
        target: Target price.

    Returns:
        dict with: rr_ratio, is_acceptable (>=1.5), risk_points, reward_points,
                   risk_pct_of_entry, reward_pct_of_entry, verdict.
    """
    risk_points = abs(entry - stop_loss)
    reward_points = abs(target - entry)

    if risk_points == 0:
        return {"error": "Entry and stop_loss are the same — invalid setup"}

    rr_ratio = round(reward_points / risk_points, 2)
    is_acceptable = rr_ratio >= 1.5

    if rr_ratio >= 3.0:
        verdict = "Excellent R:R — High probability setup"
    elif rr_ratio >= 2.0:
        verdict = "Good R:R — Acceptable setup"
    elif rr_ratio >= 1.5:
        verdict = "Minimum acceptable R:R — Consider if conviction is high"
    elif rr_ratio >= 1.0:
        verdict = "Poor R:R (<1.5) — Not recommended. Adjust target or stop-loss."
    else:
        verdict = "Very poor R:R (<1.0) — Avoid this trade"

    return {
        "rr_ratio": rr_ratio,
        "is_acceptable": is_acceptable,
        "risk_points": round(risk_points, 2),
        "reward_points": round(reward_points, 2),
        "risk_pct_of_entry": round(risk_points / entry * 100, 2),
        "reward_pct_of_entry": round(reward_points / entry * 100, 2),
        "verdict": verdict,
    }


def check_sebi_margin(
    symbol: str,
    quantity: int,
    entry_price: float,
    available_margin: float,
) -> dict:
    """
    Estimate required margin for a trade (simplified SEBI SPAN model).

    SEBI mandates:
    - Equity delivery: 100% of trade value (CNC)
    - Equity intraday (MIS): typically 20% of trade value (5x leverage)
    - F&O: SPAN margin + Exposure margin (approx 15-20% of contract value)

    This uses a simplified 20% margin estimate for intraday equity.
    In production, use the broker's actual margin API.

    Args:
        symbol: Stock ticker (for potential symbol-specific margin rules).
        quantity: Number of shares.
        entry_price: Entry price per share.
        available_margin: Available margin in INR.

    Returns:
        dict with: trade_value, required_margin_mis (intraday), required_margin_cnc (delivery),
                   available_margin, is_sufficient_mis, is_sufficient_cnc, shortfall_mis, shortfall_cnc.
    """
    trade_value = round(quantity * entry_price, 2)

    # SEBI MIS (intraday) margin: ~20% (5x leverage)
    mis_margin_pct = 0.20
    required_margin_mis = round(trade_value * mis_margin_pct, 2)

    # CNC (delivery) margin: 100% of trade value
    required_margin_cnc = trade_value

    shortfall_mis = max(0, round(required_margin_mis - available_margin, 2))
    shortfall_cnc = max(0, round(required_margin_cnc - available_margin, 2))

    return {
        "trade_value": trade_value,
        "required_margin_mis": required_margin_mis,
        "required_margin_cnc": required_margin_cnc,
        "available_margin": round(available_margin, 2),
        "is_sufficient_mis": available_margin >= required_margin_mis,
        "is_sufficient_cnc": available_margin >= required_margin_cnc,
        "shortfall_mis": shortfall_mis,
        "shortfall_cnc": shortfall_cnc,
        "margin_note": (
            "Simplified 20% MIS margin estimate. Actual margin varies by broker and SEBI VaR rules. "
            "Always verify with your broker before trading."
        ),
    }


def validate_trade(
    symbol: str,
    entry: float,
    stop_loss: float,
    target: float,
    quantity: int,
    capital: float,
    available_margin: float,
) -> dict:
    """
    Full pre-trade validation with multiple risk checks.

    Checks performed:
    1. R:R ratio must be >= 1.5
    2. Stop-loss distance must be >= 0.5% of entry (not too tight)
    3. Stop-loss distance must be <= 10% of entry (not too wide)
    4. Margin sufficiency for intraday (MIS)
    5. Max position size <= 25% of capital (concentration limit)
    6. Trade value sanity check

    Args:
        symbol: Stock ticker.
        entry: Entry price.
        stop_loss: Stop-loss price.
        target: Target price.
        quantity: Number of shares.
        capital: Total capital.
        available_margin: Available margin.

    Returns:
        dict with: is_approved (bool), reasons (list), warnings (list),
                   position_details (dict), rr_details (dict), margin_details (dict).
    """
    reasons: list[str] = []      # Hard failures — trade blocked
    warnings: list[str] = []     # Soft warnings — trade allowed with caution
    is_approved = True

    # ---- R:R Check ----
    rr = check_risk_reward(entry, stop_loss, target)
    if "error" in rr:
        reasons.append(f"R:R Error: {rr['error']}")
        is_approved = False
    elif not rr["is_acceptable"]:
        reasons.append(f"R:R ratio {rr['rr_ratio']} is below minimum 1.5. {rr['verdict']}")
        is_approved = False

    # ---- Stop-loss distance check ----
    sl_distance_pct = abs(entry - stop_loss) / entry * 100
    if sl_distance_pct < 0.5:
        reasons.append(
            f"Stop-loss too tight ({sl_distance_pct:.2f}% from entry). "
            "Minimum is 0.5% — tight stops get triggered by noise."
        )
        is_approved = False
    elif sl_distance_pct > 10:
        warnings.append(
            f"Stop-loss very wide ({sl_distance_pct:.2f}% from entry). "
            "This significantly increases risk per share."
        )

    # ---- Position sizing check ----
    position_value = quantity * entry
    position_pct = (position_value / capital * 100) if capital > 0 else 0
    if position_pct > 25:
        reasons.append(
            f"Position size ({position_pct:.1f}% of capital = ₹{position_value:,.0f}) "
            "exceeds 25% concentration limit. Reduce quantity."
        )
        is_approved = False
    elif position_pct > 15:
        warnings.append(
            f"Position is {position_pct:.1f}% of capital — consider reducing for diversification."
        )

    # ---- Margin check ----
    margin = check_sebi_margin(symbol, quantity, entry, available_margin)
    if not margin["is_sufficient_mis"]:
        reasons.append(
            f"Insufficient margin for intraday (MIS). "
            f"Required: ₹{margin['required_margin_mis']:,.0f}, "
            f"Available: ₹{available_margin:,.0f}, "
            f"Shortfall: ₹{margin['shortfall_mis']:,.0f}"
        )
        is_approved = False

    # ---- Position sizing calc ----
    pos = calculate_position(capital, entry, stop_loss)

    return {
        "is_approved": is_approved,
        "reasons": reasons,
        "warnings": warnings,
        "verdict": (
            "✅ Trade validated — proceed with caution" if is_approved
            else f"❌ Trade blocked — {len(reasons)} issue(s) found"
        ),
        "position_details": {
            "symbol": symbol,
            "entry": entry,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": quantity,
            "position_value": round(position_value, 2),
            "position_pct_of_capital": round(position_pct, 2),
            "recommended_quantity": pos.get("quantity"),
        },
        "rr_details": rr,
        "margin_details": margin,
    }
