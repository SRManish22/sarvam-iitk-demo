"""
agent/tools.py — Tool functions for Vyapar Copilot agent.

Each function calls the actual implementation from data/ or risk/ modules.
All functions return JSON-serializable dicts/lists.
Exceptions are caught and returned as {"error": str(e)}.

Also defines TOOLS_SCHEMA — OpenAI-compatible function calling schema.
"""

from __future__ import annotations
import json


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_quote(symbol: str) -> dict:
    """
    Fetch live NSE/BSE quote for a symbol.

    Args:
        symbol: Stock ticker symbol (e.g. "RELIANCE", "TCS", "NIFTY").

    Returns:
        dict with keys: symbol, ltp, change, change_pct, volume, delivery_pct,
                        high, low, open, prev_close, timestamp, source.
        On error: {"error": "<message>"}
    """
    try:
        from data.market import get_live_quote
        return get_live_quote(symbol)
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_option_chain(symbol: str, expiry: str = None) -> dict:
    """
    Fetch options chain with OI, IV, and LTP for CE/PE across all strikes.

    Args:
        symbol: Index or stock ticker (e.g. "NIFTY", "BANKNIFTY", "RELIANCE").
        expiry: Optional expiry date string "YYYY-MM-DD". Defaults to nearest expiry.

    Returns:
        dict with keys: symbol, expiry, expiries (list), strikes (list),
                        calls (list of dicts), puts (list of dicts), pcr (float),
                        max_pain (float), atm_strike (float).
        On error: {"error": "<message>"}
    """
    try:
        from data.market import get_option_chain as _get_option_chain
        return _get_option_chain(symbol, expiry)
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_news(symbol: str, limit: int = 5) -> list:
    """
    Fetch latest financial news headlines for the symbol.

    Args:
        symbol: Stock ticker or company name.
        limit: Number of news items to return (default 5).

    Returns:
        List of dicts with keys: title, source, published, url, summary.
        On error: [{"error": "<message>"}]
    """
    try:
        from data.news import get_financial_news
        return get_financial_news(symbol, limit)
    except Exception as e:
        return [{"error": str(e), "symbol": symbol}]


def analyse_technicals(symbol: str, period: str = "3mo") -> dict:
    """
    Run comprehensive technical analysis on a stock.

    Args:
        symbol: NSE stock ticker (e.g. "RELIANCE"). Automatically appends .NS for yfinance.
        period: Data period — "1mo", "3mo", "6mo", "1y", "2y" (default "3mo").

    Returns:
        dict with keys: symbol, rsi, macd, macd_signal, macd_hist,
                        bb_upper, bb_middle, bb_lower, price, ema20, ema50, ema200,
                        atr, volume_zscore, support_levels, resistance_levels,
                        signals (list of textual signals), trend (str), timestamp.
        On error: {"error": "<message>"}
    """
    try:
        from data.technicals import analyse
        return analyse(symbol, period)
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_filings(symbol: str, limit: int = 3) -> list:
    """
    Fetch latest NSE corporate filings and announcements for the symbol.

    Args:
        symbol: NSE stock ticker.
        limit: Number of filings to return (default 3).

    Returns:
        List of dicts with keys: date, headline, category, attachment_url.
        On error: [{"error": "<message>"}]
    """
    try:
        from data.filings import get_corporate_announcements
        return get_corporate_announcements(symbol, limit)
    except Exception as e:
        return [{"error": str(e), "symbol": symbol}]


