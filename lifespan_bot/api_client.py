from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests


class BinjieClient:
    """Client for https://api.binjie.fun/api/generateStream"""

    def __init__(
        self,
        base_url: str = "https://api.binjie.fun/api/generateStream",
        timeout_seconds: int = 30,
        default_user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36"
        ),
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.default_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://chat18.aichatos.xyz",
            "referer": "https://chat18.aichatos.xyz/",
            "user-agent": default_user_agent,
            # Encourage Persian output and proper decoding
            "accept-language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _post_with_retries(
        self,
        payload: Dict[str, Any],
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
    ) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.default_headers,
                    data=json.dumps(payload),
                    timeout=self.timeout_seconds,
                )
                # Retry on common transient codes
                if response.status_code in {429, 502, 503, 504, 520, 521, 522}:
                    if attempt < max_attempts:
                        time.sleep(backoff_seconds * attempt)
                        continue
                return response
            except Exception as exc:  # network errors
                last_exc = exc
                if attempt < max_attempts:
                    time.sleep(backoff_seconds * attempt)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Unreachable: retry loop exited without result")

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        user_id: Optional[str] = None,
        network: bool = True,
        without_context: bool = False,
        stream: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        headers = dict(self.default_headers)
        if extra_headers:
            headers.update(extra_headers)

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "userId": user_id or "lifespan-cli",
            "network": bool(network),
            "system": system or "",
            "withoutContext": bool(without_context),
            "stream": bool(stream),
        }
        if extra_payload:
            payload.update(extra_payload)

        response = self._post_with_retries(payload)
        if response.status_code != 200:
            raise RuntimeError(
                f"API request failed: {response.status_code} {response.text[:500]}"
            )

        # Some deployments return text/plain even for JSON content
        # Try to ensure correct decoding
        try:
            if not response.encoding:
                response.encoding = response.apparent_encoding or "utf-8"
        except Exception:
            response.encoding = "utf-8"
        text = response.text.strip()
        return text

    @staticmethod
    def try_extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to parse JSON payload from a model output. Supports:
        - Plain JSON
        - JSON wrapped in triple backticks
        - Outputs with pre/post text where a JSON object is embedded
        """
        text = text.strip()
        # Fast path: direct JSON
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try fenced code blocks
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                candidate = part.strip()
                if not candidate:
                    continue
                # Remove potential language tag line
                if "\n" in candidate:
                    first_line, rest = candidate.split("\n", 1)
                    if first_line.strip().lower() in {"json", "js", "javascript"}:
                        candidate = rest
                try:
                    return json.loads(candidate)
                except Exception:
                    continue

        # Heuristic: find first JSON object via braces balance
        start_idx = text.find("{")
        if start_idx != -1:
            depth = 0
            for i in range(start_idx, len(text)):
                ch = text[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start_idx : i + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            break
        return None
