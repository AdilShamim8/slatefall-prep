"""
core/llm_client.py
──────────────────
Handles all communication with the LLM provider.

Supports: Groq (primary), Gemini (fallback)

WHY Groq as primary:
- Free tier with generous limits (6000 RPM)
- Very fast inference (~700 tokens/sec)
- Access to Llama 3 8B — sufficient quality for MCQ generation
- No GPU required

WHY tenacity for retry:
LLM APIs fail occasionally (rate limits, timeouts, server errors).
Without retry logic, one bad API call crashes the whole session.
Exponential backoff = wait 2s, then 4s, then 8s before giving up.

WHY JSON parsing fallback:
LLMs reliably return text but NOT reliably return valid JSON.
They often wrap JSON in markdown blocks or add explanatory text.
Three-level parsing handles 99%+ of real-world LLM responses.
"""

import json
import re

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Unified client for LLM providers.
    Swap provider by changing LLM_PROVIDER in .env — no code changes.
    """

    def __init__(self):
        self.provider = config.LLM_PROVIDER
        self._client  = None
        self.model    = None
        self._setup()

    def _setup(self) -> None:
        """Initialize the configured provider."""
        if self.provider == "groq":
            self._setup_groq()
        elif self.provider == "gemini":
            self._setup_gemini()
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{self.provider}'. "
                f"Choose 'groq' or 'gemini' in your .env file."
            )

    def _setup_groq(self) -> None:
        from groq import Groq

        if not config.GROQ_API_KEY:
            raise EnvironmentError(
                "\n❌ GROQ_API_KEY is missing from your .env file.\n"
                "   1. Go to https://console.groq.com\n"
                "   2. Create a free account\n"
                "   3. Copy your API key\n"
                "   4. Add to .env: GROQ_API_KEY=your_key_here\n"
            )

        self._client = Groq(api_key=config.GROQ_API_KEY)
        self.model   = config.GROQ_MODEL
        logger.info(f"LLM provider: Groq | model: {self.model}")

    def _setup_gemini(self) -> None:
        import google.generativeai as genai

        if not config.GEMINI_API_KEY:
            raise EnvironmentError(
                "\n❌ GEMINI_API_KEY is missing from your .env file.\n"
                "   1. Go to https://aistudio.google.com/app/apikey\n"
                "   2. Create a free API key\n"
                "   3. Add to .env: GEMINI_API_KEY=your_key_here\n"
            )

        genai.configure(api_key=config.GEMINI_API_KEY)
        self._client = genai.GenerativeModel(config.GEMINI_MODEL)
        self.model   = config.GEMINI_MODEL
        logger.info(f"LLM provider: Gemini | model: {self.model}")

    # ── Core completion method ────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def complete(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Send a prompt to the LLM and return the response text.

        Retries up to 3 times with exponential backoff on any failure.
        Logs token usage after every successful call.

        Args:
            prompt:      The full prompt text
            temperature: 0.0 = deterministic, 1.0 = creative
                         0.7 chosen after testing — good variety + accuracy

        Returns:
            Raw text response from the LLM
        """
        logger.info(
            f"LLM call | provider={self.provider} | "
            f"model={self.model} | "
            f"prompt_length={len(prompt.split())} words"
        )

        if self.provider == "groq":
            return self._groq_complete(prompt, temperature)
        elif self.provider == "gemini":
            return self._gemini_complete(prompt, temperature)

    def _groq_complete(self, prompt: str, temperature: float) -> str:
        """Send request to Groq Chat Completions API."""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert educational content creator. "
                        "You generate accurate, well-structured multiple choice questions "
                        "strictly based on provided source text. "
                        "Always respond with valid JSON only — no markdown, no preamble."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=temperature,
            max_tokens=4096,
        )

        # Log token usage (useful for monitoring cost/rate limits)
        usage = response.usage
        logger.info(
            f"Groq tokens | "
            f"prompt={usage.prompt_tokens} | "
            f"completion={usage.completion_tokens} | "
            f"total={usage.total_tokens}"
        )

        return response.choices[0].message.content

    def _gemini_complete(self, prompt: str, temperature: float) -> str:
        """Send request to Gemini API."""
        response = self._client.generate_content(
            prompt,
            generation_config={
                "temperature":      temperature,
                "max_output_tokens": 4096,
            },
        )
        return response.text

    # ── JSON parsing ──────────────────────────────────────────────

    def parse_json_response(self, response: str) -> dict | list:
        """
        Parse JSON from LLM response text.

        Three-level strategy:
        1. Direct parse (LLM followed instructions perfectly)
        2. Extract from markdown code block (LLM wrapped in ```json...```)
        3. Find any JSON object/array in the text (LLM added extra prose)

        If all three fail → raises ValueError with the raw response
        so the caller can log it and handle gracefully.
        """
        # Level 1: Direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Level 2: Extract from ```json ... ``` blocks
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", response)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Level 3: Find first JSON object or array anywhere in text
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", response)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # All levels failed
        logger.error(
            f"JSON parsing failed. Raw response (first 400 chars):\n"
            f"{response[:400]}"
        )
        raise ValueError(
            f"LLM returned unparseable response. "
            f"Raw response:\n{response[:300]}"
        )


# ─── Global singleton ─────────────────────────────────────────────
llm_client = LLMClient()