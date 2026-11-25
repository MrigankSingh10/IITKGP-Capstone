"""Small OpenAI-compatible clients; errors never include response bodies or secrets."""
from dataclasses import dataclass
import os
import ssl
import time
from typing import Any
import ipaddress
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True, repr=False)
class APIConfig:
    base_url: str
    model: str
    api_key: str
    ca_file: str
    timeout: float = 30.0

    @classmethod
    def from_env(cls, prefix: str):
        names = ("BASE_URL", "MODEL", "API_KEY", "CA_FILE")
        values = [os.environ.get(f"{prefix}_{name}", "") for name in names]
        if not all(values):
            raise ValueError(f"Incomplete {prefix} configuration")
        return cls(*values)

    @staticmethod
    def _is_loopback_host(host: str | None) -> bool:
        if not host:
            return False
        cleaned = host.strip("[]").lower()
        if cleaned == "localhost":
            return True
        try:
            return ipaddress.ip_address(cleaned).is_loopback
        except ValueError:
            return False

    def __post_init__(self):
        url = urlsplit(self.base_url)
        allowed_scheme = url.scheme == "https" or (
            url.scheme == "http" and self._is_loopback_host(url.hostname)
        )
        if (not allowed_scheme or not url.hostname or url.username or url.password
                or url.query or url.fragment or not self.base_url.rstrip('/').endswith('/v1')):
            raise ValueError("Base URL must be HTTPS (or loopback HTTP), without credentials, and end in /v1")
        if not self.model or not self.api_key or self.timeout <= 0:
            raise ValueError("Model, key, and positive timeout are required")


class APIError(RuntimeError):
    pass


class HostedClient:
    def __init__(self, config: APIConfig, transport=None, retries: int = 3, sleeper=time.sleep):
        if retries < 0:
            raise ValueError("retries must be nonnegative")
        self.config, self.retries, self.sleeper = config, retries, sleeper
        cafile = config.ca_file if config.ca_file and config.ca_file.strip().lower() not in ('none', 'null') else None
        context = ssl.create_default_context(cafile=cafile)
        self.client = httpx.Client(verify=context, timeout=config.timeout, transport=transport,
                                   trust_env=False)
        self.usage: dict[str, int] = {}

    def close(self):
        self.client.close()

    def _post(self, route: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            try:
                response = self.client.post(
                    self.config.base_url.rstrip('/') + route, json=payload,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
            except httpx.TransportError:
                if attempt == self.retries:
                    raise APIError("API transport failed") from None
            else:
                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt == self.retries:
                        raise APIError(f"API failed after retries (HTTP {response.status_code})")
                elif not response.is_success:
                    raise APIError(f"API request failed (HTTP {response.status_code})")
                else:
                    try:
                        result = response.json()
                        if not isinstance(result, dict):
                            raise ValueError
                    except ValueError:
                        raise APIError("API returned invalid JSON") from None
                    usage = result.get("usage", {})
                    if isinstance(usage, dict):
                        for key, value in usage.items():
                            if isinstance(value, int) and not isinstance(value, bool):
                                self.usage[key] = self.usage.get(key, 0) + value
                    return result
            self.sleeper(2 ** (attempt + 1))
        raise APIError("API request failed")

    def chat(self, messages: list[dict[str, str]], **parameters: Any) -> dict[str, Any]:
        return self._post('/chat/completions', {**parameters, 'model': self.config.model,
                                                'messages': messages})

    def embed(self, inputs: list[str]) -> dict[str, Any]:
        if not inputs or not all(isinstance(x, str) and x for x in inputs):
            raise ValueError("inputs must be nonempty strings")
        return self._post('/embeddings', {'model': self.config.model, 'input': inputs})
