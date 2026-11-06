# Alias picker (`build -i`) specification

The step in `shelley build <tool[/version]> -i` that turns the commands inside a container into module aliases.
Source: the design canvas "shelley-bio alias picker redesign" (all recommendations accepted 5 November 2026),
updated 6 November 2026 to use the BioCommons Textual theme instead of Catppuccin Macchiato.

Read with: [`docs/style-guide.md`](../style-guide.md) (colours, symbols, printed output) and
[`alias-picker-screens.md`](alias-picker-screens.md) (every state, cell-accurate, at 80×24 and 120×40).

Precedence: for this widget's layout, keys and on-screen copy, this spec wins. For colours, symbols and anything
printed after the widget closes, the style guide wins. Where this spec says "Decided 6 Nov", it overrides the
canvas.

Stack (from the October 2026 TUI decision record): Textual 8.x inline mode (`App.run(inline=True)`), behind the
`shelley/ui` facade, `textual>=8.2,<9`. Mouse on by default; `--no-mouse` or `SHELLEY_MOUSE=0` turns it off.
**Changed 6 Nov:** `ansi_color=False` and the BioCommons theme from `style.py` (not `ansi_color=True` /
`ansi-dark`).

## The design in one paragraph

One screen for ticking and renaming. Tick with Space or a click on `[ ]`; Enter confirms. Rename by editing the
name **in its own cell** (click the name, or R / F2); nothing moves. Two short instruction lines sit above the
list and a key bar at the bottom changes with the mode. Every state is visible without colour: `[x]` ticked,
`›` highlighted row, `› Label ‹` focused button, reverse video plus "Renaming" in the key bar for an open edit.
Esc is layered: it closes the innermost thing first (rename, then dialog) and only asks to exit from the list.

## Assumptions

| # | Assumption | Notes |
|---|---|---|
| A1 | Containers yield up to about 40 commands, rarely | samtools 1.21 has 27; bedtools 2.31.1 has 38. |
| A2 | The widget is at most terminal height minus 1 row | Keeps the launching command visible. Shorter lists make the widget shorter. |
| A3 | Tick boxes are ASCII `[x]` `[ ]` | ✓ is not in Courier New or Consolas. All other glyphs used are in WGL4, except the style guide's kept exceptions. |
| A4 | On the list, Space ticks and Enter confirms | Matches nf-core/tools and other questionary-style CLIs. |
| A5 | Saving a changed name ticks that row | The footer says so, so it is never silent. |
| A6 | Clicking outside an open name field saves it | Only Esc discards an edit. |
| A7 | Discard and exit stops the whole build | |
| A8 | Ctrl+C exits at once, without the dialog | Shell convention and an escape hatch. |
| A9 | The command shown in mockups is a placeholder | Take the real command name and argument form from the CLI. |

## Layout

### Rows, top to bottom

| Rows | 80×24 | 120×40 |
|---|---|---|
| Command that launched the build (shell output, not part of the widget) | 1 | 1 |
| Title bar | 2 | 2 |
| Instructions (2 lines) | 3–4 | 3–4 |
| Gap | 5 | 5 |
| Column headings | 6 | 6 |
| List (the only part that scrolls) | 7–17 (11 rows) | 7–33 (27 rows) |
| List footer: count, messages, scroll position | 18 | 34 |
| Gap | 19 | 35 |
| Buttons (3 rows; the reason text on the middle row) | 20–22 | 36–38 |
| Gap | 23 | 39 |
| Key bar | 24 | 40 |

Rule: **list rows = terminal height − 13**. Below 24 rows the gaps go first, then the list shrinks to a minimum of
5 rows. In tmux the status bar takes a row, so an 80×24 terminal gives the app 23 rows and the list 10. A list
shorter than the available rows makes the whole widget shorter.

### Columns, left to right (character cells)

| Column | 80 cols | 120 cols |
|---|---|---|
| Margin + highlight marker `›` | 3 | 3 |
| Include (`[ ]` centred) + gap | 7 + 2 | 7 + 2 |
| Alias name + gap | 22 + 2 | 28 + 2 |
| Command | 42 | 76 |
| Scrollbar + margin | 1 + 1 | 1 + 1 |

Between 80 and 120 columns, give extra width to Command first, then Alias name up to 28. Below 80 columns the
Command column shrinks first, then Alias name down to 14.

### Shortening long text

- **Command paths:** keep the file name whole. Keep as many leading folders as fit, then `…/`.
  At 42 cells `/usr/local/opt/trinity-2.15.1/util/align_and_estimate_abundance.pl` becomes
  `/usr/…/align_and_estimate_abundance.pl`. If the file name alone is too long, cut its end with `…`.
  The printed summary always shows full paths.
