#!/usr/bin/env python3
"""
ui/cli.py — Vyapar Copilot CLI entry point.

Supports two modes:
  Text mode (default): Type queries in terminal, get Hinglish responses
  Voice mode (--voice): Speak queries via microphone, hear responses via TTS

Usage:
    python ui/cli.py                    # text mode
    python ui/cli.py --voice            # voice mode
    python ui/cli.py --broker upstox    # use Upstox broker (needs credentials)
    python ui/cli.py --broker angel     # use Angel One broker (needs credentials)
    python ui/cli.py --lang en-IN       # English language mode
"""

from __future__ import annotations

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Load .env before any imports that might need API keys
# ---------------------------------------------------------------------------
def _load_env():
    """Load environment variables from .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env_path):
        # Try current directory
        env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env()

# ---------------------------------------------------------------------------
# Broker factory
# ---------------------------------------------------------------------------

def _get_broker(broker_name: str):
    """Instantiate the requested broker adapter."""
    broker_name = (broker_name or "mock").lower()

    if broker_name == "mock":
        from broker.mock import MockBroker
        return MockBroker()

    elif broker_name == "upstox":
        try:
            from broker.upstox import UpstoxBroker
            return UpstoxBroker()
        except Exception as e:
            print(f"⚠️  Upstox broker init failed: {e}")
            print("   Falling back to MockBroker.")
            from broker.mock import MockBroker
            return MockBroker()

    elif broker_name == "angel":
        try:
            from broker.angel import AngelBroker
            return AngelBroker()
        except Exception as e:
            print(f"⚠️  Angel One broker init failed: {e}")
            print("   Falling back to MockBroker.")
            from broker.mock import MockBroker
            return MockBroker()

    else:
        print(f"⚠️  Unknown broker '{broker_name}'. Using MockBroker.")
        from broker.mock import MockBroker
        return MockBroker()


# ---------------------------------------------------------------------------
# REPL helpers
# ---------------------------------------------------------------------------

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║   🇮🇳  Vyapar Copilot — Indian Equities Trade Assistant          ║
║   Powered by Sarvam AI | Boliye, kya jaanna hai aaj?            ║
╚══════════════════════════════════════════════════════════════════╝

Commands:
  quit / exit    — Exit the copilot
  reset          — Clear conversation history
  broker         — Show current broker info
  help           — Show this help

Example queries:
  "RELIANCE ka technical analysis karo"
  "Nifty option chain dikhao"
  "TCS mein entry 3800 pe, SL 3700, target 4000 — risk calculate karo"
  "HDFC Bank ka latest news batao"
"""


def text_loop(copilot, lang: str = "hi-IN"):
    """Run the interactive text-based REPL."""
    print(BANNER)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nAlvida! Trade safe karo. 🙏")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("quit", "exit", "bye", "alvida"):
            print("Alvida! Trade safe karo. 🙏")
            break

        if lower == "reset":
            copilot.reset()
            print("✅ Conversation history cleared.\n")
            continue

        if lower == "broker":
            try:
                profile = copilot.broker.get_profile() if copilot.broker else {}
                funds = copilot.broker.get_funds() if copilot.broker else {}
                print(f"\n📊 Broker: {profile.get('broker', 'Unknown')}")
                print(f"   Client: {profile.get('client_id', 'N/A')}")
                print(f"   Available margin: ₹{funds.get('available_margin', 0):,.0f}\n")
            except Exception as e:
                print(f"Broker info error: {e}\n")
            continue

        if lower in ("help", "?"):
            print(BANNER)
            continue

        print("🤔 Thinking...", end="", flush=True)
        try:
            reply = copilot.chat(user_input)
            print(f"\r\033[K")  # Clear "Thinking..." line
            print(f"Copilot: {reply}\n")
        except Exception as e:
            print(f"\r\033[K")
            print(f"❌ Error: {e}\n")


def voice_loop(copilot, lang: str = "hi-IN"):
    """Run the interactive voice-based REPL (mic input + TTS output)."""
    try:
        from voice.stt import transcribe_from_mic
        from voice.tts import speak, play_audio
    except ImportError as e:
        print(f"❌ Voice dependencies missing: {e}")
        print("   Install with: pip install pyaudio pydub")
        print("   Falling back to text mode...\n")
        text_loop(copilot, lang)
        return

    print("\n🎙️  Vyapar Copilot — Voice Mode")
    print("   Press Enter to speak | Ctrl+C to exit")
    print("   Boliye kya puchna hai...\n")

    while True:
        try:
            input("⏎  Press Enter to speak...")
        except (EOFError, KeyboardInterrupt):
            print("\nAlvida! 🙏")
            break

        try:
            transcript = transcribe_from_mic(duration_seconds=5, language_code=lang)
            if not transcript.strip():
                print("(No speech detected, try again)\n")
                continue

            print(f"You: {transcript}")

            print("🤔 Thinking...", end="", flush=True)
            reply = copilot.chat(transcript)
            print(f"\r\033[K")
            print(f"Copilot: {reply}\n")

            # TTS output
            try:
                audio_path = speak(reply, language_code=lang)
                play_audio(audio_path)
            except Exception as tts_err:
                print(f"[TTS error: {tts_err}]")

        except KeyboardInterrupt:
            print("\nAlvida! 🙏")
            break
        except Exception as e:
            print(f"\r\033[K❌ Error: {e}\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="vyapar-copilot",
        description="Vyapar Copilot — Indian Equities Trade Assistant powered by Sarvam AI",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable voice mode: microphone input + TTS output",
    )
    parser.add_argument(
        "--broker",
        choices=["mock", "upstox", "angel"],
        default="mock",
        help="Broker to use for order placement (default: mock)",
    )
    parser.add_argument(
        "--lang",
        default="hi-IN",
        help="Language code for voice I/O (default: hi-IN for Hinglish)",
    )
    args = parser.parse_args()

    # Validate API key
    if not os.environ.get("SARVAM_API_KEY"):
        print("❌ SARVAM_API_KEY not found.")
        print("   Add it to your .env file: SARVAM_API_KEY=your_key_here")
        sys.exit(1)

    # Initialize broker
    broker = _get_broker(args.broker)

    # Initialize copilot
    print("🚀 Starting Vyapar Copilot...")
    from agent.copilot import VyaparCopilot
    copilot = VyaparCopilot(broker=broker)

    # Launch REPL
    if args.voice:
        voice_loop(copilot, lang=args.lang)
    else:
        text_loop(copilot, lang=args.lang)


if __name__ == "__main__":
    main()
