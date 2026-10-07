# Q2 spike: which ordering rule defines "latest"? (2026-10-07)

Script: `q2_version_order.py` (offline, read-only, about 4 s). It compares, per tool, the newest short version chosen by:

- **A**: `find`'s pipeline (`_version_key`);
- **B**: `build`'s sort (`_parse_version`);
- **C**: conda's `VersionOrder`, fetched verbatim from `conda/conda` main, applied to the short version.

## Results

| Population | Tools | A ≠ B |
|---|---|---|
| Tools with ≥ 2 short versions | 8,762 | 331 |
| … of which `mulled-v1/v2-*` (multi-tool containers tagged `<content hash>-<build>`) | 575 | **271** |
| … named tools | 8,187 | **60** |

- **Mulled containers have no version order.** Their "version" is a content hash, so every rule's "latest" for them is arbitrary. This accounts for 82% of the T1 disagreements.
- **A has a tie at the top in 246 tools.** It reads only the leading digits, so the winner depends on the order of the cache file.
- **A proxy for the true answer** ("the short version whose first build is newest") agrees with A 97.9%, B 98.0% and C 98.4% over all named tools. The proxy is noisy, because old versions get rebuilt, so the 60 named disagreements were judged by hand instead:

| Verdict on the 60 named disagreements | Count |
|---|---|
| Clear answer | 45 |
| Same version spelled two ways (`1.0` vs `v1.0`) | 13 |
| Ambiguous (`minnow 1.2` vs `beta_1.3`; `rdock 2013.1` vs `24.04.204_legacy`) | 2 |

| Rule | Correct on the 45 clear cases | Where it goes wrong |
|---|---|---|
| A `find` | 8 / 45 | Ignores everything after the leading digits (`1.7_2` = `1.7_11`, `r188` = `r204`) |
| B `build` | 36 / 45 | Ranks non-version tags high: `latest`, `broken`, `date.2011_11_26`, `r93` over `1.5`; and pre-releases over finals: `2.0rc6` > `2.0.6`, `0.6.8.dev0` > `0.6.8` |
| **C conda** | **43 / 45** | Treats a `p` suffix as a pre-release: `bracken 3.1p1` < `3.1`, `dazz_db 1.0p2` < `1.0` (both are patch releases upstream) |

## Conclusions

1. **Use conda's version ordering for named tools.** It is the rule Bioconda itself uses to resolve versions, it was right in 43 of 45 clear cases, and it handles `dev`, `a`, `b`, `rc`, `post`, `_N` and `rNNN` correctly. `packaging.version` is not suitable, since tags are not PEP 440.
2. **Three shelley-specific additions are needed:**
   - a leading `v` is normalised away for equality, so `1.0` and `v1.0` are one version;
   - non-version tags (`latest`, `broken`, …) are never chosen as "latest";
   - `pN` patch suffixes are a known gap: two tools in the whole cache. Accept the gap or special-case it (a decision for Fred).
3. **Mulled containers need a separate rule:** for example "require an explicit tag", or "newest by build date". There is no version to order.
4. **Delivery:** conda is not installable as a library dependency. The options are to vendor `conda/models/version.py` (715 lines, BSD-3-Clause; keep the notice) or to reimplement the subset used (about 100 lines plus property tests against the vendored copy). This is a Phase 5 decision.
