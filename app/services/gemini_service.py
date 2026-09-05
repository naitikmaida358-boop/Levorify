import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("levorify.gemini_service")

# Dynamic discovery in-memory cache: hash(api_key) -> {"models": List[str], "expires_at": float}
_DISCOVERY_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 600.0  # 10 minutes


def _score_model_preference(model_name: str) -> float:
    """
    Dynamically scores a model name so the newest and most efficient
    flash-lite, flash, and pro models rank highest, without hardcoding static model names.
    Higher score = higher priority in dynamic execution chain.
    """
    name = model_name.lower().strip().replace("models/", "")

    # Exclude non-chat generative models or models requiring the Interactions API
    if any(excluded in name for excluded in [
        "embedding", "imagen", "aqa", "realtime", "learnlm",
        "interaction", "interactions", "thinking", "whisper", "tts"
    ]):
        return -1000.0

    score = 0.0

    # 1. Dynamic version extraction (e.g. 2.5 -> 250 pts, 2.0 -> 200 pts, 1.5 -> 150 pts, 3.0 -> 300 pts)
    version_match = re.search(r"(\d+(?:\.\d+)?)", name)
    if version_match:
        try:
            ver = float(version_match.group(1))
            score += ver * 100.0
        except ValueError:
            pass

    # 2. Preference hierarchy for sovereign D2C commerce tasks (ultra-fast / economical flash-lite first)
    if "flash-lite" in name:
        score += 60.0
    elif "flash" in name:
        score += 45.0
    elif "pro" in name:
        score += 30.0
    elif "ultra" in name:
        score += 15.0
    elif "gemini" in name:
        score += 10.0

    # 3. Penalty for experimental / preview builds when stable releases exist
    if "preview" in name or "exp" in name:
        score -= 20.0

    return score


def _generate_pattern_fallback_models() -> List[str]:
    """
    Generates a candidate chain targeting standard content generation endpoints (:generateContent).
    Explicitly prioritizes stable models (gemini-2.5-flash-lite, gemini-1.5-flash, gemini-1.5-pro).
    """
    stable_models = [
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite"
    ]
    fallback_list: List[str] = []
    
    # Priority: configured model first if provided and valid
    configured = getattr(settings, "DEFAULT_GEMINI_MODEL", "gemini-2.5-flash-lite")
    if configured:
        cleaned = configured.replace("models/", "").strip()
        if cleaned and not any(ex in cleaned.lower() for ex in ["interaction", "interactions"]):
            fallback_list.append(cleaned)

    for candidate in stable_models:
        if candidate not in fallback_list:
            fallback_list.append(candidate)

    return fallback_list


