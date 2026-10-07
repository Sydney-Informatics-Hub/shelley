"""Q2 spike: which ordering rule should define "latest" for Galaxy (Bioconda) tags?

Compares, per tool, the newest *short version* chosen by:
  A  find   -> shelley.utils.cache pipeline (_version_key, stable on cache order)
  B  build  -> CVMFSModuleBuilder._sort_versions (_parse_version)
  C  conda  -> conda's VersionOrder (fetched verbatim from conda/conda main) on the short version
against a proxy for "actually newest release": the short version whose earliest build
(min mtime across its --build variants) is most recent.

The proxy is imperfect (old versions are sometimes rebuilt), so treat it as a signal, and
read the printed sample by eye.

Read-only, offline. Run from the shelley repo root:
    .venv/bin/python tmp/design/spikes/q2_version_order.py
"""

import collections
import gzip
import json
import random
import sys
import types
from pathlib import Path

HERE = Path(__file__).parent

# Load conda's version.py with its one package-relative import stubbed.
exc = types.ModuleType("conda_stub_exceptions")


class InvalidVersionSpec(ValueError):
    pass


exc.InvalidVersionSpec = InvalidVersionSpec
src = (HERE / "conda_version_upstream.py").read_text()
src = src.replace("from ..exceptions import InvalidVersionSpec", "")
conda_version = types.ModuleType("conda_version")
conda_version.__dict__["InvalidVersionSpec"] = InvalidVersionSpec
exec(compile(src, "conda_version_upstream.py", "exec"), conda_version.__dict__)
VersionOrder = conda_version.VersionOrder

sys.path.insert(0, ".")
from shelley.builder.cvmfs_builder import CVMFSModuleBuilder  # noqa: E402
from shelley.utils.cache import _version_key, compute_version_entries  # noqa: E402

short = lambda tag: tag.split("--")[0]  # noqa: E731

doc = json.load(gzip.open("shelley/data/galaxy_singularity_cache.json.gz", "rt"))
by_tool = collections.defaultdict(list)
for e in doc["entries"]:
    if e["tag"]:
        by_tool[e["tool_name"]].append((e["tag"], e["path"], e["mtime"]))

builder = CVMFSModuleBuilder()
stats = collections.Counter()
rows = []
conda_fail = set()

for tool, triples in by_tool.items():
    shorts = {short(t) for t, _, _ in triples}
    if len(shorts) < 2:
        continue
    stats["tools_multi"] += 1

    # A: find's real pipeline
    a_sorted = sorted(triples, key=lambda t: _version_key(t[0]), reverse=True)
    a = compute_version_entries(tool, a_sorted)[0]["version"]
    a_tie = sum(_version_key(t) == _version_key(a) for t in shorts) > 1
    # B: build's real sort
    b = short(builder._sort_versions([(tool, t) for t, _, _ in triples])[0][1])
    # C: conda
    try:
        c = max(shorts, key=lambda s: VersionOrder(s))
    except Exception:
        c = None
        conda_fail.add(tool)
    # Proxy: newest first appearance
    first_seen = collections.defaultdict(lambda: float("inf"))
    for t, _, m in triples:
        first_seen[short(t)] = min(first_seen[short(t)], m)
    proxy = max(first_seen, key=first_seen.get)

    disagree = a != b
    stats["disagree_ab"] += disagree
    stats["a_tie"] += a_tie
    for name, v in (("A_find", a), ("B_build", b), ("C_conda", c)):
        stats[f"{name}=proxy"] += v == proxy
        if disagree:
            stats[f"{name}=proxy|disagree"] += v == proxy
    rows.append((tool, a, b, c, proxy, disagree))

n, d = stats["tools_multi"], stats["disagree_ab"]
print(f"tools with >=2 short versions: {n}; A/B disagree: {d}; conda parse failures: {len(conda_fail)}")
print(f"A (find) has a tie at the top in {stats['a_tie']} tools (winner then depends on cache order)")
print("agreement with 'newest first appearance' proxy:")
for name in ("A_find", "B_build", "C_conda"):
    print(f"  {name:8s} all: {100*stats[f'{name}=proxy']/n:5.1f}%   on A/B disagreements: {100*stats[f'{name}=proxy|disagree']/d:5.1f}%")

random.seed(7)
sample = random.sample([r for r in rows if r[5]], 25)
print("\nsample of A/B disagreements: tool | A find | B build | C conda | proxy")
for r in sorted(sample):
    print("  " + " | ".join(str(x) for x in r[:5]))

# --- breakdown: named tools vs mulled (hash-tagged, multi-tool) containers ---
print("\nbreakdown (excluding mulled-v1/v2 hash-tagged containers):")
named = [r for r in rows if not r[0].startswith("mulled-")]
nd = [r for r in named if r[5]]
print(f"  named tools with >=2 versions: {len(named)}; A/B disagree: {len(nd)}; mulled disagreements: {d - len(nd)}")
for i, name in ((1, "A_find"), (2, "B_build"), (3, "C_conda")):
    print(f"  {name:8s} all named: {100*sum(r[i]==r[4] for r in named)/len(named):5.1f}%   on named disagreements: {100*sum(r[i]==r[4] for r in nd)/len(nd):5.1f}%")
print("  all named disagreements: tool | A find | B build | C conda | proxy")
for r in sorted(nd):
    print("    " + " | ".join(str(x) for x in r[:5]))
