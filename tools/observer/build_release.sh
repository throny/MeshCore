#!/usr/bin/env bash
# Builds the observer CoC release firmware and packages it into OUT_DIR:
#   NAME.uf2, NAME.zip (BLE DFU), NAME.hex, SHA256SUMS, provenance.json
#
# Usage: tools/observer/build_release.sh NAME OUT_DIR
#
# Patches the installed Adafruit nRF52 framework package in place (see
# docs/observer/building.md). The framework file must match the pinned
# original, or already be exactly the pinned original plus the patch.
set -euo pipefail

name="${1:?usage: build_release.sh NAME OUT_DIR}"
out="${2:?usage: build_release.sh NAME OUT_DIR}"
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid release name: $name" >&2; exit 1; }

root="$(cd "$(dirname "$0")/../.." && pwd)"
env_name="SenseCap_Solar_repeater_observer"
core="${PLATFORMIO_CORE_DIR:-$HOME/.platformio}"
packages="${PLATFORMIO_PACKAGES_DIR:-$core/packages}"
framework="$packages/framework-arduinoadafruitnrf52"
bluefruit="libraries/Bluefruit52Lib/src/bluefruit.cpp"
patch_file="$root/patches/bluefruit-pre-enable.patch"
# sha256 of the unmodified framework file the patch was written against.
export FRAMEWORK_ORIGINAL_SHA256="e0948ab89ce44748e26d5fd950caa9bafb00da78e16fcc6e77f84a38cfd798f6"

cd "$root"
pio pkg install -e "$env_name"

file_sha() { sha256sum < "$1" | cut -d' ' -f1; }
target="$framework/$bluefruit"
if [ "$(file_sha "$target")" = "$FRAMEWORK_ORIGINAL_SHA256" ]; then
  patch -p1 -d "$framework" < "$patch_file"
else
  # Accept an already patched package only if reverting the patch yields the
  # pinned original exactly.
  scratch="$(mktemp -d)"
  mkdir -p "$scratch/$(dirname "$bluefruit")"
  cp "$target" "$scratch/$bluefruit"
  patch -s -R -p1 -d "$scratch" < "$patch_file" \
    || { echo "framework file is not the pinned original: $target" >&2; exit 1; }
  reverted="$(file_sha "$scratch/$bluefruit")"
  rm -rf "$scratch"
  [ "$reverted" = "$FRAMEWORK_ORIGINAL_SHA256" ] \
    || { echo "framework file is not the pinned original: $target" >&2; exit 1; }
  echo "framework already patched"
fi
export FRAMEWORK_PATCHED_SHA256="$(file_sha "$target")"
export PATCH_SHA256="$(file_sha "$patch_file")"

# Reproducible inputs: commit time as build date, UTC, fixed locale.
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
export TZ=UTC LC_ALL=C
build_date="$(date -u -d "@$SOURCE_DATE_EPOCH" '+%d %b %Y')"
export PLATFORMIO_BUILD_FLAGS="-DFIRMWARE_VERSION='\"$name\"' -DFIRMWARE_BUILD_DATE='\"$build_date\"'"

pio run -e "$env_name"
pio run -e "$env_name" -t create_uf2

build_dir="${PLATFORMIO_BUILD_DIR:-$root/.pio/build}/$env_name"
check="$root/tools/observer/check_version.sh"
bash "$check" "$build_dir/firmware.elf" "$name" || { echo "firmware version is not exactly $name" >&2; exit 1; }
bash "$check" "$build_dir/firmware.elf" "$build_date" || { echo "firmware build date is not exactly $build_date" >&2; exit 1; }

export PIO_VERSION="$(pio --version)"
export PIO_PACKAGES_DIR="$packages"
export PIO_PLATFORMS_DIR="${PLATFORMIO_PLATFORMS_DIR:-$core/platforms}"
export FIRMWARE_BUILD_DATE="$build_date"
python3 "$root/tools/observer/package_release.py" "$build_dir" "$out" "$name"
