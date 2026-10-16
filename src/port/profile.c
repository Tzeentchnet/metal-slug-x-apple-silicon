/* Arcade feature-profile selection.
 *
 * Static and dynamic reanalysis showed that the enhancement-bearing code and RAM layout retain
 * the original addresses in the verified 250-P1 arcade program. Selection still hashes every
 * relevant code window so modified or unknown programs cannot accidentally enable writes.
 */
#include "profile.h"

#include "hashes.h"
#include "neogeo.h"
#include "sha256.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const GameProfile GAME_PROFILE_ARCADE = {
    .id = "mslugx-arcade-250-p1",
    .wait_start = 0x0039B0,
    .wait_end = 0x003A42,
    .ram_frames_per_tick = 0x008A,
    .dips_word = 0x10F000,
    .devmode_word = 0x10FE80,
    .devmode_copy_word = 0x10C2BE,
    .game_state = 0x100088,
    .game_state_playing = 2,
    .player_table = 0x10C718,
    .player_object = {0x1014C4, 0x101574},
    .object_character = 0x6F,
    .object_form = 0x93,
    .fat_food = 0x0780,
    .stage_word = 0x10C2F6,
    .fat_check_first = 0x0C0BAE,
    .fat_check_last = 0x0C0BF2,
    .fat_stage = 4,
    .spawn_routine = 0x01A0A6,
    .spawn_parent = 0x101414,
    .spawn_x = 0x0100,
    .spawn_y = 0x0060,
    .player_soldier = {0x101287, 0x101337},
    .player_lives = {0x101288, 0x101338},
    .rom_weapon_subtype = 0x0C08A8,
    .rom_weapon_ammo = 0x0C08B8,
    .rom_weapon_flag = 0x0C0918,
    .blood_word = 0x10FD8E,
    .blood_mask = 0x00FF,
    .logo_first = 41,
    .logo_last = 124,
    .logo_tm = 380,
    .logo_tm_tile = 0x0309CA,
    .logo_max_frames = 3000,
};

static const struct {
    uint32_t first;
    uint32_t last;
} ARCADE_WINDOWS[] = {
    {0x002580, 0x0025A0},     /* debug-dip development-mode gate */
    {0x0039B0, 0x003A42},     /* VBlank wait loop */
    {0x0040BC, 0x004100},     /* object allocation */
    {0x015400, 0x015410},     /* development-mode copy */
    {0x0197DC, 0x019AF8},     /* vehicle object-type table */
    {0x01A0A6, 0x01A140},     /* stage object records */
    {0x01B2B8, 0x01B2C8},     /* BLOOD option read */
    {0x0C07F0, 0x0C0A00},     /* weapon tables and pickup routine */
    {0x0C0BAE, 0x0C0BF4},     /* fat-form stage check */
    {0x0C32E4, 0x0C3320},     /* form transitions */
    {0x0C942C, 0x0C9440},     /* lives from the HERO soft dip */
};

static const char ARCADE_WINDOWS_SHA256[] =
    "f4098e70cb8b86527645e878561c0cc0111bc4653df3e68509f8eabf0239031d";

static int windows_hash(char hex[65])
{
    size_t total = 0;
    for (size_t i = 0; i < sizeof ARCADE_WINDOWS / sizeof ARCADE_WINDOWS[0]; i++)
        total += ARCADE_WINDOWS[i].last - ARCADE_WINDOWS[i].first;
    uint8_t *buffer = malloc(total);
    if (!buffer) {
        fprintf(stderr, "Could not allocate %zu bytes for arcade profile verification\n", total);
        return -1;
    }
    size_t at = 0;
    for (size_t i = 0; i < sizeof ARCADE_WINDOWS / sizeof ARCADE_WINDOWS[0]; i++) {
        size_t length = ARCADE_WINDOWS[i].last - ARCADE_WINDOWS[i].first;
        memcpy(buffer + at, ng_roms.p + ARCADE_WINDOWS[i].first, length);
        at += length;
    }
    uint8_t hash[32];
    sha256(buffer, at, hash);
    free(buffer);
    hex_string(hash, sizeof hash, hex);
    return 0;
}

const GameProfile *profile_current(void)
{
    static const uint8_t *checked;
    static const GameProfile *selected;
    if (!ng_roms.p) return NULL;
    if (checked != ng_roms.p) {
        char hex[65] = "";
        selected = NULL;
        if (windows_hash(hex) == 0 &&
            ng_roms.info.version == NG_VERSION_ARCADE &&
            !strcmp(hex, ARCADE_WINDOWS_SHA256))
            selected = &GAME_PROFILE_ARCADE;
        if (getenv("PD_PROFILE_HASH"))
            printf("profile %s windows: %s\n", selected ? selected->id : "unrecognized", hex);
        checked = ng_roms.p;
    }
    return selected;
}

int profile_supported(void)
{
    return profile_current() != NULL;
}
