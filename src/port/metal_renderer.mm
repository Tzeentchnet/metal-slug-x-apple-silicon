#import <CoreGraphics/CoreGraphics.h>
#import <CoreText/CoreText.h>
#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
#import <SDL3/SDL.h>
#import <SDL3/SDL_metal.h>

#include "renderer.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <new>
#include <simd/simd.h>
#include <string>
#include <vector>

struct RenderTexture {
    id<MTLTexture> texture;
    Renderer *owner;
    int width;
    int height;
    RenderFilter filter;
};

struct Renderer {
    SDL_Window *window;
    SDL_MetalView view;
    CAMetalLayer *layer;
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLRenderPipelineState> pipeline;
    id<MTLSamplerState> nearest;
    id<MTLSamplerState> linear;
    id<CAMetalDrawable> drawable;
    id<MTLCommandBuffer> command;
    id<MTLRenderCommandEncoder> encoder;
    RenderTexture *white;
    RenderTexture *debug_font;
    simd_float4 color;
    float scale_x;
    float scale_y;
    float offset_x;
    float offset_y;
    int output_width;
    int output_height;
    int stats_enabled;
    uint64_t frame_started_ns;
    RendererStats stats;
};

struct Vertex {
    simd_float2 position;
    simd_float2 texel;
    simd_float4 color;
};

struct FragmentParams {
    simd_float2 texture_size;
    simd_float2 source_origin;
    simd_float2 source_size;
    uint32_t mode;
    float sharp_scale;
};

static char last_error[1024];

static void set_error(const char *message)
{
    snprintf(last_error, sizeof last_error, "%s", message ? message : "unknown renderer error");
}

static void set_error(NSString *message)
{
    set_error(message ? message.UTF8String : "unknown Metal error");
}

const char *renderer_error(void)
{
    return last_error;
}

static const char *SHADERS = R"METAL(
#include <metal_stdlib>
using namespace metal;

struct Vertex {
    float2 position;
    float2 texel;
    float4 color;
};

struct VertexOut {
    float4 position [[position]];
    float2 texel;
    float4 color;
};

struct FragmentParams {
    float2 texture_size;
    float2 source_origin;
    float2 source_size;
    uint mode;
    float sharp_scale;
};

vertex VertexOut vertex_main(const device Vertex *vertices [[buffer(0)]],
                             constant float2 &output_size [[buffer(1)]],
                             uint vertex_id [[vertex_id]])
{
    Vertex v = vertices[vertex_id];
    VertexOut out;
    out.position = float4(v.position.x * 2.0 / output_size.x - 1.0,
                          1.0 - v.position.y * 2.0 / output_size.y, 0.0, 1.0);
    out.texel = v.texel;
    out.color = v.color;
    return out;
}

fragment float4 fragment_main(VertexOut in [[stage_in]],
                              texture2d<float, access::sample> texture [[texture(0)]],
                              sampler nearest_sampler [[sampler(0)]],
                              sampler linear_sampler [[sampler(1)]],
                              constant FragmentParams &params [[buffer(0)]])
{
    float4 sample;
    if (params.mode == 2) {
        float scale = params.sharp_scale;
        float2 intermediate_size = params.source_size * scale;
        float2 q = (in.texel - params.source_origin) * scale - 0.5;
        float2 base = floor(q);
        float2 fraction = fract(q);
        int2 hi = int2(max(intermediate_size - 1.0, 0.0));
        int2 a = clamp(int2(base), int2(0), hi);
        int2 b = clamp(a + int2(1, 0), int2(0), hi);
        int2 c = clamp(a + int2(0, 1), int2(0), hi);
        int2 d = clamp(a + int2(1, 1), int2(0), hi);
        uint2 origin = uint2(params.source_origin);
        uint2 pa = origin + uint2(a) / uint(scale);
        uint2 pb = origin + uint2(b) / uint(scale);
        uint2 pc = origin + uint2(c) / uint(scale);
        uint2 pd = origin + uint2(d) / uint(scale);
        float4 top = mix(texture.read(pa), texture.read(pb), fraction.x);
        float4 bottom = mix(texture.read(pc), texture.read(pd), fraction.x);
        sample = mix(top, bottom, fraction.y);
    } else if (params.mode == 1) {
        float2 uv = in.texel / params.texture_size;
        sample = texture.sample(linear_sampler, uv);
    } else {
        int2 high = int2(params.texture_size) - 1;
        float2 pixel = float2(clamp(int2(floor(in.texel)), int2(0), high)) + 0.5;
        sample = texture.sample(nearest_sampler, pixel / params.texture_size);
    }
    return sample * in.color;
}
)METAL";

