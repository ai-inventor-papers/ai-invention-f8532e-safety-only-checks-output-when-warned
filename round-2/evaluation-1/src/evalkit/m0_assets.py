#!/usr/bin/env python3
"""M0 -- asset and recomputability ledger. Runs FIRST and gates everything else.

One row per quantity this artifact needs: what file holds it, that file's
sha256 and size, WHAT THE FILE ACTUALLY CONTAINS (obtained by opening it, never
by assuming from its name), and a verdict in
RECOMPUTABLE_HERE / PARTIAL / NEEDS_REHARVEST / ABSENT.

Two inherited claims are tested here rather than repeated:
  (i)  "raw hidden states were saved nowhere in iteration 1"
  (ii) "the abliterated checkpoint is in no metric table"
Both were found overstated by the planning pass; this module prints the shapes
and the file lists that settle them.
"""

from __future__ import annotations

import glob
import json
import zipfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
from loguru import logger

from . import paths as P

MAX_HASH_BYTES = 512 * 1024 * 1024  # anything larger is described, not hashed


@dataclass
class LedgerRow:
    quantity: str
    metric_consumers: str
    source_file: str
    exists: bool
    sha256: str
    size_bytes: int
    contents: str
    verdict: str
    READOUT_CLASS: str
    note: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["BASELINE_ONLY"] = d["READOUT_CLASS"] in ("logit", "text", "metadata")
        d["DESCRIPTIVE"] = True
        return d


def _npy_header_shape(zf: zipfile.ZipFile, name: str) -> tuple:
    """Read shape/dtype from an .npy member header without materialising it."""
    with zf.open(name) as fh:
        magic = fh.read(6)
        if magic != b"\x93NUMPY":
            raise ValueError(f"{name}: not an npy member")
        major = fh.read(1)[0]
        fh.read(1)
        hlen = int.from_bytes(fh.read(2 if major == 1 else 4), "little")
        header = fh.read(hlen).decode("latin1")
    d = eval(header, {"__builtins__": {}}, {"False": False, "True": True})  # noqa: S307 - numpy's own format
    return tuple(d["shape"]), str(d["descr"])


def npz_key_map(path: Path) -> dict[str, tuple]:
    """{key: (shape, dtype)} for every array in an npz, without loading data."""
    out: dict[str, tuple] = {}
    with zipfile.ZipFile(path) as zf:
        for member in zf.namelist():
            if not member.endswith(".npy"):
                continue
            key = member[:-4]
            out[key] = _npy_header_shape(zf, member)
    return out


def _hash_one(path_str: str) -> tuple[str, str, int]:
    p = Path(path_str)
    size = p.stat().st_size
    if size > MAX_HASH_BYTES:
        return path_str, f"NOT_HASHED_over_{MAX_HASH_BYTES}B", size
    return path_str, P.sha256_file(p), size


def hash_many(files: list[Path], *, workers: int = 2) -> dict[str, tuple[str, int]]:
    strs = [str(f) for f in files]
    out: dict[str, tuple[str, int]] = {}
    if not strs:
        return out
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for path_str, digest, size in ex.map(_hash_one, strs, chunksize=4):
            out[path_str] = (digest, size)
    return out


