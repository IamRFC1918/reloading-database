#!/usr/bin/env bash
# Neues Release vorbereiten: Version in Chart.yaml setzen, committen, Tag vX.Y.Z anlegen.
#   scripts/release.sh 0.2.0          (oder 0.2.0-rc.1 für einen Pre-Release)
#   git push origin main v0.2.0       -> CI baut Image, Chart und GitHub-Release
#
# SemVer: MAJOR = inkompatible Änderung (z. B. Migration ohne Rückweg, Chart-Werte
# umbenannt), MINOR = neue Funktion, PATCH = Fehlerbehebung.
set -euo pipefail
cd "$(dirname "$0")/.."

version="${1:-}"
semver='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$'
if [[ ! "$version" =~ $semver ]]; then
  echo "Aufruf: $0 X.Y.Z[-pre]   (ohne führendes v)" >&2
  exit 1
fi

chart=charts/ladedaten/Chart.yaml
aktuell=$(awk '/^version:/ {print $2}' "$chart" | tr -d '"')

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Arbeitsverzeichnis ist nicht sauber – erst committen." >&2
  exit 1
fi
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Releases nur von main." >&2
  exit 1
fi
if git rev-parse -q --verify "refs/tags/v$version" >/dev/null; then
  echo "Tag v$version existiert bereits." >&2
  exit 1
fi
# Neue Version muss größer sein (gleich ist nur beim allerersten Tag erlaubt)
if [[ "$version" != "$aktuell" ]] && \
   [[ "$(printf '%s\n%s\n' "$aktuell" "$version" | sort -V | tail -1)" != "$version" ]]; then
  echo "Version $version ist kleiner als die aktuelle $aktuell." >&2
  exit 1
fi

sed -i.bak -E "s/^version: .*/version: $version/; s/^appVersion: .*/appVersion: \"$version\"/" "$chart"
rm -f "$chart.bak"

if ! git diff --quiet; then
  git commit -q -am "Release v$version"
fi
git tag -a "v$version" -m "Release v$version"
echo "Tag v$version angelegt. Veröffentlichen mit:"
echo "  git push origin main v$version"
