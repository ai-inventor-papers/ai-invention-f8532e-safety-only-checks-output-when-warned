# Obsolete operational scripts

Kept for provenance only; none is needed to reproduce the results.

- `finish.sh`, `status.sh`, `s1.sh`, `relaunch_sweep.sh`, `run_after_t2.sh`, `run_judge_when_ready.sh`:
  session-1 (03:36-04:47 UTC) helpers. They are superseded by `finish2.sh` and the stages in `method.py`.
- `run_csweep_after_psweep.sh`: a session-2 C-harvest launcher that was replaced, before it ran, by
  `run_tail_control.sh` (the time-gated version).
