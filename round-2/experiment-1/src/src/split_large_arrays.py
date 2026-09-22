#!/usr/bin/env python
"""Convert every per-position C-harvest tensor harvest/<tag>/D_resp.npy (120-300 MB) into
numbered parts below GitHub's 100 MiB per-file limit (harvest/<tag>/D_resp_parts/), VERIFY that
the reassembled array is bit-identical to the original, and only then delete the original.

All 18 D_resp files are converted (not only the 15 above the limit) so the layout is uniform.
Afterwards the whole workspace (excluding .venv) is scanned and the script fails loudly if any
file is still above the limit.

    uv run src/split_large_arrays.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import HARVEST, RESULTS, WS, jdump, load_npy_maybe_split, save_npy_split, setup_logging, sha256_file  # noqa: E402
from loguru import logger  # noqa: E402

LIMIT = 100 * 1024 ** 2


@logger.catch(reraise=True)
def main() -> int:
    setup_logging("split_large_arrays")
    report = []
    for f in sorted(HARVEST.glob("*/D_resp.npy")):
        tag = f.parent.name
        orig = np.load(f)
        h0 = sha256_file(f)
        d = save_npy_split(orig, f.parent, "D_resp")
        back = load_npy_maybe_split(f.parent, "D_resp.__never__")  # sanity: helper returns None
        assert back is None
        # read the PARTS (not the original): temporarily hide the original from the loader
        parts = sorted(d.glob("D_resp_part_*.npy"))
        re = np.concatenate([np.load(p) for p in parts], axis=0)
        identical = bool(re.dtype == orig.dtype and re.shape == orig.shape
                         and np.array_equal(re, orig))
        sizes = [p.stat().st_size for p in parts]
        if not identical or max(sizes) >= LIMIT:
            raise RuntimeError(f"{tag}: split verification failed (identical={identical}, "
                               f"max part {max(sizes)} bytes)")
        f.unlink()
        # after deletion the loader must reassemble the parts transparently
        via_loader = load_npy_maybe_split(f.parent, "D_resp")
        assert via_loader is not None and np.array_equal(via_loader, orig)
        report.append({"tag": tag, "original_bytes": int(orig.nbytes), "original_sha256": h0,
                       "shape": list(orig.shape), "n_parts": len(parts),
                       "max_part_bytes": int(max(sizes)), "bit_identical": identical})
        logger.info(f"{tag}: {orig.nbytes/2**20:.0f} MiB -> {len(parts)} parts "
                    f"(max {max(sizes)/2**20:.1f} MiB), bit-identical, original removed")
        del orig, re, via_loader
    over = [str(p.relative_to(WS)) for p in WS.rglob("*")
            if p.is_file() and ".venv" not in p.parts and p.stat().st_size >= LIMIT]
    jdump({"converted": report, "files_still_over_100MiB": over}, RESULTS / "split_report.json")
    if over:
        raise RuntimeError(f"files still over 100 MiB: {over}")
    logger.info(f"converted {len(report)} file(s); no file over 100 MiB remains outside .venv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