def calculate_risk(
    symbol: str,
    entry: float,
    stop_loss: float,
    target: float,
    capital: float,
    risk_pct: float = 1.0,
) -> dict:
    """
    Calculate position size, R:R ratio, max loss, and margin required.

    Args:
        symbol: Stock ticker (for margin estimation).
        entry: Entry price per share.
        stop_loss: Stop-loss price per share.
        target: Target price per share.
        capital: Total trading capital in INR.
        risk_pct: Percentage of capital to risk on this trade (default 1.0%).

    Returns:
        dict with keys: symbol, entry, stop_loss, target, capital, risk_pct,
                        quantity, risk_amount, max_loss, capital_deployed,
                        rr_ratio, is_rr_acceptable, risk_points, reward_points,
                        required_margin, is_margin_sufficient.
        On error: {"error": "<message>"}
    """
    try:
        from risk.engine import calculate_position, check_risk_reward, check_sebi_margin
        pos = calculate_position(capital, entry, stop_loss, risk_pct)
        rr = check_risk_reward(entry, stop_loss, target)
        margin = check_sebi_margin(symbol, pos["quantity"], entry, capital * 0.5)
        return {
            "symbol": symbol,
            "entry": entry,
            "stop_loss": stop_loss,
            "target": target,
            "capital": capital,
            "risk_pct": risk_pct,
            **pos,
            **rr,
            **margin,
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def place_order(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str,
    price: float = None,
    stop_loss: float = None,
    target: float = None,
) -> dict:
    """
    Place an order via the configured broker (defaults to mock broker).

    Args:
        symbol: NSE stock ticker.
        side: "BUY" or "SELL".
        quantity: Number of shares/lots.
        order_type: "MARKET", "LIMIT", "SL", "SL-M".
        price: Limit price (required for LIMIT/SL orders).
        stop_loss: Stop-loss trigger price.
        target: Target price for bracket orders.

    Returns:
        dict with keys: order_id, status, symbol, side, quantity, order_type,
                        price, stop_loss, target, timestamp, broker.
        On error: {"error": "<message>"}
    """
    try:
        from broker.mock import MockBroker
        broker = MockBroker()
        return broker.place_order(
            symbol=symbol,
            exchange="NSE",
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_loss=stop_loss,
            target=target,
        )
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# OpenAI-compatible function calling schema
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": (
                "Fetch live NSE/BSE quote for a stock or index. "
                "Returns LTP, change%, volume, delivery%, high/low/open/prev_close."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE/BSE stock ticker symbol, e.g. 'RELIANCE', 'TCS', 'NIFTY', 'BANKNIFTY'.",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_option_chain",
            "description": (
                "Fetch the full options chain for a stock or index. "
                "Returns OI, IV, LTP for all CE/PE strikes, PCR, max pain, and ATM strike."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Index or stock ticker, e.g. 'NIFTY', 'BANKNIFTY', 'RELIANCE'.",
                    },
                    "expiry": {
                        "type": "string",
                        "description": "Expiry date in YYYY-MM-DD format. If omitted, uses nearest expiry.",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": (
                "Fetch latest financial news headlines for a stock or company. "
                "Returns title, source, published date, URL, and summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker or company name, e.g. 'RELIANCE', 'Infosys'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of news articles to return (default 5, max 20).",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyse_technicals",
            "description": (
                "Run comprehensive technical analysis on a stock: RSI, MACD, Bollinger Bands, "
                "EMA 20/50/200, ATR, volume z-score, support/resistance levels, and trend signals."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock ticker, e.g. 'RELIANCE', 'HDFCBANK', 'NIFTY'.",
                    },
                    "period": {
                        "type": "string",
                        "description": "Data period: '1mo', '3mo', '6mo', '1y', '2y'. Default '3mo'.",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_filings",
            "description": (
                "Fetch latest NSE corporate announcements and filings for a stock. "
                "Includes date, headline, category, and attachment URL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock ticker, e.g. 'RELIANCE'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of filings to return (default 3).",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_risk",
            "description": (
                "Calculate position sizing, Risk:Reward ratio, max loss, and margin required for a trade setup. "
                "Uses fixed-fraction position sizing based on capital and risk percentage."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock ticker for margin estimation.",
                    },
                    "entry": {
                        "type": "number",
                        "description": "Entry price per share in INR.",
                    },
                    "stop_loss": {
                        "type": "number",
                        "description": "Stop-loss price per share in INR.",
                    },
                    "target": {
                        "type": "number",
                        "description": "Target price per share in INR.",
                    },
                    "capital": {
                        "type": "number",
                        "description": "Total trading capital in INR.",
                    },
                    "risk_pct": {
                        "type": "number",
                        "description": "Percentage of capital to risk on this trade (default 1.0).",
                    },
                },
                "required": ["symbol", "entry", "stop_loss", "target", "capital"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": (
                "Place a buy or sell order via the configured broker. "
                "Defaults to mock broker for testing. Supports MARKET, LIMIT, SL, SL-M order types."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock ticker.",
                    },
                    "side": {
                        "type": "string",
                        "enum": ["BUY", "SELL"],
                        "description": "Order direction: BUY or SELL.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of shares or lots.",
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["MARKET", "LIMIT", "SL", "SL-M"],
                        "description": "Order type.",
                    },
                    "price": {
                        "type": "number",
                        "description": "Limit price in INR (required for LIMIT/SL orders).",
                    },
                    "stop_loss": {
                        "type": "number",
                        "description": "Stop-loss trigger price in INR.",
                    },
                    "target": {
                        "type": "number",
                        "description": "Target price for bracket orders in INR.",
                    },
                },
                "required": ["symbol", "side", "quantity", "order_type"],
            },
        },
    },
]
