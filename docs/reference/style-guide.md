# shelley terminal style guide

One visual and interaction language for everything shelley prints or draws in a terminal, built from the
Australian BioCommons palette. Designed for dark terminals at 80 columns first.

Source of truth for the design: the canvas "shelley style guide (BioCommons)" (agreed 5–6 November 2026).
Example screens: [`style-guide-screens.md`](style-guide-screens.md).
Colour values: [`shelley/utils/style.py`](../../shelley/utils/style.py) (the only place hex values may appear).

## How to use this guide (humans and agents)

- Read this file before changing anything that prints to the terminal or draws a Textual widget.
- The rules marked **must** are enforced by tests (`tests/test_style.py`) or by review. Do not work around a test;
  if a rule blocks something, raise it.
- Refer to colours by **role name** (`error`, `command`, …), never by hex value or colour name. Hex values
  live only in `shelley/utils/style.py`; this document deliberately contains none, so it cannot drift from the code.
- When this guide and an older design note disagree, this guide wins. When this guide and a component spec
  (for example [`alias-picker.md`](alias-picker.md)) disagree about that component's layout, keys or copy, the spec wins;
  for colours, symbols and printed output, this guide wins.

## Decisions

| Topic | Decision |
|---|---|
| Brand colours | BioCommons hues, lightened where needed so text reaches 4.5:1 contrast. |
| Backgrounds | Dark terminals only. |
| Colour depth | Full colour (24-bit). 256- and 16-colour fallbacks are a later, low-priority task. |
| Symbols | Plain symbols paired with a word. No emoji (they break alignment; see Symbols). |
| Panels | Panels for **results only**. Status messages are plain lines. |
| Box style | Rounded corners on panels and tables; tables keep column lines. Banner stars ★ ☆ and the braille `dots` spinner kept. |
| Voice | Keep the Shelley mascot and the friendly greeting; everything else plain and helpful. |
| Textual widgets | Use the BioCommons Textual theme (built from the same roles). Catppuccin Macchiato is retired. |
| Mockups | 80 columns first. |

## Principles

1. **Colour names a role.** Each colour means one thing. It is never the only signal: every status also has a
   symbol and a word.
2. **Readable first.** Every text colour reaches at least 4.5:1 against the terminal background and against the
   raised surface Textual widgets use. Brand shades are lightened, never replaced, when they fall short.
3. **Works where researchers are.** PuTTY, tmux, Windows Terminal and VS Code over SSH. Status symbols come from
   WGL4, the character set Windows console fonts cover.
4. **Fits 80 columns.** Nothing wraps or breaks at 80 columns. Long shared prefixes (container folders) are printed
   once, not on every row.
5. **Say what to type next.** Every warning and error ends with the next command, written for where the user is:
   `search …` at the `shelley>` prompt, `shelley search …` in the shell.
6. **Friendly, not noisy.** Shelley says hello once. After that, messages are short, plain and calm. One
   exclamation mark per session, in the greeting.

## Colour roles

Use these names as Rich theme styles (`[error]…[/]`, `console.print(x, style="version")`) and as the basis
of the Textual theme. Rich can't combine a theme style with another attribute in one tag (`[error bold]` renders
unstyled), so the bold variants are theme styles of their own: `status.*`, `heading`, `label`, `prompt`,
`hint.command` and `yes`.

| Role (style name) | BioCommons source | Used for |
|---|---|---|
| `primary` | Bright Green 2413 | Prompt, headings, panel borders, table borders and headings, tool names |
| `success` | same value as `primary` | Success status lines |
| `info` | Teal 7465 | Notes |
| `path` | same value as `info` | File and container paths, image names, links |
| `warning` | Orange 7408 | Warnings; anything the user should check before continuing |
| `error` | Magenta 226, lightened 35% | Errors only |
| `version` | Dark Blue 2161, lightened 40% | Version and build strings |
| `command` | Sage 5777 | Anything the user can type: hints, examples, `module load …` |
| `muted` | Slate, lightened | Dates, sizes, secondary labels, "Try …" lead-ins, scroll hints |
| text | the terminal's own foreground | Body text. **Never set a fixed text colour in Rich output.** |
| `selection` (Textual only) | Dark Blue 2161, as a background | Highlighted row and title bars in Textual widgets, with white text |
| `purple` | Purple 241 | Not for text (fails contrast). |

Rules:

