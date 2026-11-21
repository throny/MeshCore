#!/usr/bin/env python3
"""Check and package observer firmware build output for a release.

Copies firmware.{uf2,zip,hex} from a PlatformIO build directory to
<out>/<name>.{uf2,zip,hex}, refusing anything that is not an application-only
image, and writes SHA256SUMS and provenance.json.

Usage: package_release.py BUILD_DIR OUT_DIR NAME
Called by build_release.sh, which sets the environment variables read below.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Application region of boards/nrf52840_s140_v7.ld: after the S140 SoftDevice,
# before the bootloader.
APP_START, APP_END = 0x27000, 0xED000
UF2_FAMILY_NRF52840 = 0xADA52840


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_dfu_zip(path):
    """The DFU package must hold an application and nothing else."""
    with zipfile.ZipFile(path) as package:
        if package.testzip() is not None:
            raise SystemExit(f"{path}: corrupt zip")
        manifest = json.loads(package.read("manifest.json"))["manifest"]
        if "application" not in manifest or set(manifest) - {"application", "dfu_version"}:
            raise SystemExit(f"{path}: DFU package is not application-only: {sorted(manifest)}")
        app = manifest["application"]
        expected = {"manifest.json", app["bin_file"], app["dat_file"]}
        if set(package.namelist()) != expected:
            raise SystemExit(f"{path}: unexpected files {sorted(package.namelist())}")
        return manifest


def normalize_zip(path, epoch):
    """Fix zip entry order, timestamps and modes; payload bytes stay as built."""
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    stamp = datetime.fromtimestamp(max(epoch, 315532800), timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, stamp)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])


def check_uf2(path):
    """Every block must target the nRF52840 application region."""
    data = Path(path).read_bytes()
    if not data or len(data) % 512:
        raise SystemExit(f"{path}: not a UF2 file")
    count = len(data) // 512
    for index in range(count):
        offset = index * 512
        magic1, magic2, flags, address, length, block, total, family = struct.unpack_from("<8I", data, offset)
        end_magic = struct.unpack_from("<I", data, offset + 508)[0]
        if (magic1, magic2, end_magic) != (0x0A324655, 0x9E5D5157, 0x0AB16F30):
            raise SystemExit(f"{path}: bad UF2 magic in block {index}")
        if not flags & 0x2000 or family != UF2_FAMILY_NRF52840:
            raise SystemExit(f"{path}: block {index} is not for the nRF52840")
        if block != index or total != count or length != 256:
            raise SystemExit(f"{path}: inconsistent block {index}")
        if not (APP_START <= address and address + length <= APP_END):
            raise SystemExit(f"{path}: block {index} at 0x{address:x} is outside the application region")
    return count


def package_version(path):
    """Resolved version (and source, if PlatformIO recorded one) of an installed package."""
    for meta in (".piopm", "package.json", "platform.json"):
        if (path / meta).is_file():
            data = json.loads((path / meta).read_text())
            result = {"version": data.get("version")}
            uri = (data.get("spec") or {}).get("uri")
            if uri:
                result["source"] = uri
            return result
    return None


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def build_inputs(name):
    env = os.environ
    packages, platforms = Path(env["PIO_PACKAGES_DIR"]), Path(env["PIO_PLATFORMS_DIR"])
    tag = env.get("RELEASE_TAG") or None
    return {
        "name": name,
        "tag": tag,
        "commit": git("rev-parse", "HEAD"),
        "environment": "SenseCap_Solar_repeater_observer",
        "build_flags": env["PLATFORMIO_BUILD_FLAGS"],
        "build_date": env["FIRMWARE_BUILD_DATE"],
        "platformio_version": env["PIO_VERSION"],
        "platform": {"nordicnrf52": package_version(platforms / "nordicnrf52")},
        "packages": {path.name: package_version(path) for path in sorted(packages.iterdir())
                     if path.is_dir() and package_version(path)},
        "framework_patch": {
            "file": "framework-arduinoadafruitnrf52/libraries/Bluefruit52Lib/src/bluefruit.cpp",
            "original_sha256": env["FRAMEWORK_ORIGINAL_SHA256"],
            "patched_sha256": env["FRAMEWORK_PATCHED_SHA256"],
            "patch": "patches/bluefruit-pre-enable.patch",
            "patch_sha256": env["PATCH_SHA256"],
        },
    }


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    build, out, name = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    epoch = int(os.environ["SOURCE_DATE_EPOCH"])
    provenance = build_inputs(name)
    out.mkdir(parents=True, exist_ok=False)
    for ext in ("uf2", "zip", "hex"):
        shutil.copyfile(build / f"firmware.{ext}", out / f"{name}.{ext}")
    check_dfu_zip(out / f"{name}.zip")
    normalize_zip(out / f"{name}.zip", epoch)
    dfu_manifest = check_dfu_zip(out / f"{name}.zip")
    uf2_blocks = check_uf2(out / f"{name}.uf2")

    files = [f"{name}.{ext}" for ext in ("uf2", "zip", "hex")]
    provenance.update({
        "source_date_epoch": epoch,
        "dfu_manifest": dfu_manifest,
        "uf2_blocks": uf2_blocks,
        "artifacts": {file: sha256(out / file) for file in files},
    })
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    files.append("provenance.json")
    (out / "SHA256SUMS").write_text("".join(f"{sha256(out / f)}  {f}\n" for f in files))
    print((out / "SHA256SUMS").read_text(), end="")


if __name__ == "__main__":
    main()
