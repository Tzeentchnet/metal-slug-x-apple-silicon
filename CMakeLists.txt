# Metal Slug X native recompilation for Apple Silicon.
cmake_minimum_required(VERSION 3.25)

if(NOT APPLE)
    message(FATAL_ERROR "This port supports Apple Silicon macOS only")
endif()

if(NOT DEFINED CMAKE_OSX_ARCHITECTURES)
    set(CMAKE_OSX_ARCHITECTURES arm64 CACHE STRING "Apple architecture")
endif()
if(NOT CMAKE_OSX_ARCHITECTURES STREQUAL "arm64")
    message(FATAL_ERROR "CMAKE_OSX_ARCHITECTURES must be exactly arm64")
endif()

if(NOT DEFINED CMAKE_OSX_DEPLOYMENT_TARGET)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "13.0" CACHE STRING "Minimum macOS version")
endif()
if(CMAKE_OSX_DEPLOYMENT_TARGET VERSION_LESS "13.0")
    message(FATAL_ERROR "macOS 13.0 or newer is required")
endif()

project(mslugx_port LANGUAGES C CXX OBJCXX)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# The recompiled program is generated privately from the user's copy. None of its normalized
# inputs, analysis, or generated code goes into the repository.
set(PD_GAME "${PROJECT_SOURCE_DIR}/game" CACHE PATH "User-provided game folder")
set(PD_PRIVATE "${PROJECT_BINARY_DIR}/private" CACHE PATH "Private generated-data folder")
set(PD_ROMS "${PD_PRIVATE}/roms" CACHE PATH "Private normalized recompiler inputs")
set(PD_ANALYSIS "${PD_PRIVATE}/analysis" CACHE PATH "Private analysis output")
find_program(PD_PYTHON_EXECUTABLE NAMES python3 REQUIRED)
set(Python3_EXECUTABLE "${PD_PYTHON_EXECUTABLE}" CACHE FILEPATH "Pinned Python interpreter" FORCE)
set(Python3_FIND_FRAMEWORK NEVER)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

enable_testing()

add_subdirectory(external/musashi)
add_subdirectory(external/ymfm)
add_subdirectory(src)
add_subdirectory(tests/differential)
add_subdirectory(tests/lockstep)