static id<MTLSamplerState> make_sampler(id<MTLDevice> device, MTLSamplerMinMagFilter filter)
{
    MTLSamplerDescriptor *descriptor = [[MTLSamplerDescriptor alloc] init];
    descriptor.minFilter = filter;
    descriptor.magFilter = filter;
    descriptor.sAddressMode = MTLSamplerAddressModeClampToEdge;
    descriptor.tAddressMode = MTLSamplerAddressModeClampToEdge;
    return [device newSamplerStateWithDescriptor:descriptor];
}

static RenderTexture *make_texture(Renderer *renderer, int width, int height,
                                   const void *pixels, int pitch)
{
    if (width <= 0 || height <= 0) {
        set_error("texture dimensions must be positive");
        return nullptr;
    }
    MTLTextureDescriptor *descriptor =
        [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                           width:(NSUInteger)width
                                                          height:(NSUInteger)height
                                                       mipmapped:NO];
    descriptor.usage = MTLTextureUsageShaderRead;
    id<MTLTexture> metal_texture = [renderer->device newTextureWithDescriptor:descriptor];
    if (!metal_texture) {
        set_error("Metal could not allocate a texture");
        return nullptr;
    }
    RenderTexture *texture = new (std::nothrow) RenderTexture{
        metal_texture, renderer, width, height, RENDER_FILTER_NEAREST
    };
    if (!texture) {
        set_error("out of memory while creating a texture");
        return nullptr;
    }
    if (pixels && renderer_texture_update(texture, pixels, pitch) != 0) {
        delete texture;
        return nullptr;
    }
    return texture;
}

static RenderTexture *make_debug_font(Renderer *renderer)
{
    const int width = 128;
    const int height = 60;
    std::vector<uint32_t> pixels((size_t)width * height);
    CGColorSpaceRef color_space = CGColorSpaceCreateDeviceRGB();
    CTFontRef font = CTFontCreateWithName(CFSTR("Menlo"), 8.0, nullptr);
    for (int c = 0x20; c < 0x80; c++) {
        uint32_t cell[8 * 10] = {};
        CGContextRef context = CGBitmapContextCreate(cell, 8, 10, 8, 8 * 4,
                                                     color_space,
                                                     kCGImageAlphaPremultipliedLast |
                                                     kCGBitmapByteOrder32Big);
        if (!context) continue;
        CGContextSetShouldAntialias(context, false);
        CGContextSetRGBFillColor(context, 1, 1, 1, 1);
        UniChar character = (UniChar)c;
        CGGlyph glyph = 0;
        if (CTFontGetGlyphsForCharacters(font, &character, &glyph, 1)) {
            CGRect bounds = CTFontGetBoundingRectsForGlyphs(font, kCTFontOrientationDefault,
                                                            &glyph, nullptr, 1);
            CGPoint point = CGPointMake(floor((8 - bounds.size.width) / 2 - bounds.origin.x),
                                        floor((10 - bounds.size.height) / 2 - bounds.origin.y));
            CTFontDrawGlyphs(font, &glyph, &point, 1, context);
            int ox = (c - 0x20) % 16 * 8;
            int oy = (c - 0x20) / 16 * 10;
            for (int y = 0; y < 10; y++)
                memcpy(&pixels[(size_t)(oy + y) * width + ox],
                       &cell[(size_t)y * 8], 8 * sizeof(uint32_t));
        }
        CGContextRelease(context);
    }
    CFRelease(font);
    CGColorSpaceRelease(color_space);
    return make_texture(renderer, width, height, pixels.data(), width * 4);
}

