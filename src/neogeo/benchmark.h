#ifndef NG_BENCHMARK_H
#define NG_BENCHMARK_H

#include <stdint.h>

typedef struct {
    int enabled;
    uint64_t frames;
    uint64_t frame_ns;
    uint64_t video_ns;
    uint64_t audio_ns;
} NgBenchmark;

extern NgBenchmark ng_benchmark;

uint64_t ng_benchmark_now(void);
void ng_benchmark_reset(int enabled);

#endif
