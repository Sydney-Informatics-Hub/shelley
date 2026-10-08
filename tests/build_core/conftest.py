"""Fixtures for the new build core: a fake Galaxy mount and a matching snapshot.

The mount is a directory of *empty* files named ``tool:tag``; nothing in the catalogue
reads SIF bytes. The snapshot is written in the real ``galaxy_singularity_cache`` schema,
so tests can make the two disagree (a tag on the mount but not in the snapshot).
"""

import gzip
import json
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

# Hard cases from the version-ordering spike (tmp/design/spikes/q2_results.md):
# tool -> (tags on the mount, the tag "latest" must pick).
GOLDEN = {
    "samtools": (
        ["1.9--h91753b0_8", "1.21--h50ea8bc_3", "1.10--h2e538c0_3"],
        "1.21--h50ea8bc_3",
    ),
    "gimbleprep": (["0.0.2b3--pyh0", "0.0.2b6--pyh0", "0.0.2--pyh0"], "0.0.2--pyh0"),
    "hicexplorer": (["3.7.6--py_0", "latest--0"], "3.7.6--py_0"),
    "lofreq": (["2.1.5--py_0", "broken--0"], "2.1.5--py_0"),
    "integron_finder": (["2.0.6--py_0", "2.0rc6--py_0"], "2.0.6--py_0"),
    "seqtk": (["r93--0", "1.5--h577a1d6_0", "1.5--h577a1d6_1"], "1.5--h577a1d6_1"),
    "trinity": (["2.15.2--h1", "date.2011_11_26--0"], "2.15.2--h1"),
    "burst": (["v1.0--0", "1.0--0"], "1.0--0"),
    "plink2": (["2.00a5.12--h1", "2.0.0a.6.9--h1"], "2.0.0a.6.9--h1"),
    "r-ade4": (["1.7_2--r1", "1.7_11--r1"], "1.7_11--r1"),
    "pyvcf": (["0.6.8--py_0", "0.6.8.dev0--py_0"], "0.6.8--py_0"),
    "plink": (["1.90b4--h0", "1.90b7.7--h18e278d_1"], "1.90b7.7--h18e278d_1"),
    "t_coffee": (["11.0.8--py_0"], "11.0.8--py_0"),
    "t-coffee": (["13.46.0--h1"], "13.46.0--h1"),
}
MULLED = (
    "mulled-v2-1226d02a7c9b546335231d3ce68b2c3e640c650e",
    ["35474f18-0", "35474f18-2"],
)


def golden_entries() -> list[tuple[str, str]]:
    pairs = [(tool, tag) for tool, (tags, _) in GOLDEN.items() for tag in tags]
    return pairs + [(MULLED[0], tag) for tag in MULLED[1]]


@pytest.fixture
def galaxy_mount(tmp_path: Path) -> Callable[[Iterable[tuple[str, str]]], Path]:
    """Create a fake ``all/`` directory with one empty file per ``(tool, tag)``."""

    def make(entries: Iterable[tuple[str, str]]) -> Path:
        mount = tmp_path / "cvmfs" / "all"
        mount.mkdir(parents=True, exist_ok=True)
        for tool, tag in entries:
            (mount / f"{tool}:{tag}").touch()
        return mount

    return make


@pytest.fixture
def galaxy_snapshot(tmp_path: Path) -> Callable[[Iterable[tuple[str, str]]], Path]:
    """Write a ``galaxy_singularity_cache.json.gz`` listing ``(tool, tag)`` pairs."""

    def make(entries: Iterable[tuple[str, str]]) -> Path:
        path = tmp_path / "galaxy_singularity_cache.json.gz"
        rows = [
            {
                "entry_name": f"{tool}:{tag}",
                "tool_name": tool,
                "tag": tag,
                "path": f"/cvmfs/singularity.galaxyproject.org/all/{tool}:{tag}",
                "size_bytes": 1,
                "mtime": 0.0,
            }
            for tool, tag in entries
        ]
        rows.append(  # a non-container file in the mount root, as in the real snapshot
            {
                "entry_name": "bin",
                "tool_name": "bin",
                "tag": None,
                "path": "/x/bin",
                "size_bytes": 0,
                "mtime": 0.0,
            }
        )
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": "test",
                    "cvmfs_root": "test",
                    "entry_count": len(rows),
                    "entries": rows,
                },
                f,
            )
        return path

    return make
