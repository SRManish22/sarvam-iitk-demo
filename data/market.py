"""
data/market.py — Live market data from NSE public JSON API + yfinance fallback.

NSE API doesn't require an API key but needs browser-like session headers + cookies.
Always tries NSE first; falls back to yfinance if NSE is unreachable or rate-limited.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# NSE Session management
# ---------------------------------------------------------------------------

_nse_session: Optional[requests.Session] = None
_session_created_at: float = 0.0
SESSION_TTL = 300  # Refresh session cookies every 5 minutes


def _get_nse_session() -> requests.Session:
    """
    Return a requests.Session configured with browser-like headers and NSE cookies.

    NSE requires hitting the homepage first to set cookies before API calls work.
    Session is cached and refreshed every SESSION_TTL seconds.
    """
    global _nse_session, _session_created_at

    now = time.time()
    if _nse_session is None or (now - _session_created_at) > SESSION_TTL:
        session = requests.Session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
            "X-Requested-With": "XMLHttpRequest",
        }
        session.headers.update(headers)
        try:
            # Hit homepage to get session cookies
            session.get("https://www.nseindia.com", timeout=10)
            time.sleep(0.5)  # Brief pause to avoid rate limiting
        except Exception:
            pass  # Proceed with empty cookies — API might still work
        _nse_session = session
        _session_created_at = now

    return _nse_session


# ---------------------------------------------------------------------------
# Live Quote
# ---------------------------------------------------------------------------

def get_live_quote(symbol: str) -> dict:
    """
    Fetch live quote from NSE JSON API with yfinance fallback.

    Args:
        symbol: NSE stock ticker (e.g. "RELIANCE", "TCS"). Case-insensitive.

    Returns:
        dict with: symbol, ltp, change, change_pct, volume, delivery_pct,
                   high, low, open, prev_close, week_high_52, week_low_52,
                   market_cap, pe_ratio, timestamp, source.
    """
    symbol = symbol.upper().strip()

    # Try NSE first
    try:
        return _get_nse_quote(symbol)
    except Exception:
        pass

    # Fallback to yfinance
    return get_quote_yfinance(symbol)


def _get_nse_quote(symbol: str) -> dict:
    """Fetch quote from NSE equity quote API."""
    session = _get_nse_session()
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    resp = session.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    price_info = data.get("priceInfo", {})
    trade_info = data.get("tradeInfo", {})
    meta = data.get("metadata", {})

    ltp = price_info.get("lastPrice", 0)
    prev_close = price_info.get("previousClose", 0)
    change = round(ltp - prev_close, 2)
    change_pct = round((change / prev_close * 100) if prev_close else 0, 2)

    return {
        "symbol": symbol,
        "ltp": ltp,
        "change": change,
        "change_pct": change_pct,
        "volume": trade_info.get("totalTradedVolume", 0),
        "delivery_pct": trade_info.get("deliveryToTradedQuantity", 0),
        "high": price_info.get("intraDayHighLow", {}).get("max", 0),
        "low": price_info.get("intraDayHighLow", {}).get("min", 0),
        "open": price_info.get("open", 0),
        "prev_close": prev_close,
        "week_high_52": meta.get("high52", 0),
        "week_low_52": meta.get("low52", 0),
        "market_cap": meta.get("pdSymbolPe", 0),
        "pe_ratio": meta.get("pdSymbolPe", 0),
        "timestamp": datetime.now().isoformat(),
        "source": "NSE",
    }


def get_quote_yfinance(symbol: str) -> dict:
    """
    Fetch quote from yfinance (delayed data, 15-min lag).

    Args:
        symbol: NSE ticker. Automatically appends '.NS' if not present.

    Returns:
        dict in same format as _get_nse_quote.
    """
    import yfinance as yf

    ticker_sym = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    ticker = yf.Ticker(ticker_sym)
    info = ticker.fast_info

    try:
        ltp = float(info.last_price or 0)
        prev_close = float(info.previous_close or 0)
        change = round(ltp - prev_close, 2)
        change_pct = round((change / prev_close * 100) if prev_close else 0, 2)

        return {
            "symbol": symbol,
            "ltp": ltp,
            "change": change,
            "change_pct": change_pct,
            "volume": int(info.three_month_average_volume or 0),
            "delivery_pct": None,  # Not available via yfinance
            "high": float(info.day_high or 0),
            "low": float(info.day_low or 0),
            "open": float(info.open or 0),
            "prev_close": prev_close,
            "week_high_52": float(info.fifty_two_week_high or 0),
            "week_low_52": float(info.fifty_two_week_low or 0),
            "market_cap": float(info.market_cap or 0),
            "pe_ratio": None,
            "timestamp": datetime.now().isoformat(),
            "source": "yfinance (15-min delay)",
        }
    except Exception as e:
        raise RuntimeError(f"yfinance fallback also failed for {symbol}: {e}") from e


# ---------------------------------------------------------------------------
# Option Chain
# ---------------------------------------------------------------------------

def get_option_chain(symbol: str, expiry: str = None) -> dict:
    """
    Fetch option chain from NSE.

    For indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY):
        https://www.nseindia.com/api/option-chain-indices?symbol=<SYMBOL>
    For stocks:
        https://www.nseindia.com/api/option-chain-equities?symbol=<SYMBOL>

    Args:
        symbol: Index or stock ticker (e.g. "NIFTY", "RELIANCE").
        expiry: Optional expiry date filter "YYYY-MM-DD".

    Returns:
        dict with: symbol, expiry, expiries (list), strikes (list of floats),
                   calls (list of dicts), puts (list of dicts), pcr (float),
                   max_pain (float), atm_strike (float).
    """
    symbol = symbol.upper().strip()
    INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"}

    try:
        session = _get_nse_session()
        if symbol in INDEX_SYMBOLS:
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        else:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"

        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        return _parse_option_chain(symbol, raw, expiry)

    except Exception as e:
        # Return a minimal error response
        return {
            "symbol": symbol,
            "error": str(e),
            "expiries": [],
            "strikes": [],
            "calls": [],
            "puts": [],
            "pcr": None,
            "max_pain": None,
            "atm_strike": None,
            "source": "NSE (failed)",
        }


def _parse_option_chain(symbol: str, raw: dict, expiry_filter: str = None) -> dict:
    """Parse NSE option chain response into a clean dict."""
    records = raw.get("records", {})
    all_expiries = records.get("expiryDates", [])
    data = records.get("data", [])
    underlying_value = records.get("underlyingValue", 0)

    # Pick target expiry
    target_expiry = all_expiries[0] if all_expiries else None
    if expiry_filter and expiry_filter in all_expiries:
        target_expiry = expiry_filter

    # Filter data for selected expiry
    filtered = [
        row for row in data
        if target_expiry is None or row.get("expiryDate") == target_expiry
    ]

    calls = []
    puts = []
    strikes = set()
    total_call_oi = 0
    total_put_oi = 0

    for row in filtered:
        strike = row.get("strikePrice", 0)
        strikes.add(strike)

        if "CE" in row:
            ce = row["CE"]
            calls.append({
                "strike": strike,
                "ltp": ce.get("lastPrice", 0),
                "oi": ce.get("openInterest", 0),
                "change_oi": ce.get("changeinOpenInterest", 0),
                "volume": ce.get("totalTradedVolume", 0),
                "iv": ce.get("impliedVolatility", 0),
                "bid": ce.get("bidprice", 0),
                "ask": ce.get("askPrice", 0),
                "delta": None,  # Requires Black-Scholes calculation
            })
            total_call_oi += ce.get("openInterest", 0)

        if "PE" in row:
            pe = row["PE"]
            puts.append({
                "strike": strike,
                "ltp": pe.get("lastPrice", 0),
                "oi": pe.get("openInterest", 0),
                "change_oi": pe.get("changeinOpenInterest", 0),
                "volume": pe.get("totalTradedVolume", 0),
                "iv": pe.get("impliedVolatility", 0),
                "bid": pe.get("bidprice", 0),
                "ask": pe.get("askPrice", 0),
                "delta": None,
            })
            total_put_oi += pe.get("openInterest", 0)

    pcr = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else None

    # ATM strike = closest strike to underlying value
    sorted_strikes = sorted(strikes)
    atm_strike = min(sorted_strikes, key=lambda s: abs(s - underlying_value)) if sorted_strikes else None

    # Max pain = strike where total option buyers lose the most (simplified)
    max_pain = _calculate_max_pain(calls, puts, sorted_strikes)

    return {
        "symbol": symbol,
        "expiry": target_expiry,
        "expiries": all_expiries,
        "underlying_value": underlying_value,
        "strikes": sorted_strikes,
        "calls": sorted(calls, key=lambda x: x["strike"]),
        "puts": sorted(puts, key=lambda x: x["strike"]),
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "pcr": pcr,
        "max_pain": max_pain,
        "atm_strike": atm_strike,
        "timestamp": datetime.now().isoformat(),
        "source": "NSE",
    }


def _calculate_max_pain(calls: list, puts: list, strikes: list) -> Optional[float]:
    """
    Calculate max pain strike — the price at which total option buyers lose most.

    At each candidate strike, sum:
        Loss for CE holders = max(0, candidate_strike - strike) * oi  for all strikes < candidate
        Loss for PE holders = max(0, strike - candidate_strike) * oi  for all strikes > candidate
    Max pain = candidate_strike with minimum total payout to option holders.
    """
    if not strikes:
        return None

    call_map = {c["strike"]: c["oi"] for c in calls}
    put_map = {p["strike"]: p["oi"] for p in puts}

    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for candidate in strikes:
        total_pain = 0
        for s in strikes:
            # Call pain: CE buyers at strike s lose if candidate > s
            total_pain += max(0, candidate - s) * call_map.get(s, 0)
            # Put pain: PE buyers at strike s lose if candidate < s
            total_pain += max(0, s - candidate) * put_map.get(s, 0)
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = candidate

    return max_pain_strike


# ---------------------------------------------------------------------------
# Delivery data
# ---------------------------------------------------------------------------

def get_delivery_data(symbol: str) -> dict:
    """
    Fetch delivery % from NSE bulk/block deal data.

    High delivery % (> 50%) indicates strong conviction (buying/selling).
    Low delivery % suggests intraday/speculative activity.

    Args:
        symbol: NSE stock ticker.

    Returns:
        dict with: symbol, delivery_pct, delivery_qty, traded_qty, timestamp.
    """
    symbol = symbol.upper().strip()
    try:
        session = _get_nse_session()
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}&section=trade_info"
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        trade_info = data.get("deliveryTradeSummary", {})
        return {
            "symbol": symbol,
            "delivery_pct": trade_info.get("deliveryToTradedQuantity", None),
            "delivery_qty": trade_info.get("deliveryQuantity", None),
            "traded_qty": trade_info.get("totalTradedVolume", None),
            "timestamp": datetime.now().isoformat(),
            "source": "NSE",
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "NSE (failed)"}
