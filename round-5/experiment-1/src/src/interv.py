#!/usr/bin/env python3
"""The Tier-B intervention primitive, written fresh in this artifact.

The iteration-4 causal-grid driver is confirmed missing from disk, so this
module is NOT inherited: its correctness rests on the unit tests T1-T3 in
src/unit_tests.py and on the S2 sanity signals, exactly as the plan requires.

Two operations, both implemented as forward HOOKS so that alpha=0 is a bitwise
no-op and removing the hooks is an exact restore:

    PROJECT-OUT              h <- h - (h . v) v                (v unit)
    MATCHED-NORM RANDOM R    h <- h - (h . v) r                (r unit, r _|_ v)

Both displace the activation by EXACTLY |h . v|, which is what "matched-norm
orthogonalised random at identical displacement" means. Only the direction of
the displacement differs, so R is the correct null for "this coordinate in
particular", not merely "a perturbation of this size".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
import torch


# --------------------------------------------------------------------------- #
# direction algebra                                                            #
# --------------------------------------------------------------------------- #


def orthogonal_random(v: np.ndarray, *, rng: np.random.Generator) -> np.ndarray:
    """Draw r uniform on the unit sphere, Gram-Schmidt against v, renormalise."""
    v = np.asarray(v, dtype=np.float64)
    nv = float(np.linalg.norm(v))
    if nv <= 0:
        raise ValueError("v must be non-zero")
    vu = v / nv
    for _ in range(64):
        r = rng.standard_normal(v.shape[0])
        r = r - float(r @ vu) * vu
        nr = float(np.linalg.norm(r))
        if nr > 1e-8:
            return r / nr
    raise RuntimeError("could not draw a direction orthogonal to v")


# --------------------------------------------------------------------------- #
# intervention spec                                                            #
# --------------------------------------------------------------------------- #


class NotSupported(Exception):
    """Raised when an architecture cannot support a requested primitive (e.g. W8's
    lesion cannot find an attention-output / MLP-output projection module). The
    driver catches this and marks that cell NOT_RUN rather than crashing."""


@dataclass
class Intervention:
    """Project `v` out of the residual stream over hidden-state indices lo..hi,
    or (kind='patch') replace the last-token residual with a supplied vector.

    lo/hi are HIDDEN-STATE indices (1..L); the hook is installed on decoder
    block (idx-1) for each idx in lo..hi, because hidden_states[i+1] is the
    output of block i.

    kind   'project' (default) -> h <- h - alpha*(h.v)*d   (d = v or `repl`).
           'patch'             -> h_last <- h_last + alpha*(patch_vectors[idx] - h_last),
                                   always applied at the LAST token only (site is
                                   forced to 'last' regardless of the `site` field),
                                   used for field-norm H validation (e.g. patching in
                                   a mean-benign activation per block index).
    site   'last' -> only the last real token; 'all' -> every real token;
           'from_last' -> the ORIGINAL last prompt token AND every generated
                     position (decode_hidden only: since decode re-runs the full
                     sequence with no KV cache each step, this masks every column
                     from the original last-prompt index onward, so the
                     intervention persists across the whole continuation instead
                     of only touching whichever token is currently last).
    v      unit candidate direction (kind='project'; unused for kind='patch').
    repl   None   -> project out along v (the candidate direction).
           ndarray-> displace along `repl` instead, with the SAME scalar (h . v).
                     Passing an orthogonal unit vector gives the matched-norm
                     random control R.
    patch_vectors  kind='patch' only: an (d,) ndarray applied to every intervened
                     block, OR a dict {hidden_state_idx: (d,) ndarray} for a
                     per-block vector.
    alpha  scale on the displacement / blend. alpha=0.0 is a bitwise no-op.
    explicit_position_ids  if True, the runner passes position_ids =
                     clamp(cumsum(attention_mask,-1)-1, min=0) to the forward
                     call instead of relying on the model's own inference from
                     the (left-padded) attention mask. See unit test T11.
    """

    lo: int
    hi: int
    v: np.ndarray | None = None
    site: str = "last"
    repl: np.ndarray | None = None
    alpha: float = 1.0
    kind: str = "project"
    patch_vectors: "np.ndarray | dict[int, np.ndarray] | None" = None


# Architecture (config.model_type) -> (attention-output leaf name, MLP-output leaf name).
# Used by W8's self-lesion to find the right projection modules without a hardcoded
# single naming convention (o_proj/down_proj is the Llama-family convention; gpt_neox
# and bloom use dense/dense_4h_to_h).
ARCH_LESION_MODULES: dict[str, tuple[str, str]] = {
    "llama": ("o_proj", "down_proj"),
    "qwen2": ("o_proj", "down_proj"),
    "qwen3": ("o_proj", "down_proj"),
    "qwen3_moe": ("o_proj", "down_proj"),
    "olmo": ("o_proj", "down_proj"),
    "olmo2": ("o_proj", "down_proj"),
    "gemma": ("o_proj", "down_proj"),
    "gemma2": ("o_proj", "down_proj"),
    "gemma3": ("o_proj", "down_proj"),
    "gemma3_text": ("o_proj", "down_proj"),
    "mistral": ("o_proj", "down_proj"),
    "phi3": ("o_proj", "down_proj"),
    "falcon": ("dense", "dense_4h_to_h"),
    "falcon_h1": ("o_proj", "down_proj"),
    "gpt_neox": ("dense", "dense_4h_to_h"),
    "bloom": ("dense", "dense_4h_to_h"),
}
_FALLBACK_ATTN_NAMES = ("o_proj", "dense", "out_proj", "c_proj", "wo")
_FALLBACK_MLP_NAMES = ("down_proj", "dense_4h_to_h", "fc2", "c_proj", "w2")


def lesion_module_names(model: Any, block: Any) -> tuple[str, str]:
    """Resolve (attn-out leaf name, mlp-out leaf name) for this architecture.

    Tries the ARCH_LESION_MODULES entry for config.model_type first (if its
    names are actually present on `block`), then falls back to a search over
    `block`'s own leaf module names using a priority list. Raises NotSupported
    with a clear message if neither role can be resolved, so callers can mark
    the cell NOT_RUN instead of crashing.
    """
    mt = str(getattr(getattr(model, "config", None), "model_type", "") or "")
    leaf_names = {name.split(".")[-1] for name, _ in block.named_modules() if name}
    attn_pref, mlp_pref = ARCH_LESION_MODULES.get(mt, (None, None))
    attn_order = ([attn_pref] if attn_pref else []) + list(_FALLBACK_ATTN_NAMES)
    mlp_order = ([mlp_pref] if mlp_pref else []) + list(_FALLBACK_MLP_NAMES)
    attn_name = next((n for n in attn_order if n and n in leaf_names), None)
    mlp_name = next((n for n in mlp_order if n and n in leaf_names), None)
    if attn_name is None or mlp_name is None:
        raise NotSupported(
            f"W8 lesion: could not find attention-output/MLP-output projection "
            f"modules for model_type={mt!r} (leaf names seen: {sorted(leaf_names)})"
        )
    return attn_name, mlp_name


@dataclass
class LesionSpec:
    """W8's rank-one self-lesion: y <- y - alpha (y . u) u on the attention-output
    and MLP-output projection modules of every block.

    modules  explicit leaf names to hook, e.g. ("o_proj", "down_proj"). If None
             (default), resolved per-architecture via `lesion_module_names`,
             raising NotSupported when the architecture has neither.
    """

    u: np.ndarray
    alpha: float = 1.0
    modules: tuple[str, ...] | None = None


# --------------------------------------------------------------------------- #
# the runner                                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class RunStats:
    # ||dh|| / ||h|| at the last token, keyed by INTERVENED hidden-state index
    # (1..L); group by band with core.band_indices to get a per-band view.
    disp_ratio: dict[int, list[float]] = field(default_factory=dict)
    # percentile of the intervened activation's norm inside the model's own
    # unperturbed norm distribution, same keying as disp_ratio.
    norm_pct: dict[int, list[float]] = field(default_factory=dict)

    def add(self, idx: int, ratio: Sequence[float]) -> None:
        self.disp_ratio.setdefault(idx, []).extend(float(x) for x in ratio)

    def flat(self) -> list[float]:
        """All displacement ratios pooled across intervened blocks (legacy view)."""
        out: list[float] = []
        for v in self.disp_ratio.values():
            out.extend(v)
        return out

    def by_band(self, n_layers: int) -> dict[int, list[float]]:
        """Group disp_ratio by band 1..6 using core.band_indices."""
        from core import N_BANDS, band_indices  # local import: avoid hard module coupling

        out: dict[int, list[float]] = {}
        for b in range(1, N_BANDS + 1):
            lo, hi = band_indices(n_layers, b)
            vals: list[float] = []
            for idx in range(lo, hi + 1):
                vals.extend(self.disp_ratio.get(idx, []))
            out[b] = vals
        return out


class HookedRunner:
    """Teacher-forced forward passes with optional residual-stream interventions.

    Left padding is used throughout, so the last real token is position -1 for
    every row in the batch and no attention-mask bookkeeping is needed at the
    read site.
    """

    def __init__(self, model: Any, tokenizer: Any, *, device: str = "cuda",
                 batch_size: int = 8, max_len: int = 192) -> None:
        self.model = model
        self.tok = tokenizer
        self.device = device
        self.batch_size = int(batch_size)
        self.max_len = int(max_len)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.n_layers = int(model.config.num_hidden_layers)
        self.hidden = int(model.config.hidden_size)
        self._blocks = self._find_blocks()
        if len(self._blocks) != self.n_layers:
            raise RuntimeError(
                f"found {len(self._blocks)} blocks but config says {self.n_layers}")
        self._embed = model.get_input_embeddings()
        self._final_norm = self._find_final_norm()

    def _find_final_norm(self) -> Any | None:
        """Locate the model's final residual-stream norm module (applied ONCE,
        after the last block, to produce `last_hidden_state`). Used to build
        hidden-state index L as POST-final-norm, matching transformers' own
        `output_hidden_states` convention (tie_last_hidden_states=True): index
        0=embeddings, index i (1<=i<L)=RAW output of block i-1, index L=
        final_norm(RAW output of the last block). Falls back to None (index L
        left as the last block's RAW output) if no such module is found."""
        bases = []
        for attr in ("model", "transformer", "gpt_neox", "language_model"):
            b = getattr(self.model, attr, None)
            if b is not None:
                bases.append(b)
        bases.append(self.model)
        for base in list(bases):
            inner = getattr(base, "model", None)
            if inner is not None:
                bases.append(inner)
        for base in bases:
            for name in ("norm", "final_layer_norm", "ln_f"):
                m = getattr(base, name, None)
                if m is not None:
                    return m
        return None

    # -- model surgery helpers ------------------------------------------------
    def _find_blocks(self) -> list[Any]:
        for attr in ("model", "transformer", "gpt_neox", "language_model"):
            base = getattr(self.model, attr, None)
            if base is None:
                continue
            for lattr in ("layers", "h", "blocks", "decoder"):
                mods = getattr(base, lattr, None)
                if mods is None and lattr == "decoder":
                    continue
                if mods is not None and hasattr(mods, "__len__") and len(mods) > 0:
                    return list(mods)
            inner = getattr(base, "model", None)
            if inner is not None and hasattr(inner, "layers"):
                return list(inner.layers)
        raise RuntimeError("could not locate the decoder blocks")

    # -- hooks ---------------------------------------------------------------
    def _make_resid_hook(self, iv: Intervention, idx: int, stats: RunStats,
                         collect: bool, state: dict | None):  # noqa: ANN202
        v_t = torch.as_tensor(iv.v, dtype=torch.float32, device=self.device)
        v_t = v_t / torch.linalg.norm(v_t).clamp_min(1e-12)
        if iv.repl is None:
            d_t = v_t
        else:
            d_t = torch.as_tensor(iv.repl, dtype=torch.float32, device=self.device)
            d_t = d_t / torch.linalg.norm(d_t).clamp_min(1e-12)
        alpha = float(iv.alpha)
        site = iv.site
        if site == "from_last" and state is None:
            raise ValueError(
                "Intervention.site='from_last' requires decode_hidden's internal "
                "state (it tracks the original last-prompt-token index); it is not "
                "usable from hidden_last/hidden_all_positions_mean."
            )

        def hook(_mod, _inp, out):  # noqa: ANN001, ANN202
            is_tuple = isinstance(out, tuple)
            h = out[0] if is_tuple else out
            if alpha == 0.0:
                return out
            orig_dtype = h.dtype
            hf = h.float()
            coeff = hf @ v_t                                  # (B, T)
            if site == "last":
                mask = torch.zeros_like(coeff)
                mask[:, -1] = 1.0
                coeff = coeff * mask
            elif site == "from_last":
                from_idx = state.get("from_idx") if state else None
                mask = torch.zeros_like(coeff)
                if from_idx is not None:
                    from_idx = min(int(from_idx), mask.shape[1] - 1)
                    mask[:, from_idx:] = 1.0
                else:
                    mask[:, -1] = 1.0
                coeff = coeff * mask
            delta = alpha * coeff.unsqueeze(-1) * d_t          # (B, T, d)
            if collect:
                dn = torch.linalg.norm(delta[:, -1, :], dim=-1)
                hn = torch.linalg.norm(hf[:, -1, :], dim=-1).clamp_min(1e-9)
                stats.add(idx, (dn / hn).detach().cpu().tolist())
            hnew = (hf - delta).to(orig_dtype)
            if is_tuple:
                return (hnew,) + tuple(out[1:])
            return hnew

        return hook

    def _make_patch_hook(self, iv: Intervention, idx: int, stats: RunStats,
                         collect: bool):  # noqa: ANN202
        if isinstance(iv.patch_vectors, dict):
            vec = np.asarray(iv.patch_vectors[idx], dtype=np.float32)
        else:
            vec = np.asarray(iv.patch_vectors, dtype=np.float32)
        p_t = torch.as_tensor(vec, dtype=torch.float32, device=self.device)
        alpha = float(iv.alpha)

        def hook(_mod, _inp, out):  # noqa: ANN001, ANN202
            is_tuple = isinstance(out, tuple)
            h = out[0] if is_tuple else out
            if alpha == 0.0:
                return out
            orig_dtype = h.dtype
            hf = h.float()
            last = hf[:, -1, :]
            delta_last = alpha * (p_t.unsqueeze(0) - last)     # (B, d)
            if collect:
                dn = torch.linalg.norm(delta_last, dim=-1)
                hn = torch.linalg.norm(last, dim=-1).clamp_min(1e-9)
                stats.add(idx, (dn / hn).detach().cpu().tolist())
            new_last = (last + delta_last).to(orig_dtype)
            hnew = hf.to(orig_dtype).clone()
            hnew[:, -1, :] = new_last
            if is_tuple:
                return (hnew,) + tuple(out[1:])
            return hnew

        return hook

    def _make_lesion_hook(self, spec: LesionSpec):  # noqa: ANN202
        u_t = torch.as_tensor(spec.u, dtype=torch.float32, device=self.device)
        u_t = u_t / torch.linalg.norm(u_t).clamp_min(1e-12)
        alpha = float(spec.alpha)

        def hook(_mod, _inp, out):  # noqa: ANN001, ANN202
            if alpha == 0.0:
                return out
            is_tuple = isinstance(out, tuple)
            y = out[0] if is_tuple else out
            dt = y.dtype
            yf = y.float()
            yf = yf - alpha * (yf @ u_t).unsqueeze(-1) * u_t
            ynew = yf.to(dt)
            return (ynew,) + tuple(out[1:]) if is_tuple else ynew

        return hook

    def _install(self, interventions: Sequence[Intervention] | None,
                 lesion: LesionSpec | None, stats: RunStats, collect: bool,
                 state: dict | None = None, capture: dict | None = None) -> list[Any]:
        """Install intervention/lesion hooks, THEN (if `capture` is given) our
        OWN hidden-state capture hooks on the SAME block modules.

        Registration order matters: PyTorch runs a module's forward hooks in
        registration order, and a hook's non-None return value becomes the
        `output` seen by hooks registered AFTER it on that module. Registering
        our capture hooks strictly after the intervention hooks (both here, in
        one call) guarantees the capture always sees the INTERVENED activation
        -- unlike transformers' own `output_hidden_states` recorder, whose
        hooks are installed lazily inside `model.forward()` and can end up
        registered BEFORE ours (recording the pre-hook value instead). See
        unit test T10.
        """
        handles: list[Any] = []
        for iv in interventions or []:
            for idx in range(iv.lo, iv.hi + 1):
                blk = self._blocks[idx - 1]
                if iv.kind == "patch":
                    hk = self._make_patch_hook(iv, idx, stats, collect)
                else:
                    hk = self._make_resid_hook(
                        iv, idx, stats, collect,
                        state if iv.site == "from_last" else None)
                handles.append(blk.register_forward_hook(hk))
        if lesion is not None:
            modules = lesion.modules
            if modules is None:
                modules = lesion_module_names(self.model, self._blocks[0])
            hk = self._make_lesion_hook(lesion)
            for blk in self._blocks:
                for name, mod in blk.named_modules():
                    if name.split(".")[-1] in modules:
                        handles.append(mod.register_forward_hook(hk))
        if capture is not None:
            handles.extend(self._install_own_capture(capture))
        return handles

    def _install_own_capture(self, capture: dict) -> list[Any]:
        """Register OUR OWN forward-capture hooks (embeddings, every block,
        final norm). Must be called AFTER intervention/lesion hooks so it
        observes their effect. Populates `capture` with the full (B, T, d)
        tensors; index convention documented in `_hidden_state_sequence`."""
        handles: list[Any] = []
        capture["embed"] = None
        capture["blocks"] = [None] * self.n_layers
        capture["norm"] = None

        def embed_hook(_m, _inp, out):  # noqa: ANN001, ANN202
            capture["embed"] = out[0] if isinstance(out, tuple) else out

        handles.append(self._embed.register_forward_hook(embed_hook))

        def make_block_hook(i: int):  # noqa: ANN202
            def hook(_m, _inp, out):  # noqa: ANN001, ANN202
                capture["blocks"][i] = out[0] if isinstance(out, tuple) else out

            return hook

        for i, blk in enumerate(self._blocks):
            handles.append(blk.register_forward_hook(make_block_hook(i)))

        if self._final_norm is not None:
            def norm_hook(_m, _inp, out):  # noqa: ANN001, ANN202
                capture["norm"] = out[0] if isinstance(out, tuple) else out

            handles.append(self._final_norm.register_forward_hook(norm_hook))
        return handles

    def _hidden_state_sequence(self, capture: dict) -> list["torch.Tensor"]:
        """(L+1)-length list of (B, T, d) tensors from an own-capture dict.

        index 0        = embeddings (input to block 0)
        index i, 1<=i<L = RAW output of block (i-1)
        index L         = final_norm(output of the LAST block) if a final-norm
                          module was found, else that block's RAW output.
        This matches transformers' own `output_hidden_states` convention
        (tie_last_hidden_states=True): verified against an unhooked HF pass in
        unit test T10 (max rel diff < 1e-3).
        """
        L = self.n_layers
        blocks = capture["blocks"]
        tail = capture["norm"] if capture.get("norm") is not None else blocks[L - 1]
        return [capture["embed"]] + list(blocks[: L - 1]) + [tail]

    @staticmethod
    def _position_ids(attention_mask: "torch.Tensor") -> "torch.Tensor":
        pos = attention_mask.long().cumsum(-1) - 1
        return pos.clamp(min=0)

    # -- public API ----------------------------------------------------------
    @torch.no_grad()
    def hidden_last(self, prompts: Sequence[str], *,
                    interventions: Sequence[Intervention] | None = None,
                    lesion: LesionSpec | None = None,
                    collect_stats: bool = False,
                    explicit_position_ids: bool = False) -> tuple[np.ndarray, RunStats]:
        """Return (n_prompts, L+1, d) float32 hidden states at the LAST real token.

        explicit_position_ids: pass position_ids = clamp(cumsum(attn_mask)-1, 0)
        explicitly instead of relying on the model inferring it from the
        left-padded attention mask (see unit test T11)."""
        stats = RunStats()
        capture: dict = {}
        handles = self._install(interventions, lesion, stats, collect_stats, capture=capture)
        outs: list[np.ndarray] = []
        bs = self.batch_size
        try:
            i = 0
            while i < len(prompts):
                chunk = list(prompts[i : i + bs])
                try:
                    enc = self.tok(chunk, return_tensors="pt", padding=True,
                                   truncation=True, max_length=self.max_len,
                                   add_special_tokens=False).to(self.device)
                    kwargs = dict(use_cache=False)
                    if explicit_position_ids:
                        kwargs["position_ids"] = self._position_ids(enc["attention_mask"])
                    self.model(**enc, **kwargs)
                    seq = self._hidden_state_sequence(capture)
                    hs = torch.stack([h[:, -1, :].float() for h in seq], dim=1)
                    outs.append(hs.cpu().numpy().astype(np.float32))
                    del hs, enc
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    if bs == 1:
                        raise
                    bs = max(1, bs // 2)
                    continue
                i += bs
        finally:
            for h in handles:
                h.remove()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
        return np.concatenate(outs, axis=0), stats

    @torch.no_grad()
    def hidden_all_positions_mean(self, prompts: Sequence[str], *,
                                  interventions: Sequence[Intervention] | None = None,
                                  layer_idx: int = -1) -> np.ndarray:
        """Mean over REAL token positions of hidden_states[layer_idx]. (n, d)."""
        capture: dict = {}
        handles = self._install(interventions, None, RunStats(), False, capture=capture)
        outs: list[np.ndarray] = []
        bs = self.batch_size
        try:
            i = 0
            while i < len(prompts):
                chunk = list(prompts[i : i + bs])
                try:
                    enc = self.tok(chunk, return_tensors="pt", padding=True,
                                   truncation=True, max_length=self.max_len,
                                   add_special_tokens=False).to(self.device)
                    self.model(**enc, use_cache=False)
                    seq = self._hidden_state_sequence(capture)
                    h = seq[layer_idx].float()
                    m = enc["attention_mask"].unsqueeze(-1).float()
                    pooled = (h * m).sum(1) / m.sum(1).clamp_min(1.0)
                    outs.append(pooled.cpu().numpy().astype(np.float32))
                    del h, m, pooled, enc
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    if bs == 1:
                        raise
                    bs = max(1, bs // 2)
                    continue
                i += bs
        finally:
            for h in handles:
                h.remove()
        return np.concatenate(outs, axis=0)

    @torch.no_grad()
    def decode_hidden(self, prompts: Sequence[str], *, n_new: int = 8,
                      interventions: Sequence[Intervention] | None = None,
                      explicit_position_ids: bool = False
                      ) -> tuple[np.ndarray, np.ndarray]:
        """Greedy-decode n_new tokens with the hooks LIVE.

        Any Intervention with site='from_last' applies to the ORIGINAL last
        prompt token and every generated position throughout the continuation
        (tracked via the shared `state["from_idx"]`, an absolute, fixed column
        index into the ids tensor that only grows on the right).

        Returns (hidden, token_ids):
          hidden     (n, n_new, L+1, d) float32 -- last-token hidden state at
                     EVERY hidden-state index (0=embeddings .. L=final
                     block/norm output; see HookedRunner convention) for each
                     of the n_new generated positions.
          token_ids  (n, n_new) int64 -- the greedily generated token ids.
        """
        stats = RunStats()
        state: dict = {"from_idx": None}
        capture: dict = {}
        handles = self._install(interventions, None, stats, False, state=state, capture=capture)
        outs: list[np.ndarray] = []
        ids_out: list[np.ndarray] = []
        bs = max(1, self.batch_size // 2)
        try:
            i = 0
            while i < len(prompts):
                chunk = list(prompts[i : i + bs])
                try:
                    enc = self.tok(chunk, return_tensors="pt", padding=True,
                                   truncation=True, max_length=self.max_len,
                                   add_special_tokens=False).to(self.device)
                    ids = enc["input_ids"]
                    att = enc["attention_mask"]
                    state["from_idx"] = int(ids.shape[1] - 1)
                    per_pos: list[np.ndarray] = []
                    per_ids: list[np.ndarray] = []
                    for _ in range(n_new):
                        kwargs = dict(input_ids=ids, attention_mask=att, use_cache=False)
                        if explicit_position_ids:
                            kwargs["position_ids"] = self._position_ids(att)
                        res = self.model(**kwargs)
                        seq = self._hidden_state_sequence(capture)
                        hs = torch.stack([h[:, -1, :].float() for h in seq], dim=1)
                        per_pos.append(hs.cpu().numpy().astype(np.float32))
                        nxt = res.logits[:, -1, :].argmax(-1, keepdim=True)
                        per_ids.append(nxt.cpu().numpy())
                        ids = torch.cat([ids, nxt], dim=1)
                        att = torch.cat([att, torch.ones_like(nxt)], dim=1)
                        del res, hs
                    outs.append(np.stack(per_pos, axis=1))
                    ids_out.append(np.concatenate(per_ids, axis=1))
                    del enc, ids, att
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    if bs == 1:
                        raise
                    bs = max(1, bs // 2)
                    continue
                i += bs
        finally:
            for h in handles:
                h.remove()
            state["from_idx"] = None
        return np.concatenate(outs, axis=0), np.concatenate(ids_out, axis=0)

    @torch.no_grad()
    def logits_first(self, prompts: Sequence[str], *,
                     lesion: LesionSpec | None = None) -> np.ndarray:
        """Next-token logits at the last real token. Used by unit test T3."""
        handles = self._install(None, lesion, RunStats(), False)
        outs: list[np.ndarray] = []
        try:
            for i in range(0, len(prompts), self.batch_size):
                chunk = list(prompts[i : i + self.batch_size])
                enc = self.tok(chunk, return_tensors="pt", padding=True, truncation=True,
                               max_length=self.max_len, add_special_tokens=False).to(self.device)
                res = self.model(**enc, output_hidden_states=False, use_cache=False)
                outs.append(res.logits[:, -1, :].float().cpu().numpy())
                del res, enc
        finally:
            for h in handles:
                h.remove()
        return np.concatenate(outs, axis=0)


def norm_percentile(value: float, reference: Iterable[float]) -> float:
    """Percentile of `value` inside the model's own unperturbed norm distribution."""
    ref = np.asarray(list(reference), dtype=float)
    ref = ref[np.isfinite(ref)]
    if ref.size == 0 or not np.isfinite(value):
        return float("nan")
    return float(100.0 * (ref < value).mean())