Renderer *renderer_create(SDL_Window *window, int vsync)
{
    last_error[0] = '\0';
    Renderer *renderer = new (std::nothrow) Renderer{};
    if (!renderer) {
        set_error("out of memory while creating the Metal renderer");
        return nullptr;
    }
    renderer->window = window;
    renderer->stats_enabled = getenv("PD_BENCHMARK") != nullptr;
    renderer->view = SDL_Metal_CreateView(window);
    if (!renderer->view) {
        set_error(SDL_GetError());
        delete renderer;
        return nullptr;
    }
    renderer->layer = (__bridge CAMetalLayer *)SDL_Metal_GetLayer(renderer->view);
    renderer->device = MTLCreateSystemDefaultDevice();
    if (!renderer->layer || !renderer->device) {
        set_error("Metal is unavailable on this Mac");
        renderer_destroy(renderer);
        return nullptr;
    }
    renderer->layer.device = renderer->device;
    renderer->layer.pixelFormat = MTLPixelFormatBGRA8Unorm;
    renderer->layer.framebufferOnly = NO;
    renderer->layer.maximumDrawableCount = 3;
    renderer_set_vsync(renderer, vsync);

    renderer->queue = [renderer->device newCommandQueue];
    NSError *library_error = nil;
    NSString *shader_source = [NSString stringWithUTF8String:SHADERS];
    id<MTLLibrary> library = [renderer->device newLibraryWithSource:shader_source
                                                            options:nil
                                                              error:&library_error];
    if (!library) {
        set_error(library_error.localizedDescription);
        renderer_destroy(renderer);
        return nullptr;
    }
    MTLRenderPipelineDescriptor *pipeline_descriptor = [[MTLRenderPipelineDescriptor alloc] init];
    pipeline_descriptor.vertexFunction = [library newFunctionWithName:@"vertex_main"];
    pipeline_descriptor.fragmentFunction = [library newFunctionWithName:@"fragment_main"];
    pipeline_descriptor.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    pipeline_descriptor.colorAttachments[0].blendingEnabled = YES;
    pipeline_descriptor.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
    pipeline_descriptor.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
    pipeline_descriptor.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
    pipeline_descriptor.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
    NSError *pipeline_error = nil;
    renderer->pipeline = [renderer->device newRenderPipelineStateWithDescriptor:pipeline_descriptor
                                                                           error:&pipeline_error];
    renderer->nearest = make_sampler(renderer->device, MTLSamplerMinMagFilterNearest);
    renderer->linear = make_sampler(renderer->device, MTLSamplerMinMagFilterLinear);
    if (!renderer->queue || !renderer->pipeline || !renderer->nearest || !renderer->linear) {
        set_error(pipeline_error ? pipeline_error.localizedDescription :
                                   @"Metal pipeline creation failed");
        renderer_destroy(renderer);
        return nullptr;
    }
    const uint32_t white = 0xFFFFFFFFu;
    renderer->white = make_texture(renderer, 1, 1, &white, 4);
    renderer->debug_font = make_debug_font(renderer);
    if (!renderer->white || !renderer->debug_font) {
        renderer_destroy(renderer);
        return nullptr;
    }
    renderer_set_color(renderer, 255, 255, 255, 255);
    renderer_set_transform(renderer, 1, 0, 0);
    return renderer;
}

void renderer_destroy(Renderer *renderer)
{
    if (!renderer) return;
    renderer_texture_destroy(renderer->debug_font);
    renderer_texture_destroy(renderer->white);
    renderer->encoder = nil;
    renderer->command = nil;
    renderer->drawable = nil;
    if (renderer->view) SDL_Metal_DestroyView(renderer->view);
    delete renderer;
}

void renderer_set_vsync(Renderer *renderer, int enabled)
{
    if (renderer && [renderer->layer respondsToSelector:@selector(setDisplaySyncEnabled:)])
        renderer->layer.displaySyncEnabled = enabled != 0;
}

void renderer_output_size(Renderer *renderer, int *width, int *height)
{
    int w = 0, h = 0;
    if (renderer) SDL_GetWindowSizeInPixels(renderer->window, &w, &h);
    if (width) *width = w;
    if (height) *height = h;
}

int renderer_begin(Renderer *renderer, uint8_t red, uint8_t green, uint8_t blue, uint8_t alpha)
{
    if (!renderer || renderer->encoder) {
        set_error("invalid Metal frame state");
        return -1;
    }
    int width, height;
    renderer_output_size(renderer, &width, &height);
    if (width <= 0 || height <= 0) return 1;
    renderer->layer.drawableSize = CGSizeMake(width, height);
    renderer->output_width = width;
    renderer->output_height = height;
    renderer->drawable = [renderer->layer nextDrawable];
    if (!renderer->drawable) {
        if (renderer->stats_enabled) renderer->stats.drawable_misses++;
        set_error("Metal could not acquire a drawable");
        return 1;
    }
    renderer->command = [renderer->queue commandBuffer];
    renderer->frame_started_ns = renderer->stats_enabled ? SDL_GetTicksNS() : 0;
    MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
    pass.colorAttachments[0].texture = renderer->drawable.texture;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    pass.colorAttachments[0].clearColor =
        MTLClearColorMake(red / 255.0, green / 255.0, blue / 255.0, alpha / 255.0);
    renderer->encoder = [renderer->command renderCommandEncoderWithDescriptor:pass];
    [renderer->encoder setRenderPipelineState:renderer->pipeline];
    [renderer->encoder setFragmentSamplerState:renderer->nearest atIndex:0];
    [renderer->encoder setFragmentSamplerState:renderer->linear atIndex:1];
    renderer_set_transform(renderer, 1, 0, 0);
    return 0;
}

