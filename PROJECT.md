# Vyapar Copilot — Indian Equities Trade Assistant

> An AI-powered trade assistant for Indian equity markets, built with Sarvam AI's multilingual models and integrated with NSE/BSE data, technical analysis, risk management, and broker APIs.

---

## What It Is

**Vyapar Copilot** is a voice-and-text AI agent designed specifically for Indian retail traders and investors. It speaks fluent **Hinglish** (Hindi + English code-mixed), understands the nuances of NSE/BSE markets, F&O dynamics, SEBI regulations, and helps traders:

- Analyse stocks and options in real time
- Generate trade setups with entry, stop-loss, and target levels
- Size positions correctly based on capital and risk tolerance
- Place orders via connected broker APIs (or simulate with mock broker)
- Stay updated on corporate filings, news, and macro events

---

## Features

### 📊 Multimodal Market Signals
- **Live quotes** from NSE public JSON API (no key required) with yfinance fallback
- **Options chain** with OI buildup, PCR (Put-Call Ratio), max pain, IV skew
- **Open Interest (OI) analysis**: unusual OI changes, OI concentration at strikes
- **Delivery %**: high delivery signals strong conviction moves

### 📈 Technical Analysis (pandas-ta)
- RSI(14): overbought/oversold signals
- MACD(12,26,9): trend momentum and crossovers
- Bollinger Bands(20,2): price squeeze and breakout detection
- EMA 20/50/200: trend direction and crossovers
- ATR(14): volatility-based stop-loss placement
- Volume z-score: abnormal volume spike detection (z > 2 = significant)
- Support/Resistance: swing high/low detection
- 52-week breakout detection

### 🏢 Corporate Filings & News
- NSE corporate announcements scraper (no API key)
- Quarterly results fetcher
- Google Finance RSS + Economic Times RSS news aggregation
- Optional NewsAPI integration if `NEWS_API_KEY` env var is set

### ⚖️ Risk Engine
- Fixed-fraction position sizing (risk % of capital)
- Risk:Reward ratio validation (minimum 1.5:1 required)
- SEBI margin guard (simplified 20% SPAN placeholder)
- Full pre-trade validation with multi-point checks

### 🏦 Broker Integration
| Broker | Status | Notes |
|--------|--------|-------|
| Mock Broker | ✅ Ready | No credentials needed, for testing |
| Upstox V2 | 🔧 Stub | Real API shape, needs `UPSTOX_ACCESS_TOKEN` |
| Angel One SmartAPI | 🔧 Stub | Real API shape, needs `ANGEL_API_KEY` etc. |
| Zerodha Kite | 🗺️ Roadmap | To be added |
| 5paisa | 🗺️ Roadmap | To be added |

### 🎙️ Voice Interface (Sarvam AI)
- **STT**: Sarvam `saaras:v4` — speech-to-text with Hinglish codemix support
- **TTS**: Sarvam `bulbul:v4-flash` — natural Hindi/Hinglish text-to-speech
- Microphone recording via `pyaudio` → WAV → transcription
- Domain-specific keyterms boosting: Nifty, BankNifty, SEBI, NSE, BSE, F&O

### 🤖 AI Agent (Sarvam AI)
- Powered by `sarvam-105b-conversations` model
- Tool-calling agent loop (function calling)
- Maintains conversation history for context
- Hinglish-native responses
- Always includes risk warnings and disclaimers

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ui/cli.py                               │
│              Text REPL  |  Voice REPL (mic + TTS)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    agent/copilot.py                             │
│              VyaparCopilot — Agentic Loop                       │
│   ┌─────────────────┐        ┌──────────────────────────────┐   │
│   │  Sarvam AI LLM  │◄──────►│  Tool Dispatcher (TOOL_MAP)  │   │
│   │  sarvam-105b    │        └──────────────────────────────┘   │
│   └─────────────────┘                    │                      │
└──────────────────────────────────────────┼──────────────────────┘
                                           │
        ┌──────────┬──────────┬────────────┼──────────┬──────────┐
        │          │          │            │          │          │
┌───────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌────▼───┐ ┌────▼──┐ ┌────▼──┐
│data/     │ │data/    │ │data/   │ │data/   │ │risk/  │ │broker/│
│market.py │ │filings  │ │news.py │ │techni- │ │engine │ │*.py   │
│NSE API   │ │.py      │ │RSS+    │ │cals.py │ │.py    │       │
│yfinance  │ │NSE EDGAR│ │NewsAPI │ │pandas- │ │SEBI   │ │Mock/  │
└──────────┘ └─────────┘ └────────┘ │ta      │ │guard  │ │Upstox/│
                                     └────────┘ └───────┘ │Angel  │
                                                           └───────┘

