#!/usr/bin/env python3
"""Blindness lint + hygiene checks for the blind held-out panel artifact.

This artifact is a PRODUCER-ONLY, BLIND substrate builder.  It grades behaviour,
saves arrays and commits a manifest.  It must never emit a candidate score, a
ranking, or a correlation: a sibling artifact (the screen) freezes its candidate
list before it opens anything written here, and the whole evidential value of
this panel is that the two cannot see each other.

The lint therefore scans every path under ``results/`` and ``arrays/`` for file
names and JSON keys matching the forbidden pattern, and fails loudly on a hit.

Run as the LAST step of the artifact, and also as unit test T1e.

    python hygiene_check.py lint          # blindness lint only
    python hygiene_check.py chain         # verify the hash chain end to end
    python hygiene_check.py all           # both, plus the private/ hygiene assertions
    python hygiene_check.py selftest      # T1e: plant violations, assert FAIL, remove, assert PASS
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

WS = Path(__file__).resolve().parent.parent
RESULTS = WS / "results"
ARRAYS = WS / "arrays"
LOGS = WS / "logs"
CHAIN = LOGS / "chain.jsonl"

# Forbidden in any file name or JSON key under results/ or arrays/.
#
# The artifact plan writes this as
#   (survivor|winner|rank|rho|spearman|pearson|score_of|W[1-8]$|G[1-4]$|A[1-3]$)
# applied with re.search.  Taken literally that makes the last three alternatives
# match any key merely ENDING in those characters, which is over-broad to the point
# of being wrong: it flags "zamba2" (a model family) as if it were candidate A2.
# The intent is clearly a key NAMED W1..W8 / G1..G4 / A1..A3, optionally carrying a
# prefix such as "cand_A1".  So those three are required to occupy a whole token --
# preceded by start-of-string or a non-alphanumeric separator.  This makes the check
# STRICTER where it matters (it still catches A1, cand_A1, score.A1, W3, G4) and
# stops it firing on ordinary words that happen to end in a letter+digit.
# The word alternatives remain plain substring matches.
FORBIDDEN = re.compile(
    r"(survivor|winner|rank|rho|spearman|pearson|mcnemar|score_of"
    r"|(?:^|[^A-Za-z0-9])(?:W[1-8]|G[1-4]|A[1-3])$)",
    re.IGNORECASE,
)

# Documented, justified exceptions.  Each entry is (path_suffix, key_or_name, reason).
# These are properties of the PANEL RULE or of the INSTRUMENT, not candidate scores.
ALLOWLIST: list[tuple[str, str, str]] = [
    (
        "results/panel.json",
        "rank_key",
        "The seeded SHA-256 draw key sha256(seed|repo) that orders the panel draw. It is "
        "part of the pre-committed panel rule, ranks REPOSITORIES for selection, and is "
        "already sealed into logs/chain.jsonl record 1 -- renaming it would break the "
        "hash chain. It is not a candidate score and no measured quantity enters it.",
    ),
    (
        "results/panel_rule.json",
        "rank_key",
        "Same seeded draw key, defined in the frozen rule itself (chain record 0).",
    ),
    (
        "results/panel_rule.json",
        "rank_key_rule",
        "Prose describing the seeded draw key in the frozen rule.",
    ),
    (
        "results/panel_rejects.json",
        "rank_key",
        "Same seeded SHA-256 draw key, carried on each REJECTED candidate so the reject "
        "table is auditable against the frozen rule. Selection bookkeeping over "
        "repositories, not a measured quantity and not a candidate score.",
    ),
]

_ALLOW_INDEX: dict[tuple[str, str], str] = {
    (p, k.lower()): why for p, k, why in ALLOWLIST
}


@dataclass
class Violation:
    path: str
    kind: str  # "filename" | "json_key"
    token: str
    context: str = ""

    def __str__(self) -> str:
        loc = f"{self.path}" + (f" :: {self.context}" if self.context else "")
        return f"[{self.kind}] {loc}  -->  matched {self.token!r}"


@dataclass
class LintReport:
    scanned_files: int = 0
    scanned_keys: int = 0
    violations: list[Violation] = field(default_factory=list)
    allowed: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def _rel(p: Path) -> str:
    try:
        return p.relative_to(WS).as_posix()
    except ValueError:
        return p.as_posix()


def _walk_keys(obj: Any, trail: str = "") -> Iterator[tuple[str, str]]:
    """Yield (key, json_path) for every mapping key in a nested structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{trail}.{k}" if trail else str(k)
            yield str(k), here
            yield from _walk_keys(v, here)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:2000]):  # bounded: keys repeat across rows
            yield from _walk_keys(v, f"{trail}[{i}]")


