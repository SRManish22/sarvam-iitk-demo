"""
data/filings.py — NSE corporate filings and announcements scraper.

Uses NSE public JSON APIs (no API key required).
Falls back to empty list with error message on failure.
"""

from __future__ import annotations

from datetime import datetime

import requests


def _get_nse_session() -> requests.Session:
    """Import and return cached NSE session from market module."""
    from data.market import _get_nse_session as _market_session
    return _market_session()


def get_corporate_announcements(symbol: str, limit: int = 5) -> list:
    """
    Fetch latest corporate announcements from NSE EDGAR.

    Endpoint:
        https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=<SYMBOL>

    Args:
        symbol: NSE stock ticker (e.g. "RELIANCE").
        limit: Maximum number of announcements to return (default 5).

    Returns:
        List of dicts with: date, headline, category, attachment_url, symbol.
        On error: [{"error": "<message>", "symbol": symbol}]
    """
    symbol = symbol.upper().strip()
    try:
        session = _get_nse_session()
        url = (
            "https://www.nseindia.com/api/corporate-announcements"
            f"?index=equities&symbol={symbol}"
        )
        resp = session.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data[:limit]:
            results.append({
                "symbol": symbol,
                "date": item.get("sort_date", item.get("excl_date", "")),
                "headline": item.get("desc", item.get("subject", "No headline")),
                "category": item.get("anncCateg", item.get("sm_name", "General")),
                "attachment_url": item.get("attchmntFile", ""),
                "company": item.get("sm_isin", ""),
                "source": "NSE",
            })

        return results if results else [{"symbol": symbol, "message": "No announcements found"}]

    except Exception as e:
        return [{"error": str(e), "symbol": symbol, "source": "NSE (failed)"}]


def get_quarterly_results(symbol: str) -> dict:
    """
    Fetch latest quarterly financial results from NSE.

    Endpoint:
        https://www.nseindia.com/api/financial-results?symbol=<SYMBOL>&fin_type=Quarterly

    Args:
        symbol: NSE stock ticker.

    Returns:
        dict with: symbol, period, revenue, profit, eps, yoy_growth (if available).
        On error: {"error": "<message>", "symbol": symbol}
    """
    symbol = symbol.upper().strip()
    try:
        session = _get_nse_session()
        url = (
            "https://www.nseindia.com/api/financial-results"
            f"?symbol={symbol}&fin_type=Quarterly"
        )
        resp = session.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        # NSE returns nested data; structure varies by company
        items = data.get("data", data) if isinstance(data, dict) else data
        if not items:
            return {"symbol": symbol, "message": "No financial results found"}

        latest = items[0] if isinstance(items, list) else items

        return {
            "symbol": symbol,
            "period": latest.get("toDate", latest.get("re_rslt_dt", "")),
            "revenue": latest.get("re_sales_turnover", latest.get("income", None)),
            "profit": latest.get("re_profit_after_tax", latest.get("profit", None)),
            "eps": latest.get("re_basic_eps_excluding_ei", None),
            "yoy_growth": None,  # Requires comparison with prior year — add if needed
            "raw": latest,  # Include raw data for agent to extract more fields
            "source": "NSE",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": str(e), "symbol": symbol, "source": "NSE (failed)"}


def get_board_meetings(symbol: str, limit: int = 3) -> list:
    """
    Fetch upcoming or recent board meeting announcements for a stock.

    Args:
        symbol: NSE stock ticker.
        limit: Number of entries to return.

    Returns:
        List of board meeting details.
    """
    symbol = symbol.upper().strip()
    try:
        session = _get_nse_session()
        url = (
            "https://www.nseindia.com/api/corporate-announcements"
            f"?index=equities&symbol={symbol}&category=board-meeting"
        )
        resp = session.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data[:limit]:
            results.append({
                "symbol": symbol,
                "date": item.get("sort_date", ""),
                "purpose": item.get("desc", "Board Meeting"),
                "attachment_url": item.get("attchmntFile", ""),
                "source": "NSE",
            })
        return results if results else [{"symbol": symbol, "message": "No board meetings found"}]

    except Exception as e:
        return [{"error": str(e), "symbol": symbol}]