┌───────────────────────────────────────┐
│            voice/                     │
│  stt.py (saaras:v4)  tts.py (bulbul) │
│  Hinglish STT        Hindi TTS        │
└───────────────────────────────────────┘
```

### Data Flow

1. User speaks/types a query (e.g., "RELIANCE mein entry leni chahiye kya?")
2. If voice: `voice/stt.py` transcribes audio → text
3. `agent/copilot.py` sends to Sarvam LLM with conversation history
4. LLM decides which tools to call → tool calls dispatched
5. Tools call `data/`, `risk/`, `broker/` modules → results returned
6. LLM synthesizes final Hinglish response with Signal/Setup/Risk/Action sections
7. If voice: `voice/tts.py` converts reply to audio → plays back

---

## How to Run

### Prerequisites

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Required
SARVAM_API_KEY=your_sarvam_api_key

# Optional — for real broker trading
UPSTOX_API_KEY=your_upstox_api_key
UPSTOX_SECRET=your_upstox_secret
UPSTOX_ACCESS_TOKEN=your_upstox_access_token

ANGEL_API_KEY=your_angel_api_key
ANGEL_CLIENT_ID=your_client_id
ANGEL_PASSWORD=your_password
ANGEL_TOTP_SECRET=your_totp_secret_base32

# Optional — for better news
NEWS_API_KEY=your_newsapi_org_key
```

### Run Text Mode

```bash
cd "c:\Users\Admin\Documents\Antigravity Projects\sarvam-iitk-demo"
python ui/cli.py
```

### Run Voice Mode

```bash
python ui/cli.py --voice
```

### Example Queries

```
You: RELIANCE ka technical analysis karo
You: Nifty 50 ke liye option chain dikhao
You: TCS mein entry 3500 pe, stop-loss 3400, target 3700 — risk kya hai?
You: HDFC Bank ka latest news aur filings batao
You: Agar mere paas 5 lakh capital hai, 1% risk pe INFY mein position size kya hogi?
```

---

## Sarvam AI APIs Used

| API | Model | Purpose |
|-----|-------|---------|
| Chat Completions | `sarvam-105b-conversations` | Core agent reasoning, Hinglish responses |
| Speech-to-Text | `saaras:v4` | Voice input transcription (codemix mode) |
| Text-to-Speech | `bulbul:v4-flash` | Hindi/Hinglish voice output |

**Key Sarvam Advantage**: Native Hinglish support — the model understands and responds in code-mixed Hindi+English naturally, making it feel like talking to a knowledgeable Indian trader/analyst.

---

## Project Structure

```
sarvam-iitk-demo/
├── PROJECT.md                  # This file
├── requirements.txt            # Python dependencies
├── main.py                     # Sarvam API smoke test (do not delete)
├── .env                        # API keys (git-ignored)
│
├── agent/
│   ├── __init__.py
│   ├── copilot.py              # Core agent loop (VyaparCopilot class)
│   ├── tools.py                # Tool functions + TOOLS_SCHEMA
│   └── prompts.py              # System prompt (Hinglish, trade analyst persona)
│
├── data/
│   ├── __init__.py
│   ├── market.py               # NSE JSON API + yfinance quotes & option chain
│   ├── filings.py              # NSE corporate filings scraper
│   ├── news.py                 # Google Finance RSS + ET RSS + NewsAPI
│   └── technicals.py          # pandas-ta: RSI, MACD, BB, volume z-score, etc.
│
├── risk/
│   ├── __init__.py
│   └── engine.py               # Position sizing, R:R, SEBI margin guard
│
├── broker/
│   ├── __init__.py
│   ├── base.py                 # Abstract broker interface
│   ├── mock.py                 # Mock broker (always succeeds, logs orders)
│   ├── upstox.py               # Upstox V2 adapter stub
│   └── angel.py                # Angel One SmartAPI adapter stub
│
├── voice/
│   ├── __init__.py
│   ├── stt.py                  # Sarvam saaras:v4 STT
│   └── tts.py                  # Sarvam bulbul:v4-flash TTS
│
└── ui/
    ├── __init__.py
    └── cli.py                  # Main entry point — text+voice REPL
```

---

## Roadmap

### Phase 1 — Prototype (Current) ✅
- [x] Core agent loop with tool calling
- [x] NSE market data (quotes, option chain)
- [x] Technical analysis (RSI, MACD, BB, volume)
- [x] Risk engine (position sizing, R:R, margin)
- [x] Mock broker for testing
- [x] Voice I/O (Sarvam STT + TTS)
- [x] Hinglish CLI REPL

### Phase 2 — Alpha
- [ ] Real Upstox/Angel broker integration
- [ ] Options Greeks (Delta, Gamma, Vega, Theta) via NSE data
- [ ] OI change analysis and max pain calculation
- [ ] Sector rotation dashboard
- [ ] Portfolio P&L tracking
- [ ] Zerodha Kite adapter

### Phase 3 — Beta
- [ ] Streamlit/Gradio web UI with charts
- [ ] Automated pre-market scan (top movers, breakouts, unusual OI)
- [ ] WhatsApp Bot integration via Twilio
- [ ] Push alerts for trade triggers
- [ ] Backtesting engine for strategies

### Phase 4 — Production
- [ ] Multi-user support with authentication
- [ ] Cloud deployment (GCP/AWS)
- [ ] SEBI-compliant disclaimer and logging
- [ ] Paper trading mode with full PnL tracking
- [ ] Integration with premium data (Refinitiv, Bloomberg)
- [ ] Mobile app (React Native)

---

## Disclaimer

> **This tool is for educational and informational purposes only. It does not constitute investment advice. Trading in equities and derivatives involves significant risk of loss. Past performance does not guarantee future results. Always consult a SEBI-registered investment advisor before making trading decisions.**

---

*Built with ❤️ for Indian traders — using Sarvam AI's multilingual models*