- **must** A colour always means the same role. Green is never a warning; version blue is never a path.
- **must** Colour is never the only signal. Status lines start with a symbol and a word; tables say "yes" / "no".
- **must** No hex values outside `shelley/utils/style.py`. No fixed text colour (in particular never black text).
- **must** Every text role reaches 4.5:1 on the terminal background and on the Textual surface (tested).
- Bold is for labels, headings and status words. Body text stays regular.
- At most three hues on one screen besides `muted` and text. If a screen needs more, simplify the content.
- On the Textual `panel` background (title bar, column headings) use only foreground, `primary`, `info`,
  `warning` or `command` text. `error`, `version` and `muted` fall below 4.5:1 there.
- When output isn't a terminal (piped to a file or log), Rich drops colour automatically; symbols and words
  still carry the meaning.

### Textual theme

The BioCommons Textual theme is built in `shelley/utils/style.py` from the same roles. Textual widgets must run with
`ansi_color=False` so the theme's colours are used (with ANSI colour mode on, Textual ignores theme hex values
and uses the terminal's palette).

| Textual theme field | Role / meaning |
|---|---|
| `primary` | `primary`: title text, the primary button (dark text on green), focus outlines |
| `secondary` | `selection`: highlighted row fill, with white text and the › marker |
| `accent` | `warning`: reserved for warnings in dialogs (for example "Discard and exit"); not used on ordinary buttons |
| `foreground` | light body text for widgets |
| `background` | widget ground |
| `surface` | list rows, key bar |
| `panel` | title bar, column headings |
| `success` / `warning` / `error` | the matching roles, for messages under lists |
| custom `cancel` variable | neutral raised grey with foreground text, for Cancel buttons. Cancel is never a warning colour. |

## Symbols

Every symbol comes from WGL4 unless listed as a kept exception. Emoji are not used: terminals and Rich disagree
on emoji width, which breaks panel borders (seen in the `build star` panel on the ℹ️ and ⚠️ lines).

### Status set

| Status | Symbol | Paired word | Role |
|---|---|---|---|
| Success | `√` | `Done:` or the result ("Module built") | `success` |
| Info | `i` (bold) | `Note:` | `info` |
| Warning | `!` | `Warning:` | `warning` |
| Error | `×` (U+00D7, not the letter x) | `Error:` | `error` |
| Working | Rich's `dots` spinner (`⠋ ⠙ ⠹ …`) | present tense: "Building module…" | `primary` |

### Other symbols

| Use | Symbol | Notes |
|---|---|---|
| Installed / not installed | `yes` / `no` | Words, not ✓ ✗. "yes" in `primary` bold, "no" in `muted`. |
| Tick boxes | `[x]` `[ ]` | ASCII. |
| Highlighted row, focused button | `›` and `› Label ‹` | |
| List bullet | `•` | |
| Next, leads to | `→` | |
| More above / below | `▲` `▼` | |
| Separators | `·` `…` `—` | Middle dot between short items; ellipsis for truncation. |
| Banner stars | `★` `☆` | Not in WGL4; kept by choice, decorative only. |
| Progress spinner | `⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏` (Rich `dots`) | Braille, not in WGL4; kept by choice. May show as boxes in PuTTY's default font; nothing is lost because the words beside it say what's happening. Use only in the spinner. |
| Panel and table corners | `╭ ╮ ╰ ╯` | Not in WGL4; kept by choice. Fallback `┌ ┐ └ ┘` is a one-line change if PuTTY users report boxes. |
| Mascot art | `█ ▀ ▄ ▌ ▐ ░ ▒ ▓` | Existing block art stays as is. |

**must not use:** emoji (including any character followed by U+FE0F) and `✓ ✔ ✗ ⚠ ℹ`. Tested.

## Box drawing

- Panels: Rich's rounded box, border in `primary`, title on the **left**.
- Tables: Rich's rounded box with column lines, border in `primary`, a line under the headings.
- Dialogs inside Textual widgets may use square corners `┌ ┐ └ ┘`, as drawn in the alias picker spec.

## Messages

| Message type | Shape | Rules |
|---|---|---|
| Status (success, note, warning, error) | One plain line | Symbol + word + colon in the role colour, bold. Message in plain text, sentence case, ends with a full stop. At most two follow-up lines, indented 2 spaces. |
| Follow-up hint | Indented line | Lead-in in `muted` ("Try …", "To see them:"), then the exact command in `command` bold. Written for where the user is. |
| Progress | Spinner line | Present tense with an ellipsis ("Building module for …"). Replaced by the result when done; never left on screen. |
| Result (tool info, build complete) | Panel | Title on the left names the result. Labels in a 12-cell column, `primary` bold. Blank line inside the top and bottom edges. Ends with what to do next. |
| Greeting | Panel, once per session | Mascot art and ★ ☆ stars as today; version on the right. The only exclamation mark in a session. |

