"""Traced local inference boundary; protocol calls do not use syntax repair."""
from __future__ import annotations
import hashlib
import json
import re
import time
from pathlib import Path
import httpx


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def public_case(row):
    """Whitelist inputs rather than removing a known set of answer fields."""
    return {k: row[k] for k in ("id", "dataset", "question", "context", "options") if k in row}

def normalize_label(value, options):
    """Return exactly one legal choice, or None. Never fall back to choice A."""
    if not isinstance(value, str):
        return None
    label = value.strip().strip(" .()[]").upper()
    return label if label in options else None

def extract_final_choice(text, options):
    exact = normalize_label(text, options)
    if exact:
        return exact
    cleaned = re.sub(r"[*`]+", "", str(text)).strip().strip("'\" \n\t")
    cleaned = re.sub(r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:[✅✓\-•>][ \t]*)?(?:[0-9]+[.)][ \t]*)?", "", cleaned)
    matches = re.findall(r"(?im)^\s*(?:the\s+)?(?:(?:final|correct|best)\s+)*(?:answer|option|choice)\s*(?:[:=]|is\s*:?)\s*\[?\(?([A-E])\b(?![ \t]*(?:or|and|/)[ \t]*[A-E]\b)", cleaned)
    return normalize_label(matches[-1], options) if matches else None

class TracedClient:
    def __init__(self, trace_path, base_url="http://127.0.0.1:23400/v1", model="qwen3-8b", seed=111,
                 temperature=0.0, max_output=None, token_limit=None):
        self.path = Path(trace_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.base_url, self.model, self.seed = base_url.rstrip("/"), model, seed
        self.temperature, self.max_output, self.token_limit = temperature, max_output, token_limit
        self.records = []
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=15.0), trust_env=False)

    async def close(self):
        await self.http.aclose()

    def usage(self):
        successful = [r for r in self.records if r.get("usage")]
        return {"calls": len(successful), "failed_calls": len(self.records)-len(successful),
                **{key: sum(r["usage"].get(key, 0) for r in successful)
                   for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
                "truncated_calls": sum(r.get("finish_reason") == "length" for r in self.records)}

    def append(self, record):
        self.records.append(record)
        with self.path.open("a") as f:
            f.write(dumps(record)+"\n")

    async def complete(self, system, user=None, *, tag="inference", max_tokens=512, messages=None,
                       temperature=None, seed=None, response_format=None):
        if self.token_limit is not None and self.usage()["total_tokens"] >= self.token_limit:
            raise RuntimeError("Measured token budget exhausted before the next request")
        if messages is None:
            messages = ([{"role": "system", "content": system}] if system else [])
            messages += [{"role": "user", "content": user or "Follow the instructions."}]
        request = {"model": self.model, "messages": messages,
                   "temperature": self.temperature if self.temperature is not None else (temperature or 0),
                   "max_tokens": min(max_tokens, self.max_output) if self.max_output else max_tokens,
                   "seed": self.seed if seed is None else seed, "chat_template_kwargs": {"enable_thinking": False}}
        if response_format is not None:
            request["response_format"] = response_format
        start = time.perf_counter()
        try:
            response = await self.http.post(self.base_url+"/chat/completions", json=request)
            response.raise_for_status()
            result = response.json()
            choice = result["choices"][0]
            record = {"tag": tag, "request": request, "response": choice["message"],
                      "usage": result.get("usage", {}), "finish_reason": choice.get("finish_reason"),
                      "latency_s": time.perf_counter()-start, "response_id": result.get("id")}
            self.append(record)
            return choice["message"].get("content") or ""
        except Exception as exc:
            # A failed request is visible; no silent retry or uncharged repair.
            record = {"tag": tag, "request": request, "error": str(exc),
                      "latency_s": time.perf_counter()-start}
            if isinstance(exc, httpx.HTTPStatusError):
                record.update(response_status_code=exc.response.status_code,
                              response_body=exc.response.text)
            self.append(record)
            raise