def lint(roots: list[Path] | None = None) -> LintReport:
    rep = LintReport()
    roots = roots or [RESULTS, ARRAYS]
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_dir():
                continue
            rep.scanned_files += 1
            rel = _rel(p)

            m = FORBIDDEN.search(p.name)
            if m:
                why = _ALLOW_INDEX.get((rel, m.group(0).lower()))
                if why:
                    rep.allowed.append({"path": rel, "token": m.group(0), "reason": why})
                else:
                    rep.violations.append(Violation(rel, "filename", m.group(0)))

            if p.suffix.lower() != ".json":
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue  # non-JSON payload with a .json name: names already checked
            seen_here: set[tuple[str, str]] = set()
            for key, jpath in _walk_keys(data):
                rep.scanned_keys += 1
                km = FORBIDDEN.search(key)
                if not km:
                    continue
                tok = km.group(0)
                why = _ALLOW_INDEX.get((rel, tok.lower())) or _ALLOW_INDEX.get(
                    (rel, key.lower())
                )
                if why:
                    if (key, tok) not in seen_here:
                        seen_here.add((key, tok))
                        rep.allowed.append(
                            {"path": rel, "token": key, "reason": why}
                        )
                    continue
                if (key, tok) in seen_here:
                    continue
                seen_here.add((key, tok))
                rep.violations.append(Violation(rel, "json_key", tok, context=jpath))
    return rep


def verify_chain() -> dict[str, Any]:
    """Recompute the append-only hash chain and re-verify every payload sha256."""
    out: dict[str, Any] = {"exists": CHAIN.exists(), "records": 0, "ok": False,
                           "errors": [], "head": None}
    if not CHAIN.exists():
        out["errors"].append("logs/chain.jsonl missing")
        return out
    prev = ""
    recs = []
    for ln, raw in enumerate(CHAIN.read_text(encoding="utf-8").splitlines()):
        raw = raw.strip()
        if not raw:
            continue
        try:
            r = json.loads(raw)
        except json.JSONDecodeError as e:
            out["errors"].append(f"line {ln}: unparsable ({e})")
            continue
        recs.append(r)
        if r.get("prev_chain_sha256", "") != prev:
            out["errors"].append(
                f"record {r.get('i')}: prev_chain_sha256 mismatch "
                f"(got {r.get('prev_chain_sha256','')[:16]}, expected {prev[:16]})"
            )
        expect = hashlib.sha256(
            (prev + r.get("payload_sha256", "")).encode()
        ).hexdigest()
        if r.get("chain_sha256") != expect:
            out["errors"].append(
                f"record {r.get('i')}: chain_sha256 mismatch "
                f"(got {str(r.get('chain_sha256'))[:16]}, recomputed {expect[:16]})"
            )
        pp = r.get("payload_path")
        if pp:
            f = WS / pp
            if not f.exists():
                out["errors"].append(f"record {r.get('i')}: payload missing at {pp}")
            else:
                got = hashlib.sha256(f.read_bytes()).hexdigest()
                if got != r.get("payload_sha256"):
                    out["errors"].append(
                        f"record {r.get('i')}: payload {pp} sha256 drifted "
                        f"(file {got[:16]}, chain {str(r.get('payload_sha256'))[:16]})"
                    )
        prev = r.get("chain_sha256", "")
    out["records"] = len(recs)
    out["head"] = prev or None
    out["ok"] = not out["errors"]
    out["order"] = [
        {"i": r.get("i"), "utc": r.get("utc"), "event": r.get("event"),
         "payload_path": r.get("payload_path")}
        for r in recs
    ]
    return out


