"""
Quick test suite to verify:
1. Risk Engine (pure logic)
2. Mock Broker (order simulation)
3. Market Data (free quote & technicals fallback)
4. Copilot Tool definitions
"""
import sys
import io
# Reconfigure stdout/stderr to utf-8 to avoid Windows console cp1252 encoding crashes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import traceback

def test_risk_engine():
    print("--- [1] Testing Risk Engine ---")
    from risk.engine import calculate_position, check_risk_reward, validate_trade
    
    # 1. Position sizing: Capital 100k, risk 1% (1000 INR), entry 2500, SL 2450 (risk 50/share) -> 20 shares
    pos = calculate_position(capital=100000, entry_price=2500, stop_loss=2450, risk_pct=1.0)
    assert pos.get("quantity") == 20, f"Expected 20 shares, got {pos}"
    print(f"  [OK] Position sizing calculation passed: {pos['quantity']} shares (Risk: Rs. {pos['risk_amount']})")

    # 2. Risk Reward check: Entry 2500, SL 2450 (50 risk), Target 2600 (100 reward) -> 2.0 R:R
    rr = check_risk_reward(entry=2500, stop_loss=2450, target=2600)
    assert rr.get("rr_ratio") == 2.0, f"Expected 2.0 RR, got {rr}"
    assert rr.get("is_acceptable") is True, "Expected acceptable RR"
    print(f"  [OK] Risk-Reward validation passed: R:R = {rr['rr_ratio']} (Acceptable: {rr['is_acceptable']})")

    # 3. Validation rejection on poor R:R
    bad_rr = check_risk_reward(entry=2500, stop_loss=2450, target=2530)
    assert bad_rr.get("is_acceptable") is False, "Expected rejection for R:R < 1.5"
    print(f"  [OK] Unsafe trade rejection passed: R:R = {bad_rr['rr_ratio']} (Rejected as expected)")


def test_mock_broker():
    print("\n--- [2] Testing Mock Broker ---")
    from broker.mock import MockBroker
    b = MockBroker()
    funds = b.get_funds()
    print(f"  [OK] Initial funds: Available margin = Rs. {funds['available_margin']:,}")

    order = b.place_order(
        symbol="RELIANCE",
        exchange="NSE",
        side="BUY",
        quantity=10,
        order_type="LIMIT",
        price=2500.0,
        stop_loss=2450.0,
        target=2600.0
    )
    assert order.get("status") == "COMPLETE", f"Order failed: {order}"
    print(f"  [OK] Mock order placed successfully: Order ID = {order.get('order_id')}, Status = {order.get('status')}")


def test_tools():
    print("\n--- [3] Testing Agent Tool Functions ---")
    from agent.tools import calculate_risk, get_quote
    
    # Tool wrapper for risk
    r = calculate_risk(symbol="TCS", entry=3500, stop_loss=3400, target=3700, capital=200000, risk_pct=1.5)
    assert "error" not in r, f"Risk tool error: {r}"
    print(f"  [OK] calculate_risk tool: Allowed = {r.get('is_approved')}, Rec Qty = {r.get('recommended_quantity')}")

    # Tool wrapper for quote (will hit fallback or NSE)
    print("  Fetching sample quote for RELIANCE (via NSE/yfinance)...")
    q = get_quote(symbol="RELIANCE")
    if "error" not in q:
        print(f"  [OK] get_quote returned: Price = Rs. {q.get('price')} ({q.get('source')})")
    else:
        print(f"  [INFO] get_quote handled fallback gracefully: {q.get('error')}")

if __name__ == "__main__":
    try:
        test_risk_engine()
        test_mock_broker()
        test_tools()
        print("\nAll unit tests passed successfully!")
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
