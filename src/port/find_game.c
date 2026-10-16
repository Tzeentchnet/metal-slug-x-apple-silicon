/* Bundle-aware places to look for the user's arcade ROM set on macOS. */
#include "port.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

typedef struct {
    char (*list)[1024];
    int count;
    int capacity;
} Places;

static int exists(const char *path)
{
    struct stat info;
    return stat(path, &info) == 0;
}

static void add(Places *places, const char *path)
{
    if (!exists(path)) return;
    for (int i = 0; i < places->count; i++)
        if (!strcmp(places->list[i], path)) return;
    if (places->count < places->capacity)
        snprintf(places->list[places->count++], 1024, "%s", path);
}

int game_places(const char *executable_dir, char (*list)[1024], int max)
{
    Places places = {list, 0, max};
    char path[1100];

    snprintf(path, sizeof path, "%s../Resources/game", executable_dir);
    add(&places, path);
    snprintf(path, sizeof path, "%s../../../game", executable_dir);
    add(&places, path);
    snprintf(path, sizeof path, "%sgame", executable_dir);
    add(&places, path);
    add(&places, "game");
    add(&places, "roms");

    return places.count;
}