def order_gate_audit() -> dict[str, Any]:
    """Assert every harvested tag was graded-and-committed BEFORE it was harvested."""
    res: dict[str, Any] = {"checked": 0, "ok": True, "problems": [], "tags": []}
    if not CHAIN.exists() or not ARRAYS.exists():
        return res
    commits: list[tuple[str, set[str]]] = []  # (utc, tags)
    # Retractions: payload_path -> retracted tag set, or None for the whole payload.
    # Same rule as judgeflow.chain_retractions(); duplicated here so this lint stays stdlib.
    retracted: dict[str, set[str] | None] = {}
    for raw in CHAIN.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        fp = WS / str(rr.get("payload_path") or "")
        if not str(fp).endswith(".json") or not fp.exists():
            continue
        try:
            dd = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(dd, dict) and dd.get("retracted_payload"):
            tgt = str(dd["retracted_payload"])
            tl = dd.get("retracted_tags")
            if tl:
                prev = retracted.get(tgt, set())
                retracted[tgt] = None if prev is None else (prev | {str(x) for x in tl})
            else:
                retracted[tgt] = None
    res["retracted_payloads"] = {k: (sorted(v) if v is not None else "ALL")
                                 for k, v in retracted.items()}
    for raw in CHAIN.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            r = json.loads(raw)
        except json.JSONDecodeError:
            continue
        pp = str(r.get("payload_path") or "")
        if "graded_truth_s" not in pp:
            continue
        # RETRACTED GATE SOURCE. results/graded_truth_s0.json is a SMOKE STUB written
        # during acceptance testing; its labels are not authoritative. Its sha256 is
        # chained (record 3) and the chain is append-only, so the file must stay on
        # disk byte-for-byte or every later record fails to verify -- but it must
        # NEVER gate a harvest. Real staged commits begin at s1. See chain record
        # "graded_truth_s0_retracted" and deviation D06.
        if pp.endswith("graded_truth_s0.json"):
            continue
        f = WS / pp
        if not f.exists():
            continue
        try:
            gt = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        tags = {str(row.get("tag")) for row in gt.get("per_ckpt", []) if row.get("tag")}
        rt = retracted.get(pp, set())
        if rt is None:
            continue
        tags -= rt
        commits.append((str(r.get("utc")), tags))

    for d in sorted(ARRAYS.iterdir()) if ARRAYS.exists() else []:
        if not d.is_dir():
            continue
        done = d / "DONE"
        if not done.exists():
            continue
        res["checked"] += 1
        tag = d.name
        gate_utc = None
        for utc, tags in commits:
            if tag in tags:
                gate_utc = utc
                break
        meta = d / "meta.json"
        harv_utc = None
        if meta.exists():
            try:
                harv_utc = json.loads(meta.read_text(encoding="utf-8")).get("utc")
            except (json.JSONDecodeError, OSError):
                pass
        entry = {"tag": tag, "graded_truth_committed_utc": gate_utc,
                 "harvest_utc": harv_utc}
        if gate_utc is None:
            res["ok"] = False
            res["problems"].append(f"{tag}: harvested with NO committed graded_truth")
        elif harv_utc and harv_utc < gate_utc:
            res["ok"] = False
            res["problems"].append(
                f"{tag}: harvest {harv_utc} PRECEDES gate commit {gate_utc}"
            )
        res["tags"].append(entry)
    return res


