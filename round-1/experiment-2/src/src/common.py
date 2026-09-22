"""Shared: sequence construction, direction fitting, nulls, probes."""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "8")
import hashlib, json, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
WINDOWS = {"EARLY": (5, 20), "LATE": (40, 55)}
CONT_LEN = 128
N_NULL_DIRS = 20
N_SHUFFLE = 20

LINEAGES = {
    "L1": "Qwen/Qwen3-4B-Base",
    "L2": "Qwen/Qwen3-4B",
    "L3": "Qwen/Qwen3-4B-SafeRL",
    "L4": "CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6",
    # tiny model used ONLY to smoke-test the causal-arm hooks without competing for VRAM
    "LSMOKE": "Qwen/Qwen3-0.6B",
}
IS_INSTRUCT = {"L1": False, "L2": True, "L3": True, "L4": False, "LSMOKE": True}
ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]


def load_substrate():
    return json.loads((OUT / "substrate.json").read_text())


def rng_for(tag: str) -> np.random.Generator:
    h = hashlib.sha256(("YqmEFECOIR3D|" + tag).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def random_unit_dirs(d: int, n: int, tag: str) -> np.ndarray:
    g = rng_for(tag)
    V = g.normal(size=(n, d))
    return V / np.linalg.norm(V, axis=1, keepdims=True)


def unit(v: np.ndarray) -> np.ndarray:
    nrm = np.linalg.norm(v)
    return v / nrm if nrm > 0 else v


def diff_in_means(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return A.mean(0) - B.mean(0)


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    s = math.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / max(na + nb - 2, 1))
    return float((a.mean() - b.mean()) / s) if s > 0 else 0.0


def auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    o = np.argsort(scores)
    r = np.empty(len(scores), float)
    r[o] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    s = scores[o]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            r[o[i:j + 1]] = (i + 1 + j + 1) / 2
        i = j + 1
    n1 = labels.sum()
    n0 = len(labels) - n1
    if n1 == 0 or n0 == 0:
        return 0.5
    return float((r[labels == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def cv_probe_auroc(X: np.ndarray, y: np.ndarray, folds: int = 5, tag: str = "fold",
                   ridge: float = 1.0) -> float:
    """5-fold CV linear (ridge) probe AUROC. Held-out by construction (T: in-sample
    diff-in-means at d>>n gives AUROC 1.000 on pure noise)."""
    g = rng_for(tag)
    idx = g.permutation(len(y))
    scores = np.zeros(len(y))
    for f in range(folds):
        te = idx[f::folds]
        tr = np.setdiff1d(idx, te)
        Xtr, ytr = X[tr], y[tr]
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
        Xtr = (Xtr - mu) / sd
        Xte = (X[te] - mu) / sd
        # ridge on centred labels == regularised LDA direction.
        # d >> n here, so use the DUAL form  w = X^T (X X^T + lam I)^-1 t :
        # identical solution, an n x n solve instead of d x d.
        t = ytr - ytr.mean()
        n_tr, d_tr = Xtr.shape
        lam = ridge * n_tr
        if d_tr > n_tr:
            K = Xtr @ Xtr.T + lam * np.eye(n_tr)
            a = np.linalg.solve(K, t)
            scores[te] = Xte @ (Xtr.T @ a)
        else:
            G = Xtr.T @ Xtr + lam * np.eye(d_tr)
            scores[te] = Xte @ np.linalg.solve(G, Xtr.T @ t)
    return auroc(scores, y)


def boot_ci(vals: np.ndarray, n: int = 10000, tag: str = "boot", alpha: float = 0.05):
    """Item-clustered bootstrap over the ITEM axis (vals is one value per item)."""
    g = rng_for(tag)
    m = len(vals)
    if m == 0:
        return (float("nan"),) * 3
    idx = g.integers(0, m, size=(n, m))
    means = vals[idx].mean(1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(vals.mean()), float(lo), float(hi)


def pchip_alpha_star(alphas, D, target):
    """Monotone interpolation to the alpha where D crosses `target`.
    Returns None when the curve never reaches the target inside [0, 1] - the plan
    forbids extrapolating past alpha=1 or relaxing the threshold."""
    a = np.asarray(alphas, float); y = np.asarray(D, float)
    if y[0] <= target:
        return 0.0
    for i in range(len(a) - 1):
        if (y[i] - target) * (y[i + 1] - target) <= 0:
            if y[i] == y[i + 1]:
                return float(a[i])
            t = (y[i] - target) / (y[i] - y[i + 1])
            return float(a[i] + t * (a[i + 1] - a[i]))
    return None


def interp_at(alphas, vals, a_star):
    return float(np.interp(a_star, np.asarray(alphas, float), np.asarray(vals, float)))


# --------------------------------------------------------------------------
# SHARDED NPZ. Per-(lineage, alpha) harvests are ~300-390 MB of fp16 residual
# vectors, over the 100 MB per-file deployment limit, so they are written as
# numbered parts and read back transparently. Keys are packed greedily by
# nbytes; no single array here is anywhere near the limit (largest ~6 MB).
# --------------------------------------------------------------------------
SHARD_MAX_BYTES = 90 * 1000 * 1000


def shard_paths(stem: Path) -> list[Path]:
    """Parts for `stem` (a path WITHOUT the .npz suffix), in order."""
    return sorted(stem.parent.glob(stem.name + ".part*.npz"))


def save_sharded(stem: Path, arrays: dict, max_bytes: int = SHARD_MAX_BYTES) -> list[Path]:
    """Write `arrays` across `{stem}.partNNN.npz` files, each under `max_bytes`."""
    for old in shard_paths(stem):
        old.unlink()
    parts, cur, cur_bytes = [], {}, 0
    for k, v in arrays.items():
        v = np.asarray(v)
        nb = int(v.nbytes)
        if cur and cur_bytes + nb > max_bytes:
            parts.append(cur); cur, cur_bytes = {}, 0
        cur[k] = v; cur_bytes += nb
    if cur:
        parts.append(cur)
    written = []
    for i, part in enumerate(parts, 1):
        p = stem.parent / f"{stem.name}.part{i:03d}.npz"
        np.savez(p, **part)
        written.append(p)
    return written


class ShardedNpz:
    """Dict-like view over one or more .npz parts; mirrors the NpzFile API we use."""

    def __init__(self, stem: Path):
        parts = shard_paths(stem)
        # NOTE: Path("L2_a0.00").suffix is ".00", so with_suffix() is WRONG here.
        single = stem if str(stem).endswith(".npz") else Path(str(stem) + ".npz")
        if not parts and single.exists():
            parts = [single]
        if not parts:
            raise FileNotFoundError(f"no npz or .partNNN.npz for {stem}")
        self._zs = [np.load(p) for p in parts]
        self._where = {}
        for z in self._zs:
            for k in z.files:
                self._where[k] = z
        self.parts = parts

    @property
    def files(self):
        return list(self._where)

    def __contains__(self, k):
        return k in self._where

    def __getitem__(self, k):
        return self._where[k][k]
