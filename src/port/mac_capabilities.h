#ifndef MAC_CAPABILITIES_H
#define MAC_CAPABILITIES_H

#include <stdint.h>
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    char chip_name[96];
    char model[96];
    char gpu_name[128];
    uint64_t memory_bytes;
    uint64_t metal_max_buffer_length;
    int physical_cores;
    int performance_cores;
    int marketing_generation;
    int metal_apple_family;
    int unified_memory;
    int argument_buffers_tier;
    int recommended_frames_in_flight;
} MacCapabilities;

/* Marketing generation is diagnostic only; runtime decisions use queried capabilities. */
int mac_chip_generation(const char *chip_name);
void mac_capabilities_detect(MacCapabilities *capabilities);
void mac_capabilities_print(const MacCapabilities *capabilities, FILE *stream);

#ifdef __cplusplus
}
#endif

#endif
