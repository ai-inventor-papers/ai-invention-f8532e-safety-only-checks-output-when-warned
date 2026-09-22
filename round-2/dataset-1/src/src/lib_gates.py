#!/usr/bin/env python3
"""Gate bookkeeping. Every gate in prereg.json gets an entry with an OBSERVED number
and a status in {PASS, FAIL, NOT_APPLICABLE}. A failed gate is reported as FAILED with
its number in the artifact's own summary - never relaxed, never buried.
"""
from __future__ import annotations

import json
from pathlib import Path


class Gates:
    def __init__(self, prereg: dict) -> None:
        self._spec = {g["gate_id"]: g for g in prereg["gates"]}
        self._rows: dict[str, dict] = {}

    def record(self, gate_id: str, observed, status: str, note: str = "") -> None:
        if status not in ("PASS", "FAIL", "NOT_APPLICABLE"):
            raise ValueError(f"bad gate status {status!r}")
        spec = self._spec.get(gate_id, {})
        self._rows[gate_id] = {
            "gate_id": gate_id,
            "description": spec.get("description", note or gate_id),
            "threshold": spec.get("threshold"),
            "observed": observed,
            "status": status,
            "note": note,
        }

    def check_ge(self, gate_id: str, observed, threshold, note: str = "") -> None:
        ok = observed is not None and observed >= threshold
        self.record(gate_id, observed, "PASS" if ok else "FAIL", note)

    def check_le(self, gate_id: str, observed, threshold, note: str = "") -> None:
        ok = observed is not None and observed <= threshold
        self.record(gate_id, observed, "PASS" if ok else "FAIL", note)

    def check_eq(self, gate_id: str, observed, expected, note: str = "") -> None:
        self.record(gate_id, observed, "PASS" if observed == expected else "FAIL", note)

    def missing(self) -> list[str]:
        return sorted(set(self._spec) - set(self._rows))

    def rows(self) -> list[dict]:
        out = list(self._rows.values())
        for gid in self.missing():
            spec = self._spec[gid]
            out.append({"gate_id": gid, "description": spec["description"],
                        "threshold": spec["threshold"], "observed": None,
                        "status": "NOT_APPLICABLE",
                        "note": "no observation was produced for this gate"})
        return sorted(out, key=lambda r: r["gate_id"])

    def summary(self) -> dict:
        rs = self.rows()
        return {"n_gates": len(rs),
                "n_pass": sum(r["status"] == "PASS" for r in rs),
                "n_fail": sum(r["status"] == "FAIL" for r in rs),
                "n_not_applicable": sum(r["status"] == "NOT_APPLICABLE" for r in rs),
                "failed_gates": [{"gate_id": r["gate_id"], "threshold": r["threshold"],
                                  "observed": r["observed"]}
                                 for r in rs if r["status"] == "FAIL"]}

    def write(self, path: Path) -> dict:
        payload = {"summary": self.summary(), "gates": self.rows()}
        path.write_text(json.dumps(payload, indent=1))
        return payload

    def table(self) -> str:
        lines = ["| gate_id | threshold | observed | status |",
                 "|---|---|---|---|"]
        for r in self.rows():
            lines.append(f"| {r['gate_id']} | {r['threshold']} | {r['observed']} | "
                         f"**{r['status']}** |")
        return "\n".join(lines)