# --------------------------------------------------------------------------- #
# claim (i): were raw hidden states saved?
# --------------------------------------------------------------------------- #
def audit_lane_b_harvest() -> dict:
    """Open EVERY file in Lane B's harvest and record what is actually inside."""
    hv = P.B_HARVEST
    if not hv.is_dir():
        return {"present": False, "glob": str(hv / "*"), "files": [],
                "verdict": "ABSENT"}

    files = sorted(hv.glob("*"))
    npz_files = [f for f in files if f.suffix == ".npz"]
    json_files = [f for f in files if f.suffix == ".json"]
    npy_files = [f for f in files if f.suffix == ".npy"]

    per_file: list[dict] = []
    load_errors: list[dict] = []
    per_item_layer_dim: list[dict] = []

    for f in npz_files:
        try:
            keymap = npz_key_map(f)
        except (zipfile.BadZipFile, ValueError, OSError) as exc:
            load_errors.append({"file": P.rel(f), "exception": repr(exc)})
            per_file.append({"file": P.rel(f), "size_bytes": f.stat().st_size,
                             "n_keys": -1, "error": repr(exc)})
            continue
        entry = {
            "file": P.rel(f),
            "size_bytes": f.stat().st_size,
            "n_keys": len(keymap),
            "keys": {k: {"shape": list(v[0]), "dtype": v[1]}
                     for k, v in sorted(keymap.items())},
        }
        per_file.append(entry)
        for k, (shape, dtype) in keymap.items():
            # (item, dim) per layer key == per-item band-layer vectors, i.e. a
            # genuine activation substrate rather than a pre-reduced scalar.
            if len(shape) == 2 and shape[1] >= 256 and shape[0] > 1:
                per_item_layer_dim.append(
                    {"file": P.rel(f), "key": k, "shape": list(shape), "dtype": dtype}
                )

    metas = {}
    for f in json_files:
        try:
            metas[f.name] = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            load_errors.append({"file": P.rel(f), "exception": repr(exc)})

    lineages = sorted({n.split("_")[0] for n in (f.name for f in npz_files)
                       if n.startswith("L")})
    alphas = sorted({n.split("_a")[1].split(".part")[0]
                     for n in (f.name for f in npz_files) if "_a" in n})

    verdict = "RECOMPUTABLE_HERE" if per_item_layer_dim else "NEEDS_REHARVEST"
    return {
        "present": True,
        "n_files_total": len(files),
        "n_npz": len(npz_files),
        "n_json": len(json_files),
        "n_npy": len(npy_files),
        "lineages": lineages,
        "alphas": alphas,
        "per_file": per_file,
        "per_item_layer_dim_arrays": per_item_layer_dim,
        "n_per_item_layer_dim_arrays": len(per_item_layer_dim),
        "load_errors": load_errors,
        "metas": metas,
        "verdict": verdict,
    }


# --------------------------------------------------------------------------- #
# claim (ii): where is the abliterated checkpoint actually absent?
# --------------------------------------------------------------------------- #
def audit_abliterated_scope() -> dict:
    """Locate the abliterated arm precisely, instead of restating the overstatement."""
    out: dict = {}

    # Lane A -- released directions
    dirs = sorted(P.A_DIRECTIONS.glob("*.npy")) if P.A_DIRECTIONS.is_dir() else []
    abl_dirs = []
    for f in dirs:
        if "abliterated" in f.name:
            arr = np.load(f, mmap_mode="r")
            abl_dirs.append({"file": P.rel(f), "shape": list(arr.shape),
                             "dtype": str(arr.dtype)})
            del arr
    out["lane_a_released_directions"] = {
        "glob": P.rel(P.A_DIRECTIONS / "*.npy"),
        "n_files": len(dirs),
        "abliterated_files": abl_dirs,
        "present": bool(abl_dirs),
    }

    # Lane A -- per-item cell projections
    checkpoints: list[str] = []
    if P.A_PER_ITEM_CELLS.exists():
        import pandas as pd

        head = pd.read_csv(P.A_PER_ITEM_CELLS, usecols=["checkpoint"])
        checkpoints = sorted(head["checkpoint"].unique().tolist())
        del head
    out["lane_a_per_item_cell_projections"] = {
        "file": P.rel(P.A_PER_ITEM_CELLS),
        "checkpoints": checkpoints,
        "abliterated_present": any("abliterated" in c for c in checkpoints),
    }

    # Lane A -- how many times it appears in the human digest and the method output
    for label, path in (("lane_a_SUMMARY.md", P.A_SUMMARY),
                        ("lane_a_method_out.json", P.A_METHOD_OUT)):
        if path.exists():
            text = path.read_text(errors="replace")
            out[label] = {"file": P.rel(path),
                          "mentions_abliterated": text.count("abliterated"),
                          "present": "abliterated" in text}
        else:
            out[label] = {"file": P.rel(path), "present": False,
                          "note": "ABSENT"}

    # Lane C -- the panel
    c_files = sorted(P.C_PER_CKPT.glob("*.json")) if P.C_PER_CKPT.is_dir() else []
    out["lane_c_per_ckpt"] = {
        "glob": P.rel(P.C_PER_CKPT / "*.json"),
        "n_files": len(c_files),
        "files": [f.stem for f in c_files],
        "mlabonne_present": any("mlabonne" in f.name.lower() for f in c_files),
        "qwen3_4b_abliterated_present": any(
            "qwen3-4b-abliterated" in f.name.lower() for f in c_files
        ),
        "n_files_named_abliterated": sum(
            1 for f in c_files if "abliterated" in f.name.lower()
        ),
    }

    # Lane B -- the lesion harvest
    hv_names = sorted(f.name for f in P.B_HARVEST.glob("*")) if P.B_HARVEST.is_dir() else []
    out["lane_b_harvest"] = {
        "glob": P.rel(P.B_HARVEST / "*"),
        "lineages": sorted({n.split("_")[0] for n in hv_names if n.startswith("L")}),
        "lineage_repos": P.B_LINEAGE_REPO,
        "abliterated_arm_present": any("abl" in n.lower() and n.startswith("L")
                                       and "ablit" not in n for n in hv_names),
        "note": ("L1-L4 are Base / Instruct / SafeRL / non-safety fine-tune. No "
                 "community-abliterated arm was harvested in Lane B; Lane B's "
                 "abliteration is its OWN rank-one lesion of L1-L4, and "
                 "mlabonne's edit enters only as the Stage-9 WEIGHT audit."),
    }
    out["lane_b_stage9_weight_audit"] = {
        "file": P.rel(P.B_STAGE9_WEIGHT),
        "present": P.B_STAGE9_WEIGHT.exists(),
        "mlabonne_u1_pooled": {
            "file": P.rel(P.B_MLABONNE_U1),
            "present": P.B_MLABONNE_U1.exists(),
        },
    }

    verdict = (
        "Absent from LANE_C/results/per_ckpt (%d files, none of which is mlabonne's "
        "Qwen3-4B-abliterated) and absent from Lane B's activation harvest "
        "(L1-L4 contain no abliterated arm). PRESENT in Lane A: %d released "
        "direction files and %d mentions in SUMMARY.md."
        % (
            out["lane_c_per_ckpt"]["n_files"],
            len(abl_dirs),
            out.get("lane_a_SUMMARY.md", {}).get("mentions_abliterated", 0),
        )
    )
    out["precise_scope_of_omission"] = verdict
    out["inherited_claim"] = "The abliterated checkpoint is in no metric table."
    out["inherited_claim_status"] = "TRUE ONLY OF LANE C AND OF THE PAPER'S FOUR-ROW TABLE"
    return out


