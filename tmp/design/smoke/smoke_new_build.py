"""Smoke run of the opt-in build (SHELLEY_NEW_BUILD=1) against the REAL /apps.

Switch criterion (b) of the migration plan. It drives the real CLI, including the sudo
re-exec, and checks every module by loading it with Lmod and running its tool. It
CHANGES SHARED STATE on the VM: modules it builds stay installed for every user.

Run from the shelley repo root, as a user with sudo:
    .venv/bin/python tmp/design/smoke/smoke_new_build.py
Writes tmp/design/smoke/results-<date>.md and prints the same table.
"""

import os
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from threading import Thread

sys.path.insert(0, ".")
from shelley.galaxy.catalogue import GalaxyCatalogue  # noqa: E402
from tests.build_core.roots_snapshot import changes, snapshot  # noqa: E402

LMOD_INIT = "/usr/share/lmod/lmod/init/bash"
ROOTS = [Path("/apps/shpc"), Path("/apps/local"), Path("/apps/Modules/modulefiles")]
OUT = Path("tmp/design/smoke") / f"results-{date.today()}.md"

# docs/reference/data-sources.md "Regression tool matrix": tool, tag, alias to run,
# alias that must NOT be exposed (star-fusion 1.0.0 regression).
MATRIX = [
    ("fastqc", "0.12.1--hdfd78af_0", "fastqc", None),
    ("multiqc", "1.19--pyhdfd78af_0", "multiqc", None),
    ("salmon", "1.10.1--h7e5ed60_0", "salmon", None),
    ("bcftools", "1.23.1--hb2cee57_0", "bcftools", None),
    ("bwa-mem2", "2.2.1--he70b90d_8", "bwa-mem2", None),
    ("fastp", "0.20.0--hdbcaa40_0", "fastp", None),
    ("sambamba", "0.8.1--hadffe2f_1", "sambamba", None),
    ("samblaster", "0.1.24--hc9558a2_3", "samblaster", None),
    ("samtools", "1.19--h50ea8bc_0", "samtools", None),
    ("blast", "2.5.0--hc0b0e79_3", "blastn", None),
    ("star", "2.7.11a--h0033a41_0", "STAR", None),
    ("star-fusion", "1.0.0--pl5.22.0_0", "STAR", "salmon"),
]

ENV = {**os.environ, "SHELLEY_NEW_BUILD": "1", "SHELLEY_NO_UPDATE_CHECK": "1", "COLUMNS": "120"}
rows: list[tuple[str, str, str]] = []


