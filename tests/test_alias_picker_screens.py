"""The alias picker against docs/reference/alias-picker-screens.md, and SVG snapshots of states 1–7.

The text tests compare each rendered frame with the drawn frame line by line (colour aside). The
snapshot tests (pytest-textual-snapshot) also catch colour and style changes; update them with
`pytest --snapshot-update` after a deliberate change, and review the SVGs in the diff.
"""

import re
from pathlib import Path

import pytest

from shelley.ui.alias_picker import AliasPickerApp

SCREENS = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "reference"
    / "alias-picker-screens.md"
)

SAMTOOLS = (
    "ace2sam bgzip blast2sam.pl bowtie2sam.pl export2sam.pl fasta-sanitize.pl htsfile "
    "interpolate_sam.pl libdeflate-gunzip libdeflate-gzip maq2sam-long maq2sam-short md5fa "
    "md5sum-lite novo2sam.pl plot-ampliconstats plot-bamstats psl2sam.pl sam2vcf.pl samtools "
    "samtools.pl seq_cache_populate.pl soap2sam.pl tabix wgsim wgsim_eval.pl zoom2sam.pl"
).split()
BEDTOOLS = (
    "annotateBed bamToBed bamToFastq bed12ToBed6 bedpeToBam bedToBam bedToIgv bedtools "
    "closestBed clusterBed complementBed coverageBed expandCols fastaFromBed flankBed "
    "genomeCoverageBed getOverlap groupBy intersectBed linksBed mapBed maskFastaFromBed mergeBed "
    "multiBamCov multiIntersectBed nucBed pairToBed pairToPair randomBed shiftBed shuffleBed "
    "slopBed sortBed subtractBed tagBam unionBedGraphs windowBed windowMaker"
).split()

SIZES = {"80x24": (80, 24), "120x40": (120, 40), "80x23": (80, 23)}
STATES = [1, 2, 3, 4, 5, 6, 7]


def make_app(state: int) -> AliasPickerApp:
    names, container, version = (
        (BEDTOOLS, "bedtools", "2.31.1")
        if state == 6
        else (SAMTOOLS, "samtools", "1.21")
    )
    return AliasPickerApp(
        [{"name": n, "command": f"/usr/local/bin/{n}"} for n in names],
        container,
        version,
        mouse=state != 7,
        command="shelley-bio",  # the placeholder drawn in the frames
    )


async def go_to(pilot, index: int, *, tick: bool = False) -> None:
    step = index - pilot.app.highlight
    await pilot.press(*(["down"] * step if step > 0 else ["up"] * -step))
    if tick:
        await pilot.press("space")


async def drive(pilot, state: int, width: int) -> None:
    """Put the picker into one of the drawn states."""
    wide = width >= 120
    if state == 1:
        return
    if state == 6:
        if wide:  # rows 7–33 of 38 shown, highlight on mergeBed
            await go_to(pilot, 7, tick=True)
            await go_to(pilot, 18, tick=True)
            await go_to(pilot, 32)
            await go_to(pilot, 22, tick=True)
        else:  # scrolled so maskFastaFromBed is the last visible row
            await go_to(pilot, 7, tick=True)
            await go_to(pilot, 18, tick=True)
            await go_to(pilot, 21)
        await pilot.pause()
        return
    ticks = [1, 6, 19, 23] if wide else [1, 6]
    for index in ticks:
        await go_to(pilot, index, tick=True)
    if state in (3, 4):
        await go_to(pilot, 3)
        await pilot.press("r", *"bowtie2sam")
        if state == 4:
            await pilot.press("escape")
    elif state == 5:
        await pilot.press("escape")
    elif state == 7:
        await pilot.press("tab")
    await pilot.pause()


def drawn_frames() -> dict[tuple[str, int], list[str]]:
    """{("80x24", 1): [lines…]} from the screens doc, without the launching command row."""
    frames: dict[tuple[str, int], list[str]] = {}
    size = state = None
    block: list[str] | None = None
    for line in SCREENS.read_text(encoding="utf-8").splitlines():
        if block is not None:
            if line.startswith("```"):
                frames[(size, state)] = block[1:]
                block = None
            else:
                block.append(line)
        elif m := re.match(r"## (\d+)×(\d+)", line):
            size = f"{m[1]}x{m[2]}"
        elif m := re.match(r"### (\d) · ", line):
            state = int(m[1])
        elif line.startswith("```") and state is not None:
            block = []
    return frames


FRAMES = drawn_frames()


def rendered_lines(app) -> list[str]:
    return [strip.text for strip in app.screen._compositor.render_strips()]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("size", ["80x24", "120x40"])
async def test_matches_drawn_frame(size, state):
    width, height = SIZES[size]
    expected = FRAMES[(size, state)]
    app = make_app(state)
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        await drive(pilot, state, width)
        lines = rendered_lines(app)[: len(expected)]
    if state == 3:
        # The frame draws the block cursor as █; on screen it is a reverse-video cell.
        expected = [line.replace("bowtie2sam█", "bowtie2sam ") for line in expected]
    if state == 5 and size == "120x40":
        # The 120×40 frame draws the dialog 2 rows above centre; the widget centres it over the list
        # (as the 80×24 frame does). Compare everything outside the dialog's rows.
        lines, expected = _outside_dialog(
            lines, expected, app_rows=(15, 23), frame_rows=(13, 21)
        )
    assert [line.rstrip() for line in lines] == [line.rstrip() for line in expected]


def _outside_dialog(lines, expected, *, app_rows, frame_rows):
    keep = [
        i
        for i in range(len(expected))
        if not (min(app_rows[0], frame_rows[0]) <= i < max(app_rows[1], frame_rows[1]))
    ]
    return [lines[i] for i in keep], [expected[i] for i in keep]


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("size", list(SIZES))
def test_snapshot(snap_compare, size, state):
    width, height = SIZES[size]

    async def run_before(pilot) -> None:
        await pilot.pause()
        await drive(pilot, state, width)

    assert snap_compare(
        make_app(state), terminal_size=(width, height), run_before=run_before
    )
