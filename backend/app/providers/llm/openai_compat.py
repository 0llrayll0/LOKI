"""Adapter para endpoints compatíveis com OpenAI (inclui Ollama /v1)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class OpenAICompatProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request(self, path: str, method: str = "GET", data: Any = None) -> tuple[int, dict]:
        url = self.base_url + path
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return resp.status, (json.loads(raw) if raw else {})
                except json.JSONDecodeError:
                    return resp.status, {"raw": raw}
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                payload = {}
            return exc.code, payload
        except Exception as exc:  # noqa: BLE001
            return 0, {"error": str(exc)}

    def _v1_models(self) -> list[str]:
        status, payload = self._request("/models")
        if status != 200:
            return []
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
        return out

    def list_models(self) -> list[str]:
        models = self._v1_models()
        if models:
            return models
        # Ollama native (/api/tags), tolerando base_url com ou sem /v1
        root = self.base_url
        if root.endswith("/v1"):
            root = root[:-3]
        url = root + "/api/tags"
        # temporarily fetch through urllib
        try:
            import json as _json
            import urllib.request as _ur

            req = _ur.Request(url, headers=self._headers(), method="GET")
            with _ur.urlopen(req, timeout=self.timeout) as resp:
                payload = _json.loads(resp.read().decode("utf-8"))
            out = []
            for m in (payload.get("models", []) if isinstance(payload, dict) else []):
                if isinstance(m, dict) and m.get("name"):
                    out.append(str(m["name"]))
            return out
        except Exception:
            return []

    def validate_credentials(self) -> tuple[bool, str | None]:
        models = self.list_models()
        if models:
            return True, None
        status, payload = self._request("/models")
        if status == 200:
            return True, None
        err = None
        if isinstance(payload, dict):
            err = None
            if isinstance(payload.get("error"), dict):
                err = payload.get("error", {}).get("message")
            else:
                err = payload.get("error")
        # Ollama / health
        if status == 0:
            return False, str(err or "servidor inacessível")
        return False, str(err or f"HTTP {status}")

    def health_check(self) -> tuple[bool, str | None]:
        return self.validate_credentials()

    def generate(self, prompt: str, *, max_tokens: int = 256) -> str:
        model = self.model or (self.list_models()[:1] or [""])[0]
        if not model:
            raise RuntimeError("nenhum modelo selecionado/disponível")
        status, payload = self._request(
            "/chat/completions",
            method="POST",
            data={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        if status != 200:
            err = payload.get("error") if isinstance(payload, dict) else payload
            raise RuntimeError(str(err or f"HTTP {status}"))
        try:
            return str(payload["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"resposta inesperada: {exc}") from exc


