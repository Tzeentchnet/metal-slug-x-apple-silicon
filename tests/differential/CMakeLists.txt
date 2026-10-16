# Differential tests of the recompiler against Musashi.
# They require private normalized ROMs (PD_ROMS) and the analysis listing (PD_ANALYSIS).
# The test C code is generated here, in the build directory, and is never committed.

if(NOT PD_HAVE_PROGRAM)
    message(STATUS "Differential tests disabled: the recompiled program is missing")
    return()
endif()

# Musashi base cycle table (the dump_cycles executable is defined in src/).
set(CYCLES_BIN ${CMAKE_CURRENT_BINARY_DIR}/cycles_68000.bin)
add_custom_command(OUTPUT ${CYCLES_BIN} COMMAND dump_cycles ${CYCLES_BIN} DEPENDS dump_cycles VERBATIM)
set(GEN ${CMAKE_CURRENT_BINARY_DIR}/tests_gen.c)
file(GLOB RECOMP_PY ${PROJECT_SOURCE_DIR}/tools/recomp68k/*.py)
add_custom_command(
    OUTPUT ${GEN}
    COMMAND Python3::Interpreter -I ${CMAKE_CURRENT_SOURCE_DIR}/generate_tests.py
            --roms ${PD_ROMS} --listing ${PD_ANALYSIS}/listing_p1.txt --output ${GEN} --cycles ${CYCLES_BIN}
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/generate_tests.py ${RECOMP_PY} ${CYCLES_BIN}
    COMMENT "Generating differential tests from the user's ROMs"
    VERBATIM)

add_executable(diferencial differential.c test_memory.c musashi_side.c ${GEN})
add_dependencies(diferencial recomp_analysis)
target_include_directories(diferencial PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${PROJECT_SOURCE_DIR}/src/cpu)
target_link_libraries(diferencial PRIVATE musashi)
# The generated code declares temporaries that are sometimes unused.
set_source_files_properties(${GEN} PROPERTIES COMPILE_OPTIONS "-Wno-unused-variable;-Wno-unused-but-set-variable")

add_test(NAME cpu_differential
         COMMAND diferencial ${PD_ROMS}/mslugx_game_m68k ${PD_ROMS}/mslugx_bios_m68k 64)