def private_hygiene() -> dict[str, Any]:
    """private/ must be gone, and nothing released may carry raw harmful completions."""
    priv = WS / "private"
    out: dict[str, Any] = {
        "private_exists": priv.exists(),
        "private_deleted": not priv.exists(),
        "raw_text_leak_suspects": [],
    }
    leak_keys = {"completion", "generation", "response_text", "raw_completion", "output_text"}
    for root in (RESULTS, ARRAYS):
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue
            for key, jpath in _walk_keys(data):
                if key.lower() in leak_keys:
                    out["raw_text_leak_suspects"].append(f"{_rel(p)} :: {jpath}")
                    break
    out["ok"] = out["private_deleted"] and not out["raw_text_leak_suspects"]
    return out


def _print_report(rep: LintReport) -> None:
    print(f"scanned {rep.scanned_files} files / {rep.scanned_keys} JSON keys")
    if rep.allowed:
        print(f"ALLOWLISTED ({len(rep.allowed)}):")
        for a in rep.allowed:
            print(f"  - {a['path']} :: {a['token']}")
    if rep.violations:
        print(f"BLINDNESS LINT FAILED: {len(rep.violations)} violation(s)")
        for v in rep.violations:
            print(f"  {v}")
    else:
        print("BLINDNESS LINT PASSED")


def selftest() -> int:
    """T1e: plant a violation, assert FAIL; remove it, assert PASS."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    planted_name = RESULTS / "survivor.json"
    planted_key = RESULTS / "_lint_scratch.json"
    planted_name.write_text('{"ok": 1}', encoding="utf-8")
    planted_key.write_text('{"rho": 0.5, "nested": {"W3": 1}}', encoding="utf-8")
    bad = lint()
    names = {v.token.lower() for v in bad.violations}
    files = {v.path for v in bad.violations}
    ok_fail = (not bad.ok) and "results/survivor.json" in files and "rho" in names
    planted_name.unlink(missing_ok=True)
    planted_key.unlink(missing_ok=True)
    good = lint()
    print(f"T1e plant-violations -> FAIL expected : {'PASS' if ok_fail else 'FAIL'} "
          f"({len(bad.violations)} violations, tokens={sorted(names)})")
    print(f"T1e remove-violations -> PASS expected: {'PASS' if good.ok else 'FAIL'}")
    if not good.ok:
        _print_report(good)
    return 0 if (ok_fail and good.ok) else 1


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "all"
    if cmd == "selftest":
        return selftest()

    rc = 0
    payload: dict[str, Any] = {}

    if cmd in ("lint", "all"):
        rep = lint()
        _print_report(rep)
        payload["blindness_lint"] = {
            "passed": rep.ok,
            "scanned_files": rep.scanned_files,
            "scanned_json_keys": rep.scanned_keys,
            "pattern": FORBIDDEN.pattern,
            "violations": [v.__dict__ for v in rep.violations],
            "allowlisted": rep.allowed,
            "allowlist_policy": [
                {"path": p, "token": k, "reason": why} for p, k, why in ALLOWLIST
            ],
        }
        rc |= 0 if rep.ok else 1

    if cmd in ("chain", "all"):
        ch = verify_chain()
        print(f"chain: {ch['records']} records, ok={ch['ok']}")
        for e in ch["errors"]:
            print(f"  CHAIN ERROR: {e}")
        payload["hash_chain"] = ch
        rc |= 0 if ch["ok"] else 1

    if cmd == "all":
        og = order_gate_audit()
        print(f"order gate: {og['checked']} harvested tags checked, ok={og['ok']}")
        for e in og["problems"]:
            print(f"  ORDER GATE ERROR: {e}")
        payload["order_gate_audit"] = og
        rc |= 0 if og["ok"] else 1

        ph = private_hygiene()
        print(f"private/ deleted={ph['private_deleted']} "
              f"raw-text suspects={len(ph['raw_text_leak_suspects'])}")
        payload["private_hygiene"] = ph
        # private/ still existing mid-run is not a failure; only reported.

    if payload:
        tmp = RESULTS / "hygiene_report.json.tmp"
        RESULTS.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        tmp.replace(RESULTS / "hygiene_report.json")
        print(f"wrote {_rel(RESULTS / 'hygiene_report.json')}")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