def shelley(*args, env=ENV, stdin=subprocess.DEVNULL, timeout=1800):
    start = time.monotonic()
    r = subprocess.run(
        [sys.executable, "-m", "shelley", *args],
        env=env, stdin=stdin, capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout + r.stderr, time.monotonic() - start


def loads_and_runs(tool, tag, alias, absent=None) -> tuple[bool, str]:
    script = (
        f"source {LMOD_INIT} && module load singularity && module load {tool}/{tag} "
        f"&& command -v {alias} >/dev/null && (timeout 300 {alias} --version 2>&1 || "
        f"timeout 300 {alias} -h 2>&1 || true) | head -3"
    )
    if absent:
        script += f" && ! command -v {absent} >/dev/null && echo ABSENT_OK"
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    ok = r.returncode == 0 and bool(out) and "command not found" not in out
    if absent:
        ok = ok and "ABSENT_OK" in out
    return ok, out.replace("\n", " ")[:90]


def record(name, ok, detail):
    status = "PASS" if ok else "FAIL"
    rows.append((name, status, detail.replace("|", "/")))
    print(f"{status} | {name} | {detail}", flush=True)


def no_asides() -> bool:
    return not any(p for root in ROOTS for p in root.rglob("*.aside"))


def main() -> None:
    before_all = snapshot(*ROOTS)

    # A. the regression matrix, one build each
    for tool, tag, alias, absent in MATRIX:
        code, out, secs = shelley("build", f"{tool}/{tag}")
        ok, ran = loads_and_runs(tool, tag, alias, absent) if code == 0 else (False, out[-200:])
        record(f"build {tool}/{tag}", code == 0 and ok, f"exit {code}, {secs:.0f} s; {ran}")
    sf = Path("/apps/local/quay.io/biocontainers/star-fusion/1.0.0--pl5.22.0_0/aliases.yaml")
    record("legacy star-fusion entry replaced by an authored one", sf.is_file(), f"marker {sf}")

    # B/C. not found and typo: reported before any sudo prompt
    for spec in ("parabricks", "seurat", "seqtkk"):
        code, out, _ = shelley("build", spec)
        ok = code == 1 and "not found" in out and "elevated privileges" not in out
        record(f"not found before sudo: {spec}", ok, out.strip().splitlines()[-2][:90] if out.strip() else "")

    # D. rebuild an installed tag
    code, out, secs = shelley("build", "samtools/1.19--h50ea8bc_0")
    ok, ran = loads_and_runs("samtools", "1.19--h50ea8bc_0", "samtools")
    record("rebuild samtools/1.19", code == 0 and ok and no_asides(), f"exit {code}, {secs:.0f} s; no .aside: {no_asides()}")

    # E. dead proxy: a fastqc tag that is not installed
    tags = [t.raw for t in GalaxyCatalogue().tags("fastqc") if t.raw != "0.12.1--hdfd78af_0"]
    before = snapshot(*ROOTS)
    proxy_env = {**ENV, "https_proxy": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
    code, out, _ = shelley("build", f"fastqc/{tags[0]}", env=proxy_env)
    unchanged = changes(before, snapshot(*ROOTS)) == []
    record("dead proxy: fails, names GitHub, writes nothing", code == 1 and "Couldn't reach GitHub" in out and unchanged,
           f"exit {code}; /apps unchanged: {unchanged}")

    # F. cancelled -i (no terminal in the root child) on an installed tag
    before = snapshot(*ROOTS)
    code, out, _ = shelley("build", "samtools/1.19--h50ea8bc_0", "-i")
    unchanged = changes(before, snapshot(*ROOTS)) == []
    ok, _ = loads_and_runs("samtools", "1.19--h50ea8bc_0", "samtools")
    record("cancelled -i keeps the installed module", code == 1 and unchanged and ok, f"exit {code}; /apps unchanged: {unchanged}; still runs: {ok}")

    # G. tools file: resolve all, one elevation, failures do not stop the rest
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("multiqc/1.19--pyhdfd78af_0\nnosuchtool  # typo\nbcftools/1.23.1--hb2cee57_0\n")
    code, out, secs = shelley("build", f.name)
    elevations = out.count("Running with elevated privileges")
    record("batch: one sudo, bad spec reported, others built", code == 1 and elevations == 1 and out.count("Module Built Successfully") == 2,
           f"exit {code}, {secs:.0f} s; elevations {elevations}")

    # H. two builds of the same tool at once (R11)
    results = []
    threads = [Thread(target=lambda: results.append(shelley("build", "salmon/1.10.1--h7e5ed60_0"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ok, _ = loads_and_runs("salmon", "1.10.1--h7e5ed60_0", "salmon")
    record("concurrent rebuilds of one tool", all(r[0] == 0 for r in results) and ok and no_asides(),
           f"exits {[r[0] for r in results]}; runs: {ok}; no .aside: {no_asides()}")

    # I. the OLD clean on a module built by the new path, then rebuild it
    old_env = {k: v for k, v in ENV.items() if k != "SHELLEY_NEW_BUILD"}
    code, out, _ = shelley("clean", "fastp:0.20.0--hdbcaa40_0", "-y", env=old_env)
    gone = not Path("/apps/Modules/modulefiles/fastp/0.20.0--hdbcaa40_0.lua").exists()
    entry_gone = not Path("/apps/local/quay.io/biocontainers/fastp").exists()
    record("old clean removes a new-path module", code == 0 and gone and entry_gone, f"exit {code}; link gone {gone}; registry entry gone {entry_gone}")
    code, _, _ = shelley("build", "fastp/0.20.0--hdbcaa40_0")
    record("rebuild fastp after old clean", code == 0, f"exit {code}")

    passed = sum(r[1] == "PASS" for r in rows)
    added = len([k for k in changes(before_all, snapshot(*ROOTS)) if k not in before_all])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        f"# Smoke run: opt-in build against the real /apps ({date.today()})\n\n"
        f"Host: {os.uname().nodename}. Script: `tmp/design/smoke/smoke_new_build.py`. "
        f"{passed}/{len(rows)} checks passed; {added} paths added under the build roots.\n\n"
        "| Check | Result | Detail |\n|---|---|---|\n"
        + "".join(f"| {n} | {s} | {d} |\n" for n, s, d in rows)
    )
    print(f"\n{passed}/{len(rows)} passed; report: {OUT}")


if __name__ == "__main__":
    main()
