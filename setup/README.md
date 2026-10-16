# Apple Silicon build environment

The port uses a repository-local, hash-checked tool environment. Xcode Command Line Tools provide
AppleClang and the macOS SDK; CMake, Ninja, Python, and SDL3 are downloaded from the pinned official
artifacts in `versions.json`.

## Install or repair

```sh
./setup/bootstrap.sh
```

The bootstrap:

- requires an Apple Silicon Mac running macOS 13 or newer;
- verifies every downloaded archive before extraction;
- probes the installed SDKs by compiling and linking an arm64 executable, then records the newest
  coherent SDK rather than assuming the currently selected SDK works;
- installs tools under `.tools/`, which is ignored by source control;
- leaves the user's ROM files under `game/` untouched.

The current MAME source can also be downloaded for analysis and differential verification:

```sh
./setup/bootstrap.sh --analysis-tools
```

This obtains the pinned source only. Build the focused MAME oracle after activating the
environment:

```sh
source setup/env.sh
python3 setup/build_mame.py
```

## Activate

```sh
source setup/env.sh
```

This exports `PD_ROOT`, `PD_REPO`, `PD_TOOLS`, `PD_GAME`, `PD_PRIVATE`,
`CMAKE_PREFIX_PATH`, `CMAKE_GENERATOR`, `SDKROOT`, and an arm64 tool `PATH` for the current shell.

## Verify only

```sh
./setup/bootstrap.sh --verify-only
```

No administrator access, global package manager, registry, or shell profile modification is used.
Deleting `.tools/` and `.private/` uninstalls the environment and private generated outputs.
