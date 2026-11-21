# Build, test and release the observer firmware

The observer firmware is the `SenseCap_Solar_repeater_observer` PlatformIO
environment. The Bluetooth LE CoC log transport is enabled by building it with
`-DSENSECAP_OBSERVER_COC_CHANNELS=2`; without that flag the environment builds
the GATT-only observer (`v1.18.0-obs544`).

These are application-only images: they do not include a bootloader or
SoftDevice update. Confirm your board and bootloader, back up your identity,
and have a recovery method before flashing. This is community firmware, not an
official MeshCore release.

## Framework patch

The CoC build needs one hook in the Adafruit nRF52 framework so the L2CAP
channel configuration is set before `sd_ble_enable`. It is
`patches/bluefruit-pre-enable.patch` and is applied to the installed
PlatformIO package, not to this repository. The scripts below refuse to patch a
`bluefruit.cpp` whose SHA-256 is not the pinned original
(`e0948ab8…98f6`), so a changed framework cannot slip in unnoticed. Applying
the patch affects every project using that PlatformIO package; it is inert
unless the firmware defines `bluefruit_configure_peripheral`.

## Build locally (Linux)

```sh
pip install platformio
tools/observer/build_release.sh observer-coc-local out/release
```

This installs the packages, checks and applies the framework patch (an already
patched package is accepted if it reverts to the pinned original), builds with
CoC enabled, and writes `<name>.uf2`, `<name>.zip`, `<name>.hex`, `SHA256SUMS`
and `provenance.json` to the output directory, which must not exist yet. The
build date and compiler timestamps come from the commit time
(`SOURCE_DATE_EPOCH`).

Packaging fails unless the DFU zip contains only an application (no bootloader
or SoftDevice) and every UF2 block lies in the application region
(`0x27000`–`0xED000`).

## Tests

```sh
pio test -e native -f test_observer_transport
pio pkg install -e SenseCap_Solar_repeater_observer
tools/observer/run_coc_tests.sh
```

`run_coc_tests.sh` builds and runs the standalone CoC programs in
`test/test_observer_coc` (two of them against the real S140 headers from the
framework package), cross-compiles the CoC core for Cortex-M4, and checks the
version selection, the BLE event dispatch order and the framework patch. It
needs `g++`; it never touches Bluetooth hardware.

These tests do not prove board compatibility, recovery, power use, or
sustained radio performance.

## Release

CI (`.github/workflows/observer-build.yml`) runs the tests and the release
build on every push to `observer-coc`, uploading the files as the
`observer-coc-release` artifact.

To publish, push a tag matching `v*-coc*` on the commit to release:

```sh
git tag v1.18.0-coc.2
git push origin v1.18.0-coc.2
```

The workflow builds with the tag as the firmware version and creates a GitHub
prerelease (never marked latest) with the five files. To try the release path
without publishing, run the workflow manually with `dry_run` checked and
download the artifact.