class GeminiBYOKService:
    """
    Autonomous BYOK Gemini Service with Runtime Model Auto-Discovery and
    Dynamic Self-Healing Fallback Engine.
    
    Eliminates hardcoded model strings: queries Google's available models at runtime,
    dynamically scores and ranks discovered endpoints, and cascades through a resilient
    fallback chain so execution never breaks with 404 errors.
    """

    @staticmethod
    def _get_candidate_bases() -> List[str]:
        configured_base = getattr(settings, "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
        candidate_bases = [
            configured_base,
            "https://generativelanguage.googleapis.com/v1beta",
            "https://generativelanguage.googleapis.com/v1"
        ]
        return list(dict.fromkeys(candidate_bases))

    @classmethod
    async def discover_available_models(
        cls,
        api_key: str,
        client: Optional[httpx.AsyncClient] = None
    ) -> List[str]:
        """
        Dynamically queries Google's Generative Language /models endpoint using the caller's key.
        Filters for models supporting 'generateContent' and sorts them by dynamic preference.
        Caches results in-memory with a 10-minute TTL.
        """
        clean_key = (api_key or "").strip()
        if not clean_key:
            return []

        # Check cache
        key_hash = hashlib.sha256(clean_key.encode("utf-8")).hexdigest()
        now = time.time()
        cached = _DISCOVERY_CACHE.get(key_hash)
        if cached and cached["expires_at"] > now:
            return cached["models"]

        candidate_bases = cls._get_candidate_bases()
        discovered_models: List[str] = []

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close_client = True

        try:
            for base in candidate_bases:
                try:
                    res = await client.get(f"{base}/models", params={"key": clean_key})
                    if res.status_code == 200:
                        data = res.json()
                        raw_models = data.get("models", [])
                        
                        # Filter models that support generateContent and exclude interaction-only or non-standard models
                        capable = [
                            m.get("name", "").replace("models/", "").strip()
                            for m in raw_models
                            if "generateContent" in m.get("supportedGenerationMethods", [])
                            and m.get("name")
                            and not any(bad in m.get("name", "").lower() for bad in ["interaction", "interactions", "embedding", "imagen", "aqa", "realtime", "thinking"])
                        ]
                        
                        # Score and rank discovered models
                        scored = sorted(
                            [m for m in capable if _score_model_preference(m) > 0],
                            key=_score_model_preference,
                            reverse=True
                        )
                        
                        if scored:
                            discovered_models = scored
                            logger.info(
                                f"Auto-discovered {len(discovered_models)} capable models from Google runtime. "
                                f"Top candidate: {discovered_models[0]}"
                            )
                            break
                except httpx.RequestError as exc:
                    logger.warning(f"Error querying models endpoint at {base}: {exc}")
                    continue
        finally:
            if should_close_client:
                await client.aclose()

        if discovered_models:
            _DISCOVERY_CACHE[key_hash] = {
                "models": discovered_models,
                "expires_at": now + CACHE_TTL_SECONDS
            }

        return discovered_models

    @classmethod
    async def get_prioritized_candidates(
        cls,
        api_key: str,
        requested_model: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None
    ) -> List[str]:
        """
        Builds a robust, deduplicated candidate chain ordered by preference:
        1. Explicit user/caller requested model (if any, excluding interaction models)
        2. Configured default model from settings
        3. Dynamically discovered capable models from Google's runtime API
        4. Pattern-based fallback matrix with stable models (gemini-2.5-flash-lite, gemini-1.5-flash, gemini-1.5-pro)
        """
        candidates: List[str] = []

        # 1. Caller specified model
        if requested_model:
            clean_req = requested_model.replace("models/", "").strip()
            if clean_req and not any(bad in clean_req.lower() for bad in ["interaction", "interactions"]):
                candidates.append(clean_req)

        # 2. Configured model
        configured = getattr(settings, "DEFAULT_GEMINI_MODEL", "gemini-2.5-flash-lite")
        if configured:
            clean_cfg = configured.replace("models/", "").strip()
            if clean_cfg and clean_cfg not in candidates and not any(bad in clean_cfg.lower() for bad in ["interaction", "interactions"]):
                candidates.append(clean_cfg)

        # 3. Dynamic runtime discovery from Google
        try:
            discovered = await cls.discover_available_models(api_key, client=client)
            for m in discovered:
                if m not in candidates and not any(bad in m.lower() for bad in ["interaction", "interactions"]):
                    candidates.append(m)
        except Exception as exc:
            logger.warning(f"Model auto-discovery encountered non-fatal error: {exc}")

        # 4. Resilient pattern-based fallback
        for pattern_model in _generate_pattern_fallback_models():
            if pattern_model not in candidates:
                candidates.append(pattern_model)

        # Ensure primary stable models are always present in fallback chain
        for stable in ["gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro"]:
            if stable not in candidates:
                candidates.append(stable)

        return candidates

    @classmethod
    async def verify_key(cls, api_key: str) -> Dict[str, Any]:
        """
        Verifies the validity of the user's Google Gemini API key.
        Queries Google's canonical /models endpoint to validate authentication permissions
        without spending generation tokens.
        """
        clean_key = (api_key or "").strip()
        if not clean_key:
            return {"valid": False, "message": "API key cannot be empty."}

        candidate_bases = cls._get_candidate_bases()

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Primary verification: GET /models?key=...
            for base in candidate_bases:
                try:
                    res = await client.get(f"{base}/models", params={"key": clean_key})
                    if res.status_code == 200:
                        # Auto-populate discovery cache from successful response
                        data = res.json()
                        raw_models = data.get("models", [])
                        capable = [
                            m.get("name", "").replace("models/", "").strip()
                            for m in raw_models
                            if "generateContent" in m.get("supportedGenerationMethods", [])
                        ]
                        scored = sorted(
                            [m for m in capable if _score_model_preference(m) > 0],
                            key=_score_model_preference,
                            reverse=True
                        )
                        if scored:
                            key_hash = hashlib.sha256(clean_key.encode("utf-8")).hexdigest()
                            _DISCOVERY_CACHE[key_hash] = {
                                "models": scored,
                                "expires_at": time.time() + CACHE_TTL_SECONDS
                            }
                            top_model = scored[0]
                            return {
                                "valid": True,
                                "message": f"Google Gemini API key verified. Auto-discovered {len(scored)} models (primary: {top_model})."
                            }
                        return {"valid": True, "message": "Google Gemini API key verified and operational."}
                    elif res.status_code in (400, 403):
                        data = res.json()
                        err_msg = data.get("error", {}).get("message", "Invalid API key or insufficient permissions.")
                        return {"valid": False, "message": f"Google Gemini rejected key: {err_msg}"}
                except httpx.RequestError:
                    continue

            # 2. Secondary fallback probe using candidate models
            candidates = await cls.get_prioritized_candidates(clean_key, client=client)
            for test_model in candidates[:3]:
                for base in candidate_bases:
                    url = f"{base}/models/{test_model}:generateContent"
                    payload = {
                        "contents": [{"parts": [{"text": "PING"}]}],
                        "generationConfig": {"maxOutputTokens": 5, "temperature": 0.0}
                    }
                    headers = {"Content-Type": "application/json"}
                    params = {"key": clean_key}

                    try:
                        response = await client.post(url, headers=headers, json=payload, params=params)
                        if response.status_code == 200:
                            return {"valid": True, "message": f"Google Gemini API key verified with {test_model}."}
                        elif response.status_code in (400, 403):
                            data = response.json()
                            err_msg = data.get("error", {}).get("message", "Invalid API key or insufficient permissions.")
                            return {"valid": False, "message": f"Google Gemini rejected key: {err_msg}"}
                        elif response.status_code == 404:
                            continue
                    except httpx.RequestError as exc:
                        logger.debug(f"Secondary probe error for {test_model}: {exc}")
                        continue

            return {"valid": False, "message": "Google Gemini endpoint unreachable or key invalid."}

    @classmethod
    async def generate_d2c_content(
        cls,
        api_key: str,
        system_instruction: str,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes an autonomous completion request against Google Gemini using the caller's BYOK key.
        
        Dynamically discovers models, iterates candidate fallback chains, and gracefully handles
        endpoint migrations or deprecated models to ensure zero 404 errors.
        """
        clean_key = (api_key or "").strip()
        if not clean_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gemini BYOK key is missing or invalid."
            )

        candidate_bases = cls._get_candidate_bases()
        
        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        
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
        params = {"key": clean_key}

        start_time = time.perf_counter()
        response: Optional[httpx.Response] = None
        successful_model: Optional[str] = None
        last_error_detail: Optional[str] = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build dynamic, prioritized candidate list targeting standard content generation endpoints
            candidates = await cls.get_prioritized_candidates(
                api_key=clean_key,
                requested_model=model,
                client=client
            )

            candidate_queue = list(candidates)
            tried_models = set()

            # Iterate through candidate models with dynamic fallback support
            while candidate_queue:
                candidate_model = candidate_queue.pop(0)
                if candidate_model in tried_models:
                    continue
                tried_models.add(candidate_model)

                for base in candidate_bases:
                    url = f"{base}/models/{candidate_model}:generateContent"
                    try:
                        res = await client.post(url, headers=headers, json=payload, params=params)
                        
                        if res.status_code == 200:
                            response = res
                            successful_model = candidate_model
                            break
                        elif res.status_code == 404:
                            logger.info(
                                f"Model '{candidate_model}' at '{base}' returned 404. "
                                f"Dynamic engine cascading to next candidate..."
                            )
                            continue
                        elif res.status_code in (400, 403):
                            # Inspect error to see if it's model-specific vs auth
                            try:
                                err_json = res.json()
                                msg = err_json.get("error", {}).get("message", "")
                            except Exception:
                                msg = res.text
                            
                            msg_lower = msg.lower()

                            # If Google reports "Interactions API" error, immediately default fallback to standard gemini-2.5-flash-lite
                            if "interaction" in msg_lower or "interactions api" in msg_lower:
                                logger.warning(
                                    f"Google returned Interactions API error for '{candidate_model}': {msg}. "
                                    f"Immediately defaulting fallback cascade to standard 'gemini-2.5-flash-lite'..."
                                )
                                last_error_detail = msg
                                # Immediately push standard gemini-2.5-flash-lite and stable fallbacks to the front of queue
                                if "gemini-2.5-flash-lite" not in tried_models:
                                    candidate_queue = ["gemini-2.5-flash-lite"] + [c for c in candidate_queue if c != "gemini-2.5-flash-lite"]
                                break

                            # If model is unsupported/not found for this version/endpoint, fall back
                            if any(phrase in msg_lower for phrase in ["not found", "unsupported", "only supports"]):
                                logger.info(f"Model '{candidate_model}' reported unsupported: {msg}. Cascading...")
                                last_error_detail = msg
                                break
                            
                            # Otherwise, authentication or client payload error
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Gemini BYOK Key Error: {msg}"
                            )
                        elif res.status_code == 429:
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Gemini BYOK Quota Exceeded on your personal Google AI key. Please check your AI Studio limits."
                            )
                        elif res.status_code in (500, 502, 503, 504):
                            # Upstream transient error on this model, try fallback
                            logger.warning(f"Google Gemini upstream {res.status_code} on {candidate_model}. Cascading...")
                            last_error_detail = f"Upstream error {res.status_code} on {candidate_model}"
                            continue
                        else:
                            last_error_detail = f"Status {res.status_code} from provider"
                            continue
                    except httpx.TimeoutException:
                        logger.warning(f"Timeout on {candidate_model} at {base}. Cascading...")
                        last_error_detail = "Timeout contacting Google Gemini"
                        continue
                    except httpx.RequestError as exc:
                        logger.warning(f"Network error on {candidate_model} at {base}: {exc}")
                        last_error_detail = str(exc)
                        continue

                if response is not None:
                    break

        if response is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unable to complete request across dynamic candidate models. Last error: {last_error_detail or 'No available endpoint responded'}"
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response_json = response.json()

        candidates_data = response_json.get("candidates", [])
        if not candidates_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No generation candidates returned from Google Gemini."
            )

        first_candidate = candidates_data[0]
        parts = first_candidate.get("content", {}).get("parts", [])
        raw_text = "".join(part.get("text", "") for part in parts)

        usage = response_json.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)

        parsed_result: Any = raw_text
        if response_schema:
            try:
                parsed_result = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed_result = {"raw_output": raw_text}

        return {
            "model": successful_model or "gemini-auto",
            "latency_ms": latency_ms,
            "total_tokens": total_tokens,
            "result": parsed_result
        }


gemini_service = GeminiBYOKService()
