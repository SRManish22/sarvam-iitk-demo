"""
voice/tts.py — Text-to-Speech using Sarvam AI bulbul:v4-flash.

Converts Hinglish text responses to natural Hindi voice output.
Supports multiple speakers and language codes.
"""

from __future__ import annotations

import os


# Available Sarvam TTS speakers for Indian languages
SPEAKERS = {
    "hi-IN": "kavya_hi_conversational",   # Hindi — natural conversational female
    "en-IN": "anushka",                   # Indian English — female
    "ta-IN": "pavithra",                  # Tamil — female
    "te-IN": "charulatha",                # Telugu — female
    "kn-IN": "ananya",                    # Kannada — female
    "mr-IN": "aarohi",                    # Marathi — female
    "gu-IN": "tanishka",                  # Gujarati — female
    "pa-IN": "gurpreet",                  # Punjabi — male
    "bn-IN": "subhashini",               # Bengali — female
}


def speak(
    text: str,
    language_code: str = "hi-IN",
    output_path: str = "reply.wav",
    speaker: str = None,
    pace: float = 1.0,
) -> str:
    """
    Convert text to speech using Sarvam bulbul:v4-flash.

    Saves the audio to output_path and returns the path.

    Args:
        text: Text to convert (max 2500 characters per request).
        language_code: Target language — "hi-IN", "en-IN", "ta-IN", etc.
        output_path: Path to save the WAV file (default "reply.wav").
        speaker: Speaker ID. If None, uses the best speaker for the language.
        pace: Speech speed — 0.5 (slow) to 2.0 (fast). Default 1.0.

    Returns:
        Path to the saved WAV file.
    """
    from sarvamai import SarvamAI
    from sarvamai.play import save

    client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

    # Select speaker
    selected_speaker = speaker or SPEAKERS.get(language_code, "kavya_hi_conversational")

    # bulbul:v4-flash has a 2500 character limit per request
    text_to_speak = text[:2500]
    if len(text) > 2500:
        print(f"[TTS] Text truncated from {len(text)} to 2500 characters for bulbul:v4-flash")

    response = client.text_to_speech.convert(
        text=text_to_speak,
        language_code=language_code,
        model="bulbul:v4-flash",
        speaker=selected_speaker,
        pace=pace,
        speech_sample_rate=22050,
    )

    save(response, output_path)
    return output_path


def speak_long(
    text: str,
    language_code: str = "hi-IN",
    output_dir: str = ".",
    speaker: str = None,
) -> list[str]:
    """
    Convert long text to speech by splitting into chunks of 2500 chars.

    Saves each chunk as a separate WAV file.

    Args:
        text: Full text to speak (can be > 2500 chars).
        language_code: Target language code.
        output_dir: Directory to save WAV chunks.
        speaker: Speaker ID.

    Returns:
        List of paths to saved WAV files, in order.
    """
    import math

    chunk_size = 2500
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    paths = []

    for idx, chunk in enumerate(chunks):
        output_path = os.path.join(output_dir, f"reply_chunk_{idx:03d}.wav")
        speak(chunk, language_code=language_code, output_path=output_path, speaker=speaker)
        paths.append(output_path)

    return paths


def play_audio(path: str):
    """
    Play an audio file.

    Tries pydub + simpleaudio for cross-platform playback.
    Falls back to os.startfile on Windows for native playback.

    Args:
        path: Path to WAV or audio file.
    """
    try:
        from pydub import AudioSegment
        from pydub.playback import play as pydub_play

        audio = AudioSegment.from_wav(path)
        pydub_play(audio)
    except ImportError:
        # pydub or simpleaudio not available — use OS native player
        _play_native(path)
    except Exception as e:
        print(f"[TTS] pydub playback failed ({e}), trying native player...")
        _play_native(path)


def _play_native(path: str):
    """Use OS native file handler to play audio."""
    import subprocess
    import sys

    abs_path = os.path.abspath(path)

    if sys.platform == "win32":
        os.startfile(abs_path)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", abs_path], check=False)
    else:
        # Linux — try common players
        for player in ["aplay", "paplay", "mpg123", "vlc"]:
            try:
                subprocess.run([player, abs_path], check=True, capture_output=True)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        print(f"[TTS] Could not play audio. Saved to: {abs_path}")
