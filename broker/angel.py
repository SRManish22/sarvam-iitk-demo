"""
broker/angel.py — Angel One SmartAPI adapter for Vyapar Copilot.

This is a stub adapter with the correct Angel One SmartAPI shapes.
Activate by setting the required environment variables.

TOTP Setup:
    Angel One uses TOTP-based 2FA. You must:
    1. Enable TOTP in Angel One app settings
    2. Save the TOTP secret (base32) as ANGEL_TOTP_SECRET in .env
    3. The adapter auto-generates TOTP on login

Required env vars:
    ANGEL_API_KEY       — From Angel One Developer Portal (SmartAPI)
    ANGEL_CLIENT_ID     — Your Angel One client ID (e.g. "A12345678")
    ANGEL_PASSWORD      — Your Angel One trading PIN (4-digit PIN or full password)
    ANGEL_TOTP_SECRET   — TOTP secret in base32 format from Angel app

SmartAPI Docs: https://smartapi.angelbroking.com/docs
SDK: pip install smartapi-python
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from broker.base import BrokerBase


class AngelBroker(BrokerBase):
    """
    Angel One SmartAPI adapter for Vyapar Copilot.

    Uses the official smartapi-python SDK.
    Session is created on instantiation using TOTP-based 2FA.

    Product codes: DELIVERY, INTRADAY, MARGIN, CARRYFORWARD
    Exchange codes: NSE, BSE, NFO, MCX
    Order types: MARKET, LIMIT, STOPLOSS_LIMIT, STOPLOSS_MARKET
    """

    PRODUCT_MAP = {
        "MIS": "INTRADAY",
        "CNC": "DELIVERY",
        "NRML": "CARRYFORWARD",
        "MARGIN": "MARGIN",
    }

    ORDER_TYPE_MAP = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "STOPLOSS_LIMIT",
        "SL-M": "STOPLOSS_MARKET",
    }

    SIDE_MAP = {
        "BUY": "BUY",
        "SELL": "SELL",
    }

    def __init__(self):
        try:
            import pyotp
            from smartapi import SmartConnect
        except ImportError as e:
            raise ImportError(
                f"Missing dependency: {e}. "
                "Install with: pip install smartapi-python pyotp"
            ) from e

        self.api_key = os.environ.get("ANGEL_API_KEY")
        client_id = os.environ.get("ANGEL_CLIENT_ID")
        password = os.environ.get("ANGEL_PASSWORD")
        totp_secret = os.environ.get("ANGEL_TOTP_SECRET", "")

        if not all([self.api_key, client_id, password]):
            raise ValueError(
                "Missing Angel One credentials. Set ANGEL_API_KEY, "
                "ANGEL_CLIENT_ID, ANGEL_PASSWORD in .env"
            )

        # Generate current TOTP
        totp = pyotp.TOTP(totp_secret).now() if totp_secret else ""

        # Initialize SmartConnect and create session
        self.obj = SmartConnect(api_key=self.api_key)
        session_data = self.obj.generateSession(client_id, password, totp)

        if session_data.get("status") is False:
            raise ValueError(
                f"Angel One login failed: {session_data.get('message', 'Unknown error')}"
            )

        self.auth_token = session_data["data"]["jwtToken"]
        self.refresh_token = session_data["data"]["refreshToken"]
        self.feed_token = self.obj.getfeedToken()

    def get_profile(self) -> dict:
        """Fetch user profile using SmartAPI."""
        profile_data = self.obj.getProfile(self.refresh_token)
        profile = profile_data.get("data", {})
        return {
            "client_id": profile.get("clientcode", ""),
            "name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "mobile": profile.get("mobileno", ""),
            "exchanges": profile.get("exchanges", []),
            "products": profile.get("products", []),
            "broker": "Angel One",
            "raw": profile,
        }

    def get_funds(self) -> dict:
        """Fetch RMS fund limits from SmartAPI."""
        funds_data = self.obj.rmsLimit()
        funds = funds_data.get("data", {})
        return {
            "available_margin": float(funds.get("availablecash", 0)),
            "used_margin": float(funds.get("utiliseddebits", 0)),
            "total_balance": float(funds.get("availablecash", 0)),
            "equity_margin": float(funds.get("availablecash", 0)),
            "commodity_margin": 0,
            "currency": "INR",
            "as_of": datetime.now().isoformat(),
            "raw": funds,
        }

    def get_positions(self) -> list:
        """Fetch open positions from SmartAPI."""
        positions_data = self.obj.position()
        positions = positions_data.get("data", []) or []
        return [
            {
                "symbol": pos.get("tradingsymbol", ""),
                "exchange": pos.get("exchange", ""),
                "product": pos.get("producttype", ""),
                "side": "BUY" if int(pos.get("netqty", 0)) > 0 else "SELL",
                "quantity": abs(int(pos.get("netqty", 0))),
                "avg_price": float(pos.get("netprice", 0)),
                "ltp": float(pos.get("ltp", 0)),
                "pnl": float(pos.get("pnl", 0)),
                "value": float(pos.get("netvalue", 0)),
                "raw": pos,
            }
            for pos in positions
        ]

    def get_holdings(self) -> list:
        """Fetch long-term holdings from SmartAPI."""
        holdings_data = self.obj.holding()
        holdings = holdings_data.get("data", []) or []
        return [
            {
                "symbol": h.get("tradingsymbol", ""),
                "exchange": h.get("exchange", ""),
                "quantity": int(h.get("quantity", 0)),
                "avg_price": float(h.get("averageprice", 0)),
                "ltp": float(h.get("ltp", 0)),
                "current_value": float(h.get("marketvalue", 0)),
                "pnl": float(h.get("profitandloss", 0)),
                "pnl_pct": float(h.get("pnlpercentage", 0)),
                "isin": h.get("isin", ""),
                "raw": h,
            }
            for h in holdings
        ]

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
        Place an order via Angel One SmartAPI.

        SmartAPI requires symboltoken (instrument token) for each symbol.
        In production, load the instrument master and look up the token.
        """
        order_params = {
            "variety": "NORMAL",            # NORMAL, STOPLOSS, AMO, ROBO (bracket)
            "tradingsymbol": symbol.upper(),
            "symboltoken": "",              # Must look up from instrument master
            "transactiontype": self.SIDE_MAP.get(side.upper(), "BUY"),
            "exchange": exchange.upper(),
            "ordertype": self.ORDER_TYPE_MAP.get(order_type.upper(), "MARKET"),
            "producttype": self.PRODUCT_MAP.get(product.upper(), "INTRADAY"),
            "duration": "DAY",
            "price": str(price or 0),
            "squareoff": str(target or 0),
            "stoploss": str(stop_loss or 0),
            "quantity": str(quantity),
        }

        # For bracket/cover orders (ROBO variety), set squareoff and stoploss
        if target and stop_loss:
            order_params["variety"] = "ROBO"

        response = self.obj.placeOrder(order_params)

        if response.get("status") is False:
            return {
                "error": response.get("message", "Order placement failed"),
                "symbol": symbol,
            }

        order_id = response.get("data", {}).get("orderid", "")
        return {
            "order_id": order_id,
            "status": "PLACED",
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "side": side.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "price": price,
            "stop_loss": stop_loss,
            "target": target,
            "product": product.upper(),
            "broker": "Angel One",
            "timestamp": datetime.now().isoformat(),
            "raw": response,
        }

    def get_order_status(self, order_id: str) -> dict:
        """Fetch order status from SmartAPI order book."""
        order_book = self.obj.orderBook()
        orders = order_book.get("data", []) or []
        for order in orders:
            if order.get("orderid") == order_id:
                return {
                    "order_id": order_id,
                    "status": order.get("status", ""),
                    "filled_qty": int(order.get("filledshares", 0)),
                    "pending_qty": int(order.get("unfilledshares", 0)),
                    "avg_price": float(order.get("averageprice", 0)),
                    "symbol": order.get("tradingsymbol", ""),
                    "side": order.get("transactiontype", ""),
                    "exchange": order.get("exchange", ""),
                    "timestamp": order.get("updatetime", ""),
                    "raw": order,
                }
        return {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "message": f"Order {order_id} not found in Angel One order book",
        }

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a pending order via SmartAPI."""
        payload = {"variety": "NORMAL", "orderid": order_id}
        response = self.obj.cancelOrder(order_id, "NORMAL")

        if response.get("status") is False:
            return {
                "order_id": order_id,
                "status": "CANCEL_FAILED",
                "message": response.get("message", "Cancel failed"),
            }

        return {
            "order_id": order_id,
            "status": "CANCELLED",
            "message": "Order cancelled via Angel One SmartAPI",
            "raw": response,
        }

    def logout(self):
        """Terminate the SmartAPI session."""
        try:
            self.obj.terminateSession(os.environ.get("ANGEL_CLIENT_ID"))
        except Exception:
            pass
