# Style guide example screens

Transcribed from the design canvas "shelley style guide (BioCommons)". Every frame is 80 columns.

Notation: colours and weights are written as **Rich markup using the role names** from [`style-guide.md`](style-guide.md),
e.g. `[status.error]× Error:[/]`. Rich can't combine a theme style with another attribute in one tag (`[error bold]` renders
unstyled), so the bold variants are theme styles of their own: `status.*`, `heading`, `label`, `prompt`,
`hint.command` and `yes`.
This is exactly how the output should be produced in code: use the role
names as Rich theme styles, never hex values. Text with no markup uses the terminal's own foreground colour.
Literal `[ ]` and `[x]` are tick boxes, not markup.

## Messages and result panels

### Tool not found. One status line, then what to try. Commands are written for the shelley> prompt because that's where the user is.
```
[prompt]shelley>[/] find lsdkfjsldkfj
[status.error]× Error:[/] No tool or container matches "lsdkfjsldkfj".
  [muted]Try searching by what it does:[/]  [hint.command]search <description>[/]
  [muted]For example:[/]  [hint.command]search quality control[/]

[prompt]shelley>[/]
```

### Greeting (once per interactive session). Mascot, stars and friendly line kept as today. Followed by the help table (Tables board).
```
[muted]$[/] shelley interactive
[primary]╭[/][primary]──────────────────────────────────────────────────────────────────────────────[/][primary]╮[/]
[primary]│[/]     [info]★         ☆            ★              ☆      ★                ☆     ★[/]    [primary]│[/]
[primary]│[/]        [info]☆            ★               ☆                  ★[/]                     [primary]│[/]
[primary]│[/]        [muted][ Shelley mascot block art, unchanged ]                    ★[/]          [primary]│[/]
[primary]│[/]  [info]──────────────────────────────────────────────────────────────────────────[/]  [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  [label]Hey there, I'm Shelley!                                            v0.5.0[/]   [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]╰[/][primary]──────────────────────────────────────────────────────────────────────────────[/][primary]╯[/]
```

### Build with no version given. A warning line replaces today's 20-row panel. Instead of listing 10 of 31 versions, it points to the command that lists them all.
```
[prompt]shelley>[/] build star
[status.warning]! Warning:[/] No version given, so building the latest: [version]2.7.11b--h5ca1c30_8[/]
  [muted]31 versions available. To see them:[/]  [hint.command]find star -v[/]
  [muted]To build a different one:[/]  [hint.command]build star/<version>[/]
[status.info]i Note:[/] Running with elevated privileges.
[primary]-[/] Building module for star [version]2.7.11b--h5ca1c30_8[/]…
```

### Build complete (result panel). Replaces the spinner line when the build finishes. Labels in a fixed 12-cell column; what to type next in the command colour.
```
[primary]╭[/][primary]─ Build complete ─────────────────────────────────────────────────────────────[/][primary]╮[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  [status.success]√ Module built[/]                                                              [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  [label]Tool[/]      [primary]star[/]                                                              [primary]│[/]
[primary]│[/]  [label]Version[/]   [version]2.7.11b--h5ca1c30_8[/]                                               [primary]│[/]
[primary]│[/]  [label]Module[/]    [path]/apps/Modules/modulefiles/star/2.7.11b--h5ca1c30_8.lua[/]            [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  [muted]To load it[/]    [hint.command]module load star/2.7.11b--h5ca1c30_8[/]                          [primary]│[/]
[primary]│[/]  [muted]To list all[/]   [hint.command]module avail[/]                                                  [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]╰[/][primary]──────────────────────────────────────────────────────────────────────────────[/][primary]╯[/]

[prompt]shelley>[/]
```

### Tool information (result panel). Description capped at 3 lines; labels in a 12-cell column; a Builds line tells people where to go next.
```
[prompt]shelley>[/] find fastqc
[primary]╭[/][primary]─ FastQC ─────────────────────────────────────────────────────────────────────[/][primary]╮[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  This tool aims to provide a QC report which can spot problems or biases     [primary]│[/]
[primary]│[/]  which originate either in the sequencer or in the starting library          [primary]│[/]
[primary]│[/]  material. It can be run in one of two modes. …                              [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  [label]Homepage[/]  [path]http://www.bioinformatics.babraham.ac.uk/projects/fastqc/[/]         [primary]│[/]
[primary]│[/]  [label]Operations[/]Sequence composition calculation,                                 [primary]│[/]
[primary]│[/]            Sequencing quality control, Statistical calculation               [primary]│[/]
[primary]│[/]  [label]Inputs[/]    Raw sequence, BAM, FASTQ, FASTQ-like format (text), SAM           [primary]│[/]
[primary]│[/]  [label]Outputs[/]   Sequence report, HTML                                             [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]│[/]  [label]Builds[/]    27 available [muted]· to list them:[/] [hint.command]find fastqc -v[/]                       [primary]│[/]
[primary]│[/]                                                                              [primary]│[/]
[primary]╰[/][primary]──────────────────────────────────────────────────────────────────────────────[/][primary]╯[/]
```

