#!/usr/bin/env bash
# Example post-processing script

# 1. Trigger Jellyfin library rescan
curl -sS --fail --max-time 10 -X POST -H "Authorization: MediaBrowser Token=\"$(secret-tool lookup service jellyfin)\"" "http://127.0.0.1:8096/Library/Refresh"

# 2. rsync epub/ to KOReader
: "${KOR_HOST:?set KOR_HOST, e.g. root@192.168.1.67}"
cd "$(dirname "$0")" || exit
rsync -avz --no-o --no-g --progress -e ssh \
	--rsync-path="mntroot rw >/dev/null 2>&1; rsync" \
	./epub/ "$KOR_HOST":/mnt/us/books/
