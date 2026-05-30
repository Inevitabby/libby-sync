#!/usr/bin/env bash
# KOR_HOST: SSH target running KOReader, e.g. root@192.168.1.50
cd "$(dirname "$0")" || exit
rsync -avz --no-o --no-g --progress -e ssh \
	--rsync-path="mntroot rw >/dev/null 2>&1; rsync" \
	./epub/ "${KOR_HOST:?set KOR_HOST}":/mnt/us/books/
