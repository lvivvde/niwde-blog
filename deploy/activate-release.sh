#!/usr/bin/env bash
set -euo pipefail

release_id="${1:-}"
site_root="/srv/niwde-blog"

if [[ ! "$release_id" =~ ^[0-9a-f]{40}$ ]]; then
	echo "Invalid release id" >&2
	exit 2
fi

release_path="$site_root/releases/$release_id"
if [[ ! -d "$release_path" || ! -f "$release_path/index.html" ]]; then
	echo "Release is incomplete: $release_path" >&2
	exit 3
fi

temporary_link="$site_root/.current-$release_id"
ln -s "$release_path" "$temporary_link"
mv -Tf "$temporary_link" "$site_root/current"

mapfile -t old_releases < <(
	find "$site_root/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
		| sort -rn \
		| tail -n +4 \
		| cut -d' ' -f2-
)

for old_release in "${old_releases[@]}"; do
	case "$old_release" in
		"$site_root"/releases/*) rm -rf -- "$old_release" ;;
		*) echo "Refusing unsafe cleanup target: $old_release" >&2; exit 4 ;;
	esac
done

echo "Activated $release_id"
