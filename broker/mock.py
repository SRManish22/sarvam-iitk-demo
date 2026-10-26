"""
broker/mock.py — Mock broker for testing without real API credentials.

Simulates all broker operations: order placement, fund queries, positions.
All orders always succeed. Order book is kept in-memory for the session.
Logs all operations to stdout for visibility during development.
"""

from __future__ import annotations

import random
import string
from datetime import datetime
from typing import Optional

from broker.base import BrokerBase


def _generate_order_id() -> str:
    """Generate a random order ID mimicking real broker format."""
    return "MOCK" + "".join(random.choices(string.digits, k=10))


class MockBroker(BrokerBase):
    """
    Simulated broker for testing Vyapar Copilot without real API credentials.

    Features:
    - Always returns successful order placements
    - Maintains in-memory order book and positions
    - Logs all operations to stdout
    - Simulates realistic fund balances

    Usage:
        broker = MockBroker()
        result = broker.place_order("RELIANCE", "NSE", "BUY", 10, "LIMIT", price=2900)
    """

    def __init__(self):
        self.orders: list[dict] = []
        self.order_counter: int = 1000
        # Simulated positions (empty at start)
        self._positions: list[dict] = []
        # Simulated holdings
        self._holdings: list[dict] = [
            {
                "symbol": "RELIANCE",
                "exchange": "NSE",
                "quantity": 5,
                "avg_price": 2800.0,
                "ltp": 2950.0,
                "current_value": 14750.0,
                "pnl": 750.0,
                "pnl_pct": 5.36,
                "isin": "INE002A01018",
            },
            {
                "symbol": "TCS",
                "exchange": "NSE",
                "quantity": 2,
                "avg_price": 3600.0,
                "ltp": 3780.0,
                "current_value": 7560.0,
                "pnl": 360.0,
                "pnl_pct": 5.0,
                "isin": "INE467B01029",
            },
        ]
        print("[MockBroker] Initialized — paper trading mode active 📝")

    def get_profile(self) -> dict:
        """Return mock user profile."""
        profile = {
            "client_id": "MOCK_CLIENT_001",
            "name": "Demo Trader",
            "email": "demo@vyaparcopilot.in",
            "mobile": "+91-9999999999",
            "exchanges": ["NSE", "BSE", "NFO", "MCX"],
            "products": ["CNC", "MIS", "NRML"],
            "broker": "MockBroker",
            "account_type": "Individual",
        }
        print(f"[MockBroker] get_profile() → {profile['client_id']}")
        return profile

    def get_funds(self) -> dict:
        """Return mock fund balances."""
        funds = {
            "available_margin": 500000.0,
            "used_margin": 50000.0,
            "total_balance": 550000.0,
            "equity_margin": 450000.0,
            "commodity_margin": 50000.0,
            "currency": "INR",
            "as_of": datetime.now().isoformat(),
        }
        print(f"[MockBroker] get_funds() → available: ₹{funds['available_margin']:,.0f}")
        return funds

    def get_positions(self) -> list:
        """Return current open positions."""
        print(f"[MockBroker] get_positions() → {len(self._positions)} open positions")
        return list(self._positions)

    def get_holdings(self) -> list:
        """Return long-term holdings."""
        print(f"[MockBroker] get_holdings() → {len(self._holdings)} holdings")
        return list(self._holdings)

    def place_order(
        self,
        symbol: str,
        exchange: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        product: str = "MIS",
    ) -> dict:
        """
        Simulate order placement. Always succeeds.

        Logs order details to stdout and stores in in-memory order book.
        """
        order_id = _generate_order_id()
        self.order_counter += 1

        order = {
            "order_id": order_id,
            "status": "COMPLETE",
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "side": side.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "price": price,
            "stop_loss": stop_loss,
            "target": target,
            "product": product.upper(),
            "filled_qty": quantity,
            "avg_price": price or 0.0,
            "broker": "MockBroker",
            "timestamp": datetime.now().isoformat(),
            "message": f"[PAPER TRADE] Order simulated successfully. No real money involved.",
        }

        self.orders.append(order)

        # Add to simulated positions
        self._positions.append({
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "product": product.upper(),
            "side": side.upper(),
            "quantity": quantity,
            "avg_price": price or 0.0,
            "ltp": price or 0.0,
            "pnl": 0.0,
            "value": (price or 0.0) * quantity,
            "order_id": order_id,
        })

        print(
            f"[MockBroker] 📋 ORDER PLACED"
            f"\n  Order ID : {order_id}"
            f"\n  Symbol   : {symbol.upper()} ({exchange})"
            f"\n  Side     : {side.upper()}"
            f"\n  Qty      : {quantity}"
            f"\n  Type     : {order_type}"
            f"\n  Price    : ₹{price or 'MARKET'}"
            f"\n  SL       : ₹{stop_loss or 'None'}"
            f"\n  Target   : ₹{target or 'None'}"
            f"\n  Product  : {product}"
            f"\n  Status   : COMPLETE (paper trade)"
        )
        return order

    def get_order_status(self, order_id: str) -> dict:
        """Fetch status of a placed order."""
        for order in self.orders:
            if order["order_id"] == order_id:
                print(f"[MockBroker] get_order_status({order_id}) → {order['status']}")
                return order
        result = {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "message": f"Order {order_id} not found in mock order book",
        }
        print(f"[MockBroker] get_order_status({order_id}) → NOT_FOUND")
        return result

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a pending order."""
        for order in self.orders:
            if order["order_id"] == order_id:
                order["status"] = "CANCELLED"
                print(f"[MockBroker] cancel_order({order_id}) → CANCELLED")
                return {
                    "order_id": order_id,
                    "status": "CANCELLED",
                    "message": "Order cancelled successfully (paper trade)",
                }
        result = {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "message": f"Order {order_id} not found — cannot cancel",
        }
        print(f"[MockBroker] cancel_order({order_id}) → NOT_FOUND")
        return result

    def get_order_book(self) -> list:
        """Return all orders placed in this session."""
        return list(self.orders)