- **Alias names:** cut the end with `…`. The full name appears when you rename it.

### Scroll position

Shown three ways: footer text (`▲ 22 more above · ▼ 16 more below`), the scrollbar thumb, and the highlight that
the list follows. When everything fits the footer says `All 27 shown` and there is no scrollbar.

## States

All eight are drawn in [`alias-picker-screens.md`](alias-picker-screens.md):

1. Initial: nothing ticked, Confirm greyed with its reason beside it, highlight on row 1.
2. Some ticked: `[x]`, count updates, Confirm available, reason hidden.
3. Rename in progress: name cell becomes a field in place (reverse video, block cursor, all text selected on
   open); key bar shows rename keys.
4. Rename cancelled: original name back, highlight unchanged, footer note.
5. "Discard and exit?" dialog over the dimmed list; Keep editing focused.
6. Long list scrolled partway: footer shows above and below counts.
7. No-mouse mode: key-based instructions, "Keyboard only" in the title bar; focus on Confirm shown.
8. After Confirm: the widget clears and the summary prints (see "After the widget").

## Colours (BioCommons Textual theme)

Decided 6 Nov. Replaces the canvas's 16-colour ANSI table. Theme values are in `style.py`; contrast figures
below are checked by the style tests.

| Element | Theme value | Cue that works without colour | Contrast |
|---|---|---|---|
| Widget ground | `background` | | |
| List rows, key bar | `surface` | | |
| Title bar, column headings | `panel`, foreground text, bold | Position, bold | 9.7:1 |
| Highlighted row | `secondary` (selection) fill, white text | `›` in the margin | 7.3:1 |
| Highlighted row while focus is on the buttons | `panel` fill, foreground text | `›` stays; focused button shows `› ‹` | 9.7:1 |
| Ticked rows | no colour change | `[x]` and the count | |
| Confirm, available | `primary` fill, dark text (the `background` value) | Label | 6.6:1 |
| Confirm, unavailable | `muted` text on `surface`, no fill | Reason text "Tick at least one alias to confirm" | 4.6:1 |
| Cancel | custom `cancel` grey fill, foreground text | Label | 8.7:1 |
| Discard and exit (dialog) | `warning` fill, dark text. **Default, pending PO sign-off** | Label | 7.9:1 |
| Keep editing (dialog, default focus) | `secondary` fill, white text, shown `› Keep editing ‹` | `› ‹` | 7.3:1 |
| Name field while renaming | reverse video | Block cursor, "Renaming" in the key bar | |
| Footer count, scroll text | foreground (count), `muted` (scroll text) | Words | |
| Footer messages | foreground text; `warning` for "Tick at least one alias first." | Words | |
| Key bar keys | bold foreground | | |

Do not put `error`, `version` or `muted` text on `panel` (below 4.5:1).

## Interactions

Keys work in both mouse and no-mouse modes. "Click" means a single left click; no double-clicks, drags or hovers.

### On the list (normal mode)

| Action | Mouse | Keyboard | Result |
|---|---|---|---|
| Move the highlight | Click a row's Command cell or empty space | ↑ ↓ | `›` and highlight move to that row; the list scrolls to keep it in view. |
| Page / ends | Scroll wheel; drag or click the scrollbar | PgUp PgDn Home End | List scrolls; footer updates. The wheel scrolls without moving the highlight. |
| Tick / untick | Click the `[ ]` cell | Space (highlighted row) | `[ ]` ↔ `[x]`. Count updates. Confirm available at 1 tick, unavailable at 0. Clicking a box also moves the highlight there. |
| Start renaming | Click the alias name | R or F2 | Name cell becomes a field in place, all text selected so typing replaces it. Key bar switches to rename keys. |
| Confirm | Click Confirm | Enter on the list, or Tab to Confirm then Enter / Space | Widget clears; summary prints; build continues. |
| Confirm with nothing ticked | Click greyed Confirm | Enter | Nothing happens except the footer message "Tick at least one alias first." The reason beside the button stays. |
| Ask to exit | Click Cancel | Esc | If anything is ticked or renamed: opens "Discard and exit?" with Keep editing focused. **Decided 6 Nov (style guide), pending PO sign-off:** if nothing is ticked or renamed, exit straight away with the cancel line. |
| Focus buttons and back | (click a button directly) | Tab / Shift+Tab | Order: list → Confirm → Cancel → list. Focused button shows `› Label ‹`; list highlight dims but keeps `›`. Greyed Confirm is skipped. |
| Abort immediately | none | Ctrl+C | Exits at once without the dialog; prints the cancel line. |

### While renaming

