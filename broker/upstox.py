"""
broker/upstox.py — Upstox V2 API adapter for Vyapar Copilot.

This is a stub adapter with the correct Upstox V2 API shapes.
Activate by setting the required environment variables and obtaining an OAuth access token.

OAuth Flow:
    1. Direct user to: https://api.upstox.com/v2/login/authorization/dialog?
       response_type=code&client_id={UPSTOX_API_KEY}&redirect_uri={REDIRECT_URI}
    2. Exchange the auth code for access token via POST /v2/login/authorization/token
    3. Set UPSTOX_ACCESS_TOKEN in your .env

Required env vars:
    UPSTOX_API_KEY        — From Upstox Developer Portal
    UPSTOX_SECRET         — App secret
    UPSTOX_ACCESS_TOKEN   — OAuth2 bearer token (refreshed daily)

Upstox V2 API Docs: https://upstox.com/developer/api-documentation/
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import requests

from broker.base import BrokerBase


class UpstoxBroker(BrokerBase):
    """
    Upstox V2 API adapter.

    All endpoints use Bearer token authentication.
    Exchange codes: NSE_EQ, BSE_EQ, NSE_FO, BSE_FO, MCX_FO, NCD_FO.
    """

    BASE_URL = "https://api.upstox.com/v2"

    # Upstox instrument key format: "NSE_EQ|{ISIN}" or "NSE_EQ|{symbol}"
    # Full instrument master: https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz
    EXCHANGE_MAP = {
        "NSE": "NSE_EQ",
        "BSE": "BSE_EQ",
        "NFO": "NSE_FO",
        "MCX": "MCX_FO",
    }

    ORDER_TYPE_MAP = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "SL",
        "SL-M": "SL-M",
    }

    PRODUCT_MAP = {
        "MIS": "I",      # Upstox uses "I" for intraday
        "CNC": "D",      # "D" for delivery
        "NRML": "O",     # "O" for overnight (F&O)
    }

    def __init__(self):
        self.api_key = os.environ.get("UPSTOX_API_KEY")
        self.access_token = os.environ.get("UPSTOX_ACCESS_TOKEN")

        if not self.access_token:
            raise ValueError(
                "UPSTOX_ACCESS_TOKEN not set. "
                "Complete OAuth flow and set the token in .env\n"
                "OAuth URL: https://api.upstox.com/v2/login/authorization/dialog"
            )

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated GET request to Upstox API."""
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Make authenticated POST request to Upstox API."""
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated DELETE request to Upstox API."""
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.delete(url, headers=self.headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_profile(self) -> dict:
        """
        GET /v2/user/profile

        Returns user profile with exchanges, products, and account details.
        """
        data = self._get("/user/profile")
        profile = data.get("data", {})
        return {
            "client_id": profile.get("user_id", ""),
            "name": profile.get("user_name", ""),
            "email": profile.get("email", ""),
            "mobile": profile.get("mobile_number", ""),
            "exchanges": profile.get("exchanges", []),
            "products": profile.get("products", []),
            "broker": "Upstox",
            "raw": profile,
        }

    def get_funds(self) -> dict:
        """
        GET /v2/user/fund-and-margin?segment=SEC

        Returns equity segment funds and margin details.
        """
        data = self._get("/user/fund-and-margin", params={"segment": "SEC"})
        equity = data.get("data", {}).get("equity", {})
        return {
            "available_margin": equity.get("available_margin", 0),
            "used_margin": equity.get("used_margin", 0),
            "total_balance": equity.get("total_balance_without_collateral", 0),
            "equity_margin": equity.get("available_margin", 0),
            "commodity_margin": 0,  # Separate segment
            "currency": "INR",
            "as_of": datetime.now().isoformat(),
            "raw": equity,
        }

    def get_positions(self) -> list:
        """
        GET /v2/portfolio/short-term-positions

        Returns all open intraday (MIS) and overnight (NRML) positions.
        """
        data = self._get("/portfolio/short-term-positions")
        positions = data.get("data", [])
        return [
            {
                "symbol": pos.get("trading_symbol", ""),
                "exchange": pos.get("exchange", ""),
                "product": pos.get("product", ""),
                "side": "BUY" if pos.get("quantity", 0) > 0 else "SELL",
                "quantity": abs(pos.get("quantity", 0)),
                "avg_price": pos.get("average_price", 0),
                "ltp": pos.get("last_price", 0),
                "pnl": pos.get("pnl", 0),
                "value": pos.get("value", 0),
                "raw": pos,
            }
            for pos in positions
        ]

    def get_holdings(self) -> list:
        """
        GET /v2/portfolio/long-term-holdings

        Returns all delivery (CNC) holdings.
        """
        data = self._get("/portfolio/long-term-holdings")
        holdings = data.get("data", [])
        return [
            {
                "symbol": h.get("trading_symbol", ""),
                "exchange": h.get("exchange", ""),
                "quantity": h.get("quantity", 0),
                "avg_price": h.get("average_price", 0),
                "ltp": h.get("last_price", 0),
                "current_value": h.get("current_value", 0),
                "pnl": h.get("pnl", 0),
                "pnl_pct": h.get("pnl_pct", 0),
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
        POST /v2/order/place

        Places an order using Upstox V2 API.
        Instrument key format: "NSE_EQ|RELIANCE" (for NSE equity).
        """
        upstox_exchange = self.EXCHANGE_MAP.get(exchange.upper(), "NSE_EQ")
        instrument_key = f"{upstox_exchange}|{symbol.upper()}"

        payload = {
            "quantity": quantity,
            "product": self.PRODUCT_MAP.get(product.upper(), "I"),
            "validity": "DAY",
            "price": price or 0,
            "tag": "VyaparCopilot",
            "instrument_token": instrument_key,
            "order_type": self.ORDER_TYPE_MAP.get(order_type.upper(), "MARKET"),
            "transaction_type": side.upper(),
            "disclosed_quantity": 0,
            "trigger_price": stop_loss or 0,
            "is_amo": False,  # After Market Order flag
        }

        data = self._post("/order/place", payload)
        order_data = data.get("data", {})

        return {
            "order_id": order_data.get("order_id", ""),
            "status": data.get("status", ""),
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "side": side.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "price": price,
            "stop_loss": stop_loss,
            "target": target,
            "product": product.upper(),
            "broker": "Upstox",
            "timestamp": datetime.now().isoformat(),
            "raw": data,
        }

    def get_order_status(self, order_id: str) -> dict:
        """
        GET /v2/order/details?order_id={order_id}

        Returns current status of an order.
        """
        data = self._get("/order/details", params={"order_id": order_id})
        order = data.get("data", {})
        return {
            "order_id": order_id,
            "status": order.get("status", ""),
            "filled_qty": order.get("filled_quantity", 0),
            "pending_qty": order.get("quantity", 0) - order.get("filled_quantity", 0),
            "avg_price": order.get("average_price", 0),
            "symbol": order.get("trading_symbol", ""),
            "side": order.get("transaction_type", ""),
            "exchange": order.get("exchange", ""),
            "timestamp": order.get("order_timestamp", ""),
            "raw": order,
        }

    def cancel_order(self, order_id: str) -> dict:
        """
        DELETE /v2/order/cancel?order_id={order_id}

        Cancels a pending order.
        """
        data = self._delete("/order/cancel", params={"order_id": order_id})
        return {
            "order_id": order_id,
            "status": "CANCELLED",
            "message": "Order cancelled via Upstox V2 API",
            "raw": data,
        }

    def get_market_quote(self, symbol: str, exchange: str = "NSE") -> dict:
        """
        GET /v2/market-quote/quotes?instrument_key={key}

        Fetch live market quote using Upstox Market Data API.
        """
        upstox_exchange = self.EXCHANGE_MAP.get(exchange.upper(), "NSE_EQ")
        instrument_key = f"{upstox_exchange}|{symbol.upper()}"
        data = self._get("/market-quote/quotes", params={"instrument_key": instrument_key})
        return data.get("data", {})
