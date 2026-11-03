# Libby Sync

CLI scripts for Linux to download your Libby loans to disk/Jellyfin/E-Reader/etc. Supports e-books that have the option to be read as EPUB (DRM), and all audiobooks.

# Setup

```bash
uvx patchright install chromium
./dl.py login
ACSM_CONVERTER=/path/to/tool ./libby-sync
```

> Dependencies: `uv`, `ffmpeg` (if downloading audiobooks)

# libby-sync

Bash script that just runs the scripts below.

```mermaid
flowchart TD
    dl["<b>1.</b> dl.py"]

    subgraph raw["Raw"]
        acsm[("acsm/")]
        parts[("audio_parts/")]
    end

    convert["<b>2a.</b> convert.sh"]
    stitch["<b>2b.</b> stitch.sh"]

    subgraph processed["Processed"]
        epub[("epub/")]
        audio[("audiobooks/")]
    end

    subgraph mine["Example: Post-processing"]
        sync["<b>3.</b> sync.sh"]
        kor["KOReader"]
        jf["Jellyfin<br/><i>(for OPDS & API)</i>"]
    end

    dl --> acsm --> convert --> epub
    dl --> parts --> stitch --> audio

    epub ~~~ sync
    audio ~~~ sync

    sync -->|rsync epub/| kor
    sync -.->|trigger rescan| jf
    processed -.->|library dirs| jf

    classDef script fill:#e3f2fd,stroke:#1565c0,color:#000
    classDef inFolder fill:#fff3cd,stroke:#b58900,color:#000
    classDef outFolder fill:#d4edda,stroke:#2e7d32,color:#000
    classDef external fill:#eeeeee,stroke:#616161,color:#000

    class dl,convert,stitch,sync script
    class acsm,parts inFolder
    class epub,audio outFolder
    class kor,jf external

    style mine fill:none,stroke:#888,stroke-dasharray: 5 5
```

# dl.py

Downloads new ACSM files and audiobook parts from Libby. (ACSM files are valid for 6 hours.)

# convert.sh

Runs `$ACSM_CONVERTER`[^BYO] on each ACSM and puts the result in `epub/`.

[^BYO]: Bring your own.

# stitch.sh

Stitches audio parts into a single file. Outputs to `audiobooks/` 

# examples/sync.sh

My own post-processing, shown for reference[^lie]. rsyncs EPUBs to a Kindle running KOReader and triggers a Jellyfin library scan.

[^lie]: Okay I lied, it's for bragging rights.
