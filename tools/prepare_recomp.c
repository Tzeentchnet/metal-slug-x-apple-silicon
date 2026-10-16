/* Writes the private P1/P2 and BIOS inputs used by the static analyzer and recompiler.
 * The runtime loader performs all candidate discovery, hash validation, BIOS selection, and
 * MAME-to-runtime conversion. This tool only converts its CPU-view P/BIOS bytes back to the
 * original file byte order expected by the existing analysis tools.
 */
#include "neogeo.h"
#include "sha256.h"
#include "hashes.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static void usage(void)
{
    fprintf(stderr,
            "Usage: prepare_recomp --input GAME --output DIR "
            "[--require-version arcade|gog] [--require-bios NAME]\n");
}

static int write_atomic(const char *path, const void *data, size_t size)
{
    char temporary[1200];
    if (snprintf(temporary, sizeof temporary, "%s.tmp", path) >= (int)sizeof temporary) {
        fprintf(stderr, "Output path is too long: %s\n", path);
        return -1;
    }
    FILE *file = fopen(temporary, "wb");
    if (!file) {
        fprintf(stderr, "Could not create %s: %s\n", temporary, strerror(errno));
        return -1;
    }
    int ok = fwrite(data, 1, size, file) == size;
    if (fclose(file) != 0) ok = 0;
    if (!ok) {
        fprintf(stderr, "Could not write %s\n", temporary);
        remove(temporary);
        return -1;
    }
    if (rename(temporary, path) != 0) {
        fprintf(stderr, "Could not replace %s: %s\n", path, strerror(errno));
        remove(temporary);
        return -1;
    }
    return 0;
}

static void file_order(uint8_t *data, size_t size)
{
    for (size_t i = 0; i + 1 < size; i += 2) {
        uint8_t value = data[i];
        data[i] = data[i + 1];
        data[i + 1] = value;
    }
}

static const char *version_name(int version)
{
    switch (version) {
    case NG_VERSION_DOTEMU: return "legacy";
    case NG_VERSION_ARCADE: return "arcade";
    default: return "unknown";
    }
}

int main(int argc, char **argv)
{
    const char *input = NULL, *output = NULL, *required_version = NULL, *required_bios = NULL;
    for (int i = 1; i < argc; i++) {
        const char *value = i + 1 < argc ? argv[i + 1] : NULL;
        if (!strcmp(argv[i], "--input") && value) { input = value; i++; }
        else if (!strcmp(argv[i], "--output") && value) { output = value; i++; }
        else if (!strcmp(argv[i], "--require-version") && value) { required_version = value; i++; }
        else if (!strcmp(argv[i], "--require-bios") && value) { required_bios = value; i++; }
        else { usage(); return 2; }
    }
    if (!input || !output) { usage(); return 2; }

    NgRoms roms;
    char error[1200];
    if (ng_roms_load(&roms, input, error, sizeof error) != 0) {
        fprintf(stderr, "%s\n", error);
        return 1;
    }
    const char *actual_version = version_name(roms.info.version);
    if (required_version && strcmp(required_version, actual_version)) {
        fprintf(stderr, "Expected the %s P1, loaded %s\n", required_version, actual_version);
        ng_roms_free(&roms);
        return 1;
    }
    if (required_bios && strcmp(required_bios, roms.info.bios)) {
        fprintf(stderr, "Expected BIOS %s, loaded %s\n", required_bios, roms.info.bios);
        ng_roms_free(&roms);
        return 1;
    }

    file_order(roms.p, roms.p_size);
    file_order(roms.bios, 131072);
    char program_path[1200], bios_path[1200], manifest_path[1200];
    if (snprintf(program_path, sizeof program_path, "%s/mslugx_game_m68k", output) >= (int)sizeof program_path ||
        snprintf(bios_path, sizeof bios_path, "%s/mslugx_bios_m68k", output) >= (int)sizeof bios_path ||
        snprintf(manifest_path, sizeof manifest_path, "%s/manifest.json", output) >= (int)sizeof manifest_path) {
        fprintf(stderr, "Output path is too long: %s\n", output);
        ng_roms_free(&roms);
        return 1;
    }
    if (write_atomic(program_path, roms.p, roms.p_size) != 0 ||
        write_atomic(bios_path, roms.bios, 131072) != 0) {
        ng_roms_free(&roms);
        return 1;
    }

    uint8_t program_hash[32], bios_hash[32];
    char program_hex[65], bios_hex[65];
    sha256(roms.p, roms.p_size, program_hash);
    sha256(roms.bios, 131072, bios_hash);
    hex_string(program_hash, 32, program_hex);
    hex_string(bios_hash, 32, bios_hex);
    char manifest[1024];
    int manifest_size = snprintf(
        manifest, sizeof manifest,
        "{\n"
        "  \"schema\": 1,\n"
        "  \"version\": \"%s\",\n"
        "  \"bios\": \"%s\",\n"
        "  \"verified\": %s,\n"
        "  \"program_size\": %u,\n"
        "  \"program_sha256\": \"%s\",\n"
        "  \"bios_sha256\": \"%s\"\n"
        "}\n",
        actual_version, roms.info.bios, roms.info.verified ? "true" : "false",
        roms.p_size, program_hex, bios_hex);
    if (manifest_size < 0 || manifest_size >= (int)sizeof manifest ||
        write_atomic(manifest_path, manifest, (size_t)manifest_size) != 0) {
        ng_roms_free(&roms);
        return 1;
    }
    printf("%s\n%s\n", roms.info.description, manifest_path);
    ng_roms_free(&roms);
    return 0;
}
