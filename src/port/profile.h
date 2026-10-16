/* Verified Metal Slug X arcade-program profile used by native frontend features. */
#ifndef PROFILE_H
#define PROFILE_H

#include <stdint.h>

typedef struct {
    const char *id;
    uint32_t wait_start;
    uint32_t wait_end;
    uint16_t ram_frames_per_tick;
    uint32_t dips_word;
    uint32_t devmode_word;
    uint32_t devmode_copy_word;
    uint32_t game_state;
    uint8_t game_state_playing;
    uint32_t player_table;
    uint32_t player_object[2];
    uint8_t object_character;
    uint8_t object_form;
    uint16_t fat_food;
    uint32_t stage_word;
    uint32_t fat_check_first;
    uint32_t fat_check_last;
    uint16_t fat_stage;
    uint32_t spawn_routine;
    uint32_t spawn_parent;
    uint16_t spawn_x;
    uint16_t spawn_y;
    uint32_t player_soldier[2];
    uint32_t player_lives[2];
    uint32_t rom_weapon_subtype;
    uint32_t rom_weapon_ammo;
    uint32_t rom_weapon_flag;
    uint32_t blood_word;
    uint16_t blood_mask;
    uint16_t logo_first;
    uint16_t logo_last;
    uint16_t logo_tm;
    uint32_t logo_tm_tile;
    uint16_t logo_max_frames;
} GameProfile;

extern const GameProfile GAME_PROFILE_ARCADE;

/* Returns the selected profile only when all feature-bearing windows match the verified arcade
 * P1. Unknown or modified programs deliberately receive no enhancement profile. */
const GameProfile *profile_current(void);
int profile_supported(void);

/* Compatibility names keep feature code readable while all values come from one profile. */
#define PROFILE_WAIT_START           (GAME_PROFILE_ARCADE.wait_start)
#define PROFILE_WAIT_END             (GAME_PROFILE_ARCADE.wait_end)
#define PROFILE_RAM_FRAMES_PER_TICK  (GAME_PROFILE_ARCADE.ram_frames_per_tick)
#define PROFILE_DIPS_WORD            (GAME_PROFILE_ARCADE.dips_word)
#define PROFILE_DEVMODE_WORD         (GAME_PROFILE_ARCADE.devmode_word)
#define PROFILE_DEVMODE_COPY_WORD    (GAME_PROFILE_ARCADE.devmode_copy_word)
#define PROFILE_GAME_STATE           (GAME_PROFILE_ARCADE.game_state)
#define PROFILE_GAME_STATE_PLAYING   (GAME_PROFILE_ARCADE.game_state_playing)
#define PROFILE_PLAYER_TABLE         (GAME_PROFILE_ARCADE.player_table)
#define PROFILE_PLAYER1_OBJECT       (GAME_PROFILE_ARCADE.player_object[0])
#define PROFILE_PLAYER2_OBJECT       (GAME_PROFILE_ARCADE.player_object[1])
#define PROFILE_OBJECT_CHARACTER     (GAME_PROFILE_ARCADE.object_character)
#define PROFILE_OBJECT_FORM          (GAME_PROFILE_ARCADE.object_form)
#define PROFILE_FAT_FOOD             (GAME_PROFILE_ARCADE.fat_food)
#define PROFILE_STAGE_WORD           (GAME_PROFILE_ARCADE.stage_word)
#define PROFILE_FAT_CHECK_FIRST      (GAME_PROFILE_ARCADE.fat_check_first)
#define PROFILE_FAT_CHECK_LAST       (GAME_PROFILE_ARCADE.fat_check_last)
#define PROFILE_FAT_STAGE            (GAME_PROFILE_ARCADE.fat_stage)
#define PROFILE_SPAWN_ROUTINE        (GAME_PROFILE_ARCADE.spawn_routine)
#define PROFILE_SPAWN_PARENT         (GAME_PROFILE_ARCADE.spawn_parent)
#define PROFILE_SPAWN_X              (GAME_PROFILE_ARCADE.spawn_x)
#define PROFILE_SPAWN_Y              (GAME_PROFILE_ARCADE.spawn_y)
#define PROFILE_PLAYER1_SOLDIER      (GAME_PROFILE_ARCADE.player_soldier[0])
#define PROFILE_PLAYER2_SOLDIER      (GAME_PROFILE_ARCADE.player_soldier[1])
#define PROFILE_PLAYER1_LIVES        (GAME_PROFILE_ARCADE.player_lives[0])
#define PROFILE_PLAYER2_LIVES        (GAME_PROFILE_ARCADE.player_lives[1])
#define PROFILE_ROM_WEAPON_SUBTYPE   (GAME_PROFILE_ARCADE.rom_weapon_subtype)
#define PROFILE_ROM_WEAPON_AMMO      (GAME_PROFILE_ARCADE.rom_weapon_ammo)
#define PROFILE_ROM_WEAPON_FLAG      (GAME_PROFILE_ARCADE.rom_weapon_flag)
#define PROFILE_BLOOD_WORD           (GAME_PROFILE_ARCADE.blood_word)
#define PROFILE_BLOOD_MASK           (GAME_PROFILE_ARCADE.blood_mask)
#define PROFILE_LOGO_FIRST           (GAME_PROFILE_ARCADE.logo_first)
#define PROFILE_LOGO_LAST            (GAME_PROFILE_ARCADE.logo_last)
#define PROFILE_LOGO_TM              (GAME_PROFILE_ARCADE.logo_tm)
#define PROFILE_LOGO_TM_TILE         (GAME_PROFILE_ARCADE.logo_tm_tile)
#define PROFILE_LOGO_MAX_FRAMES      (GAME_PROFILE_ARCADE.logo_max_frames)

#endif
