"""
data/technicals.py — Technical analysis using pandas-ta and yfinance.

Downloads OHLCV data from yfinance (.NS suffix for NSE stocks) and
computes a comprehensive set of indicators used in Indian equity trading.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd


def analyse(symbol: str, period: str = "3mo", interval: str = "1d") -> dict:
    """
    Download OHLCV data and compute technical indicators.

    Indicators computed:
    - RSI(14): momentum oscillator (overbought >70, oversold <30)
    - MACD(12,26,9): trend momentum and signal line crossover
    - Bollinger Bands(20,2): volatility channel
    - EMA 20, 50, 200: trend direction
    - ATR(14): average true range for stop-loss sizing
    - Volume z-score: (vol - vol_ma20) / vol_std — spike if z > 2
    - Support/Resistance: recent swing highs and lows

    Args:
        symbol: NSE ticker (e.g. "RELIANCE"). '.NS' appended automatically.
        period: yfinance period string — "1mo", "3mo", "6mo", "1y", "2y".
        interval: OHLCV interval — "1d", "1h", "15m".

    Returns:
        Comprehensive dict of indicators and textual signals.
    """
    import yfinance as yf

    ticker_sym = symbol.upper()
    if not ticker_sym.endswith(".NS") and not ticker_sym.endswith(".BO"):
        ticker_sym = f"{ticker_sym}.NS"

    df = yf.download(ticker_sym, period=period, interval=interval, progress=False, auto_adjust=True)

    if df.empty:
        return {"error": f"No data returned for {symbol}. Check ticker symbol.", "symbol": symbol}

    # Flatten MultiIndex columns if present (yfinance sometimes returns them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()
    if len(df) < 30:
        return {"error": f"Insufficient data for {symbol} ({len(df)} bars). Try a longer period.", "symbol": symbol}

    # ---- Import pandas_ta ----
    try:
        import pandas_ta as ta
    except ImportError:
        return {"error": "pandas-ta not installed. Run: pip install pandas-ta", "symbol": symbol}

    # ---- RSI ----
    rsi_series = ta.rsi(df["Close"], length=14)
    rsi = float(rsi_series.iloc[-1]) if rsi_series is not None and not rsi_series.empty else None

    # ---- MACD ----
    macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        macd_col = [c for c in macd_df.columns if "MACD_12" in c and "MACDs" not in c and "MACDh" not in c]
        macd_sig_col = [c for c in macd_df.columns if "MACDs" in c]
        macd_hist_col = [c for c in macd_df.columns if "MACDh" in c]
        macd_val = float(macd_df[macd_col[0]].iloc[-1]) if macd_col else None
        macd_signal = float(macd_df[macd_sig_col[0]].iloc[-1]) if macd_sig_col else None
        macd_hist = float(macd_df[macd_hist_col[0]].iloc[-1]) if macd_hist_col else None
    else:
        macd_val = macd_signal = macd_hist = None

    # ---- Bollinger Bands ----
    bb_df = ta.bbands(df["Close"], length=20, std=2)
    if bb_df is not None and not bb_df.empty:
        bb_upper_col = [c for c in bb_df.columns if "BBU" in c]
        bb_mid_col = [c for c in bb_df.columns if "BBM" in c]
        bb_lower_col = [c for c in bb_df.columns if "BBL" in c]
        bb_upper = float(bb_df[bb_upper_col[0]].iloc[-1]) if bb_upper_col else None
        bb_middle = float(bb_df[bb_mid_col[0]].iloc[-1]) if bb_mid_col else None
        bb_lower = float(bb_df[bb_lower_col[0]].iloc[-1]) if bb_lower_col else None
    else:
        bb_upper = bb_middle = bb_lower = None

    # ---- EMAs ----
    ema20 = _safe_ema(df["Close"], 20)
    ema50 = _safe_ema(df["Close"], 50)
    ema200 = _safe_ema(df["Close"], 200)

    # ---- ATR ----
    atr_series = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    atr = float(atr_series.iloc[-1]) if atr_series is not None and not atr_series.empty else None

    # ---- Volume Z-Score ----
    vol_ma = df["Volume"].rolling(20).mean()
    vol_std = df["Volume"].rolling(20).std()
    vol_zscore_series = (df["Volume"] - vol_ma) / vol_std
    vol_zscore = float(vol_zscore_series.iloc[-1]) if not vol_zscore_series.empty else None

    # ---- Current price ----
    price = float(df["Close"].iloc[-1])

    # ---- Support and Resistance ----
    support_levels, resistance_levels = _find_support_resistance(df)

    # ---- Generate textual signals ----
    signals = _generate_signals(
        price=price,
        rsi=rsi,
        macd_val=macd_val,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        vol_zscore=vol_zscore,
    )

    # ---- Overall trend ----
    trend = _determine_trend(price, ema20, ema50, ema200)

    return {
        "symbol": symbol,
        "price": round(price, 2),
        "rsi": round(rsi, 2) if rsi is not None else None,
        "macd": round(macd_val, 4) if macd_val is not None else None,
        "macd_signal": round(macd_signal, 4) if macd_signal is not None else None,
        "macd_hist": round(macd_hist, 4) if macd_hist is not None else None,
        "bb_upper": round(bb_upper, 2) if bb_upper is not None else None,
        "bb_middle": round(bb_middle, 2) if bb_middle is not None else None,
        "bb_lower": round(bb_lower, 2) if bb_lower is not None else None,
        "ema20": round(ema20, 2) if ema20 is not None else None,
        "ema50": round(ema50, 2) if ema50 is not None else None,
        "ema200": round(ema200, 2) if ema200 is not None else None,
        "atr": round(atr, 2) if atr is not None else None,
        "volume_zscore": round(vol_zscore, 2) if vol_zscore is not None else None,
        "support_levels": [round(s, 2) for s in support_levels],
        "resistance_levels": [round(r, 2) for r in resistance_levels],
        "signals": signals,
        "trend": trend,
        "data_bars": len(df),
        "period": period,
        "interval": interval,
        "timestamp": datetime.now().isoformat(),
        "source": "yfinance + pandas-ta",
    }


def detect_breakout(symbol: str) -> dict:
    """
    Detect if a stock is breaking out above 52-week high or recent resistance.

    Args:
        symbol: NSE stock ticker.

    Returns:
        dict with: symbol, is_breakout, breakout_type, current_price,
                   resistance_level, volume_confirmation.
    """
    import yfinance as yf

    ticker_sym = symbol.upper()
    if not ticker_sym.endswith(".NS"):
        ticker_sym = f"{ticker_sym}.NS"

    try:
        ticker = yf.Ticker(ticker_sym)
        df = yf.download(ticker_sym, period="1y", interval="1d", progress=False, auto_adjust=True)

        if df.empty:
            return {"error": f"No data for {symbol}", "symbol": symbol}

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        price = float(df["Close"].iloc[-1])
        high_52w = float(df["High"].max())
        high_50d = float(df["High"].iloc[-50:].max()) if len(df) >= 50 else high_52w

        is_52w_breakout = price >= (high_52w * 0.995)  # Within 0.5% of 52W high
        is_50d_breakout = price >= (high_50d * 0.995)

        vol_today = float(df["Volume"].iloc[-1])
        vol_avg_20 = float(df["Volume"].iloc[-20:].mean())
        vol_confirmation = vol_today > (vol_avg_20 * 1.5)

        return {
            "symbol": symbol,
            "current_price": round(price, 2),
            "high_52_week": round(high_52w, 2),
            "high_50_day": round(high_50d, 2),
            "is_52w_breakout": is_52w_breakout,
            "is_50d_breakout": is_50d_breakout,
            "is_breakout": is_52w_breakout or is_50d_breakout,
            "breakout_type": (
                "52-Week High Breakout" if is_52w_breakout
                else "50-Day High Breakout" if is_50d_breakout
                else "No Breakout"
            ),
            "volume_confirmation": vol_confirmation,
            "today_volume": int(vol_today),
            "avg_volume_20d": int(vol_avg_20),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def calculate_atr_stoploss(symbol: str, multiplier: float = 2.0) -> dict:
    """
    Calculate an ATR-based stop-loss level.

    Stop-loss = current_price - (ATR(14) * multiplier)

    Args:
        symbol: NSE stock ticker.
        multiplier: ATR multiplier for stop-loss distance (default 2.0).

    Returns:
        dict with: symbol, price, atr, multiplier, stop_loss_long, stop_loss_short.
    """
    import yfinance as yf

    ticker_sym = symbol.upper()
    if not ticker_sym.endswith(".NS"):
        ticker_sym = f"{ticker_sym}.NS"

    try:
        import pandas_ta as ta

        df = yf.download(ticker_sym, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return {"error": f"No data for {symbol}", "symbol": symbol}

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        atr_series = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        atr = float(atr_series.iloc[-1]) if atr_series is not None and not atr_series.empty else None
        price = float(df["Close"].iloc[-1])

        if atr is None:
            return {"error": "ATR calculation failed", "symbol": symbol}

        stop_loss_long = round(price - (atr * multiplier), 2)
        stop_loss_short = round(price + (atr * multiplier), 2)

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "atr_14": round(atr, 2),
            "multiplier": multiplier,
            "stop_loss_long": stop_loss_long,   # For long (buy) trades
            "stop_loss_short": stop_loss_short,  # For short (sell) trades
            "stop_distance_pct": round((atr * multiplier / price) * 100, 2),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_ema(series: pd.Series, length: int) -> Optional[float]:
    """Compute EMA safely, returning None if insufficient data."""
    try:
        import pandas_ta as ta
        ema_series = ta.ema(series, length=length)
        if ema_series is not None and not ema_series.empty and not pd.isna(ema_series.iloc[-1]):
            return float(ema_series.iloc[-1])
    except Exception:
        pass
    return None


def _find_support_resistance(df: pd.DataFrame, window: int = 10, n_levels: int = 3) -> tuple:
    """
    Find support and resistance levels from swing highs and lows.

    Uses a rolling window to find local maxima (resistance) and minima (support).

    Returns:
        Tuple of (support_levels, resistance_levels) sorted lists.
    """
    price = float(df["Close"].iloc[-1])
    highs = []
    lows = []

    for i in range(window, len(df) - window):
        window_high = df["High"].iloc[i - window:i + window].max()
        window_low = df["Low"].iloc[i - window:i + window].min()

        if df["High"].iloc[i] == window_high:
            highs.append(float(df["High"].iloc[i]))
        if df["Low"].iloc[i] == window_low:
            lows.append(float(df["Low"].iloc[i]))

    # Cluster nearby levels (within 0.5% of each other)
    resistance = _cluster_levels([h for h in highs if h > price])[:n_levels]
    support = _cluster_levels([l for l in lows if l < price])[-n_levels:]

    return sorted(support), sorted(resistance)


def _cluster_levels(levels: list, tolerance: float = 0.005) -> list:
    """Cluster nearby price levels to remove duplicates."""
    if not levels:
        return []
    levels = sorted(levels)
    clustered = [levels[0]]
    for level in levels[1:]:
        if abs(level - clustered[-1]) / clustered[-1] > tolerance:
            clustered.append(level)
    return clustered


def _generate_signals(
    price: float,
    rsi: Optional[float],
    macd_val: Optional[float],
    macd_signal: Optional[float],
    macd_hist: Optional[float],
    bb_upper: Optional[float],
    bb_lower: Optional[float],
    ema20: Optional[float],
    ema50: Optional[float],
    ema200: Optional[float],
    vol_zscore: Optional[float],
) -> list:
    """Generate a list of textual trading signals based on indicator values."""
    signals = []

    # RSI signals
    if rsi is not None:
        if rsi > 70:
            signals.append(f"RSI {rsi:.1f} — Overbought zone (>70). Caution for longs.")
        elif rsi < 30:
            signals.append(f"RSI {rsi:.1f} — Oversold zone (<30). Watch for reversal.")
        elif 50 < rsi <= 70:
            signals.append(f"RSI {rsi:.1f} — Bullish momentum (50-70 range).")
        elif 30 <= rsi < 50:
            signals.append(f"RSI {rsi:.1f} — Bearish momentum (30-50 range).")

    # MACD signals
    if macd_val is not None and macd_signal is not None:
        if macd_val > macd_signal:
            signals.append("MACD bullish crossover — Positive momentum.")
        else:
            signals.append("MACD bearish crossover — Negative momentum.")
        if macd_hist is not None and macd_hist > 0:
            signals.append(f"MACD histogram positive ({macd_hist:.4f}) — Momentum strengthening.")
        elif macd_hist is not None:
            signals.append(f"MACD histogram negative ({macd_hist:.4f}) — Momentum weakening.")

    # Bollinger Band signals
    if bb_upper is not None and bb_lower is not None:
        if price >= bb_upper:
            signals.append(f"Price touching Upper Bollinger Band ({bb_upper:.2f}) — Possible mean reversion or breakout.")
        elif price <= bb_lower:
            signals.append(f"Price touching Lower Bollinger Band ({bb_lower:.2f}) — Possible bounce or breakdown.")
        else:
            band_pct = (price - bb_lower) / (bb_upper - bb_lower) * 100
            signals.append(f"Price at {band_pct:.0f}% of Bollinger Band range.")

    # EMA signals
    if ema20 is not None:
        signals.append(f"EMA20: {ema20:.2f} — Price {'above' if price > ema20 else 'below'} (short-term trend: {'bullish' if price > ema20 else 'bearish'}).")
    if ema50 is not None:
        signals.append(f"EMA50: {ema50:.2f} — Price {'above' if price > ema50 else 'below'} (medium-term trend: {'bullish' if price > ema50 else 'bearish'}).")
    if ema200 is not None:
        signals.append(f"EMA200: {ema200:.2f} — Price {'above' if price > ema200 else 'below'} (long-term trend: {'bullish' if price > ema200 else 'bearish'}).")

    # EMA Golden/Death cross
    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            signals.append("EMA20 > EMA50 — Golden cross zone (bullish).")
        else:
            signals.append("EMA20 < EMA50 — Death cross zone (bearish).")

    # Volume signals
    if vol_zscore is not None:
        if vol_zscore > 2:
            signals.append(f"Volume z-score {vol_zscore:.1f} — ABNORMAL VOLUME SPIKE. High activity, possible breakout/breakdown.")
        elif vol_zscore > 1:
            signals.append(f"Volume z-score {vol_zscore:.1f} — Above-average volume. Watch for direction confirmation.")
        elif vol_zscore < -1:
            signals.append(f"Volume z-score {vol_zscore:.1f} — Below-average volume. Low conviction move.")

    return signals


def _determine_trend(
    price: float,
    ema20: Optional[float],
    ema50: Optional[float],
    ema200: Optional[float],
) -> str:
    """Determine overall trend based on EMA stack."""
    bullish_count = 0
    bearish_count = 0

    for ema in [ema20, ema50, ema200]:
        if ema is not None:
            if price > ema:
                bullish_count += 1
            else:
                bearish_count += 1

    if bullish_count == 3:
        return "Strong Uptrend"
    elif bullish_count == 2:
        return "Uptrend"
    elif bullish_count == 1:
        return "Downtrend"
    elif bearish_count == 3:
        return "Strong Downtrend"
    else:
        return "Sideways/Consolidation"
