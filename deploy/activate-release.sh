#!/usr/bin/env bash
set -euo pipefail

if (( $# != 1 )) || (( EUID != 0 )); then
	echo "This command requires one release id and root privileges" >&2
	exit 1
fi

release_id="$1"
site_root="/srv/niwde-blog"

if [[ ! "$release_id" =~ ^[0-9a-f]{40}$ ]]; then
	echo "Invalid release id" >&2
	exit 2
fi

incoming_path="$site_root/incoming/$release_id"
release_path="$site_root/releases/$release_id"
prepared_path="$site_root/.prepared-$release_id"
allowed_signers="/etc/niwde-blog/deploy-signing-allowed-signers"

if [[ ! -d "$incoming_path" || ! -f "$incoming_path/index.html" \
	|| ! -f "$incoming_path/.manifest.sha256" \
	|| ! -f "$incoming_path/.manifest.sha256.sig" ]]; then
	echo "Incoming release is incomplete: $incoming_path" >&2
	exit 3
fi

if [[ -n "$(find "$incoming_path" -type l -print -quit)" ]]; then
	echo "Incoming release contains a symbolic link" >&2
	exit 4
fi

(
	cd "$incoming_path"
	ssh-keygen -Y verify \
		-f "$allowed_signers" \
		-I niwde-blog \
		-n niwde-blog \
		-s .manifest.sha256.sig < .manifest.sha256
	sha256sum --check --strict .manifest.sha256
)

cleanup_prepared() {
	case "$prepared_path" in
		"$site_root"/.prepared-*) rm -rf -- "$prepared_path" ;;
		*) echo "Refusing unsafe prepared path: $prepared_path" >&2 ;;
	esac
}
trap cleanup_prepared EXIT

cleanup_prepared
install -d -o root -g root -m 0755 "$prepared_path"
cp -a --no-preserve=ownership "$incoming_path/." "$prepared_path/"
chown -R root:root "$prepared_path"
find "$prepared_path" -type d -exec chmod 0755 {} +
find "$prepared_path" -type f -exec chmod 0644 {} +

if [[ -e "$release_path" ]]; then
	case "$release_path" in
		"$site_root"/releases/*) rm -rf -- "$release_path" ;;
		*) echo "Refusing unsafe release path: $release_path" >&2; exit 5 ;;
	esac
fi
mv "$prepared_path" "$release_path"

temporary_link="$site_root/.current-$release_id"
ln -s "$release_path" "$temporary_link"
mv -Tf "$temporary_link" "$site_root/current"

case "$incoming_path" in
	"$site_root"/incoming/*) rm -rf -- "$incoming_path" ;;
	*) echo "Refusing unsafe incoming path: $incoming_path" >&2; exit 6 ;;
esac

mapfile -t old_releases < <(
	find "$site_root/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
		| sort -rn \
		| tail -n +4 \
		| cut -d' ' -f2-
)

for old_release in "${old_releases[@]}"; do
	case "$old_release" in
		"$site_root"/releases/*) rm -rf -- "$old_release" ;;
		*) echo "Refusing unsafe cleanup target: $old_release" >&2; exit 7 ;;
	esac
done

trap - EXIT
echo "Activated $release_id"
