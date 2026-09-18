#!/bin/sh
# Re-fetch the generated illustrations and re-encode them into img/*.webp.
#
# Source of truth is img_prompts.json: it holds every image's Higgsfield generation
# id, its raw PNG url and the exact prompt used. Nothing here generates anything —
# it only pulls what already exists and encodes it, so the asset step is repeatable
# without spending credits.
#
#   ./make_images.sh            # fetch + encode at the defaults below
#   SIZE=1024 Q=80 ./make_images.sh
#
# The card renders the image at 260 CSS px, which is 780 device px on a 3x phone,
# so 768 is the honest target; going higher only grows the file.
set -eu

SIZE="${SIZE:-768}"
Q="${Q:-75}"
CACHE="${CACHE:-.img_cache}"

command -v cwebp >/dev/null || { echo "cwebp not found (brew install webp)" >&2; exit 1; }

mkdir -p "$CACHE" img

python3 - "$CACHE" <<'PY' | while IFS='	' read -r stem url; do
import json, sys
d = json.load(open("img_prompts.json", encoding="utf-8"))
for section in ("generated", "generated_documentary"):
    for stem, e in d.get(section, {}).items():
        print(stem + "\t" + e["raw_url"])
PY
    png="$CACHE/$stem.png"
    if [ ! -s "$png" ]; then
        printf 'fetch  %s\n' "$stem"
        curl -fsS -o "$png" "$url"
    fi
    cwebp -quiet -q "$Q" -resize "$SIZE" "$SIZE" "$png" -o "img/$stem.webp"
    printf 'encode %-14s %s KB\n' "$stem" "$(( $(wc -c < "img/$stem.webp") / 1024 ))"
done

printf '\ntotal img/: %s KB at %spx q%s\n' "$(( $(cat img/*.webp | wc -c) / 1024 ))" "$SIZE" "$Q"
