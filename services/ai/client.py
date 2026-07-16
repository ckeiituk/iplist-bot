"""
Gemini API client with automatic key rotation.
"""

import httpx
from bot.core.logging import get_logger
from bot.core.exceptions import GeminiAPIError

logger = get_logger(__name__)


class GeminiClient:
    """Client for Google Gemini API with key rotation."""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    # Gemma 4 reasoning is always on and its tokens count against
    # maxOutputTokens, so the answer budget needs extra room on top.
    REASONING_HEADROOM = 1024

    def __init__(self, api_keys: list[str], model: str):
        self._api_keys = api_keys
        self._model = model
        self._current_key_index = 0
    
    def _get_next_key(self) -> str:
        """Rotate to the next available API key."""
        if not self._api_keys or self._api_keys == [""]:
            raise GeminiAPIError("No GEMINI_API_KEY provided")
        
        key = self._api_keys[self._current_key_index]
        self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
        return key
    
    async def generate(self, prompt: str, max_tokens: int = 50) -> str:
        """
        Call Gemini API with automatic key rotation on 429/403 errors.
        
        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in the final answer (reasoning
                headroom is added on top)
            
        Returns:
            Generated text response
            
        Raises:
            GeminiAPIError: If all API keys fail
        """
        url = f"{self.BASE_URL}/{self._model}:generateContent"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens + self.REASONING_HEADROOM,
                "temperature": 0.1,
            },
        }
        
        attempts = len(self._api_keys)
        last_error: Exception | None = None
        
        for _ in range(attempts):
            try:
                api_key = self._get_next_key()
            except GeminiAPIError:
                raise GeminiAPIError("GEMINI_API_KEY not configured")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(
                        url,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": api_key,
                        },
                        json=payload,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if "candidates" in result and result["candidates"]:
                            parts = result["candidates"][0]["content"]["parts"]
                            answer = "".join(
                                part.get("text", "")
                                for part in parts
                                if not part.get("thought")
                            ).strip()
                            if not answer:
                                raise GeminiAPIError("No answer text returned from Gemini")
                            return answer
                        else:
                            raise GeminiAPIError("No candidates returned from Gemini")
                    
                    if response.status_code in [429, 403]:
                        logger.warning(
                            f"Gemini API key {api_key[:5]}... failed with {response.status_code}. Rotating key."
                        )
                        last_error = GeminiAPIError(f"API returned {response.status_code}")
                        continue
                    
                    response.raise_for_status()
                    
                except httpx.HTTPError as e:
                    logger.error(f"HTTP Error with key {api_key[:5]}...: {e}")
                    last_error = e
                    continue
                except Exception as e:
                    last_error = e
                    continue
        
        raise last_error if last_error else GeminiAPIError("All Gemini API keys failed")