### Status line anatomy. The same four shapes everywhere, including inside the alias picker's message area later.
```
[status.success]√ Done:[/] Module built for star.
[status.info]i Note:[/] Running with elevated privileges.
[status.warning]! Warning:[/] No version given, so building the latest.
[status.error]× Error:[/] No tool or container matches "lsdkfjsldkfj".
  [muted]Try …[/]  [hint.command]command to type[/]
```

## Tables

### Help (after the greeting). Two columns instead of three: each example sits under its description, so the build command fits. Row lines kept because rows are two lines tall.
```
[heading]Available commands[/]
[primary]╭[/][primary]─────────────────────────────[/][primary]┬[/][primary]────────────────────────────────────────────────[/][primary]╮[/]
[primary]│[/] [heading]Command[/]                     [primary]│[/] [heading]What it does[/]                                   [primary]│[/]
[primary]├[/][primary]─────────────────────────────[/][primary]┼[/][primary]────────────────────────────────────────────────[/][primary]┤[/]
[primary]│[/] [hint.command]find <tool> [-v][/]            [primary]│[/] Find a tool. -v also lists container paths.    [primary]│[/]
[primary]│[/]                             [primary]│[/] [muted]e.g.[/] [command]find fastqc[/]                               [primary]│[/]
[primary]├[/][primary]─────────────────────────────[/][primary]┼[/][primary]────────────────────────────────────────────────[/][primary]┤[/]
[primary]│[/] [hint.command]search <description>[/]        [primary]│[/] Search for tools by what they do.              [primary]│[/]
[primary]│[/]                             [primary]│[/] [muted]e.g.[/] [command]search quality control[/]                    [primary]│[/]
[primary]├[/][primary]─────────────────────────────[/][primary]┼[/][primary]────────────────────────────────────────────────[/][primary]┤[/]
[primary]│[/] [hint.command]build <tool[/version]> [-i][/] [primary]│[/] Build an Lmod module. -i to choose aliases.    [primary]│[/]
[primary]│[/]                             [primary]│[/] [muted]e.g.[/] [command]build samtools/1.21[/]                       [primary]│[/]
[primary]├[/][primary]─────────────────────────────[/][primary]┼[/][primary]────────────────────────────────────────────────[/][primary]┤[/]
[primary]│[/] [hint.command]help[/]                        [primary]│[/] Show this table.                               [primary]│[/]
[primary]├[/][primary]─────────────────────────────[/][primary]┼[/][primary]────────────────────────────────────────────────[/][primary]┤[/]
[primary]│[/] [hint.command]exit[/]                        [primary]│[/] Leave interactive mode.                        [primary]│[/]
[primary]╰[/][primary]─────────────────────────────[/][primary]┴[/][primary]────────────────────────────────────────────────[/][primary]╯[/]

[prompt]shelley>[/]
```

### Printed alias summary (after Confirm in the picker). Follows this guide. Colour drops away when piped to a log; the box stays readable.
```
[status.success]√ Done:[/] Aliases chosen for samtools 1.21: 5 of 27
[primary]╭[/][primary]───────────[/][primary]┬[/][primary]───────────────────────────────────────────────────────[/][primary]╮[/]
[primary]│[/] [heading]Alias[/]     [primary]│[/] [heading]Command[/]                                               [primary]│[/]
[primary]├[/][primary]───────────[/][primary]┼[/][primary]───────────────────────────────────────────────────────[/][primary]┤[/]
[primary]│[/] [hint.command]bgzip[/]     [primary]│[/] [path]/usr/local/bin/bgzip[/]                                  [primary]│[/]
[primary]│[/] [hint.command]htsfile[/]   [primary]│[/] [path]/usr/local/bin/htsfile[/]                                [primary]│[/]
[primary]│[/] [hint.command]sam2vcf[/]   [primary]│[/] [path]/usr/local/bin/sam2vcf.pl[/]  [muted](renamed from sam2vcf.pl)[/]  [primary]│[/]
[primary]│[/] [hint.command]samtools[/]  [primary]│[/] [path]/usr/local/bin/samtools[/]                               [primary]│[/]
[primary]│[/] [hint.command]tabix[/]     [primary]│[/] [path]/usr/local/bin/tabix[/]                                  [primary]│[/]
[primary]╰[/][primary]───────────[/][primary]┴[/][primary]───────────────────────────────────────────────────────[/][primary]╯[/]
  [muted]To add or change aliases, run the build again:[/]  [hint.command]build samtools/1.21 -i[/]
```

