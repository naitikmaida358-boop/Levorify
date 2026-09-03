import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("levorify.gemini_service")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiBYOKService:
    """
    High-Velocity Asynchronous Service executing AI prompts via dynamic BYOK.
    Passes the user's individual Google Gemini API key to Google's endpoints,
    ensuring Levorify incurs zero LLM runtime infrastructure costs.
    """

    @staticmethod
    async def verify_key(api_key: str) -> Dict[str, Any]:
        """
        Pings Google Gemini API with a lightweight test probe to verify key validity.
        """
        url = f"{GEMINI_API_BASE}/models/{settings.DEFAULT_GEMINI_MODEL}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": "Reply with 'VALID' only."}]}],
            "generationConfig": {"maxOutputTokens": 5, "temperature": 0.0}
        }
        headers = {"Content-Type": "application/json"}
        params = {"key": api_key}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload, params=params)
                if response.status_code == 200:
                    return {"valid": True, "message": "Google Gemini API key verified and operational."}
                elif response.status_code in (400, 403):
                    data = response.json()
                    err_msg = data.get("error", {}).get("message", "Invalid API key or insufficient permissions.")
                    return {"valid": False, "message": f"Google Gemini rejected key: {err_msg}"}
                else:
                    return {"valid": False, "message": f"Provider responded with status {response.status_code}."}
            except httpx.RequestError as exc:
                return {"valid": False, "message": f"Network error contacting Google Gemini: {str(exc)}"}

    @staticmethod
    async def generate_d2c_content(
        api_key: str,
        system_instruction: str,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a dynamic completion request against Google Gemini using the caller's key.
        """
        selected_model = model or settings.DEFAULT_GEMINI_MODEL
        url = f"{GEMINI_API_BASE}/models/{selected_model}:generateContent"
        
        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        
        # If structured JSON schema output is requested
        if response_schema:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        headers = {"Content-Type": "application/json"}
        params = {"key": api_key}

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload, params=params)
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Google Gemini API request timed out after 30 seconds."
                )
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Network error communicating with Google Gemini: {str(exc)}"
                )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if response.status_code != 200:
            error_data = {}
            try:
                error_data = response.json()
            except Exception:
                error_data = {"raw": response.text}
            
            error_detail = error_data.get("error", {}).get("message", "Error returned from Google Gemini API.")
            logger.error(f"Gemini API returned {response.status_code}: {error_detail}")
            
            if response.status_code in (400, 403):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gemini BYOK Key Error: {error_detail}"
                )
            elif response.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Gemini BYOK Quota Exceeded on your personal Google AI key. Please check your AI Studio limits."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Gemini Upstream Error ({response.status_code}): {error_detail}"
                )

        response_json = response.json()
        
        # Extract generated content text
        candidates = response_json.get("candidates", [])
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No generation candidates returned from Google Gemini."
            )
            
        first_candidate = candidates[0]
        parts = first_candidate.get("content", {}).get("parts", [])
        raw_text = "".join(part.get("text", "") for part in parts)
        
        # Usage metadata
        usage = response_json.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)

        # Parse JSON if applicable
        parsed_result: Any = raw_text
        if response_schema:
            try:
                parsed_result = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed_result = {"raw_output": raw_text}

        return {
            "model": selected_model,
            "latency_ms": latency_ms,
            "total_tokens": total_tokens,
            "result": parsed_result
        }


gemini_service = GeminiBYOKService()