| Action | Mouse | Keyboard | Result |
|---|---|---|---|
| Type a new name | none | Letters, Backspace, Delete | Edits the field. Long names scroll inside it. |
| Move within the name | Click inside the field | ← → Home End | Moves the text cursor. |
| Save | Click anywhere outside the field | Enter | Field closes, new name shown. If changed, the row is ticked and the footer says "Renamed bowtie2sam.pl to bowtie2sam and ticked it." If unchanged, nothing is ticked. A click outside then also does what it normally would. |
| Cancel the rename | none | Esc | Field closes, original name restored, highlight stays, footer says "Rename cancelled. Kept bowtie2sam.pl." Does **not** open the exit dialog. |
| Scroll while renaming | Wheel | ↑ ↓ PgUp PgDn | Saves the edit first, then scrolls or moves, so the field never floats away from its row. |
| Tab while renaming | n/a | Tab | Saves, then moves focus to Confirm. |

Space typed in the field is a character, not a tick (Textual gotcha: a focused `Input` swallows printable keys;
see the decision record).

### In the "Discard and exit?" dialog

| Action | Mouse | Keyboard | Result |
|---|---|---|---|
| Keep editing | Click Keep editing | Esc, or Enter (default focus) | Dialog closes; ticks, names, highlight and scroll position unchanged. |
| Discard and exit | Click Discard and exit | → or Tab, then Enter | Widget clears; prints the cancel line; exits non-zero. |
| Click outside | Click the dimmed list | n/a | Nothing. The dialog must be answered. |

### Other events

| Event | Result |
|---|---|
| Terminal resized | Layout recalculates (rows and columns rules above); the highlighted row stays in view; an open rename stays open. |
| Terminal smaller than 80×24 | Gaps go first, then the list shrinks (minimum 5 rows). Command column shrinks first, then Alias name to 14. |
| Mouse events don't arrive (PuTTY untested; tmux confirmed working) | Everything works by keyboard; the key bar is always visible. Nothing depends on hover. |
| Output is not a terminal | Not covered by the canvas. Do not open the widget; keep whatever `-i` does without a TTY today. If it does nothing sensible, print an `× Error:` line saying `-i` needs an interactive terminal, and flag it in the PR. |

## Copy deck

Final wording. Placeholders: `[container]`, `[version]`, `[n]`, `[total]`, `[old]`, `[new]`. The only three verbs
are **alias**, **tick** and **rename**; avoid "include", "select" and "entry" in new copy.

### Title bar

| ID | Text | Notes |
|---|---|---|
| `title.left` | `Choose aliases — [container] [version]` | e.g. "Choose aliases — samtools 1.21" |
| `title.right` | the real command name + ` build` (mockups show `shelley-bio build`) | Mouse mode |
| `title.right.nomouse` | `Keyboard only` | With `--no-mouse` |

### Instructions

| ID | Text |
|---|---|
| `help.line1` | `Click [ ] to tick the aliases you'll use. You can rebuild later to add more.` |
| `help.line2` | `Click a name to rename it. The Command column needs no action.` |
| `help.line1.nomouse` | `Press Space to tick the aliases you'll use. You can rebuild later to add more.` (78 cells, the widest line at 80 columns) |
| `help.line2.nomouse` | `Press R to rename the highlighted alias. The Command column needs no action.` |

### Column headings and cells

| ID | Text |
|---|---|
| `col.include` | `Include` |
| `col.alias` | `Alias name` |
| `col.command` | `Command` |
| `tick.on` / `tick.off` | `[x]` / `[ ]` |

### List footer

| ID | Where | Text | Notes |
|---|---|---|---|
| `count` | Left, always | `[n] of [total] ticked` | |
| `scroll.below` | Right | `▼ [n] more below` | |
| `scroll.both` | Right | `▲ [n] more above · ▼ [n] more below` | |
| `scroll.above` | Right | `▲ [n] more above` | |
| `scroll.all` | Right | `All [total] shown` | |
| `msg.rename.saved` | After count, 4 s or until the next action | `Renamed [old] to [new] and ticked it.` | Drop "and ticked it" if already ticked |
| `msg.rename.cancelled` | Same | `Rename cancelled. Kept [old].` | |
| `msg.confirm.empty` | Same | `Tick at least one alias first.` | |

### Buttons

| ID | Text | Notes |
|---|---|---|
| `btn.confirm` | `Confirm` | Focused: `› Confirm ‹` |
| `btn.cancel` | `Cancel` | Focused: `› Cancel ‹` |
| `btn.confirm.reason` | `Tick at least one alias to confirm` | Left of the buttons while Confirm is unavailable |

### Key bar (keys in bold)