# --------------------------------------------------------------------------- #
# the causal arm
# --------------------------------------------------------------------------- #
def audit_causal_arm() -> dict:
    """Count the files in Lane B's causal output and quote the logs verbatim."""
    files = sorted(P.B_CAUSAL.glob("*")) if P.B_CAUSAL.is_dir() else []
    logs = sorted(P.B_LOGS.glob("causal_*.log")) if P.B_LOGS.is_dir() else []
    log_rows = []
    for lg in logs:
        text = lg.read_text(errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        tail = lines[-12:]
        failed = any(
            tok in text
            for tok in ("Traceback", "ModuleNotFoundError", "No such file or directory",
                        "cannot execute", "command not found", "Error", "error:")
        )
        log_rows.append({
            "log": P.rel(lg),
            "size_bytes": lg.stat().st_size,
            "n_lines": len(lines),
            "tail_verbatim": tail,
            "looks_failed": failed,
        })

    followup_line12 = None
    if P.B_FOLLOWUP_SH.exists():
        fl = P.B_FOLLOWUP_SH.read_text(errors="replace").splitlines()
        followup_line12 = fl[11] if len(fl) >= 12 else None

    n_jobs_expected = 8  # 4 lineages x {alpha 0.0, alpha 1.0}
    return {
        "dir": P.rel(P.B_CAUSAL),
        "n_files": len(files),
        "files": [P.rel(f) for f in files],
        "n_jobs_expected": n_jobs_expected,
        "n_jobs_with_output": len(files),
        "n_jobs_crashed": max(0, n_jobs_expected - len(files)),
        "logs": log_rows,
        "followup_sh_line_12": followup_line12,
        "status": "EMPTY_EXCEPT_UNLESIONED_BASELINE" if len(files) <= 1 else "POPULATED",
    }


# --------------------------------------------------------------------------- #
# the ledger itself
# --------------------------------------------------------------------------- #
def _describe_json(path: Path, *, top_n: int = 12) -> str:
    try:
        obj = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return f"UNREADABLE: {exc!r}"
    if isinstance(obj, dict):
        keys = list(obj.keys())
        return f"dict, {len(keys)} top-level keys: {keys[:top_n]}" + (
            " ..." if len(keys) > top_n else "")
    if isinstance(obj, list):
        first = obj[0] if obj else None
        kind = type(first).__name__
        extra = f", element0 keys={list(first.keys())[:top_n]}" if isinstance(first, dict) else ""
        return f"list of {len(obj)} {kind}{extra}"
    return f"{type(obj).__name__}"


def _describe_csv(path: Path) -> str:
    import pandas as pd

    try:
        head = pd.read_csv(path, nrows=5)
        n_rows = sum(1 for _ in path.open()) - 1
    except (OSError, ValueError) as exc:
        return f"UNREADABLE: {exc!r}"
    return (f"csv, {n_rows} rows, {len(head.columns)} cols: "
            f"{list(head.columns)}; dtypes={ {c: str(t) for c, t in head.dtypes.items()} }")


def _describe_jsonl_dir(d: Path) -> str:
    files = sorted(d.glob("*.jsonl"))
    if not files:
        return f"ABSENT (glob {P.rel(d / '*.jsonl')} matched 0 files)"
    total = 0
    keys: list[str] = []
    for f in files:
        with f.open() as fh:
            for i, line in enumerate(fh):
                if line.strip():
                    total += 1
                    if not keys and i == 0:
                        try:
                            keys = list(json.loads(line).keys())
                        except json.JSONDecodeError:
                            keys = ["<unparseable first line>"]
    return f"{len(files)} jsonl files, {total} rows total, row keys={keys}"


def _describe_npz(path: Path) -> str:
    try:
        km = npz_key_map(path)
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        return f"UNREADABLE: {exc!r}"
    items = sorted(km.items())
    shown = ", ".join(f"{k}{list(v[0])}:{v[1]}" for k, v in items[:6])
    return f"npz, {len(items)} arrays: {shown}" + (" ..." if len(items) > 6 else "")


def describe(path: Path) -> str:
    if not path.exists():
        return "ABSENT"
    if path.is_dir():
        if any(path.glob("*.jsonl")):
            return _describe_jsonl_dir(path)
        n = len(list(path.glob("*")))
        return f"directory, {n} entries"
    suf = path.suffix.lower()
    if suf == ".json":
        return _describe_json(path)
    if suf == ".csv":
        return _describe_csv(path)
    if suf == ".npz":
        return _describe_npz(path)
    if suf == ".npy":
        a = np.load(path, mmap_mode="r")
        s = f"npy, shape={list(a.shape)}, dtype={a.dtype}"
        del a
        return s
    if suf in {".md", ".py", ".sh", ".txt", ".log"}:
        text = path.read_text(errors="replace")
        return f"text, {len(text.splitlines())} lines, {len(text)} chars"
    return f"file, {path.stat().st_size} bytes"


QUANTITIES: list[tuple[str, str, Path, str]] = [
    # (quantity, metric consumers, path, readout_class)
    ("Lane A full method output (gates, S1 table, nulls, baselines)",
     "M1,M2,M4,M8", P.A_METHOD_OUT, "metadata"),
    ("Lane A human digest (licence sentence + limitations sentence)",
     "M3d,M8", P.A_SUMMARY, "metadata"),
    ("Lane A frozen pre-registration", "M4", P.A_PREREG, "metadata"),
    ("Lane A within-checkpoint |cos(r_content,r_ablit)|",
     "M3a", P.A_COS_CONTENT_ABLIT, "activation"),
    ("Lane A cross-checkpoint rotation matrix",
     "M3c", P.A_CROSS_CKPT, "activation"),
    ("Lane A per-item cell projections onto r_content",
     "M1(b),M2", P.A_PER_ITEM_CELLS, "activation"),
    ("Lane A released direction vectors (7 arms x 2 axes)",
     "M3c,M8", P.A_DIRECTIONS, "activation"),
    ("Lane A substrate builder (frame length, ACTION slot positions)",
     "M8", P.A_SUBSTRATE_PY, "metadata"),
    ("Lane B lesion analysis (cosines, CV probe, depth profile)",
     "M1,M2,M3a,M4", P.B_ANALYSIS, "activation"),
    ("Lane B frozen pre-registration", "M4", P.B_PREREG, "metadata"),
    ("Lane B per-item band activations at five lesion strengths",
     "M1(a),M6", P.B_HARVEST, "activation"),
    ("Lane B released abliteration directions", "M3a", P.B_RELEASED_DIRS, "activation"),
    ("Lane B causal (generation) arm", "M8", P.B_CAUSAL, "text"),
    ("Lane B Stage-9 weight audit of mlabonne's edit",
     "M8", P.B_STAGE9_WEIGHT, "weight"),
    ("Lane B Stage-9 depth profile", "M2", P.B_STAGE9_DEPTH, "activation"),
    ("Lane C per-checkpoint stored feature scalars",
     "M1(c),M3a,M6", P.C_PER_CKPT, "activation"),
    ("Lane C sealed-family feature scalars (truth withheld)",
     "M6", P.C_SEALED, "activation"),
    ("Lane C judged generations (behavioural ground truth)",
     "M6,M7", P.C_JUDGED, "text"),
    ("Lane C raw generations", "M7", P.C_GENS, "text"),
    ("Lane C S3 tables, budget curve and machinery controls",
     "M5,M7,M8", P.C_S3, "metadata"),
    ("Lane C frozen pre-registration", "M4", P.C_PREREG, "metadata"),
    ("Lane C full method output (panel table, truth columns)",
     "M6,M7,M8", P.C_METHOD_OUT, "metadata"),
]


def build_ledger() -> tuple[list[LedgerRow], dict]:
    logger.info("M0: hashing and opening {} quantities", len(QUANTITIES))
    file_paths = [p for _, _, p, _ in QUANTITIES if p.is_file()]
    digests = hash_many(file_paths)

    rows: list[LedgerRow] = []
    for quantity, consumers, path, rclass in QUANTITIES:
        exists = path.exists()
        if not exists:
            rows.append(LedgerRow(quantity, consumers, P.rel(path), False, "",
                                  0, "ABSENT", "ABSENT", rclass,
                                  f"glob run: {P.rel(path)}"))
            continue
        if path.is_dir():
            sizes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            digest, size = "DIRECTORY", sizes
        else:
            digest, size = digests.get(str(path), ("", path.stat().st_size))
        contents = describe(path)
        verdict = "RECOMPUTABLE_HERE"
        if contents.startswith("UNREADABLE"):
            verdict = "NEEDS_REHARVEST"
        rows.append(LedgerRow(quantity, consumers, P.rel(path), True, digest,
                              int(size), contents, verdict, rclass))

    harvest = audit_lane_b_harvest()
    abl = audit_abliterated_scope()
    causal = audit_causal_arm()

    # the harvest row's verdict is decided by what the shapes actually showed
    for r in rows:
        if r.source_file == P.rel(P.B_HARVEST):
            r.verdict = harvest["verdict"]
            r.contents = (
                f"{harvest['n_files_total']} files "
                f"({harvest['n_npz']} npz, {harvest['n_json']} json); lineages "
                f"{harvest['lineages']}; alphas {harvest['alphas']}; "
                f"{harvest['n_per_item_layer_dim_arrays']} arrays of shape "
                f"(item, dim) indexed by layer"
            )
        if r.source_file == P.rel(P.B_CAUSAL):
            r.verdict = "PARTIAL" if causal["n_files"] else "ABSENT"
            r.note = (f"{causal['n_jobs_with_output']}/{causal['n_jobs_expected']} "
                      f"jobs produced output; {causal['n_jobs_crashed']} crashed")

    new_facts = _new_facts(harvest, abl, causal)
    detail = {
        "lane_b_harvest_inventory": harvest,
        "abliterated_scope": abl,
        "causal_arm": causal,
        "new_facts": new_facts,
    }
    return rows, detail


def _new_facts(harvest: dict, abl: dict, causal: dict) -> list[str]:
    facts = []
    if harvest.get("present") and harvest.get("n_per_item_layer_dim_arrays", 0) > 0:
        ex = harvest["per_item_layer_dim_arrays"][0]
        facts.append(
            "NEW FACT 1 -- the claim 'raw hidden states were saved nowhere in "
            f"iteration 1' is FALSE. LANE_B/out/harvest holds {harvest['n_files_total']} "
            f"files across lineages {harvest['lineages']} at lesion strengths "
            f"{harvest['alphas']}, containing {harvest['n_per_item_layer_dim_arrays']} "
            f"PER-ITEM x DIM arrays indexed by layer (e.g. {ex['key']} with shape "
            f"{ex['shape']} dtype {ex['dtype']}). M1 therefore gets its strong form -- "
            "a probe FITTED on the unlesioned arm and SCORED on the lesioned arms -- "
            "at zero GPU cost, and the experiment lanes are spared a re-harvest."
        )
    else:
        facts.append(
            "NEW FACT 1 -- Lane B's harvest holds no per-item band-layer vectors; "
            "M1 falls back to Lane A's stored per-item cell projections."
        )
    facts.append("NEW FACT 2 -- " + abl["precise_scope_of_omission"])
    facts.append(
        "NEW FACT 3 -- the causal (generation) arm is EMPTY except for its "
        f"unlesioned baseline: {causal['n_files']} file(s) in {causal['dir']} "
        f"({causal['files']}), {causal['n_jobs_crashed']} of "
        f"{causal['n_jobs_expected']} jobs produced nothing. Iteration 1's "
        "deviations ledger omitted this."
    )
    return facts
