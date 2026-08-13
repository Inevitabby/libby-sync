#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

for dir in "$PWD"/audio_parts/*/; do
	name="$(basename "$dir")"
	mkdir -p "audiobooks/${name%_*}"

	ffmpeg -loglevel error -n -f concat -safe 0 \
		-i <(printf "file '%s'\n" "$dir"*.mp3) \
		-c copy "audiobooks/${name%_*}/$name.mp3"
done
