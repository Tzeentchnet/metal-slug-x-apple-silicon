# Releasing

## Clean artifact

Configure a fresh interpreter-only build:

```sh
source setup/env.sh
cmake -S . -B build-dist \
  -DPD_RECOMPILED=OFF \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64
cmake --build build-dist -j 8
ctest --test-dir build-dist -R '^mac_capabilities$' --output-on-failure
```

Create ad-hoc-signed local artifacts:

```sh
python3 -I tools/package_release.py --build build-dist --out release
```

The result is an arm64-only ZIP and compressed DMG. The app contains licenses and a
`BUILD-INFO.json` manifest; the sibling `game/` directory contains instructions only.

## Developer ID and notarization

Store notary credentials once:

```sh
xcrun notarytool store-credentials mslugx-notary \
  --apple-id YOUR_APPLE_ID \
  --team-id YOUR_TEAM_ID \
  --password YOUR_APP_SPECIFIC_PASSWORD
```

Then package:

```sh
python3 -I tools/package_release.py \
  --build build-dist \
  --out release \
  --sign-identity "Developer ID Application: NAME (TEAMID)" \
  --notarize-profile mslugx-notary
```

The script signs SDL3.framework before the app, verifies strict nested signatures, submits the app,
staples it, creates the final artifacts, then notarizes and staples the DMG.

## Audit guarantees

`tools/audit.py release` checks:

- one expected top-level package;
- only the app, SDL3 framework, licenses, clean manifest, and game-folder guide;
- clean-build flags in `BUILD-INFO.json`;
- a reasonable interpreter-app binary size;
- copied ROM byte runs when `--roms` or `PD_GAME` is available.

Repository-history audit requires a Git worktree:

```sh
python3 -I tools/audit.py history --roms game
```

Never package `build-personal` or any directory containing normalized inputs, listings, coverage
files, generated program sources, cached title graphics, gameplay screenshots, save states, or
ROMs. The repository permits only the exact, hash-allowlisted ROM-free frontend captures under
`docs/screenshots/`; they are documentation and are not bundled into release artifacts.
