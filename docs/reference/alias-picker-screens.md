# Alias picker screens (plain text)

Transcribed from the design canvas "shelley-bio alias picker redesign". Each block is one terminal frame,
cell-accurate: row 1 is the shell command that launched the build; the widget uses the remaining rows.
Colour is not shown here; the colour of every element is in `alias-picker.md` (section "Colours").

Notes on reading these frames:
- `█` is the scrollbar thumb and `│` its track. When everything fits there is no scrollbar.
- Frame 5 shows the dialog over the list; on screen the list behind it is dimmed.
- In frame 3, `bowtie2sam█` is the text field with a block cursor, drawn in reverse video.
- Container contents (samtools 1.21, 27 commands; bedtools 2.31.1, 38 commands) are realistic examples, not fixtures from the code.
- The command shown (`shelley-bio build samtools`) is a placeholder (spec assumption A9); take the real form from the CLI.

## 80×24 (the minimum size)

### 1 · Initial. Nothing ticked. Confirm is greyed out and the reason sits right beside it. The highlight (›) starts on the first row; the footer says how many rows are below.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                               shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
 ›   [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [ ]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    blast2sam.pl            /usr/local/bin/blast2sam.pl               █
     [ ]    bowtie2sam.pl           /usr/local/bin/bowtie2sam.pl              █
     [ ]    export2sam.pl           /usr/local/bin/export2sam.pl              │
     [ ]    fasta-sanitize.pl       /usr/local/bin/fasta-sanitize.pl          │
     [ ]    htsfile                 /usr/local/bin/htsfile                    │
     [ ]    interpolate_sam.pl      /usr/local/bin/interpolate_sam.pl         │
     [ ]    libdeflate-gunzip       /usr/local/bin/libdeflate-gunzip          │
     [ ]    libdeflate-gzip         /usr/local/bin/libdeflate-gzip            │
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               │
   0 of 27 ticked                                              ▼ 16 more below  


   Tick at least one alias to confirm                 Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 2 · Some rows ticked. [x] marks each choice without colour. The count updates under the list. Confirm turns green and its reason disappears.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                               shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
     [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [x]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    blast2sam.pl            /usr/local/bin/blast2sam.pl               █
     [ ]    bowtie2sam.pl           /usr/local/bin/bowtie2sam.pl              █
     [ ]    export2sam.pl           /usr/local/bin/export2sam.pl              │
     [ ]    fasta-sanitize.pl       /usr/local/bin/fasta-sanitize.pl          │
 ›   [x]    htsfile                 /usr/local/bin/htsfile                    │
     [ ]    interpolate_sam.pl      /usr/local/bin/interpolate_sam.pl         │
     [ ]    libdeflate-gunzip       /usr/local/bin/libdeflate-gunzip          │
     [ ]    libdeflate-gzip         /usr/local/bin/libdeflate-gzip            │
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               │
   2 of 27 ticked                                              ▼ 16 more below  


                                                      Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 3 · Rename in progress. Clicking the name (or R) turns that cell into a field in place: reverse video plus a block cursor. The row does not move. The key bar switches to rename keys.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                               shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
     [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [x]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    blast2sam.pl            /usr/local/bin/blast2sam.pl               █
 ›   [ ]    bowtie2sam█             /usr/local/bin/bowtie2sam.pl              █
     [ ]    export2sam.pl           /usr/local/bin/export2sam.pl              │
     [ ]    fasta-sanitize.pl       /usr/local/bin/fasta-sanitize.pl          │
     [x]    htsfile                 /usr/local/bin/htsfile                    │
     [ ]    interpolate_sam.pl      /usr/local/bin/interpolate_sam.pl         │
     [ ]    libdeflate-gunzip       /usr/local/bin/libdeflate-gunzip          │
     [ ]    libdeflate-gzip         /usr/local/bin/libdeflate-gzip            │
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               │
   2 of 27 ticked                                              ▼ 16 more below  


                                                      Confirm        Cancel


 Renaming Enter Save new name   Esc Keep old name   ←→ Move in name
```

### 4 · After Esc cancels the rename. The original name is back, the highlight stays on the same row, and a short note under the list confirms nothing changed. The normal key bar returns.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                               shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
     [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [x]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    blast2sam.pl            /usr/local/bin/blast2sam.pl               █
 ›   [ ]    bowtie2sam.pl           /usr/local/bin/bowtie2sam.pl              █
     [ ]    export2sam.pl           /usr/local/bin/export2sam.pl              │
     [ ]    fasta-sanitize.pl       /usr/local/bin/fasta-sanitize.pl          │
     [x]    htsfile                 /usr/local/bin/htsfile                    │
     [ ]    interpolate_sam.pl      /usr/local/bin/interpolate_sam.pl         │
     [ ]    libdeflate-gunzip       /usr/local/bin/libdeflate-gunzip          │
     [ ]    libdeflate-gzip         /usr/local/bin/libdeflate-gzip            │
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               │
   2 of 27 ticked   Rename cancelled. Kept bowtie2sam.pl.      ▼ 16 more below  


                                                      Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 5 · "Discard and exit?" Opened by Esc on the list or by Cancel. Keep editing is focused (› ‹), so a second Esc or a reflex Enter is safe. The screen behind is dimmed.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                               shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
     [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [x]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    bla┌────────────────────────────────────────────────┐             █
     [ ]    bow│ Discard and exit?                              │             █
     [ ]    exp│                                                │             │
     [ ]    fas│ Nothing will be built, and your ticks and      │.pl          │
 ›   [x]    hts│ renames will be lost.                          │             │
     [ ]    int│                                                │m.pl         │
     [ ]    lib│     › Keep editing ‹     Discard and exit      │zip          │
     [ ]    lib└────────────────────────────────────────────────┘p            │
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               │
   2 of 27 ticked                                              ▼ 16 more below  


                                                      Confirm        Cancel


 Enter Choose   ←→ Switch button   Esc Keep editing
```

### 6 · Long list, scrolled partway. bedtools, 38 commands (near the largest containers in use). Words say what is above and below; the thumb is a second cue. The count includes the tick on bedtools, which is scrolled out of view.
```
$ shelley-bio build bedtools
 Choose aliases — bedtools 2.31.1                             shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name              Command
     [ ]    coverageBed             /usr/local/bin/coverageBed                │
     [ ]    expandCols              /usr/local/bin/expandCols                 │
     [ ]    fastaFromBed            /usr/local/bin/fastaFromBed               │
     [ ]    flankBed                /usr/local/bin/flankBed                   █
     [ ]    genomeCoverageBed       /usr/local/bin/genomeCoverageBed          █
     [ ]    getOverlap              /usr/local/bin/getOverlap                 █
     [ ]    groupBy                 /usr/local/bin/groupBy                    │
     [x]    intersectBed            /usr/local/bin/intersectBed               │
     [ ]    linksBed                /usr/local/bin/linksBed                   │
     [ ]    mapBed                  /usr/local/bin/mapBed                     │
 ›   [ ]    maskFastaFromBed        /usr/local/bin/maskFastaFromBed           │
   2 of 38 ticked                            ▲ 11 more above · ▼ 16 more below  


                                                      Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 7 · No-mouse mode. Instructions name keys instead of clicks, and the title bar says why clicks won't work. Tab has moved focus to Confirm (› ‹); the list highlight dims but keeps its ›.
```
$ shelley-bio build samtools --no-mouse
 Choose aliases — samtools 1.21                                   Keyboard only 
 Press Space to tick the aliases you'll use. You can rebuild later to add more.
 Press R to rename the highlighted alias. The Command column needs no action.

   Include  Alias name              Command
     [ ]    ace2sam                 /usr/local/bin/ace2sam                    █
     [x]    bgzip                   /usr/local/bin/bgzip                      █
     [ ]    blast2sam.pl            /usr/local/bin/blast2sam.pl               █
     [ ]    bowtie2sam.pl           /usr/local/bin/bowtie2sam.pl              █
     [ ]    export2sam.pl           /usr/local/bin/export2sam.pl              │
     [ ]    fasta-sanitize.pl       /usr/local/bin/fasta-sanitize.pl          │
 ›   [x]    htsfile                 /usr/local/bin/htsfile                    │
     [ ]    interpolate_sam.pl      /usr/local/bin/interpolate_sam.pl         │
     [ ]    libdeflate-gunzip       /usr/local/bin/libdeflate-gunzip          │
     [ ]    libdeflate-gzip         /usr/local/bin/libdeflate-gzip            │
     [ ]    maq2sam-long            /usr/local/bin/maq2sam-long               │
   2 of 27 ticked                                              ▼ 16 more below  


                                                    › Confirm ‹      Cancel


 ←→ Switch button   Enter Press button   Shift+Tab Back to list   Esc Exit
```

### 8 · After Confirm
Superseded. The canvas showed a plain-text summary here; the style guide replaced it with a status line plus a rounded table. See "Printed alias summary" in [`style-guide-screens.md`](style-guide-screens.md).

## 120×40

### 1 · Initial. Nothing ticked; Confirm greyed with its reason beside it; highlight on the first row.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                                                                       shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name                    Command
 ›   [ ]    ace2sam                       /usr/local/bin/ace2sam
     [ ]    bgzip                         /usr/local/bin/bgzip
     [ ]    blast2sam.pl                  /usr/local/bin/blast2sam.pl
     [ ]    bowtie2sam.pl                 /usr/local/bin/bowtie2sam.pl
     [ ]    export2sam.pl                 /usr/local/bin/export2sam.pl
     [ ]    fasta-sanitize.pl             /usr/local/bin/fasta-sanitize.pl
     [ ]    htsfile                       /usr/local/bin/htsfile
     [ ]    interpolate_sam.pl            /usr/local/bin/interpolate_sam.pl
     [ ]    libdeflate-gunzip             /usr/local/bin/libdeflate-gunzip
     [ ]    libdeflate-gzip               /usr/local/bin/libdeflate-gzip
     [ ]    maq2sam-long                  /usr/local/bin/maq2sam-long
     [ ]    maq2sam-short                 /usr/local/bin/maq2sam-short
     [ ]    md5fa                         /usr/local/bin/md5fa
     [ ]    md5sum-lite                   /usr/local/bin/md5sum-lite
     [ ]    novo2sam.pl                   /usr/local/bin/novo2sam.pl
     [ ]    plot-ampliconstats            /usr/local/bin/plot-ampliconstats
     [ ]    plot-bamstats                 /usr/local/bin/plot-bamstats
     [ ]    psl2sam.pl                    /usr/local/bin/psl2sam.pl
     [ ]    sam2vcf.pl                    /usr/local/bin/sam2vcf.pl
     [ ]    samtools                      /usr/local/bin/samtools
     [ ]    samtools.pl                   /usr/local/bin/samtools.pl
     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl
     [ ]    soap2sam.pl                   /usr/local/bin/soap2sam.pl
     [ ]    tabix                         /usr/local/bin/tabix
     [ ]    wgsim                         /usr/local/bin/wgsim
     [ ]    wgsim_eval.pl                 /usr/local/bin/wgsim_eval.pl
     [ ]    zoom2sam.pl                   /usr/local/bin/zoom2sam.pl
   0 of 27 ticked                                                                                         All 27 shown  


   Tick at least one alias to confirm                                                         Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 2 · Some rows ticked. Four ticked, each shown as [x]; the count reads "4 of 27 ticked"; Confirm is available.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                                                                       shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name                    Command
     [ ]    ace2sam                       /usr/local/bin/ace2sam
     [x]    bgzip                         /usr/local/bin/bgzip
     [ ]    blast2sam.pl                  /usr/local/bin/blast2sam.pl
     [ ]    bowtie2sam.pl                 /usr/local/bin/bowtie2sam.pl
     [ ]    export2sam.pl                 /usr/local/bin/export2sam.pl
     [ ]    fasta-sanitize.pl             /usr/local/bin/fasta-sanitize.pl
     [x]    htsfile                       /usr/local/bin/htsfile
     [ ]    interpolate_sam.pl            /usr/local/bin/interpolate_sam.pl
     [ ]    libdeflate-gunzip             /usr/local/bin/libdeflate-gunzip
     [ ]    libdeflate-gzip               /usr/local/bin/libdeflate-gzip
     [ ]    maq2sam-long                  /usr/local/bin/maq2sam-long
     [ ]    maq2sam-short                 /usr/local/bin/maq2sam-short
     [ ]    md5fa                         /usr/local/bin/md5fa
     [ ]    md5sum-lite                   /usr/local/bin/md5sum-lite
     [ ]    novo2sam.pl                   /usr/local/bin/novo2sam.pl
     [ ]    plot-ampliconstats            /usr/local/bin/plot-ampliconstats
     [ ]    plot-bamstats                 /usr/local/bin/plot-bamstats
     [ ]    psl2sam.pl                    /usr/local/bin/psl2sam.pl
     [ ]    sam2vcf.pl                    /usr/local/bin/sam2vcf.pl
     [x]    samtools                      /usr/local/bin/samtools
     [ ]    samtools.pl                   /usr/local/bin/samtools.pl
     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl
     [ ]    soap2sam.pl                   /usr/local/bin/soap2sam.pl
 ›   [x]    tabix                         /usr/local/bin/tabix
     [ ]    wgsim                         /usr/local/bin/wgsim
     [ ]    wgsim_eval.pl                 /usr/local/bin/wgsim_eval.pl
     [ ]    zoom2sam.pl                   /usr/local/bin/zoom2sam.pl
   4 of 27 ticked                                                                                         All 27 shown  


                                                                                              Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 3 · Rename in progress. The name cell becomes a 28-cell field in place; the row stays put. The key bar shows only the keys that work now.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                                                                       shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name                    Command
     [ ]    ace2sam                       /usr/local/bin/ace2sam
     [x]    bgzip                         /usr/local/bin/bgzip
     [ ]    blast2sam.pl                  /usr/local/bin/blast2sam.pl
 ›   [ ]    bowtie2sam█                   /usr/local/bin/bowtie2sam.pl
     [ ]    export2sam.pl                 /usr/local/bin/export2sam.pl
     [ ]    fasta-sanitize.pl             /usr/local/bin/fasta-sanitize.pl
     [x]    htsfile                       /usr/local/bin/htsfile
     [ ]    interpolate_sam.pl            /usr/local/bin/interpolate_sam.pl
     [ ]    libdeflate-gunzip             /usr/local/bin/libdeflate-gunzip
     [ ]    libdeflate-gzip               /usr/local/bin/libdeflate-gzip
     [ ]    maq2sam-long                  /usr/local/bin/maq2sam-long
     [ ]    maq2sam-short                 /usr/local/bin/maq2sam-short
     [ ]    md5fa                         /usr/local/bin/md5fa
     [ ]    md5sum-lite                   /usr/local/bin/md5sum-lite
     [ ]    novo2sam.pl                   /usr/local/bin/novo2sam.pl
     [ ]    plot-ampliconstats            /usr/local/bin/plot-ampliconstats
     [ ]    plot-bamstats                 /usr/local/bin/plot-bamstats
     [ ]    psl2sam.pl                    /usr/local/bin/psl2sam.pl
     [ ]    sam2vcf.pl                    /usr/local/bin/sam2vcf.pl
     [x]    samtools                      /usr/local/bin/samtools
     [ ]    samtools.pl                   /usr/local/bin/samtools.pl
     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl
     [ ]    soap2sam.pl                   /usr/local/bin/soap2sam.pl
     [x]    tabix                         /usr/local/bin/tabix
     [ ]    wgsim                         /usr/local/bin/wgsim
     [ ]    wgsim_eval.pl                 /usr/local/bin/wgsim_eval.pl
     [ ]    zoom2sam.pl                   /usr/local/bin/zoom2sam.pl
   4 of 27 ticked                                                                                         All 27 shown  


                                                                                              Confirm        Cancel


 Renaming Enter Save new name   Esc Keep old name   ←→ Move in name   Home End Start or end of name
```

### 4 · After Esc cancels the rename. Original name restored, highlight unchanged, a note under the list confirms it. Tick state is untouched.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                                                                       shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name                    Command
     [ ]    ace2sam                       /usr/local/bin/ace2sam
     [x]    bgzip                         /usr/local/bin/bgzip
     [ ]    blast2sam.pl                  /usr/local/bin/blast2sam.pl
 ›   [ ]    bowtie2sam.pl                 /usr/local/bin/bowtie2sam.pl
     [ ]    export2sam.pl                 /usr/local/bin/export2sam.pl
     [ ]    fasta-sanitize.pl             /usr/local/bin/fasta-sanitize.pl
     [x]    htsfile                       /usr/local/bin/htsfile
     [ ]    interpolate_sam.pl            /usr/local/bin/interpolate_sam.pl
     [ ]    libdeflate-gunzip             /usr/local/bin/libdeflate-gunzip
     [ ]    libdeflate-gzip               /usr/local/bin/libdeflate-gzip
     [ ]    maq2sam-long                  /usr/local/bin/maq2sam-long
     [ ]    maq2sam-short                 /usr/local/bin/maq2sam-short
     [ ]    md5fa                         /usr/local/bin/md5fa
     [ ]    md5sum-lite                   /usr/local/bin/md5sum-lite
     [ ]    novo2sam.pl                   /usr/local/bin/novo2sam.pl
     [ ]    plot-ampliconstats            /usr/local/bin/plot-ampliconstats
     [ ]    plot-bamstats                 /usr/local/bin/plot-bamstats
     [ ]    psl2sam.pl                    /usr/local/bin/psl2sam.pl
     [ ]    sam2vcf.pl                    /usr/local/bin/sam2vcf.pl
     [x]    samtools                      /usr/local/bin/samtools
     [ ]    samtools.pl                   /usr/local/bin/samtools.pl
     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl
     [ ]    soap2sam.pl                   /usr/local/bin/soap2sam.pl
     [x]    tabix                         /usr/local/bin/tabix
     [ ]    wgsim                         /usr/local/bin/wgsim
     [ ]    wgsim_eval.pl                 /usr/local/bin/wgsim_eval.pl
     [ ]    zoom2sam.pl                   /usr/local/bin/zoom2sam.pl
   4 of 27 ticked   Rename cancelled. Kept bowtie2sam.pl.                                                 All 27 shown  


                                                                                              Confirm        Cancel


 ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 5 · "Discard and exit?" Centred over the list. Keep editing is focused by default; Esc also means Keep editing. The screen behind is dimmed.
```
$ shelley-bio build samtools
 Choose aliases — samtools 1.21                                                                       shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name                    Command
     [ ]    ace2sam                       /usr/local/bin/ace2sam
     [x]    bgzip                         /usr/local/bin/bgzip
     [ ]    blast2sam.pl                  /usr/local/bin/blast2sam.pl
     [ ]    bowtie2sam.pl                 /usr/local/bin/bowtie2sam.pl
     [ ]    export2sam.pl                 /usr/local/bin/export2sam.pl
     [ ]    fasta-sanitize.pl             /usr/local/bin/fasta-sanitize.pl
     [x]    htsfile                       /usr/local/bin/htsfile
     [ ]    interpolate_sam.pl            /usr/local/bin/interpolate_sam.pl
     [ ]    libdeflate-gunzip   ┌──────────────────────────────────────────────────────┐
     [ ]    libdeflate-gzip     │ Discard and exit?                                    │
     [ ]    maq2sam-long        │                                                      │
     [ ]    maq2sam-short       │ Nothing will be built, and your ticks and renames    │
     [ ]    md5fa               │ will be lost.                                        │
     [ ]    md5sum-lite         │                                                      │
     [ ]    novo2sam.pl         │           › Keep editing ‹     Discard and exit      │
     [ ]    plot-ampliconstats  └──────────────────────────────────────────────────────┘
     [ ]    plot-bamstats                 /usr/local/bin/plot-bamstats
     [ ]    psl2sam.pl                    /usr/local/bin/psl2sam.pl
     [ ]    sam2vcf.pl                    /usr/local/bin/sam2vcf.pl
     [x]    samtools                      /usr/local/bin/samtools
     [ ]    samtools.pl                   /usr/local/bin/samtools.pl
     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl
     [ ]    soap2sam.pl                   /usr/local/bin/soap2sam.pl
 ›   [x]    tabix                         /usr/local/bin/tabix
     [ ]    wgsim                         /usr/local/bin/wgsim
     [ ]    wgsim_eval.pl                 /usr/local/bin/wgsim_eval.pl
     [ ]    zoom2sam.pl                   /usr/local/bin/zoom2sam.pl
   4 of 27 ticked                                                                                         All 27 shown  


                                                                                              Confirm        Cancel


 Enter Choose   ←→ Switch button   Esc Keep editing
```

### 6 · Long list, scrolled partway. bedtools, rows 7–33 of 38. Footer words give the exact counts above and below; the scrollbar thumb gives the rough position.
```
$ shelley-bio build bedtools
 Choose aliases — bedtools 2.31.1                                                                     shelley-bio build 
 Click [ ] to tick the aliases you'll use. You can rebuild later to add more.
 Click a name to rename it. The Command column needs no action.

   Include  Alias name                    Command
     [ ]    bedToIgv                      /usr/local/bin/bedToIgv                                                     │
     [x]    bedtools                      /usr/local/bin/bedtools                                                     │
     [ ]    closestBed                    /usr/local/bin/closestBed                                                   │
     [ ]    clusterBed                    /usr/local/bin/clusterBed                                                   │
     [ ]    complementBed                 /usr/local/bin/complementBed                                                █
     [ ]    coverageBed                   /usr/local/bin/coverageBed                                                  █
     [ ]    expandCols                    /usr/local/bin/expandCols                                                   █
     [ ]    fastaFromBed                  /usr/local/bin/fastaFromBed                                                 █
     [ ]    flankBed                      /usr/local/bin/flankBed                                                     █
     [ ]    genomeCoverageBed             /usr/local/bin/genomeCoverageBed                                            █
     [ ]    getOverlap                    /usr/local/bin/getOverlap                                                   █
     [ ]    groupBy                       /usr/local/bin/groupBy                                                      █
     [x]    intersectBed                  /usr/local/bin/intersectBed                                                 █
     [ ]    linksBed                      /usr/local/bin/linksBed                                                     █
     [ ]    mapBed                        /usr/local/bin/mapBed                                                       █
     [ ]    maskFastaFromBed              /usr/local/bin/maskFastaFromBed                                             █
 ›   [x]    mergeBed                      /usr/local/bin/mergeBed                                                     █
     [ ]    multiBamCov                   /usr/local/bin/multiBamCov                                                  █
     [ ]    multiIntersectBed             /usr/local/bin/multiIntersectBed                                            █
     [ ]    nucBed                        /usr/local/bin/nucBed                                                       █
     [ ]    pairToBed                     /usr/local/bin/pairToBed                                                    █
     [ ]    pairToPair                    /usr/local/bin/pairToPair                                                   █
     [ ]    randomBed                     /usr/local/bin/randomBed                                                    █
     [ ]    shiftBed                      /usr/local/bin/shiftBed                                                     │
     [ ]    shuffleBed                    /usr/local/bin/shuffleBed                                                   │
     [ ]    slopBed                       /usr/local/bin/slopBed                                                      │
     [ ]    sortBed                       /usr/local/bin/sortBed                                                      │
   3 of 38 ticked                                                                      ▲ 6 more above · ▼ 5 more below  


                                                                                              Confirm        Cancel


 ↑↓ Move   PgUp PgDn Page   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit
```

### 7 · No-mouse mode. Key-based instructions and a "Keyboard only" label. Tab has moved focus to Confirm (› ‹); the list keeps a dimmed highlight with its › so you can see where you were.
```
$ shelley-bio build samtools --no-mouse
 Choose aliases — samtools 1.21                                                                           Keyboard only 
 Press Space to tick the aliases you'll use. You can rebuild later to add more.
 Press R to rename the highlighted alias. The Command column needs no action.

   Include  Alias name                    Command
     [ ]    ace2sam                       /usr/local/bin/ace2sam
     [x]    bgzip                         /usr/local/bin/bgzip
     [ ]    blast2sam.pl                  /usr/local/bin/blast2sam.pl
     [ ]    bowtie2sam.pl                 /usr/local/bin/bowtie2sam.pl
     [ ]    export2sam.pl                 /usr/local/bin/export2sam.pl
     [ ]    fasta-sanitize.pl             /usr/local/bin/fasta-sanitize.pl
     [x]    htsfile                       /usr/local/bin/htsfile
     [ ]    interpolate_sam.pl            /usr/local/bin/interpolate_sam.pl
     [ ]    libdeflate-gunzip             /usr/local/bin/libdeflate-gunzip
     [ ]    libdeflate-gzip               /usr/local/bin/libdeflate-gzip
     [ ]    maq2sam-long                  /usr/local/bin/maq2sam-long
     [ ]    maq2sam-short                 /usr/local/bin/maq2sam-short
     [ ]    md5fa                         /usr/local/bin/md5fa
     [ ]    md5sum-lite                   /usr/local/bin/md5sum-lite
     [ ]    novo2sam.pl                   /usr/local/bin/novo2sam.pl
     [ ]    plot-ampliconstats            /usr/local/bin/plot-ampliconstats
     [ ]    plot-bamstats                 /usr/local/bin/plot-bamstats
     [ ]    psl2sam.pl                    /usr/local/bin/psl2sam.pl
     [ ]    sam2vcf.pl                    /usr/local/bin/sam2vcf.pl
     [x]    samtools                      /usr/local/bin/samtools
     [ ]    samtools.pl                   /usr/local/bin/samtools.pl
     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl
     [ ]    soap2sam.pl                   /usr/local/bin/soap2sam.pl
 ›   [x]    tabix                         /usr/local/bin/tabix
     [ ]    wgsim                         /usr/local/bin/wgsim
     [ ]    wgsim_eval.pl                 /usr/local/bin/wgsim_eval.pl
     [ ]    zoom2sam.pl                   /usr/local/bin/zoom2sam.pl
   4 of 27 ticked                                                                                         All 27 shown  


                                                                                            › Confirm ‹      Cancel


 ←→ Switch button   Enter Press button   Shift+Tab Back to list   Esc Exit
```

### 8 · After Confirm
Superseded. The canvas showed a plain-text summary here; the style guide replaced it with a status line plus a rounded table. See "Printed alias summary" in [`style-guide-screens.md`](style-guide-screens.md).
