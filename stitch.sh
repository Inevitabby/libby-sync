#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

for input_dir in "$PWD"/audio_parts/*/; do
	name="$(basename "$input_dir")"
	output_dir="audiobooks/${name%_*}"

	[[ -e $output_dir/$name.mp3 ]] && continue

	mkdir -p "$output_dir"
	ffmpeg -loglevel error -f concat -safe 0 \
		-i <(printf "file '%s'\n" "$input_dir"*.mp3) \
		-c copy "$output_dir/$name.mp3"
done
