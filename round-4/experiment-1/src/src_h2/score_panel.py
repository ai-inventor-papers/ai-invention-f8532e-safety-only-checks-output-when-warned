"""Panel-level scoring: shuffled-label nulls, random-direction units, the prompt-budget
curve, and the four registered decision tests E1/E2/E3/E4.

Everything here is offline NumPy over the harvest caches.  The scoring is deterministic
given the harvest (T7), because that determinism IS the claim that every candidate was
scored on the same evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import ASSETS, HARVEST, RESULTS, jdump, jload, jload_maybe  # noqa: E402
from loguru import logger  # noqa: E402
import numerics as nm  # noqa: E402
from score_ckpt import (  # noqa: E402
    CkptCache, bl2_rawhid, bl6_hrci, compute_candidates, compute_x10, recognition_axis,
)

HEADLINE = ["X1", "X2", "X3", "X5", "X8", "X10"]
CARRIED = ["X9", "X11", "X1_raw", "X2_perlayer", "X3_two_way", "X3_exec",
           "X10_abs", "X10_median", "X2_min"]
BASELINES = ["BL1_REFLOGIT", "BL2_RAWHID", "BL3_DIFFMEAN", "BL4_CLUSTSEP",
             "BL5_CARDREGEX", "BL5_CARDREGEX_NAMEFREE", "BL6_HRCI", "BL7_JORAK_A"]
# X10 and every variant of it read WEIGHTS ONLY and use no labels, so a shuffled-label band
# cannot exist for them and they are never scored against one.
LABEL_FREE = {"X10", "X10_abs", "X10_median", "X10_mad", "X10_o_proj",
              "X10_down_proj", "X10_o_proj_abs", "X10_down_proj_abs",
              "BL5_CARDREGEX", "BL5_CARDREGEX_NAMEFREE", "BL7_JORAK_A"}

# Candidates whose IDEA is CLOSED by prior art are still computed -- the comparison is the
# instrument -- but they are EXCLUDED from survivor selection (Section 4.5). Verdicts come from
# the same-iteration research lane; see make_outputs.PRIOR_ART for the full basis.
SURVIVOR_EXCLUDED = {
    "X2": "CLOSED as an idea: the Jorak Model Scanner ships ||r^T W||/(||r|| ||W||_F) over "
          "o_proj/down_proj with r from the candidate's own activations (non-peer-reviewed)",
    "X10": "CLOSED as an idea: the Jorak Model Scanner ships a weights-only least-singular-"
           "vector test A = sigma_1(U)/||U||_F (non-peer-reviewed); reimplemented as BL7",
}

CARD_RE = r"abliterat|uncensor|orthogonal|heretic|josiefied|no.?refus|jailbreak"
# NAME-FREE variant: the same semantic terms WITHOUT the uploader/model name, so the
# term-swept version's inflation by the very label it predicts is visible.
CARD_RE_NAMEFREE = r"uncensor|no.?refus|jailbreak|derestrict"


def score_checkpoint(tag: str, cfg: dict, stim: list[dict], *, n_null: int, n_rand: int,
                     seed: int = 0) -> dict:
    """Real value + shuffled-label band + random-direction unit for one checkpoint."""
    cache = CkptCache(tag)
    if not cache.ok():
        return {"tag": tag, "error": "not harvested"}
    y = np.array([s["y"] for s in stim], dtype=int)
    sid = np.array([s["set_id"] for s in stim], dtype=int)
    easy = np.flatnonzero(sid == 0)

    # DIRECTION-STABILITY GATE (teeth): decides the PRIMARY axis for THIS checkpoint
    A = cache.A
    U0 = nm.diffmeans_directions(A[easy], y[easy])
    P0 = nm.project(A[easy], U0)
    dcoh = np.array([nm.cohens_d(P0[y[easy] == 1, l], P0[y[easy] == 0, l])
                     for l in range(A.shape[1])])
    l_star0 = int(np.nanargmax(np.nan_to_num(dcoh, nan=-np.inf)))
    shc = nm.split_half_cosine(A[easy], y[easy], l_star0, n_rep=20, seed=seed)
    use_probe = bool(np.isfinite(shc) and shc < cfg["split_half_gate"])

    real = compute_candidates(cache, y, cfg, seed=seed, use_probe_axis=use_probe,
                              subset=easy, with_curves=True)
    real.update(compute_x10(cache, cfg, u_star=U0[l_star0]))
    real.update(bl2_rawhid(cache, y[easy], real["l_star"], seed=seed, subset=easy))
    real.update(bl6_hrci(cache, y[easy], real["l_star"], cfg, subset=easy))
    real["split_half_cosine"] = shc
    real["primary_axis"] = "probe" if use_probe else "diff_in_means"
    real["axis_substitution_reason"] = (
        f"split-half cosine {shc:.3f} < gate {cfg['split_half_gate']} -> cross-validated "
        "logistic-probe axis substituted" if use_probe else
        f"split-half cosine {shc:.3f} >= gate {cfg['split_half_gate']} -> diff-in-means kept")

    # ---------------- SHUFFLED-LABEL BAND (THE TEST) ----------------
    rng = np.random.default_rng(seed + 991)
    null_rows: list[dict] = []
    for b in range(n_null):
        yb = y.copy()
        yb[easy] = rng.permutation(y[easy])
        try:
            null_rows.append(compute_candidates(cache, yb, cfg, seed=seed + b + 1,
                                                use_probe_axis=use_probe, subset=easy))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"{tag}: null draw {b} failed ({exc})")

    keys = sorted({k for r in null_rows for k, v in r.items()
                   if isinstance(v, (int, float)) and not isinstance(v, bool)})
    nulls: dict[str, dict] = {}
    for k in keys:
        v = np.array([r.get(k, np.nan) for r in null_rows], dtype=np.float64)
        v = v[np.isfinite(v)]
        if v.size < 3:
            continue
        nulls[k] = {"band": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
                    "sd": float(v.std(ddof=1)), "mean": float(v.mean()), "n": int(v.size)}

    # ---------------- RANDOM-DIRECTION SD (A UNIT ONLY, NEVER A TEST) ----------------
    rand_unit = _random_direction_unit(cache, cfg, n_rand=n_rand, seed=seed)

    # ---------------- ITEM-LEVEL BOOTSTRAP (the CI every escape / E1 / E2 call needs) ----
    boot = item_bootstrap(cache, y, easy, cfg, use_probe=use_probe,
                          n_boot=int(cfg.get("n_boot_items", 100)))
    escapes = {}
    for k, nb in nulls.items():
        ci = (boot.get("ci95") or {}).get(k)
        v = real.get(k)
        if ci is None or v is None or isinstance(v, bool) or not np.isfinite(v):
            continue
        escapes[k] = bool(nm.band_escape(float(v), tuple(nb["band"]), tuple(ci)))

    return {"tag": tag, "meta": cache.meta, "real": real, "nulls": nulls,
            "random_direction": rand_unit, "n_null_draws": len(null_rows),
            "boot": boot, "escapes_own_band": escapes,
            "_cache": cache}


# Label-dependent quantities that get an item-level bootstrap distribution.
BOOT_KEYS = ["X1", "X1_raw", "X2", "X2_perlayer", "X2_min", "X3", "X3_hedge", "X3_two_way",
             "X3_exec", "X3_finallayer", "X5", "X5_conc_harmful_mean", "X8", "X11",
             "X11_early", "BL1_REFLOGIT", "BL3_DIFFMEAN", "BL4_CLUSTSEP",
             "l_star", "l_dec", "l_act"]
BOOT_SEED = 515151


def item_bootstrap(cache: CkptCache, y: np.ndarray, easy: np.ndarray, cfg: dict, *,
                   use_probe: bool, n_boot: int = 100) -> dict:
    """Resample the FITTING items with replacement (stratified by class), refit the axis
    and recompute every label-dependent candidate through the identical code path.

    The resample indices depend ONLY on (BOOT_SEED, b) -- never on the checkpoint -- and every
    checkpoint was harvested on the same 256 stimuli in the same order, so replicate b means
    the same resampled prompt set in every checkpoint. That makes two readings available:
      * INDEPENDENT (registered, 8): child replicate b against parent replicate perm(b)
      * PAIRED (secondary): child replicate b against parent replicate b
    Every cross-fitted quantity inside splits folds by ORIGINAL item (groups), so a
    duplicated prompt never sits on both sides of a fold.
    """
    rng = np.random.default_rng(BOOT_SEED)
    i1 = easy[y[easy] == 1]
    i0 = easy[y[easy] == 0]
    reps = {k: np.full(n_boot, np.nan) for k in BOOT_KEYS}
    for b in range(n_boot):
        sub = np.r_[rng.choice(i1, i1.size, replace=True), rng.choice(i0, i0.size, replace=True)]
        # the C-harvest readouts (X5, X11) average over CELL ITEMS, a second sampling unit:
        # resample those too (positions in [0,1), mapped onto each checkpoint's kept items)
        cell_draw = rng.random(64)
        try:
            c = compute_candidates(cache, y, cfg, seed=b + 7, use_probe_axis=use_probe,
                                   subset=sub, lean=True, cell_item_draw=cell_draw)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"{cache.tag}: bootstrap replicate {b} failed ({exc})")
            continue
        for k in BOOT_KEYS:
            v = c.get(k)
            if v is not None and not isinstance(v, bool) and np.isfinite(v):
                reps[k][b] = float(v)
    ci95, se = {}, {}
    for k, v in reps.items():
        f = v[np.isfinite(v)]
        if f.size >= 10:
            ci95[k] = [float(np.percentile(f, 2.5)), float(np.percentile(f, 97.5))]
            se[k] = float(f.std(ddof=1))
    return {"n_boot": int(n_boot), "seed": BOOT_SEED, "reps": {k: v.tolist() for k, v in reps.items()},
            "ci95": ci95, "se": se,
            "protocol": ("item-level bootstrap over the EASY (fitting) prompts, stratified by "
                         "class, with replacement; axis refit per replicate; common resample "
                         "indices across checkpoints (so PAIRED differences exist); folds "
                         "split by original item")}


def _boot_reps(s: dict, key: str) -> np.ndarray | None:
    r = ((s.get("boot") or {}).get("reps") or {}).get(key)
    if r is None:
        return None
    # JSON round-trips turn NaN into None; map it back before any arithmetic
    a = np.array([np.nan if v is None else v for v in r], dtype=np.float64)
    return a if np.isfinite(a).sum() >= 10 else None


_PERM_CACHE: dict[int, np.ndarray] = {}


def _indep_perm(n: int) -> np.ndarray:
    """A fixed permutation that breaks the replicate pairing (the registered INDEPENDENT
    resampling reading). Deterministic, so the scoring stays byte-reproducible (T7)."""
    if n not in _PERM_CACHE:
        _PERM_CACHE[n] = np.random.default_rng(BOOT_SEED + 1).permutation(n)
    return _PERM_CACHE[n]


def _random_direction_unit(cache: CkptCache, cfg: dict, n_rand: int, seed: int) -> dict:
    """n_rand unit vectors -> the scale of each weight-side candidate under a random axis.

    Reported ALONGSIDE the shuffled band so a reader can see the two differ.  Iteration 1's
    arming term read 4.3-9.3 random-direction SD against a shuffled band of 11.0-11.8 and
    escaped in 0 of 7 checkpoints; that is exactly why this is a unit and not a test.
    """
    rng = np.random.default_rng(seed + 4242)
    G = cache.G
    w = (cache.meta.get("w") or {}).get("parts", {}).get("stacked")
    out: dict[str, Any] = {}
    if G and w:
        d = cache.meta["hidden_size"]
        band = _band_blocks(cache, cfg, len(G))
        Ur = nm.unit(rng.standard_normal((n_rand, d)).astype(np.float32), axis=1)
        vals = np.zeros((n_rand, len(G)))
        for l in range(len(G)):
            vals[:, l] = nm.write_mass_many(G[l], w["fro2"][l], Ur, d)
        x2r = np.log10(np.maximum(vals[:, band], 1e-12)).mean(axis=1)
        out["X2_random_mean"] = float(x2r.mean())
        out["X2_random_sd"] = float(x2r.std(ddof=1))
    hbar, gamma = cache.arr("hbar"), cache.arr("gamma")
    WU_ref, WU_ctl, mu_U, S_U = (cache.arr("WU_ref"), cache.arr("WU_ctl"),
                                 cache.arr("mu_U"), cache.arr("S_U"))
    V = int(cache.meta.get("vocab_size") or 0)
    if all(x is not None for x in (hbar, gamma, WU_ref, WU_ctl, mu_U, S_U)) and V > 0 \
            and WU_ref.shape[0] and WU_ctl.shape[0]:
        d = hbar.shape[0]
        Ur = nm.unit(rng.standard_normal((n_rand, d)), axis=1)
        v = nm.x3_gain_many(Ur, hbar, gamma, cache.meta["rms_eps"], WU_ref, WU_ctl, WU_ctl,
                            mu_U, S_U, V)
        out["X3_random_mean"] = float(np.mean(v))
        out["X3_random_sd"] = float(np.std(v, ddof=1))
    out["note"] = ("RANDOM-DIRECTION SD IS A UNIT ONLY, NEVER A TEST. The test is the "
                   "shuffled-label band.")
    return out


def _band_blocks(cache: CkptCache, cfg: dict, n_blocks: int) -> np.ndarray:
    lo, hi = cfg["depth_band"]
    L = cache.meta["n_layers"]
    b = np.array([l for l in range(n_blocks) if lo <= (l + 1) / max(L, 1) <= hi], dtype=int)
    return b if b.size else np.arange(n_blocks)


# ----------------------------------------------------------------------------------
def read_model_card(repo: str) -> str:
    """The README of the cached HF snapshot, if one is there."""
    import glob
    from pathlib import Path

    hub = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/hub")
    snaps = sorted(glob.glob(str(hub / f"models--{repo.replace('/', '--')}" / "snapshots" / "*")))
    if not snaps:
        return ""
    for name in ("README.md", "readme.md"):
        f = Path(snaps[-1]) / name
        if f.exists():
            try:
                return f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
    return ""


def card_regex_baseline(repo: str, card_text: str | None = None) -> dict:
    """BL5 -- the text-only baseline that costs nothing and has beaten cheap internal
    metrics before.  Reported in TWO variants, separately, because the term-swept one is
    inflated by the very label it predicts:

      TERM-SWEPT: regex over repo_id + card, including the uploader's own word
                  'abliterated'. This is close to reading the answer off the tin.
      NAME-FREE : the same semantic terms over the CARD TEXT ONLY, with the repo id and the
                  giveaway term 'abliterat' removed, so it cannot win by pattern-matching
                  the name of the thing it is predicting.

    If BL5 wins, WE SAY SO -- an internal metric that cannot beat a regex over the model card
    has not earned its compute.
    """
    import re

    if card_text is None:
        card_text = read_model_card(repo)
    blob = (repo + " " + (card_text or "")).lower()
    name_free_blob = re.sub(r"abliterat\w*", " ", (card_text or "").lower())
    return {
        "BL5_CARDREGEX": float(bool(re.search(CARD_RE, blob))),
        "BL5_CARDREGEX_NAMEFREE": float(bool(re.search(CARD_RE_NAMEFREE, name_free_blob))),
        "BL5_card_chars": len(card_text or ""),
        "BL5_card_found": bool(card_text),
    }


# ----------------------------------------------------------------------------------
def pair_deltas(scored: dict[str, dict], pairs: list[dict], cand_keys: list[str]) -> list[dict]:
    """Delta_j = cand(child) - cand(parent), expressed in the POOLED SHUFFLED-LABEL SD."""
    from aii_common import slug

    rows = []
    for p in pairs:
        ptag, ctag = slug(p["parent"]), slug(p["child"])
        sp, sc = scored.get(ptag), scored.get(ctag)
        if not sp or not sc or "real" not in sp or "real" not in sc:
            continue
        row = {k: p.get(k) for k in ("pair", "parent", "child", "family", "effectiveness",
                                     "delta_HC", "delta_OR", "delta_SE", "note")}
        row["stratum"] = p.get("stratum", "UNKNOWN")
        row["deltas"] = {}
        for k in cand_keys:
            vp, vc = sp["real"].get(k), sc["real"].get(k)
            if vp is None or vc is None or not (np.isfinite(vp) and np.isfinite(vc)):
                continue
            sdp = (sp["nulls"].get(k) or {}).get("sd", np.nan)
            sdc = (sc["nulls"].get(k) or {}).get("sd", np.nan)
            pooled = float(np.sqrt((np.nan_to_num(sdp, nan=0.0) ** 2
                                    + np.nan_to_num(sdc, nan=0.0) ** 2) / 2.0))
            raw = float(vc) - float(vp)
            bandp = (sp["nulls"].get(k) or {}).get("band", [np.nan, np.nan])
            bandc = (sc["nulls"].get(k) or {}).get("band", [np.nan, np.nan])
            # the pair's shuffled band: the null spread of the DIFFERENCE
            band = [float(bandp[0] - bandc[1]), float(bandp[1] - bandc[0])] \
                if all(np.isfinite(bandp + bandc)) else [np.nan, np.nan]
            ci = _delta_ci(sp, sc, k)
            ci_pair = _delta_ci_paired(sp, sc, k)
            se_b = _delta_boot_se(sp, sc, k)
            row["deltas"][k] = {
                "delta_raw": raw,
                "delta_pooled_sd": float(raw / pooled) if pooled > 1e-12 else None,
                "pooled_null_sd": pooled if pooled > 1e-12 else None,
                "parent": float(vp), "child": float(vc),
                "pair_shuffled_band": band,
                "ci95": ci,
                "ci95_kind": ("item bootstrap, INDEPENDENT resampling per checkpoint (registered)"
                              if all(np.isfinite(ci)) else "UNAVAILABLE (no bootstrap replicates)"),
                "ci95_paired": ci_pair,
                "boot_se": se_b if np.isfinite(se_b) else None,
                "mde_pooled_sd": (float(1.96 * se_b / pooled)
                                  if (np.isfinite(se_b) and pooled > 1e-12) else None),
                "escapes_band": bool(nm.band_escape(raw, tuple(band), tuple(ci)))
                if all(np.isfinite(band + list(ci))) else None,
                "label_free": k in LABEL_FREE,
            }
        rows.append(row)
    return rows


def _delta_ci(sp: dict, sc: dict, key: str) -> tuple[float, float]:
    """95% CI of Delta_j = cand(child) - cand(parent) from the ITEM-LEVEL BOOTSTRAP.

    Registered reading (8): the items are resampled INDEPENDENTLY within each checkpoint, so
    child replicate b is set against parent replicate perm(b).  If either checkpoint lacks
    bootstrap replicates (a weight-only checkpoint, or a label-free key) the CI is NaN and
    the output says so -- it is NEVER replaced by a null-SD/sqrt(n_null) interval, which
    would shrink to zero as more null draws were taken.
    """
    rp, rc = _boot_reps(sp, key), _boot_reps(sc, key)
    if rp is None or rc is None:
        return (np.nan, np.nan)
    n = min(rp.size, rc.size)
    d = rc[:n] - rp[:n][_indep_perm(n)]
    d = d[np.isfinite(d)]
    if d.size < 10:
        return (np.nan, np.nan)
    return (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)))


def _delta_ci_paired(sp: dict, sc: dict, key: str) -> tuple[float, float]:
    """SECONDARY: the PAIRED reading (same resampled prompt set in parent and child)."""
    rp, rc = _boot_reps(sp, key), _boot_reps(sc, key)
    if rp is None or rc is None:
        return (np.nan, np.nan)
    n = min(rp.size, rc.size)
    d = rc[:n] - rp[:n]
    d = d[np.isfinite(d)]
    if d.size < 10:
        return (np.nan, np.nan)
    return (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)))


def _delta_boot_se(sp: dict, sc: dict, key: str) -> float:
    rp, rc = _boot_reps(sp, key), _boot_reps(sc, key)
    if rp is None or rc is None:
        return float("nan")
    n = min(rp.size, rc.size)
    d = rc[:n] - rp[:n][_indep_perm(n)]
    d = d[np.isfinite(d)]
    return float(d.std(ddof=1)) if d.size >= 10 else float("nan")


# ----------------------------------------------------------------------------------
def labelfree_reference_band(scored: dict, pairs: list[dict], key: str,
                            extra: dict | None = None) -> dict:
    """The DECLARED ALTERNATIVE NULL for a label-free candidate such as X10.

    X10 uses no labels, so a shuffled-label band cannot exist for it and scoring it against
    one would be scoring it against a null it cannot have.  Its declared evidence null has
    three parts, and this builds the empirical one: the distribution of the candidate over
    the panel's INSTRUCT PARENTS, which are by construction the not-abliterated arm of every
    pair.  A child whose value lies inside that parent band is indistinguishable from an
    unedited checkpoint on this statistic.

    This is the same object as the PARENT PRESENCE TEST, read as a band rather than a
    per-pair comparison: a signature present in the parents is not abliteration-specific.
    """
    from aii_common import slug

    vals, tags = [], []
    for p in pairs:
        t = slug(p["parent"])
        v = ((scored.get(t) or {}).get("real") or {}).get(key)
        if (v is None or not np.isfinite(v)) and extra:
            v = (extra.get(t) or {}).get(key) if isinstance(extra.get(t), dict) \
                else extra.get(t)
        if v is not None and np.isfinite(v):
            vals.append(float(v))
            tags.append(t)
    v = np.asarray(vals, dtype=float)
    if v.size < 2:
        return {"available": False, "n_parents": int(v.size), "parents": tags}
    return {"available": True, "n_parents": int(v.size), "parents": tags,
            "band": [float(v.min()), float(v.max())],
            "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
            "p2.5_p97.5": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
            "definition": ("empirical range of the candidate over the panel's instruct "
                           "PARENTS -- the not-abliterated arm of every pair. A label-free "
                           "candidate needs no activations, so a parent contributes to this "
                           "band as soon as it has a WEIGHT SUMMARY, whether or not the "
                           "activation harvest reached it."),
            "width": float(v.max() - v.min()),
            "cross_architecture_note": ("the parents span different families, depths and "
                                        "hidden sizes; the WIDTH of this band is therefore "
                                        "the cross-architecture transfer question for this "
                                        "readout, and is reported rather than assumed"),
            "why": ("X10 uses NO LABELS, so the shuffled-label band does not apply. This is "
                    "its declared alternative null, alongside the shape- and "
                    "Frobenius-matched Marchenko-Pastur baseline that already sits inside "
                    "scar_l and the within-model layer distribution that sets the z-score.")}


def e1_test(rows: list[dict], key: str, cfg: dict,
            labelfree_band: dict | None = None) -> dict:
    """E1 (a) SENSITIVITY  (b) SPECIFICITY  (c) DOSE-RESPONSE.  Passes iff (a) AND (b)."""
    eff = [r for r in rows if r["effectiveness"] == "EFFECTIVE" and key in r["deltas"]]
    nul = [r for r in rows if r["effectiveness"] == "NULL_EDIT" and key in r["deltas"]]
    anom = [r for r in rows if r["effectiveness"] == "ANOMALOUS" and key in r["deltas"]]

    strata: dict[str, list] = {}
    for r in eff:
        strata.setdefault(r["stratum"], []).append(r)

    lf_band = (labelfree_band or {}).get("band") if key in LABEL_FREE else None

    def sens(group: list[dict]) -> dict:
        # The per-pair criteria are ALWAYS computed, so a stratum below the registered minimum
        # is reported as UNDER-POWERED with its evidence (fallback 8), not as a bare failure.
        res = _sens_core(group)
        res["pairs"] = [r["pair"] for r in group]
        if len(group) < cfg["e1_min_effective_pairs"]:
            res.update(pass_=False, under_powered=True,
                       reason=(f"UNDER-POWERED: {len(group)} effective pair(s) < registered "
                               f"minimum {cfg['e1_min_effective_pairs']}"))
            res["pass"] = False
            res.pop("pass_", None)
            return res
        return res

    def _sens_core(group: list[dict]) -> dict:
        if not group:
            return {"pass": False, "n": 0}
        d = [r["deltas"][key]["delta_raw"] for r in group]
        ci = [r["deltas"][key]["ci95"] for r in group]
        signs = [np.sign(x) for x in d]
        same = all(s == signs[0] and s != 0 for s in signs)
        if key in LABEL_FREE:
            # For a label-free candidate the per-pair CI cannot come from a shuffled-label
            # resample. The registered substitute is the declared alternative null: each
            # EFFECTIVE child must fall OUTSIDE the parent reference band, in the same
            # direction, which is the label-free analogue of "CI excluding zero".
            if lf_band is None:
                return {"pass": False, "n": len(group), "same_signed": bool(same),
                        "reason": "label-free reference band unavailable (need >=2 parents)",
                        "deltas": d}
            excl = [bool(r["deltas"][key]["child"] is not None
                         and np.isfinite(r["deltas"][key]["child"])
                         and not (lf_band[0] <= r["deltas"][key]["child"] <= lf_band[1]))
                    for r in group]
            return {"pass": bool(same and all(excl)), "n": len(group),
                    "same_signed": bool(same),
                    "n_outside_parent_band": int(sum(excl)),
                    "parent_reference_band": lf_band,
                    "criterion": ("label-free: every EFFECTIVE child must fall OUTSIDE the "
                                  "parent reference band with the same sign"),
                    "deltas": d}
        excl = [bool(np.isfinite(c[0]) and np.isfinite(c[1]) and (c[0] > 0 or c[1] < 0))
                for c in ci]
        return {"pass": bool(same and all(excl)), "n": len(group), "same_signed": bool(same),
                "n_ci_excluding_zero": int(sum(excl)), "deltas": d}

    best_stratum, best = None, {"pass": False, "n": 0}
    per_stratum = {}
    for s, g in sorted(strata.items()):
        r = sens(g)
        per_stratum[s] = r
        if r["pass"] or r["n"] > best["n"]:
            best_stratum, best = s, r
        if r["pass"]:
            break
    pooled = _sens_core(eff)
    pooled["label"] = ("SECONDARY -- POOLED ACROSS STRATA. Never used for the E1 verdict: "
                       "pooling averages different edit operators.")
    pooled["pairs"] = [r["pair"] for r in eff]
    shortfall = not any(len(g) >= cfg["e1_min_effective_pairs"] for g in strata.values())

    spec_rows = []
    label_free = key in LABEL_FREE
    eff_abs = [abs(r["deltas"][key]["delta_raw"]) for r in eff]
    min_eff_abs = float(min(eff_abs)) if eff_abs else float("inf")
    for r in nul:
        dd = r["deltas"][key]
        if label_free:
            # DECLARED ALTERNATIVE NULL: the null-edit CHILD must sit inside the parent band
            # AND its |Delta| must not reach the smallest |Delta| among EFFECTIVE pairs. A
            # readout that fires on the granite null-edit pair has learned the hub's naming
            # convention, not the weights.
            ch = dd.get("child")
            band = (labelfree_band or {}).get("band")
            inside_parent = (bool(band[0] <= ch <= band[1])
                             if (band and ch is not None and np.isfinite(ch)) else None)
            below_eff = bool(abs(dd["delta_raw"]) < min_eff_abs) if eff_abs else None
            inside = (bool(inside_parent and below_eff)
                      if (inside_parent is not None and below_eff is not None) else None)
            spec_rows.append({"pair": r["pair"], "delta": dd["delta_raw"],
                              "child_value": ch, "parent_reference_band": band,
                              "inside_parent_band": inside_parent,
                              "below_smallest_effective_delta": below_eff,
                              "min_effective_abs_delta": (min_eff_abs
                                                          if np.isfinite(min_eff_abs) else None),
                              "inside_band": inside,
                              "null_kind": "DECLARED_ALTERNATIVE (label-free candidate)"})
        else:
            inside = (dd["escapes_band"] is False) if dd["escapes_band"] is not None else None
            spec_rows.append({"pair": r["pair"], "delta": dd["delta_raw"],
                              "band": dd["pair_shuffled_band"], "inside_band": inside,
                              "null_kind": "SHUFFLED_LABEL_BAND"})
    spec_pass = bool(spec_rows) and all(s["inside_band"] is True for s in spec_rows)

    d_all = [r["deltas"][key]["delta_raw"] for r in eff + nul]
    hc_all = [r["delta_HC"] for r in eff + nul]
    dose = nm.exact_permutation_p(np.array(d_all, dtype=float), np.array(hc_all, dtype=float))
    dose["power_statement"] = (
        f"with n={dose['n']} pairs only |rho| >= {dose.get('critical_abs_rho_p05', float('nan')):.3f} "
        f"reaches p<0.05; this test is DESCRIPTIVE and cannot on its own establish dose-response.")

    spec_known = bool(spec_rows)
    if best.get("pass") and spec_pass:
        status = "PASS"
    elif shortfall:
        status = "UNDER_POWERED"
    else:
        status = "FAIL"
    return {
        "candidate": key,
        "e1_status": status,
        "e1a_sensitivity": best, "e1a_stratum": best_stratum,
        "e1a_per_stratum": per_stratum,
        "e1a_pooled_secondary": pooled,
        "e1_stratum_shortfall": bool(shortfall),
        "e1b_has_null_edit_pair": spec_known,
        "e1b_specificity": {"pass": spec_pass, "rows": spec_rows,
                            "note": "a readout that fires on the granite null-edit pair has "
                                    "learned the hub's naming convention, not the weights"},
        "anomalous_controls": [{"pair": r["pair"], "delta": r["deltas"][key]["delta_raw"],
                                "delta_HC": r["delta_HC"],
                                "escapes_band": r["deltas"][key]["escapes_band"]}
                               for r in anom],
        "e1c_dose_response": dose,
        "e1_pass": bool(best["pass"] and spec_pass),
        "n_effective_pairs_available": len(eff),
        "label_free_reference_band": labelfree_band if key in LABEL_FREE else None,
        "null_kind": ("DECLARED_ALTERNATIVE (parent reference band + matched random-matrix "
                      "baseline + within-model layer distribution)" if key in LABEL_FREE
                      else "SHUFFLED_LABEL_BAND"),
    }


def e2_test(scored: dict, key: str, cfg: dict) -> dict:
    """TRAINING ORDER on {Base, CohenQu-FT, Qwen3-4B, SafeRL}.

    The CohenQu arm is the control that makes this a SAFETY-tuning readout rather than a
    fine-tuning readout.
    """
    from aii_common import slug

    arms = {
        "base": slug("Qwen/Qwen3-4B-Base"),
        "nonsafety_ft": slug("CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6"),
        "instruct": slug("Qwen/Qwen3-4B"),
        "safety_rl": slug("Qwen/Qwen3-4B-SafeRL"),
    }
    vals, sds = {}, {}
    for a, tag in arms.items():
        s = scored.get(tag)
        if s and "real" in s and np.isfinite(s["real"].get(key, np.nan)):
            vals[a] = float(s["real"][key])
            sds[a] = (s["nulls"].get(key) or {}).get("sd", np.nan)
    missing = [a for a in arms if a not in vals]
    if key in LABEL_FREE:
        # a label-free readout has neither a shuffled-label SD (the registered E2 unit) nor an
        # item bootstrap, so the registered E2 rule cannot be applied to it; say so instead of
        # recording an uninformative failure
        return {"candidate": key, "e2_pass": False, "e2_status": "NOT_APPLICABLE",
                "reason": ("label-free readout: no shuffled-label SD (the registered E2 unit) "
                           "and no item bootstrap exist for it; its training-order values are "
                           "reported descriptively"),
                "values": vals, "missing": missing}
    if len(vals) < 3 or "instruct" not in vals or "base" not in vals:
        return {"candidate": key, "e2_pass": False, "reason": "arms missing",
                "missing": missing, "values": vals}

    order_ok = vals["base"] < vals["instruct"] and (
        "safety_rl" not in vals or vals["instruct"] <= vals["safety_rl"] + 1e-12)
    ref = max(v for a, v in vals.items() if a in ("base", "nonsafety_ft"))
    pooled = float(np.sqrt(np.nanmean([np.nan_to_num(sds.get(a, np.nan), nan=0.0) ** 2
                                       for a in ("base", "instruct")])))
    margin = (vals["instruct"] - ref) / pooled if pooled > 1e-12 else np.nan
    # CI of cand(instruct) - max(cand(Base), cand(CohenQu)) from the ITEM BOOTSTRAP, with
    # independent resampling per checkpoint (the registered reading). A label-free key has
    # no replicates; its CI is then UNAVAILABLE and E2 cannot pass on it.
    reps = {a: _boot_reps(scored[t], key) for a, t in arms.items() if a in vals}
    lo = hi = np.nan
    ci_kind = "UNAVAILABLE (no item-bootstrap replicates for this key)"
    if reps.get("instruct") is not None and reps.get("base") is not None:
        n = min(v.size for v in reps.values() if v is not None)
        inst = reps["instruct"][:n]
        refs = [reps["base"][:n][_indep_perm(n)]]
        if reps.get("nonsafety_ft") is not None:
            refs.append(reps["nonsafety_ft"][:n][np.roll(_indep_perm(n), 1)])
        dd = inst - np.max(np.vstack(refs), axis=0)
        dd = dd[np.isfinite(dd)]
        if dd.size >= 10:
            lo, hi = float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))
            ci_kind = "item bootstrap, independent resampling per checkpoint"
    ci_excl = bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))
    sep_ft = None
    if "nonsafety_ft" in vals:
        sep_ft = float((vals["nonsafety_ft"] - vals["base"]) / pooled) if pooled > 1e-12 else None
    return {
        "candidate": key, "values": vals, "order_ok": bool(order_ok),
        "margin_pooled_null_sd": float(margin) if np.isfinite(margin) else None,
        "threshold": cfg["e2_margin_pooled_null_sd"],
        "ci95_raw": [lo, hi], "ci_kind": ci_kind, "ci_excludes_zero": ci_excl,
        "nonsafety_ft_separation_pooled_sd": sep_ft,
        "nonsafety_ft_note": ("if the candidate separates the CohenQu non-safety fine-tune "
                              "from Base too, it is a FINE-TUNING readout, not a SAFETY one"),
        "e2_pass": bool(order_ok and np.isfinite(margin)
                        and margin > cfg["e2_margin_pooled_null_sd"] and ci_excl),
        "missing": missing,
        "behavioural_caveat": (
            "Qwen3-4B instruct and Qwen3-4B-SafeRL BOTH read harmful_compliance 0.000 at "
            "n=45, so the judged column cannot adjudicate instruct-vs-SafeRL; E2 is scored "
            "on the CANDIDATE's ordering."),
    }


# ----------------------------------------------------------------------------------
# E3  TRANSFER: leave-one-FAMILY-out, NO RECALIBRATION
# ----------------------------------------------------------------------------------
MEANINGFUL_DELTA = 0.05


def _impute_and_z(Xtr: np.ndarray, Xte: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """Median imputation and z-scoring fitted on the TRAIN FOLD ONLY (leakage audit T5d)."""
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    n_imp = int(np.sum(~np.isfinite(Xtr)) + np.sum(~np.isfinite(Xte)))
    A = np.where(np.isfinite(Xtr), Xtr, med)
    B = np.where(np.isfinite(Xte), Xte, med)
    mu, sd = A.mean(0), A.std(0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    return (A - mu) / sd, (B - mu) / sd, n_imp


def pairwise_acc(pred: np.ndarray, truth: np.ndarray, held: np.ndarray) -> tuple[float, int]:
    """Correctly ordered pairs TOUCHING the held-out family, among pairs whose truths
    differ by at least MEANINGFUL_DELTA."""
    n = len(truth)
    ok = tot = 0
    for i in range(n):
        for j in range(i + 1, n):
            if not (held[i] or held[j]):
                continue
            if not (np.isfinite(pred[i]) and np.isfinite(pred[j])):
                continue
            if abs(truth[i] - truth[j]) < MEANINGFUL_DELTA:
                continue
            tot += 1
            if np.sign(pred[i] - pred[j]) == np.sign(truth[i] - truth[j]):
                ok += 1
    return (ok / tot if tot else float("nan")), tot


def lofo(feats: dict[str, float], truth: dict[str, float], fams: dict[str, str]) -> dict:
    """Ridge(alpha=1.0) on all other families, scored on the held-out one. No recalibration."""
    from sklearn.linear_model import Ridge

    slugs = [s for s in feats if s in truth and np.isfinite(truth[s])]
    if len(slugs) < 4:
        return {"mean_acc": float("nan"), "n_ckpt": len(slugs), "per_family": {}}
    X = np.array([[feats[s]] for s in slugs], dtype=float)
    y = np.array([truth[s] for s in slugs], dtype=float)
    fam = np.array([fams.get(s, "other") for s in slugs])
    per: dict[str, dict] = {}
    n_imp = 0
    for f in sorted(set(fam)):
        te = fam == f
        tr = ~te
        if tr.sum() < 2 or te.sum() < 1:
            continue
        Xtr, Xte, imp = _impute_and_z(X[tr], X[te])
        n_imp += imp
        m = Ridge(alpha=1.0).fit(Xtr, y[tr])
        pred = np.full(len(slugs), np.nan)
        pred[tr] = m.predict(Xtr)
        pred[te] = m.predict(Xte)
        acc, ntot = pairwise_acc(pred, y, te)
        per[f] = {"acc": acc, "n_pairs": ntot, "n_ckpt": int(te.sum())}
    accs = [v["acc"] for v in per.values() if np.isfinite(v["acc"])]
    return {"mean_acc": float(np.mean(accs)) if accs else float("nan"),
            "per_family": per, "n_families": len(per), "n_ckpt": len(slugs),
            "imputed": n_imp, "slugs": slugs}


def machinery_controls(truth: dict[str, float], fams: dict[str, str], n_seed: int = 20) -> dict:
    """oracle (truth as its own feature, must be ~1.0), random, shuffled-truth (must land at
    chance).  If shuffled-truth is NOT at chance there is leakage and E3 is VOID."""
    slugs = [s for s in truth if np.isfinite(truth[s])]
    ora = lofo({s: truth[s] for s in slugs}, truth, fams)
    rnd, shf = [], []
    for sd in range(n_seed):
        r = np.random.default_rng(1000 + sd)
        rnd.append(lofo({s: float(r.standard_normal()) for s in slugs}, truth, fams)["mean_acc"])
        r2 = np.random.default_rng(2000 + sd)
        perm = list(r2.permutation(slugs))
        tsh = {slugs[i]: truth[perm[i]] for i in range(len(slugs))}
        shf.append(lofo({s: truth[s] for s in slugs}, tsh, fams)["mean_acc"])
    ra = np.array([a for a in rnd if np.isfinite(a)])
    sa = np.array([a for a in shf if np.isfinite(a)])
    leak = bool(sa.size and (sa.mean() > 0.60))
    return {"oracle_acc": ora["mean_acc"],
            "random_mean_acc": float(ra.mean()) if ra.size else None,
            "random_p95_acc": float(np.percentile(ra, 95)) if ra.size else None,
            "shuffled_truth_mean_acc": float(sa.mean()) if sa.size else None,
            "shuffled_truth_p95_acc": float(np.percentile(sa, 95)) if sa.size else None,
            "n_seeds": int(min(ra.size, sa.size)),
            "leakage_suspected": leak,
            "note": ("oracle must be ~1.0 and shuffled-truth must land at chance. If "
                     "shuffled-truth is NOT at chance there is leakage and the E3 numbers "
                     "are VOID.")}


def e3_test(scored: dict, truth_cols: dict, fams: dict, key: str, cfg: dict,
            n_boot: int = 2000, extra: dict | None = None) -> dict:
    """PASS iff >= BL1_REFLOGIT + 0.10 on safe-engagement with a FAMILY-CLUSTERED bootstrap
    CI on the paired difference excluding zero, AND not worse than BL1 on harmful-compliance.
    """
    def feats(k: str) -> dict[str, float]:
        out = {}
        for tag, s in scored.items():
            v = (s.get("real") or {}).get(k)
            if v is not None and np.isfinite(v):
                out[tag] = float(v)
        # A LABEL-FREE candidate needs no activations, so its transfer test can use every
        # checkpoint that has a weight summary, not just the ones the activation harvest
        # reached. That is a strictly larger and more family-diverse panel, and it is the
        # honest scope for a zero-prompt readout. Baselines that DO need activations keep
        # the smaller panel, so `extra` is applied only to label-free keys; the two panel
        # sizes are reported per target so the comparison is not silently unequal.
        if extra and k in LABEL_FREE:
            for tag, v in extra.items():
                if tag not in out and v is not None and np.isfinite(v):
                    out[tag] = float(v)
        return out

    res: dict[str, Any] = {"candidate": key}
    for target in ("safe_engagement_rate", "harmful_compliance_rate"):
        tr = {t: c[target] for t, c in truth_cols.items()
              if c and np.isfinite(c.get(target, np.nan))}
        cand = lofo(feats(key), tr, fams)
        base = lofo(feats("BL1_REFLOGIT"), tr, fams)
        fam_c = sorted(cand.get("per_family", {}))
        diffs = np.array([cand["per_family"][f]["acc"] - base["per_family"].get(f, {}).get(
            "acc", np.nan) for f in fam_c], dtype=float)
        m, lo, hi = nm.cluster_bootstrap_ci(diffs, np.array(fam_c), n_boot=n_boot) \
            if np.isfinite(diffs).sum() >= 2 else (float("nan"),) * 3
        res[target] = {
            "candidate_mean_acc": cand["mean_acc"], "bl1_mean_acc": base["mean_acc"],
            "candidate_panel_n": cand.get("n_ckpt", 0), "bl1_panel_n": base.get("n_ckpt", 0),
            "panels_equal": bool(cand.get("n_ckpt", 0) == base.get("n_ckpt", 0)),
            "margin": (cand["mean_acc"] - base["mean_acc"])
            if np.isfinite(cand["mean_acc"]) and np.isfinite(base["mean_acc"]) else None,
            "per_family_diff_mean": m, "per_family_diff_ci95": [lo, hi],
            "n_families": cand.get("n_families", 0), "n_ckpt": cand.get("n_ckpt", 0),
            "per_family": cand.get("per_family", {}),
        }
    se = res["safe_engagement_rate"]
    hc = res["harmful_compliance_rate"]
    ci_excl = bool(np.isfinite(se["per_family_diff_ci95"][0])
                   and se["per_family_diff_ci95"][0] > 0)
    margin_ok = bool(se["margin"] is not None and se["margin"] >= cfg["e3_margin_vs_bl1"])
    hc_ok = bool(hc["margin"] is not None and hc["margin"] >= -1e-9)
    res["e3_pass"] = bool(margin_ok and ci_excl and hc_ok)
    res["e3_margin_vs_BL1"] = se["margin"]
    res["e3_ci95"] = se["per_family_diff_ci95"]
    res["feature_note"] = ("ONE feature per candidate and per baseline, so the ridge has the "
                           "same capacity for every row and the comparison is not won by "
                           "feature count. For a LABEL-FREE candidate the panel is widened to "
                           "every checkpoint with a weight summary, because such a candidate "
                           "needs no activations; candidate_panel_n and bl1_panel_n are "
                           "reported per target so an unequal comparison is visible rather "
                           "than hidden.")
    return res


# ----------------------------------------------------------------------------------
# PROMPT-BUDGET CURVE (report in FULL, never its maximum)
# ----------------------------------------------------------------------------------
def budget_curve(tag: str, cfg: dict, stim: list[dict], keys: list[str],
                 n_resample: int = 20, seed: int = 0) -> dict:
    """k in {0,4,8,16,32,128}: refit u and the probe on that subsample only, recompute
    every candidate.  Reported at EVERY k with its CI, and with an explicit
    flat / monotone / NON-MONOTONE verdict -- never as a scan maximum."""
    cache = CkptCache(tag)
    if not cache.ok():
        return {"tag": tag, "error": "not harvested"}
    y = np.array([s["y"] for s in stim], dtype=int)
    sid = np.array([s["set_id"] for s in stim], dtype=int)
    easy = np.flatnonzero(sid == 0)
    out: dict[str, Any] = {"tag": tag, "ks": {}}
    x10 = compute_x10(cache, cfg)

    for k in cfg["budget_ks"]:
        if k == 0:
            # k=0: only X10 is defined. X2's 'weights-only' form would take u = the layer's
            # minimal singular direction, which IS X10's direction -- the SAME object.
            # Reported ONCE, under X10, not counted twice.
            out["ks"]["0"] = {
                "X10": x10.get("X10"),
                "X10_abs": x10.get("X10_abs"),
                "BL7_JORAK_A": x10.get("BL7_JORAK_A"),
                "note": ("at k=0 only X10 is defined; a 'weights-only X2' would use the "
                         "layer's minimal singular direction, which IS X10's direction, so "
                         "it is the same object and is not double counted"),
            }
            continue
        vals: dict[str, list[float]] = {kk: [] for kk in keys}
        # per-draw values keyed by draw index r (NaN when a draw failed), so a pair's
        # Delta(k) can be formed draw-by-draw: draw r selects the SAME items in every checkpoint
        draws_k: dict[str, list] = {kk: [None] * n_resample for kk in keys}
        for r in range(n_resample):
            rr = np.random.default_rng(seed * 7919 + k * 31 + r)
            i1 = rr.permutation(easy[y[easy] == 1])[: max(k // 2, 1)]
            i0 = rr.permutation(easy[y[easy] == 0])[: max(k // 2, 1)]
            sub = np.r_[i1, i0]
            if sub.size < 4 or len(np.unique(y[sub])) < 2:
                continue
            try:
                c = compute_candidates(cache, y, cfg, seed=seed + r, subset=sub, lean=True)
            except Exception:  # noqa: BLE001
                continue
            for kk in keys:
                v = c.get(kk)
                if v is not None and not isinstance(v, bool) and np.isfinite(v):
                    vals[kk].append(float(v))
                    draws_k[kk][r] = float(v)
        row = {}
        for kk, vv in vals.items():
            if len(vv) >= 3:
                m, lo, hi = nm.bootstrap_ci(np.array(vv), n_boot=1000, seed=seed)
                row[kk] = {"mean": m, "ci95": [lo, hi], "n_draws": len(vv),
                           "sd_across_draws": float(np.std(vv, ddof=1))}
        out["ks"][str(k)] = row
        out.setdefault("draws", {})[str(k)] = draws_k
    cache.free()

    verdicts = {}
    for kk in keys:
        seq = [out["ks"][str(k)].get(kk, {}).get("mean") for k in cfg["budget_ks"] if k > 0]
        seq = [s for s in seq if s is not None and np.isfinite(s)]
        if len(seq) < 3:
            verdicts[kk] = "UNDEFINED"
            continue
        d = np.diff(seq)
        rng_ = max(seq) - min(seq)
        if rng_ < 1e-9 or rng_ < 0.02 * max(abs(np.mean(seq)), 1e-9):
            verdicts[kk] = "FLAT"
        elif np.all(d >= -1e-12) or np.all(d <= 1e-12):
            verdicts[kk] = "MONOTONE"
        else:
            verdicts[kk] = "NON_MONOTONE"
    out["monotonicity_verdict"] = verdicts
    out["reporting_rule"] = ("the curve is reported at EVERY k with its CI; a scan maximum "
                             "is NEVER reported as a result")
    return out


def budget_pair_deltas(budget: dict, pairs: list[dict], scored: dict, keys: list[str],
                       ks: list[int]) -> list[dict]:
    """Delta_j(k) = cand(child) - cand(parent) at a prompt budget of k, formed DRAW BY DRAW
    (draw r fits u on the same k items in both checkpoints), expressed in the pair's pooled
    shuffled-label SD from the FULL-set nulls. Reported at EVERY k; never as a scan maximum."""
    from aii_common import slug

    out = []
    for p in pairs:
        pt, ct = slug(p["parent"]), slug(p["child"])
        bp, bc = budget.get(pt), budget.get(ct)
        if not bp or not bc or "draws" not in bp or "draws" not in bc:
            continue
        row = {"pair": p["pair"], "effectiveness": p.get("effectiveness"),
               "stratum": p.get("stratum"), "delta_HC": p.get("delta_HC"), "by_k": {}}
        for k in ks:
            if k == 0:
                kp = (bp["ks"].get("0") or {})
                kc = (bc["ks"].get("0") or {})
                row["by_k"]["0"] = {kk: (None if kp.get(kk) is None or kc.get(kk) is None
                                         else float(kc[kk]) - float(kp[kk]))
                                    for kk in ("X10", "X10_abs", "BL7_JORAK_A")}
                continue
            dp, dc = bp["draws"].get(str(k), {}), bc["draws"].get(str(k), {})
            cell = {}
            for kk in keys:
                a = np.array([np.nan if v is None else v for v in dp.get(kk, [])], dtype=float)
                b = np.array([np.nan if v is None else v for v in dc.get(kk, [])], dtype=float)
                n = min(a.size, b.size)
                if n == 0:
                    continue
                d = (b[:n] - a[:n])
                d = d[np.isfinite(d)]
                if d.size < 3:
                    continue
                sdp = ((scored.get(pt) or {}).get("nulls", {}).get(kk) or {}).get("sd")
                sdc = ((scored.get(ct) or {}).get("nulls", {}).get(kk) or {}).get("sd")
                pooled = (float(np.sqrt(((sdp or 0.0) ** 2 + (sdc or 0.0) ** 2) / 2.0))
                          if (sdp or sdc) else None)
                cell[kk] = {"mean_delta": float(d.mean()),
                            "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                            "frac_draws_same_sign_as_mean": float(np.mean(np.sign(d) == np.sign(d.mean()))),
                            "mean_delta_pooled_sd": (float(d.mean() / pooled)
                                                     if pooled and pooled > 1e-12 else None),
                            "n_draws": int(d.size)}
            row["by_k"][str(k)] = cell
        out.append(row)
    return out


def x2_parent_identity_rows(scored: dict, pairs: list[dict], cfg: dict,
                            stim: list[dict]) -> list[dict]:
    """X2_parent: the CHILD's write mass along the PARENT's own harm axis.

    STRUCTURALLY GUARANTEED, NOT A RESULT. Orthogonalising a write matrix against a direction
    close to the parent's harm axis drives ||u_parent^T M_child|| towards zero by construction,
    so a collapse here is an algebraic identity of the edit, not evidence that a parent-free
    readout works. Reported (the plan requires it in the output text), labelled
    structurally_guaranteed = True, and EXCLUDED from every E-test and from survivor selection.
    X2_own -- the child's write mass along the axis refit on the CHILD's OWN activations -- is
    the metric.
    """
    from aii_common import slug

    y = np.array([s["y"] for s in stim], dtype=int)
    sid = np.array([s["set_id"] for s in stim], dtype=int)
    easy = np.flatnonzero(sid == 0)
    rows = []
    for p in pairs:
        pt, ct = slug(p["parent"]), slug(p["child"])
        sp_, sc_ = scored.get(pt) or {}, scored.get(ct) or {}
        if "real" not in sp_ or not (HARVEST / ct / "W_DONE").exists():
            continue
        try:
            cp = CkptCache(pt)
            if not cp.ok():
                continue
            ls = int(sp_["real"]["l_star"])
            A = cp.A[easy]
            ye = y[easy]
            if sp_["real"].get("primary_axis") == "probe":
                u = nm.logistic_probe_direction(A[:, ls, :], ye, seed=0)
            else:
                u = nm.unit(A[ye == 1, ls, :].mean(0) - A[ye == 0, ls, :].mean(0))
            cp.free()
            cc = CkptCache(ct) if (HARVEST / ct / "meta.json").exists() else None
            if cc is None:
                continue
            G = cc.G
            w = (cc.meta.get("w") or {}).get("parts", {}).get("stacked")
            if not G or not w or len(u) != G[0].shape[0]:
                continue
            d = int(len(u))
            wm = np.array([nm.write_mass(G[l], w["fro2"][l], u, d) for l in range(len(G))])
            band = _band_blocks(cc, cfg, len(G))
            x2p = float(np.mean(np.log10(np.maximum(wm[band], 1e-12))))
            rows.append({
                "pair": p["pair"], "parent": p["parent"], "child": p["child"],
                "X2_parent": x2p, "X2_parent_min": float(np.log10(max(wm.min(), 1e-12))),
                "X2_own_child": (sc_.get("real") or {}).get("X2"),
                "X2_parent_checkpoint": sp_["real"].get("X2"),
                "structurally_guaranteed": True,
                "excluded_from_scoring": True,
                "note": ("the child's write mass along the PARENT's axis; its collapse is an "
                         "algebraic identity of an orthogonalisation against (a direction "
                         "close to) that axis. X2_own, refit on the child's own activations, "
                         "is the metric."),
            })
            cc.free()
        except Exception as exc:  # noqa: BLE001
            rows.append({"pair": p["pair"], "error": repr(exc)})
    return rows