Status line anatomy (Rich markup):

```
[status.success]√ Done:[/] Module built for star.
[status.info]i Note:[/] Running with elevated privileges.
[status.warning]! Warning:[/] No version given, so building the latest.
[status.error]× Error:[/] No tool or container matches "lsdkfjsldkfj".
  [muted]Try searching by what it does:[/]  [hint.command]search quality control[/]
```

Follow-up lines line up two spaces in from the symbol.

## Tables

| Rule | Detail |
|---|---|
| Style | Rounded box with column lines, in `primary`. Headings `primary` bold, with a line under them. Row lines only when rows wrap onto two lines. One space of padding inside each cell. |
| Title | Above the box, on the left: bold `primary` title, then `muted` facts separated by ` · `. |
| Fit 80 columns | Borders and padding cost 3 columns per column plus 1. Plan widths to total 80 or less; lift shared prefixes out (a `Location` line) before shortening anything. |
| Shortening | Only the last column may be shortened, with `…` at the end. Version strings are never shortened. |
| Cell colours | Versions `version`, paths and image names `path`, commands `command`, dates and sizes `muted`. |
| Yes / no | Words: "yes" `primary` bold, "no" `muted`. |
| Length | Print everything (containers top out around 40 rows). No Next / Exit paging. |
| End line | One "To … :" line under the box with the next command, when there is an obvious next step. |
| Lists of versions | Don't print partial lists inside messages ("… and 21 more"); give the count and the command that lists them. |

## Pickers (Textual widgets)

Every time shelley needs a choice it uses a small inline Textual picker with the same layout, keys and words.

| Rule | Detail |
|---|---|
| When | When the user must choose, or to browse a long list. Short reference output is printed instead. Never Next / Exit paging. |
| Layout | Title bar (task — tool version), one or two lines of plain instructions, the list, a footer line (count · scroll position), buttons on the right, key bar at the bottom. Same order in every picker. |
| Height | Content height, up to terminal height minus 1. Short lists make short widgets. |
| Primary button | A specific verb (Install, Confirm), `primary` green, left of Cancel. Greyed with a visible reason when unavailable. |
| Cancel | Neutral grey, never a warning colour. |
| State without colour | `[x]` ticked, `›` highlighted row, `› Label ‹` focused button, reverse video plus a mode word in the key bar for an open text field. |
| After the picker | The widget clears and a status line (and, where useful, a table) reports what happened. |

One key vocabulary for every picker:

| Key | Word in the key bar | Meaning |
|---|---|---|
| ↑ ↓ | Move | Move the highlight. PgUp / PgDn and Home / End where lists scroll. |
| Enter | the primary button's verb | Do the main action. The key-bar word matches the green button's label. |
| Space | Tick | Only where several items can be chosen. |
| R / F2 | Rename | Only where names can be changed. |
| Tab | Buttons | Move focus between the list and the buttons. |
| Esc | Cancel or Exit | Closes the innermost thing first. Asks "Discard and exit?" only when ticks or renames would be lost; otherwise exits straight away. |
| Ctrl+C | (not shown) | Exits at once, no dialog. |

## Voice and copy

- Say what happened, then what to do: "No tool or container matches …" then "Try searching by what it does".
- Quote the user's own input in straight double quotes, exactly as typed.
- Name versions in full once (`2.7.11b--h5ca1c30_8`); afterwards the short form (`2.7.11b`) is fine.
- Numbers as digits. No "successfully", "simply" or "just".
- Friendly in the greeting, plain everywhere else. Errors never blame ("Invalid input!") and never apologise at length.
- Hints are written for where the user is: inside interactive mode without the `shelley` prefix, in the shell with it.

## Terminal support and checks

- Target terminals: PuTTY (default font Courier New), Windows Terminal (Consolas / Cascadia), tmux, VS Code over SSH.
- Before release: check `√` and `×` render in Courier New and Consolas.
- tmux often does not pass 24-bit colour through, so it rounds colours to its 256-colour palette. Until fallbacks
  exist, check that `primary`, `warning` and `error` stay distinguishable there.

## Not yet (roadmap)

- **Now:** Rich output adopts the colour roles and adjusted shades; plain status symbols replace emoji; all tables
  use the rounded bordered style at 80 columns; panels for results only; the alias picker uses the BioCommons theme.
- **Next:** questionary prompts ("Select one to install", Next / Exit paging) replaced by Textual pickers;
  `find -v` opens in a scrollable Textual view.
- **Later, low priority:** tested 256- and 16-colour fallbacks for tmux and PuTTY.