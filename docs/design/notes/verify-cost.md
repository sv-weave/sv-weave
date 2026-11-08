# Verify cost (decision D9): measurements

Measured 2026-11-08 in P4 with `tests/perf/test_verify_cost.py`
(`pytest -m perf -s tests/perf`), on an AMD Ryzen 9 9950X, pyslang 12.1.0,
Python 3.12. Two runs; they agreed to within about 10%. Seconds.

| Scenario | Classes in model | Woven | Load | Model | Verify `full` | Verify `syntax` | Total (`full`) |
|---|---|---|---|---|---|---|---|
| small: 8 classes | 15 | 8 | 0.001 | 0.001 | 0.002 | 0.002 | 0.014 |
| plain-400: 400 classes, 4-deep chains | 407 | 400 | 0.002 | 0.020 | 0.18 | 0.16 | 0.26 |
| UVM: Verilator's bundled UVM, a 200-item env with a test, plus 200 woven classes | 1309 | 200 | 0.48 | 0.69 | 0.27 | 0.06 | 1.5 |
| same, second run, unchanged inputs | 1309 | 200 | 0.51 | 0.68 | 0 (cached) | – | 1.2 |

## Observations

- **`full` costs less than Load.** Re-elaborating the UVM design with the woven code
  takes 0.27 s, against 0.48 s for the first load. Reusing the parsed user trees
  (design §7.3) works and saves the parse.
- **`syntax` saves little on small output.** On plain-400 its time is dominated by the
  rand-safety token walk in Python, which both levels run.
- **The cache makes repeat runs free**, and the manifest is unchanged by a cache hit,
  so incremental flows see no change.
- **Model building is the largest stage** on UVM (0.69 s): every UVM class is
  modelled, although none is a target. If this matters, model unselected packages
  lazily.

## Proposal for D9

Keep **`full` as the default**, with the cache. It costs a fraction of a second on a
UVM testbench and catches errors `syntax` cannot (name resolution, signatures,
concreteness). `syntax` and `off` stay available for very large designs. Re-measure
on a production testbench before closing D9 for good: this env is small next to a
real one, and the cost should grow roughly linearly with design size.
