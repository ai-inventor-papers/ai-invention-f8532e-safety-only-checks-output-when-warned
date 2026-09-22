#!/usr/bin/env python3
"""Async OpenRouter client with a hard spend cap and cost-ledger booking.

Every call's cost is appended to AII_COST_LEDGER so it reaches the run budget.
The cap is enforced BEFORE each request is issued; once tripped, all remaining
calls return None and the caller must report the uncovered work as NOT EVALUATED.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger

API_URL = "https://openrouter.ai/api/v1/chat/completions"
CATALOG_URL = "https://openrouter.ai/api/v1/models"


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class ORClient:
    cap_usd: float
    tool: str = "aii_or_call_llms"
    _spent: float = 0.0
    _n_calls: int = 0
    _n_fail: int = 0
    _prices: dict[str, tuple[float, float]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _ledger: str | None = field(default_factory=lambda: os.environ.get("AII_COST_LEDGER"))

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def n_calls(self) -> int:
        return self._n_calls

    @property
    def n_fail(self) -> int:
        return self._n_fail

    async def load_catalog(self, session: aiohttp.ClientSession) -> None:
        async with session.get(CATALOG_URL, timeout=aiohttp.ClientTimeout(total=60)) as r:
            data = await r.json()
        for m in data.get("data", []):
            p = m.get("pricing") or {}
            try:
                self._prices[m["id"]] = (float(p.get("prompt", 0) or 0), float(p.get("completion", 0) or 0))
            except (TypeError, ValueError):
                continue
        logger.info(f"OpenRouter catalog loaded: {len(self._prices)} models priced")

    def _cost(self, model: str, usage: dict[str, Any]) -> float:
        if usage.get("cost") is not None:
            try:
                return float(usage["cost"])
            except (TypeError, ValueError):
                pass
        pin, pout = self._prices.get(model, (0.0, 0.0))
        return usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout

    def _book(self, cost: float, **meta: Any) -> None:
        if not self._ledger:
            return
        rec = {"ts": time.time(), "tool": self.tool, "cost_usd": float(cost), **meta}
        try:
            with open(self._ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError as e:
            logger.warning(f"ledger write failed: {e}")

    async def call(
        self,
        session: aiohttp.ClientSession,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 3000,
        temperature: float = 0.0,
        retries: int = 3,
    ) -> dict[str, Any] | None:
        """Returns {'text':…, 'cost':…} or None if the budget is exhausted / the call failed."""
        async with self._lock:
            if self._spent >= self.cap_usd:
                return None
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        headers = {
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        }
        for attempt in range(retries):
            try:
                async with session.post(
                    API_URL, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=180)
                ) as r:
                    if r.status in (429, 500, 502, 503, 520, 524):
                        await asyncio.sleep(2 ** attempt + 1)
                        continue
                    data = await r.json()
                if "error" in data and not data.get("choices"):
                    logger.warning(f"{model}: API error {str(data['error'])[:200]}")
                    await asyncio.sleep(2 ** attempt)
                    continue
                usage = data.get("usage") or {}
                cost = self._cost(model, usage)
                text = data["choices"][0]["message"]["content"] or ""
                async with self._lock:
                    self._spent += cost
                    self._n_calls += 1
                self._book(
                    cost,
                    model=model,
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                )
                return {"text": text, "cost": cost, "usage": usage}
            except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, json.JSONDecodeError) as e:
                logger.warning(f"{model}: attempt {attempt+1}/{retries} failed: {type(e).__name__}: {e}")
                await asyncio.sleep(2 ** attempt)
        async with self._lock:
            self._n_fail += 1
        return None


_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def parse_json(text: str) -> Any | None:
    """Tolerant JSON extraction from a model reply."""
    if not text:
        return None
    m = _JSON_RE.search(text)
    cand = m.group(1) if m else text
    for c in (cand, cand[cand.find("["): cand.rfind("]") + 1], cand[cand.find("{"): cand.rfind("}") + 1]):
        if not c:
            continue
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    return None