static void finish_frame(Renderer *renderer, int present)
{
    if (!renderer || !renderer->command) return;
    if (renderer->encoder) {
        [renderer->encoder endEncoding];
        renderer->encoder = nil;
    }
    if (present && renderer->drawable) [renderer->command presentDrawable:renderer->drawable];
    [renderer->command commit];
}

void renderer_present(Renderer *renderer)
{
    if (!renderer || !renderer->command) return;
    uint64_t encoded = renderer->stats_enabled ? SDL_GetTicksNS() : 0;
    finish_frame(renderer, 1);
    if (renderer->stats_enabled) {
        renderer->stats.encode_ns += encoded - renderer->frame_started_ns;
        [renderer->command waitUntilCompleted];
        if (renderer->command.GPUEndTime >= renderer->command.GPUStartTime)
            renderer->stats.gpu_ns +=
                (uint64_t)((renderer->command.GPUEndTime - renderer->command.GPUStartTime) * 1e9);
        renderer->stats.frames++;
    }
    renderer->command = nil;
    renderer->drawable = nil;
}

void renderer_get_stats(const Renderer *renderer, RendererStats *stats)
{
    if (stats) *stats = renderer ? renderer->stats : RendererStats{};
}

int renderer_save_png(Renderer *renderer, const char *path)
{
    if (!renderer || !renderer->command || !renderer->drawable) {
        set_error("no Metal frame is available to capture");
        return -1;
    }
    id<MTLTexture> texture = renderer->drawable.texture;
    finish_frame(renderer, 1);
    [renderer->command waitUntilCompleted];
    if (renderer->command.error) {
        set_error(renderer->command.error.localizedDescription);
        renderer->command = nil;
        renderer->drawable = nil;
        return -1;
    }
    const int width = renderer->output_width;
    const int height = renderer->output_height;
    std::vector<uint32_t> pixels((size_t)width * height);
    [texture getBytes:pixels.data()
          bytesPerRow:(NSUInteger)width * 4
           fromRegion:MTLRegionMake2D(0, 0, width, height)
          mipmapLevel:0];
    SDL_Surface *surface = SDL_CreateSurfaceFrom(width, height, SDL_PIXELFORMAT_BGRA32,
                                                 pixels.data(), width * 4);
    int result = surface && SDL_SavePNG(surface, path) ? 0 : -1;
    if (surface) SDL_DestroySurface(surface);
    if (result != 0) set_error(SDL_GetError());
    renderer->command = nil;
    renderer->drawable = nil;
    return result;
}

void renderer_set_transform(Renderer *renderer, float scale, float offset_x, float offset_y)
{
    if (!renderer) return;
    renderer->scale_x = scale;
    renderer->scale_y = scale;
    renderer->offset_x = offset_x;
    renderer->offset_y = offset_y;
}

void renderer_set_scale(Renderer *renderer, float scale_x, float scale_y)
{
    if (!renderer) return;
    renderer->scale_x = scale_x;
    renderer->scale_y = scale_y;
    renderer->offset_x = 0;
    renderer->offset_y = 0;
}

void renderer_set_color(Renderer *renderer, uint8_t red, uint8_t green, uint8_t blue, uint8_t alpha)
{
    if (!renderer) return;
    renderer->color = simd_make_float4(red / 255.0f, green / 255.0f,
                                       blue / 255.0f, alpha / 255.0f);
}

static void draw(Renderer *renderer, RenderTexture *texture,
                 const SDL_FRect *source, const SDL_FRect *destination, simd_float4 color)
{
    if (!renderer || !renderer->encoder || !texture || !destination) return;
    SDL_FRect src = source ? *source :
        SDL_FRect{0, 0, (float)texture->width, (float)texture->height};
    float x0 = destination->x * renderer->scale_x + renderer->offset_x;
    float y0 = destination->y * renderer->scale_y + renderer->offset_y;
    float x1 = (destination->x + destination->w) * renderer->scale_x + renderer->offset_x;
    float y1 = (destination->y + destination->h) * renderer->scale_y + renderer->offset_y;
    Vertex vertices[4] = {
        {{x0, y0}, {src.x, src.y}, color},
        {{x1, y0}, {src.x + src.w, src.y}, color},
        {{x0, y1}, {src.x, src.y + src.h}, color},
        {{x1, y1}, {src.x + src.w, src.y + src.h}, color},
    };
    float ratio = std::max((x1 - x0) / src.w, (y1 - y0) / src.h);
    float sharp_scale = std::clamp(std::ceil(ratio), 1.0f, 8.0f);
    FragmentParams params = {
        {(float)texture->width, (float)texture->height},
        {src.x, src.y},
        {src.w, src.h},
        (uint32_t)texture->filter,
        sharp_scale
    };
    simd_float2 output = {(float)renderer->output_width, (float)renderer->output_height};
    [renderer->encoder setVertexBytes:vertices length:sizeof vertices atIndex:0];
    [renderer->encoder setVertexBytes:&output length:sizeof output atIndex:1];
    [renderer->encoder setFragmentTexture:texture->texture atIndex:0];
    [renderer->encoder setFragmentBytes:&params length:sizeof params atIndex:0];
    [renderer->encoder drawPrimitives:MTLPrimitiveTypeTriangleStrip vertexStart:0 vertexCount:4];
}

