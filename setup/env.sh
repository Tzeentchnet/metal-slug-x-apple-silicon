#!/bin/sh

_pd_script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE:-$0}")" && pwd)
export PD_REPO=$(CDPATH= cd -- "$_pd_script_dir/.." && pwd)
export PD_ROOT="$PD_REPO"
export PD_TOOLS="$PD_REPO/.tools"
export PD_GAME="${PD_GAME:-$PD_REPO/game}"
export PD_PRIVATE="${PD_PRIVATE:-$PD_REPO/.private}"

_pd_cmake="$PD_TOOLS/cmake/CMake.app/Contents/bin"
_pd_ninja="$PD_TOOLS/ninja"
_pd_python="$PD_TOOLS/python/bin"
export PATH="$_pd_cmake:$_pd_ninja:$_pd_python:$PATH"

export CMAKE_GENERATOR=Ninja
export CMAKE_PREFIX_PATH="$PD_TOOLS/sdl3${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export DYLD_FRAMEWORK_PATH="$PD_TOOLS/sdl3/SDL3.xcframework/macos-arm64_x86_64${DYLD_FRAMEWORK_PATH:+:$DYLD_FRAMEWORK_PATH}"
export PIP_CACHE_DIR="$PD_TOOLS/cache/pip"

if [ -f "$PD_TOOLS/sdk-path" ]; then
    export SDKROOT=$(cat "$PD_TOOLS/sdk-path")
    export CMAKE_OSX_SYSROOT="$SDKROOT"
fi

if [ -x "$PD_TOOLS/mame-build/mame" ]; then
    export PD_MAME="$PD_TOOLS/mame-build/mame"
fi

unset _pd_script_dir _pd_cmake _pd_ninja _pd_python
