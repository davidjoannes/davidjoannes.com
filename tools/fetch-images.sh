#!/usr/bin/env bash
# Downloads every file listed in tools/image-urls.txt into the same path it had on WordPress.
set -u
fetch() {
  url="$1"; path="${url#https://davidjoannes.com/}"
  [ -s "$path" ] && exit 0
  mkdir -p "$(dirname "$path")"
  if curl -fsSL --retry 2 --max-time 120 --max-filesize 95000000 -A "Mozilla/5.0 (site migration)" -o "$path" "$url"; then :; else rm -f "$path"; echo "$url" >> tools/missing.tmp; fi
}
export -f fetch
: > tools/missing.tmp
grep -v '^$' tools/image-urls.txt | xargs -P 8 -I{} bash -c 'fetch "$@"' _ {}
while read -r url path; do
  [ -z "$url" ] && continue; [ -s "$path" ] && continue
  mkdir -p "$(dirname "$path")"
  curl -fsSL --retry 2 --max-time 120 -A "Mozilla/5.0 (site migration)" -o "$path" "$url" || { rm -f "$path"; echo "$url" >> tools/missing.tmp; }
done < tools/extra-files.txt
sort -u tools/missing.tmp > tools/missing.txt
rm -f tools/missing.tmp
echo "missing: $(wc -l < tools/missing.txt)"