### Builds of a tool (find fastqc -v), printed today. The bordered table is back, 75 columns wide. The container folder is printed once above it, so each row shows only the image name. Printed in full with no paging; later this opens in a scrollable Textual view (Prompts board). Frame cut after 10 of 27 rows.
```
[prompt]shelley>[/] find fastqc -v
[muted][tool information panel, as on the Messages board][/]

[heading]Builds of FastQC[/] [muted]· 27 · highest version first[/]
[muted]Location[/]  [path]/cvmfs/singularity.galaxyproject.org/all/[/]
[primary]╭[/][primary]────────────────────[/][primary]┬[/][primary]────────────[/][primary]┬[/][primary]───────────[/][primary]┬[/][primary]───────────────────────────[/][primary]╮[/]
[primary]│[/] [heading]Version[/]            [primary]│[/] [heading]Date[/]       [primary]│[/] [heading]Installed[/] [primary]│[/] [heading]Image[/]                     [primary]│[/]
[primary]├[/][primary]────────────────────[/][primary]┼[/][primary]────────────[/][primary]┼[/][primary]───────────[/][primary]┼[/][primary]───────────────────────────[/][primary]┤[/]
[primary]│[/] [version]0.12.1--hdfd78af_0[/] [primary]│[/] [muted]2023-03-04[/] [primary]│[/] [yes]yes[/]       [primary]│[/] [path]fastqc:0.12.1--hdfd78af_0[/] [primary]│[/]
[primary]│[/] [version]0.11.9--hdfd78af_1[/] [primary]│[/] [muted]2021-03-25[/] [primary]│[/] [yes]yes[/]       [primary]│[/] [path]fastqc:0.11.9--hdfd78af_1[/] [primary]│[/]
[primary]│[/] [version]0.11.9--0[/]          [primary]│[/] [muted]2020-01-25[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.9--0[/]          [primary]│[/]
[primary]│[/] [version]0.11.8--2[/]          [primary]│[/] [muted]2019-10-27[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.8--2[/]          [primary]│[/]
[primary]│[/] [version]0.11.8--1[/]          [primary]│[/] [muted]2019-08-15[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.8--1[/]          [primary]│[/]
[primary]│[/] [version]0.11.8--0[/]          [primary]│[/] [muted]2019-09-02[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.8--0[/]          [primary]│[/]
[primary]│[/] [version]0.11.7--hdfd78af_7[/] [primary]│[/] [muted]2021-03-25[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.7--hdfd78af_7[/] [primary]│[/]
[primary]│[/] [version]0.11.7--pl5.22.0_2[/] [primary]│[/] [muted]2019-08-15[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.7--pl5.22.0_2[/] [primary]│[/]
[primary]│[/] [version]0.11.7--pl5.22.0_1[/] [primary]│[/] [muted]2019-09-02[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.7--pl5.22.0_1[/] [primary]│[/]
[primary]│[/] [version]0.11.7--pl5.22.0_0[/] [primary]│[/] [muted]2019-09-02[/] [primary]│[/] [no]no[/]        [primary]│[/] [path]fastqc:0.11.7--pl5.22.0_0[/] [primary]│[/]
[primary]│[/] [muted]⋮ 17 more rows[/]     [primary]│[/]            [primary]│[/]           [primary]│[/]                           [primary]│[/]
[primary]╰[/][primary]────────────────────[/][primary]┴[/][primary]────────────[/][primary]┴[/][primary]───────────[/][primary]┴[/][primary]───────────────────────────[/][primary]╯[/]
[muted]To build one:[/]  [hint.command]build fastqc/<version>[/]
```

## Pickers

The alias picker in the BioCommons theme is **in scope now** (it was drawn as "later" on the canvas; that changed on 6 November). The other two pickers are **later** and are not part of the current work; they are here so future pickers stay consistent.

