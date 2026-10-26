import os
from sarvamai import SarvamAI

# Load .env file into os.environ if present
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    raise ValueError("SARVAM_API_KEY not found in environment. Please paste your key into .env")

# SDK reads api_subscription_key; SARVAM_API_KEY env var is also picked up automatically
client = SarvamAI(api_subscription_key=api_key)

# Correct native SDK signature: client.chat.completions(...) — NOT .completions.create()
response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "Hello! Give me a one-sentence greeting."},
    ],
    temperature=0.7,
    max_tokens=100,
)

print(response.choices[0].message.content)