| ID | Mode | Text |
|---|---|---|
| `keys.list` | List focused | `↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit` (at 120 columns add `PgUp PgDn Page` after Move) |
| `keys.buttons` | A button focused | `←→ Switch button   Enter Press button   Shift+Tab Back to list   Esc Exit` |
| `keys.rename` | Renaming | `Renaming   Enter Save new name   Esc Keep old name   ←→ Move in name` (at 120 columns add `Home End Start or end of name`) |
| `keys.dialog` | Dialog open | `Enter Choose   ←→ Switch button   Esc Keep editing` |

### Dialog

| ID | Text |
|---|---|
| `dlg.title` | `Discard and exit?` (bold) |
| `dlg.body` | `Nothing will be built, and your ticks and renames will be lost.` (wraps to 2 lines) |
| `dlg.keep` | `Keep editing` (left, default focus) |
| `dlg.discard` | `Discard and exit` (right) |

## After the widget

The widget clears itself (inline mode leaves nothing behind), then prints to the normal console.
**Decided 6 Nov:** this follows the style guide's "Printed alias summary", replacing the canvas's plain-text
`sum.*` rows.

After Confirm (Rich markup, 80 columns; see `docs/style-guide/screens.md`):

```
[success bold]√ Done:[/] Aliases chosen for samtools 1.21: 5 of 27
╭───────────┬───────────────────────────────────────────────────────╮
│ Alias     │ Command                                               │
├───────────┼───────────────────────────────────────────────────────┤
│ bgzip     │ /usr/local/bin/bgzip                                  │
│ sam2vcf   │ /usr/local/bin/sam2vcf.pl  (renamed from sam2vcf.pl)  │
╰───────────┴───────────────────────────────────────────────────────╯
  [muted]To add or change aliases, run the build again:[/]  [command bold]build samtools/1.21 -i[/]
```

- Table: rounded, `primary` border and bold headings; alias in `command` bold; path in `path`; the
  "(renamed from …)" note in `muted`. Full paths, never shortened; if a path doesn't fit at 80 columns, let Rich wrap the Command cell onto a
  second line rather than cut it (the summary is the record people copy from).
- The hint is written for where the user is: `build …` at the `shelley>` prompt, `shelley build …` in the shell.

After Discard and exit, or Ctrl+C: print `Cancelled. No aliases were saved and nothing was built.` and exit
non-zero (pending PO sign-off on exit status and wording, Q7 / Q13).

## Open questions (build the default; list in the PR for sign-off)

| # | Question | Build this default |
|---|---|---|
| Q2 | Can a field sit exactly over a cell and stay aligned on scroll and resize? | Yes, with "scrolling saves the edit first". Prototype first; fallback below. |
| Q3 | Should Enter on the list confirm, or tick? | Confirm; Space ticks. Revisit after watching 3–5 researchers. |
| Q4 | Should saving a rename tick the row? | Yes, with the footer message. |
| Q5 | Should renamed rows carry a lasting marker? | No marker. |
| Q6 | Should Esc skip the dialog when nothing would be lost? | **Yes** (style guide picker rule, 6 Nov). Canvas default was "always ask". PO to confirm. |
| Q7 | Exit status when discarded? | Non-zero (use the CLI's existing cancel/abort code if one exists, else 1). |
| Q8 | Should Ctrl+C skip the dialog? | Yes. |
| Q9 | Longest alias and path in the catalogue? | Unknown; columns are 22 / 28. Log the longest seen if easy. |
| Q10 | Full terminal height minus one? | Yes. |
| Q12 | Exact command name and container label? | Take from the CLI. |
| Q13 | Same cancel line for Ctrl+C, Cancel and Discard? | Yes. |
| new | Discard and exit button colour | `warning` fill (see Colours). |
| new | Does the widget paint its own `background`, or leave the terminal's? | Paint the theme background; check in PuTTY and Windows Terminal and report. |

## Fallback if in-place rename fails the prototype

Option (c) from the canvas: a fixed edit bar under the list, full width, labelled `Rename [old] to:`. The list
never moves. It costs one row (take it from the gap above the buttons). Keys, messages and auto-tick behaviour stay
the same. Use it only if the prototype shows the in-cell field drifting or breaking on scroll or resize.

## Tests

- **Behaviour:** one Textual Pilot test per row of the interaction tables above (action → expected result),
  including the dialog and the "nothing to lose" Esc path.
- **Layout:** snapshot tests (pytest-textual-snapshot) at 80×24, 120×40 and 80×23 (tmux), for states 1–7.
- **Pure functions:** path shortening, alias truncation, footer text, row/column calculation, unit-tested directly.
- **Manual (not automatable; Pilot is headless and not inline):** PuTTY, Windows Terminal, tmux with and without
  `set -g mouse on`, VS Code over SSH. Check `[x]`, `›`, `√`, `×`, rounded corners, mouse clicks, colours.