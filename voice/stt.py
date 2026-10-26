"""
voice/stt.py — Speech-to-Text using Sarvam AI saaras:v4.

Supports:
- File transcription (WAV, MP3, etc.)
- Live microphone recording + transcription
- Hinglish codemix mode for Indian trader queries
- Domain keyterms boosting for financial vocabulary
"""

from __future__ import annotations

import os
import tempfile


def load_client():
    """Create and return an authenticated SarvamAI client."""
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])


def transcribe_file(audio_path: str, language_code: str = "hi-IN") -> str:
    """
    Transcribe an audio file using Sarvam saaras:v4.

    Supports codemix mode for Hinglish speech — the natural mix of
    Hindi and English used by Indian traders and analysts.

    Keyterms boost recognition accuracy for financial vocabulary:
    Nifty, BankNifty, SEBI, NSE, BSE, F&O, RELIANCE, TCS, etc.

    Args:
        audio_path: Path to audio file (WAV, MP3, M4A, FLAC, OGG).
        language_code: Primary language code:
            "hi-IN" — Hindi / Hinglish (default)
            "en-IN" — Indian English
            "ta-IN" — Tamil
            "te-IN" — Telugu
            "kn-IN" — Kannada
            "mr-IN" — Marathi
            "gu-IN" — Gujarati
            "pa-IN" — Punjabi

    Returns:
        Transcribed text string.
    """
    client = load_client()

    financial_keyterms = [
        "Nifty", "BankNifty", "FinNifty", "MidcapNifty",
        "SEBI", "NSE", "BSE", "MCX",
        "F&O", "futures", "options", "call", "put",
        "intraday", "delivery", "BTST", "STBT",
        "RSI", "MACD", "EMA", "ATR",
        "stop loss", "target", "entry", "exit",
        "bullish", "bearish", "breakout", "breakdown",
        "support", "resistance",
        "RELIANCE", "TCS", "INFOSYS", "HDFC", "ICICI",
        "crore", "lakh", "rupee",
    ]

    with open(audio_path, "rb") as f:
        response = client.speech_to_text.transcribe(
            file=f,
            model="saaras:v4",
            language_code=language_code,
            mode="codemix",       # Handles Hinglish naturally
            keyterms=financial_keyterms,
        )

    return response.transcript


def transcribe_from_mic(duration_seconds: int = 5, language_code: str = "hi-IN") -> str:
    """
    Record audio from the microphone and transcribe it.

    Records for the specified duration, saves to a temp WAV file,
    then transcribes using Sarvam saaras:v4.

    Requires pyaudio to be installed: pip install pyaudio

    Args:
        duration_seconds: How long to record (default 5 seconds).
        language_code: Language/dialect for transcription (default "hi-IN").

    Returns:
        Transcribed text string.

    Raises:
        ImportError: If pyaudio is not installed.
        RuntimeError: If microphone recording fails.
    """
    try:
        import pyaudio
        import wave
    except ImportError:
        raise ImportError(
            "pyaudio is required for microphone input. "
            "Install with: pip install pyaudio\n"
            "On Windows, you may need: pip install pipwin && pipwin install pyaudio"
        )

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000  # 16kHz required by Sarvam STT

    p = pyaudio.PyAudio()

    print(f"🎙️  Recording for {duration_seconds}s... Speak now!")

    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        frames = []
        num_chunks = int(RATE / CHUNK * duration_seconds)
        for i in range(num_chunks):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
    except Exception as e:
        p.terminate()
        raise RuntimeError(f"Microphone recording failed: {e}") from e

    p.terminate()
    print("✅ Recording done. Transcribing...")

    # Save to temp WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))

        transcript = transcribe_file(tmp_path, language_code)
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return transcript
