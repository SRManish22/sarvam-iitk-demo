"""
data/news.py — Financial news aggregator using free RSS feeds.

Sources:
  1. Google Finance RSS (no key required)
  2. Economic Times RSS (no key required)
  3. NewsAPI (optional — set NEWS_API_KEY in env for better results)

Falls back gracefully if any source fails.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus


def get_financial_news(symbol: str, limit: int = 5) -> list:
    """
    Fetch latest financial news for a symbol from multiple free sources.

    Priority:
    1. NewsAPI (if NEWS_API_KEY set)
    2. Google Finance RSS
    3. Economic Times RSS

    Args:
        symbol: Stock ticker or company name (e.g. "RELIANCE", "Infosys").
        limit: Number of news items to return (default 5, max 20).

    Returns:
        List of dicts with: title, source, published, url, summary.
        On error: [{"error": "<message>"}]
    """
    limit = min(limit, 20)
    results: list[dict] = []

    # Try NewsAPI first if key is available
    news_api_key = os.environ.get("NEWS_API_KEY")
    if news_api_key:
        try:
            news_api_results = _get_newsapi(symbol, limit, news_api_key)
            results.extend(news_api_results)
        except Exception:
            pass

    # Google Finance RSS
    if len(results) < limit:
        try:
            google_results = _get_google_finance_rss(symbol, limit - len(results))
            results.extend(google_results)
        except Exception:
            pass

    # Economic Times RSS (general — no symbol filter possible via ET RSS)
    if len(results) < limit:
        try:
            et_results = _get_et_rss(symbol, limit - len(results))
            results.extend(et_results)
        except Exception:
            pass

    if not results:
        return [{"error": "No news sources returned results", "symbol": symbol}]

    # Deduplicate by title, limit to requested count
    seen = set()
    deduped = []
    for item in results:
        title = item.get("title", "")
        if title not in seen:
            seen.add(title)
            deduped.append(item)
        if len(deduped) >= limit:
            break

    return deduped


def _get_google_finance_rss(symbol: str, limit: int) -> list:
    """
    Fetch news from Google News RSS for a stock query.

    RSS URL: https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en
    """
    import requests

    query = quote_plus(f"{symbol} stock NSE India")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    return _parse_rss(resp.text, source="Google News", limit=limit)


def _get_et_rss(symbol: str, limit: int) -> list:
    """
    Fetch news from Economic Times markets RSS feed.

    Filters results to those mentioning the symbol.
    """
    import requests

    url = "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    all_items = _parse_rss(resp.text, source="Economic Times", limit=50)

    # Filter to items mentioning the symbol or company
    sym_upper = symbol.upper()
    filtered = [
        item for item in all_items
        if sym_upper in item.get("title", "").upper()
        or sym_upper in item.get("summary", "").upper()
    ]

    # If no filtered results, return generic market news
    if not filtered:
        filtered = all_items

    return filtered[:limit]


def _get_newsapi(symbol: str, limit: int, api_key: str) -> list:
    """
    Fetch news from NewsAPI.org.

    Endpoint: https://newsapi.org/v2/everything
    """
    import requests

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f"{symbol} NSE stock India",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": limit,
        "apiKey": api_key,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for article in data.get("articles", []):
        results.append({
            "title": article.get("title", ""),
            "source": article.get("source", {}).get("name", "NewsAPI"),
            "published": article.get("publishedAt", ""),
            "url": article.get("url", ""),
            "summary": (article.get("description") or "")[:300],
        })
    return results


def _parse_rss(xml_text: str, source: str, limit: int) -> list:
    """
    Parse RSS/Atom XML and return list of news items.

    Handles both RSS 2.0 and basic Atom formats.
    """
    results = []
    try:
        root = ET.fromstring(xml_text)
        # Handle both RSS and Atom namespaces
        ns = {}
        if "feed" in root.tag:
            # Atom format
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            for entry in entries[:limit]:
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                published_el = entry.find("atom:published", ns)
                summary_el = entry.find("atom:summary", ns)
                results.append({
                    "title": title_el.text if title_el is not None else "",
                    "source": source,
                    "published": published_el.text if published_el is not None else "",
                    "url": link_el.get("href", "") if link_el is not None else "",
                    "summary": (summary_el.text or "")[:300] if summary_el is not None else "",
                })
        else:
            # RSS 2.0 format
            channel = root.find("channel")
            if channel is None:
                channel = root
            items = channel.findall("item")
            for item in items[:limit]:
                title_el = item.find("title")
                link_el = item.find("link")
                pubdate_el = item.find("pubDate")
                desc_el = item.find("description")
                results.append({
                    "title": title_el.text if title_el is not None else "",
                    "source": source,
                    "published": pubdate_el.text if pubdate_el is not None else "",
                    "url": link_el.text if link_el is not None else "",
                    "summary": _strip_html(
                        (desc_el.text or "")[:500] if desc_el is not None else ""
                    ),
                })
    except ET.ParseError:
        pass  # Return whatever we parsed so far

    return results


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()
