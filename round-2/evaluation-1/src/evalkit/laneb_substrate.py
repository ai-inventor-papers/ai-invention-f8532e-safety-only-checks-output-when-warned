#!/usr/bin/env python3
"""Reader for Lane B's per-item activation harvest.

The harvest is stored as axis-0 row shards: ``L{n}_a{alpha}.part00{1..5}.npz``.
Arrays are keyed ``<group>|win|<EARLY|LATE>|<layer>`` and ``<group>|lastp|<layer>``,
with axis 0 in the SAME ORDER as ``L{n}_index.json[group]``.

Nothing here holds more than one (lineage, alpha) pooled matrix at a time.
"""

from __future__ import annotations

import gc
import json
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from loguru import logger

from . import paths as P


@dataclass(frozen=True)
class LineageMeta:
    lineage: str
    repo: str
    band: tuple[int, ...]
    alphas: tuple[str, ...]
    n_layers: int
    d_model: int
    r_ablit_layer: int
    n_seqs: dict


@lru_cache(maxsize=8)
def meta(lineage: str) -> LineageMeta:
    m = json.loads((P.B_HARVEST / f"{lineage}_meta.json").read_text())
    return LineageMeta(
        lineage=lineage,
        repo=m["repo"],
        band=tuple(int(x) for x in m["band"]),
        alphas=tuple(f"{a:.2f}" for a in m["alphas"]),
        n_layers=int(m["model_facts"]["n_layers"]),
        d_model=int(m["model_facts"]["d_model"]),
        r_ablit_layer=int(m["r_ablit_layer"]),
        n_seqs=m["n_seqs"],
    )


@lru_cache(maxsize=8)
def index(lineage: str) -> dict:
    return json.loads((P.B_HARVEST / f"{lineage}_index.json").read_text())


@lru_cache(maxsize=64)
def key_to_part(lineage: str, alpha: str) -> dict[str, str]:
    """{array key: part filename} built from the zip central directories only."""
    mapping: dict[str, str] = {}
    parts = sorted(P.B_HARVEST.glob(f"{lineage}_a{alpha}.part*.npz"))
    if not parts:
        raise FileNotFoundError(
            f"glob {P.rel(P.B_HARVEST / f'{lineage}_a{alpha}.part*.npz')} matched 0 files"
        )
    for part in parts:
        with zipfile.ZipFile(part) as zf:
            for member in zf.namelist():
                if member.endswith(".npy"):
                    mapping[member[:-4]] = part.name
    return mapping


def load_array(lineage: str, alpha: str, key: str) -> np.ndarray:
    """Load ONE array. Raises FileNotFoundError naming the glob if the key is absent."""
    mapping = key_to_part(lineage, alpha)
    if key not in mapping:
        raise KeyError(
            f"key {key!r} absent from {lineage}_a{alpha}.part*.npz "
            f"(available groups: {sorted({k.split('|')[0] for k in mapping})})"
        )
    with np.load(P.B_HARVEST / mapping[key]) as z:
        return np.asarray(z[key])


def band_pool(lineage: str, alpha: str, group: str, window: str,
              *, layers: tuple[int, ...] | None = None) -> np.ndarray:
    """Mean-pool ``group|win|window|layer`` over the frozen band -> (n_rows, d_model).

    Accumulates in float32 one layer at a time and frees each layer immediately,
    so peak memory is two matrices rather than the whole band.
    """
    lay = layers if layers is not None else meta(lineage).band
    acc: np.ndarray | None = None
    used: list[int] = []
    for layer in lay:
        key = f"{group}|win|{window}|{layer}"
        try:
            arr = load_array(lineage, alpha, key)
        except KeyError:
            continue
        a32 = arr.astype(np.float32, copy=False)
        acc = a32.copy() if acc is None else acc + a32
        used.append(layer)
        del arr, a32
    if acc is None:
        raise KeyError(f"no band layers found for {group}|win|{window} in {lineage} a={alpha}")
    acc /= len(used)
    gc.collect()
    logger.debug("band_pool {} a={} {}|{} -> {} over layers {}",
                 lineage, alpha, group, window, acc.shape, used)
    return acc


def item_frame(lineage: str):
    """Index rows for the ``item`` group as a DataFrame aligned to axis 0."""
    import pandas as pd

    rows = index(lineage)["item"]
    df = pd.DataFrame(rows)
    df["row"] = np.arange(len(df))
    return df


def verify_row_alignment(lineage: str, alpha: str = "0.00") -> dict:
    """Confirm the index length equals axis 0 of a band array before any fit."""
    n_index = len(index(lineage)["item"])
    layer = meta(lineage).band[0]
    key = f"item|win|EARLY|{layer}"
    mapping = key_to_part(lineage, alpha)
    part = P.B_HARVEST / mapping[key]
    with zipfile.ZipFile(part) as zf:
        from .m0_assets import _npy_header_shape

        shape, dtype = _npy_header_shape(zf, key + ".npy")
    ok = int(shape[0]) == n_index
    return {"lineage": lineage, "alpha": alpha, "key": key,
            "index_rows": n_index, "array_rows": int(shape[0]),
            "d_model": int(shape[1]), "dtype": dtype, "aligned": ok,
            "part_file": P.rel(part)}