void renderer_fill_rect(Renderer *renderer, const SDL_FRect *rect)
{
    if (!renderer) return;
    SDL_FRect full = {
        -renderer->offset_x / renderer->scale_x,
        -renderer->offset_y / renderer->scale_y,
        renderer->output_width / renderer->scale_x,
        renderer->output_height / renderer->scale_y
    };
    draw(renderer, renderer->white, nullptr, rect ? rect : &full, renderer->color);
}

void renderer_fill_rects(Renderer *renderer, const SDL_FRect *rects, int count)
{
    for (int i = 0; i < count; i++) renderer_fill_rect(renderer, &rects[i]);
}

void renderer_stroke_rect(Renderer *renderer, const SDL_FRect *rect)
{
    if (!renderer || !rect) return;
    float sx = 1.0f / renderer->scale_x;
    float sy = 1.0f / renderer->scale_y;
    SDL_FRect sides[4] = {
        {rect->x, rect->y, rect->w, sy},
        {rect->x, rect->y + rect->h - sy, rect->w, sy},
        {rect->x, rect->y, sx, rect->h},
        {rect->x + rect->w - sx, rect->y, sx, rect->h}
    };
    renderer_fill_rects(renderer, sides, 4);
}

void renderer_debug_text(Renderer *renderer, float x, float y, const char *text)
{
    if (!renderer || !text) return;
    for (; *text; text++, x += 8) {
        int c = (unsigned char)*text;
        if (c < 0x20 || c > 0x7f) c = '?';
        c -= 0x20;
        if (!c) continue;
        SDL_FRect source = {(float)(c % 16) * 8, (float)(c / 16) * 10, 8, 10};
        SDL_FRect destination = {x, y, 8, 10};
        draw(renderer, renderer->debug_font, &source, &destination, renderer->color);
    }
}

RenderTexture *renderer_texture_create(Renderer *renderer, int width, int height,
                                       const void *pixels, int pitch)
{
    return renderer ? make_texture(renderer, width, height, pixels, pitch) : nullptr;
}

void renderer_texture_destroy(RenderTexture *texture)
{
    delete texture;
}

int renderer_texture_update(RenderTexture *texture, const void *pixels, int pitch)
{
    if (!texture || !pixels || pitch < texture->width * 4) {
        set_error("invalid texture update");
        return -1;
    }
    uint64_t started = texture->owner->stats_enabled ? SDL_GetTicksNS() : 0;
    [texture->texture replaceRegion:MTLRegionMake2D(0, 0, texture->width, texture->height)
                        mipmapLevel:0
                          withBytes:pixels
                        bytesPerRow:(NSUInteger)pitch];
    if (texture->owner->stats_enabled) {
        texture->owner->stats.texture_upload_ns += SDL_GetTicksNS() - started;
        texture->owner->stats.texture_uploads++;
    }
    return 0;
}

void renderer_texture_size(const RenderTexture *texture, float *width, float *height)
{
    if (width) *width = texture ? (float)texture->width : 0;
    if (height) *height = texture ? (float)texture->height : 0;
}

void renderer_texture_set_filter(RenderTexture *texture, RenderFilter filter)
{
    if (texture) texture->filter = filter;
}

void renderer_draw_texture(Renderer *renderer, RenderTexture *texture,
                           const SDL_FRect *source, const SDL_FRect *destination)
{
    if (!renderer || !texture) return;
    SDL_FRect full = {
        -renderer->offset_x / renderer->scale_x,
        -renderer->offset_y / renderer->scale_y,
        renderer->output_width / renderer->scale_x,
        renderer->output_height / renderer->scale_y
    };
    draw(renderer, texture, source, destination ? destination : &full,
         simd_make_float4(1, 1, 1, 1));
}
