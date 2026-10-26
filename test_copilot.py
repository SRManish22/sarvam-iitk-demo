import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure env is loaded
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

from agent.copilot import VyaparCopilot
from broker.mock import MockBroker

print("Initializing VyaparCopilot with MockBroker...")
broker = MockBroker()
copilot = VyaparCopilot(broker=broker)

print("\n--- Testing Single-Turn Query to Sarvam AI ---")
query = "Namaste! Ek line mein batao aap kaun ho aur Indian traders ki kaise help karte ho?"
print(f"User: {query}")

reply = copilot.chat(query)
print(f"\nCopilot reply:\n{reply}\n")
