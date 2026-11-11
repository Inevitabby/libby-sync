#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

if [ -z "${ACSM_CONVERTER:-}" ]; then
	echo "convert.sh: ACSM_CONVERTER not set, skipping" >&2
	exit 0
fi
ACSM_CONVERTER="$(realpath "$ACSM_CONVERTER")"

mkdir -p epub
cd acsm || exit 1

for file in *.acsm; do
	# Guard: Skip already-processed
	[ -s "$file" ] || continue

	cp "$file" ../epub/
	if ! "$ACSM_CONVERTER" "../epub/$file"; then
		echo "convert.sh: failed on $file" >&2
		rm -f "../epub/$file"
		continue
	fi

	# Mark as processed
	truncate -s 0 "$file"
done