### The alias picker in the BioCommons theme (in scope now). Same layout, keys and copy as [`alias-picker.md`](alias-picker.md). Highlighted row in Dark Blue with white text; Confirm in brand green; Cancel neutral.
```
[muted]$[/] shelley build samtools/1.21 -i
 Choose aliases — samtools 1.21                                   shelley build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
     [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [x]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    blast2sam.pl            /usr/local/bin/blast2sam.pl               █
     [ ]    bowtie2sam.pl           /usr/local/bin/bowtie2sam.pl              █
     [ ]    export2sam.pl           /usr/local/bin/export2sam.pl              [muted]│[/]
     [ ]    fasta-sanitize.pl       /usr/local/bin/fasta-sanitize.pl          [muted]│[/]
 ›   [x]    htsfile                 /usr/local/bin/htsfile                    │
     [ ]    interpolate_sam.pl      /usr/local/bin/interpolate_sam.pl         [muted]│[/]
     [ ]    libdeflate-gunzip       /usr/local/bin/libdeflate-gunzip          [muted]│[/]
     [ ]    libdeflate-gzip         /usr/local/bin/libdeflate-gzip            [muted]│[/]
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               [muted]│[/]
   2 of 27 ticked                                              [muted]▼ 16 more below[/]  


                                                   Confirm        Cancel


 [bold]↑↓[/] Move   [bold]Space[/] Tick   [bold]R[/] Rename   [bold]Enter[/] Confirm   [bold]Tab[/] Buttons   [bold]Esc[/] Exit
```

### (Later) Choose one build. Replaces questionary's "Select one to install" list. The widget is only as tall as it needs to be (15 rows here); Esc cancels straight away because nothing would be lost.
```
[prompt]shelley>[/] build fastqc/0.11.8
 Choose a build — fastqc 0.11.8                                   shelley build 
 3 builds match this version. Click one, or use ↑↓, then Install.

   Build                   Size        Modified
 › 0.11.8--2               253.5 MB    2019-10-27
   0.11.8--1               259.1 MB    2019-08-15
   0.11.8--0               147.2 MB    2019-09-02
   [muted]Highest build number first[/]                                      [muted]All 3 shown[/]  


                                                   Install        Cancel


 [bold]↑↓[/] Move   [bold]Enter[/] Install   [bold]Tab[/] Buttons   [bold]Esc[/] Cancel
```

### (Later) Browse builds (find fastqc -v, later). Replaces both the printed table and the old Next / Exit paging with one scrollable list. Read-only by default; Enter offers the obvious next step, building the highlighted version.
```
[prompt]shelley>[/] find fastqc -v
 Builds of FastQC — 27                                             shelley find 
 Images in /cvmfs/singularity.galaxyproject.org/all/
 Scroll to browse. Enter builds the highlighted version.

   Version               Date        Installed  Image
 › 0.12.1--hdfd78af_0    2023-03-04  [yes]yes[/]        fastqc:0.12.1--hdfd78af_0
   0.11.9--hdfd78af_1    [muted]2021-03-25[/]  [yes]yes[/]        fastqc:0.11.9--hdfd78af_1
   0.11.9--0             [muted]2020-01-25[/]  [no]no[/]         fastqc:0.11.9--0
   0.11.8--2             [muted]2019-10-27[/]  [no]no[/]         fastqc:0.11.8--2
   0.11.8--1             [muted]2019-08-15[/]  [no]no[/]         fastqc:0.11.8--1
   0.11.8--0             [muted]2019-09-02[/]  [no]no[/]         fastqc:0.11.8--0
   0.11.7--hdfd78af_7    [muted]2021-03-25[/]  [no]no[/]         fastqc:0.11.7--hdfd78af_7
   0.11.7--pl5.22.0_2    [muted]2019-08-15[/]  [no]no[/]         fastqc:0.11.7--pl5.22.0_2
   0.11.7--pl5.22.0_1    [muted]2019-09-02[/]  [no]no[/]         fastqc:0.11.7--pl5.22.0_1
   0.11.7--pl5.22.0_0    [muted]2019-09-02[/]  [no]no[/]         fastqc:0.11.7--pl5.22.0_0
   [muted]Highest version first[/]                                       [muted]▼ 17 more below[/]  


                                                   Build          Close


 [bold]↑↓[/] Move   [bold]PgUp PgDn[/] Page   [bold]Enter[/] Build   [bold]Tab[/] Buttons   [bold]Esc[/] Close
```
