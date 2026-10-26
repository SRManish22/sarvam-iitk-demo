"""
broker/base.py — Abstract base class for all broker adapters.

All broker implementations must inherit from BrokerBase and implement
all abstract methods. This ensures a uniform interface across brokers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BrokerBase(ABC):
    """
    Abstract broker interface for Vyapar Copilot.

    Concrete implementations: MockBroker, UpstoxBroker, AngelBroker.
    """

    @abstractmethod
    def get_profile(self) -> dict:
        """
        Fetch the logged-in user's profile.

        Returns:
            dict with: client_id, name, email, mobile, exchanges, products.
        """
        ...

    @abstractmethod
    def get_funds(self) -> dict:
        """
        Fetch available funds and margin.

        Returns:
            dict with: available_margin, used_margin, total_balance,
                       equity_margin, commodity_margin.
        """
        ...

    @abstractmethod
    def get_positions(self) -> list:
        """
        Fetch current open positions (intraday MIS positions).

        Returns:
            List of dicts with: symbol, exchange, product, side, quantity,
                                avg_price, ltp, pnl, value.
        """
        ...

    @abstractmethod
    def get_holdings(self) -> list:
        """
        Fetch long-term holdings (delivery CNC positions).

        Returns:
            List of dicts with: symbol, exchange, quantity, avg_price,
                                ltp, current_value, pnl, pnl_pct, isin.
        """
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        exchange: str,
        side: str,
        quantity: int,
        order_type: str,
        price: float = None,
        stop_loss: float = None,
        target: float = None,
        product: str = "MIS",
    ) -> dict:
        """
        Place an order with the broker.

        Args:
            symbol: NSE/BSE stock ticker.
            exchange: "NSE" or "BSE".
            side: "BUY" or "SELL".
            quantity: Number of shares.
            order_type: "MARKET", "LIMIT", "SL", "SL-M".
            price: Limit price (required for LIMIT and SL orders).
            stop_loss: Stop-loss trigger price.
            target: Target price (for bracket orders, if supported).
            product: "MIS" (intraday), "CNC" (delivery), "NRML" (F&O overnight).

        Returns:
            dict with: order_id, status, symbol, side, quantity, order_type,
                       price, exchange, product, timestamp.
        """
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict:
        """
        Fetch status of an order by ID.

        Args:
            order_id: Unique order identifier returned by place_order.

        Returns:
            dict with: order_id, status, filled_qty, pending_qty, avg_price,
                       symbol, side, exchange, timestamp.
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel.

        Returns:
            dict with: order_id, status ("CANCELLED"), message.
        """
        ...
