#ifndef RENDERER_H
#define RENDERER_H

#include <SDL3/SDL.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct Renderer Renderer;
typedef struct RenderTexture RenderTexture;

typedef enum {
    RENDER_FILTER_NEAREST,
    RENDER_FILTER_LINEAR,
    RENDER_FILTER_SHARP
} RenderFilter;

typedef struct {
    uint64_t frames;
    uint64_t encode_ns;
    uint64_t gpu_ns;
    uint64_t texture_uploads;
    uint64_t texture_upload_ns;
    uint64_t drawable_misses;
} RendererStats;

Renderer *renderer_create(SDL_Window *window, int vsync);
void renderer_destroy(Renderer *renderer);
const char *renderer_error(void);

void renderer_set_vsync(Renderer *renderer, int enabled);
void renderer_output_size(Renderer *renderer, int *width, int *height);
int renderer_begin(Renderer *renderer, uint8_t red, uint8_t green, uint8_t blue, uint8_t alpha);
void renderer_present(Renderer *renderer);
int renderer_save_png(Renderer *renderer, const char *path);
void renderer_get_stats(const Renderer *renderer, RendererStats *stats);

void renderer_set_transform(Renderer *renderer, float scale, float offset_x, float offset_y);
void renderer_set_scale(Renderer *renderer, float scale_x, float scale_y);
void renderer_set_color(Renderer *renderer, uint8_t red, uint8_t green, uint8_t blue, uint8_t alpha);
void renderer_fill_rect(Renderer *renderer, const SDL_FRect *rect);
void renderer_fill_rects(Renderer *renderer, const SDL_FRect *rects, int count);
void renderer_stroke_rect(Renderer *renderer, const SDL_FRect *rect);
void renderer_debug_text(Renderer *renderer, float x, float y, const char *text);

RenderTexture *renderer_texture_create(Renderer *renderer, int width, int height,
                                       const void *pixels, int pitch);
void renderer_texture_destroy(RenderTexture *texture);
int renderer_texture_update(RenderTexture *texture, const void *pixels, int pitch);
void renderer_texture_size(const RenderTexture *texture, float *width, float *height);
void renderer_texture_set_filter(RenderTexture *texture, RenderFilter filter);
void renderer_draw_texture(Renderer *renderer, RenderTexture *texture,
                           const SDL_FRect *source, const SDL_FRect *destination);

#ifdef __cplusplus
}
#endif

#endif
