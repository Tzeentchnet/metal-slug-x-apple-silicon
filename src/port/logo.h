/* Game title screen logo for the start menu (Phase 6C). */
#ifndef LOGO_H
#define LOGO_H

#include "renderer.h"

/* Loads the logo from `cache` (PNG in the user's folder) or, if it does not exist, generates it:
 * runs the machine silently up to the title screen, redraws only the logo sprites and saves it.
 * The machine goes back exactly to the state it was in. Returns 0 if there is a logo. */
int logo_prepare(Renderer *r, const char *cache);
RenderTexture *logo_texture(void);       /* NULL if there is no logo */
void logo_destroy(void);

#endif
