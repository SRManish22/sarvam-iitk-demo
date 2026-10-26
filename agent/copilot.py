"""
agent/copilot.py — Core agent loop for Vyapar Copilot.

Implements VyaparCopilot class with:
- Sarvam AI LLM integration (sarvam-105b-conversations)
- Agentic tool-calling loop
- Conversation history management
- Fallback JSON-block parsing if SDK doesn't expose tool_calls natively
"""

from __future__ import annotations

import json
import os
import re

from agent.prompts import SYSTEM_PROMPT
from agent.tools import (
    TOOLS_SCHEMA,
    analyse_technicals,
    calculate_risk,
    get_filings,
    get_news,
    get_option_chain,
    get_quote,
    place_order,
)

TOOL_MAP = {
    "get_quote": get_quote,
    "get_option_chain": get_option_chain,
    "get_news": get_news,
    "analyse_technicals": analyse_technicals,
    "get_filings": get_filings,
    "calculate_risk": calculate_risk,
    "place_order": place_order,
}

# Maximum agentic loop iterations to prevent infinite loops
MAX_ITERATIONS = 10


class VyaparCopilot:
    """
    Main agent class for Vyapar Copilot — Indian Equities Trade Assistant.

    Manages conversation history and runs the agentic tool-calling loop
    using Sarvam AI's sarvam-105b-conversations model.
    """

    def __init__(self, broker=None):
        """
        Initialise the copilot.

        Args:
            broker: Optional broker adapter instance (defaults to MockBroker if None).
                    The broker instance is used by place_order tool calls.
        """
        from sarvamai import SarvamAI

        api_key = os.environ.get("SARVAM_API_KEY")
        if not api_key:
            raise ValueError("SARVAM_API_KEY not set in environment. Add it to .env file.")

        self.client = SarvamAI(api_subscription_key=api_key)
        self.broker = broker
        self.conversation_history: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Build a condensed tool description for fallback prompt injection
        self._tool_descriptions = self._build_tool_descriptions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """
        Send a user message, execute any tool calls, and return the final reply.

        Implements an agentic loop:
        1. Append user message to history.
        2. Call Sarvam LLM.
        3. If response contains tool calls → execute them → loop.
        4. If no tool calls → return final text reply.

        Args:
            user_message: The user's text input.

        Returns:
            The assistant's final text reply.
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        for iteration in range(MAX_ITERATIONS):
            try:
                response = self.client.chat.completions(
                    model="sarvam-105b-conversations",
                    messages=self.conversation_history,
                    temperature=0.3,
                    max_tokens=2048,
                )
            except Exception as e:
                error_reply = f"Maafi karo yaar, API mein kuch issue aa gaya: {e}"
                self.conversation_history.append(
                    {"role": "assistant", "content": error_reply}
                )
                return error_reply

            choice = response.choices[0]
            message = choice.message
            content = getattr(message, "content", "") or ""

            # ---- Path 1: Native tool_calls from SDK ----
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                # Append assistant message with tool calls to history
                self.conversation_history.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )
                # Execute each tool call
                for tc in tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except Exception:
                        fn_args = {}
                    result = self._dispatch_tool(fn_name, fn_args)
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    )
                # Continue loop to get next LLM response
                continue

            # ---- Path 2: Fallback — parse JSON tool call blocks from content ----
            # Some LLM responses may embed tool calls as JSON blocks like:
            # ```tool_call
            # {"name": "get_quote", "arguments": {"symbol": "RELIANCE"}}
            # ```
            parsed_calls = self._extract_json_tool_calls(content)
            if parsed_calls:
                # Strip tool call blocks from displayed content
                clean_content = self._strip_tool_call_blocks(content)
                self.conversation_history.append(
                    {"role": "assistant", "content": clean_content}
                )
                for call in parsed_calls:
                    fn_name = call.get("name", "")
                    fn_args = call.get("arguments", {})
                    result = self._dispatch_tool(fn_name, fn_args)
                    # Inject tool result as a user message (fallback pattern)
                    self.conversation_history.append(
                        {
                            "role": "user",
                            "content": (
                                f"[Tool result for {fn_name}]:\n"
                                + json.dumps(result, ensure_ascii=False, default=str)
                            ),
                        }
                    )
                # Continue loop
                continue

            # ---- Path 3: Final text reply — no tool calls ----
            reply = content.strip()
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply

        # If we hit MAX_ITERATIONS, return whatever we have
        last_content = self.conversation_history[-1].get("content", "")
        if self.conversation_history[-1]["role"] != "assistant":
            last_content = "Yaar, bahut saare tool calls ho gaye. Thoda aur specific question karo?"
            self.conversation_history.append(
                {"role": "assistant", "content": last_content}
            )
        return last_content

    def reset(self):
        """Clear conversation history, keeping only the system prompt."""
        self.conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def get_history(self) -> list[dict]:
        """Return a copy of the conversation history."""
        return list(self.conversation_history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch_tool(self, fn_name: str, fn_args: dict) -> dict | list:
        """Look up and call a tool function by name."""
        fn = TOOL_MAP.get(fn_name)
        if fn is None:
            return {"error": f"Unknown tool: {fn_name}"}
        try:
            return fn(**fn_args)
        except TypeError as e:
            return {"error": f"Bad arguments for {fn_name}: {e}"}
        except Exception as e:
            return {"error": f"Tool {fn_name} failed: {e}"}

    def _extract_json_tool_calls(self, content: str) -> list[dict]:
        """
        Parse JSON tool call blocks from LLM response content.

        Looks for blocks like:
            ```tool_call
            {"name": "get_quote", "arguments": {"symbol": "RELIANCE"}}
            ```
        Also handles plain ```json blocks with "name" key as tool calls.
        """
        calls = []
        # Match ```tool_call ... ``` blocks
        pattern = r"```tool_call\s*\n(.*?)\n```"
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            try:
                obj = json.loads(match.strip())
                if "name" in obj:
                    calls.append(obj)
            except json.JSONDecodeError:
                pass
        # Also match ```json ... ``` blocks that look like tool calls
        json_pattern = r"```json\s*\n(.*?)\n```"
        json_matches = re.findall(json_pattern, content, re.DOTALL)
        for match in json_matches:
            try:
                obj = json.loads(match.strip())
                if "name" in obj and "arguments" in obj:
                    calls.append(obj)
            except json.JSONDecodeError:
                pass
        return calls

    def _strip_tool_call_blocks(self, content: str) -> str:
        """Remove tool_call code blocks from content string."""
        content = re.sub(r"```tool_call\s*\n.*?\n```", "", content, flags=re.DOTALL)
        return content.strip()

    def _build_tool_descriptions(self) -> str:
        """Build a concise tool description string for fallback prompt injection."""
        lines = ["Available tools (call using JSON blocks):"]
        for tool in TOOLS_SCHEMA:
            fn = tool["function"]
            params = list(fn["parameters"]["properties"].keys())
            lines.append(f"- {fn['name']}({', '.join(params)}): {fn['description'][:80]}")
        return "\n".join(lines)
