#import <Metal/Metal.h>

#include "mac_capabilities.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <sys/sysctl.h>

static int read_sysctl(const char *name, void *output, size_t size)
{
    size_t length = size;
    return sysctlbyname(name, output, &length, nullptr, 0) == 0;
}

static void read_sysctl_string(const char *name, char *output, size_t size)
{
    if (!read_sysctl(name, output, size)) snprintf(output, size, "unknown");
    output[size - 1] = '\0';
}

int mac_chip_generation(const char *chip_name)
{
    if (!chip_name) return 0;
    const char *apple = strstr(chip_name, "Apple M");
    if (!apple) return 0;
    const char *number = apple + strlen("Apple M");
    if (!isdigit((unsigned char)*number)) return 0;
    int generation = 0;
    while (isdigit((unsigned char)*number)) {
        generation = generation * 10 + (*number - '0');
        number++;
    }
    return generation;
}

static int apple_gpu_family(id<MTLDevice> device)
{
    static const MTLGPUFamily FAMILIES[] = {
        MTLGPUFamilyApple10, MTLGPUFamilyApple9, MTLGPUFamilyApple8, MTLGPUFamilyApple7,
        MTLGPUFamilyApple6, MTLGPUFamilyApple5, MTLGPUFamilyApple4, MTLGPUFamilyApple3,
        MTLGPUFamilyApple2, MTLGPUFamilyApple1,
    };
    for (MTLGPUFamily family : FAMILIES)
        if ([device supportsFamily:family]) return (int)family - 1000;
    return 0;
}

void mac_capabilities_detect(MacCapabilities *capabilities)
{
    memset(capabilities, 0, sizeof *capabilities);
    read_sysctl_string("machdep.cpu.brand_string", capabilities->chip_name,
                       sizeof capabilities->chip_name);
    read_sysctl_string("hw.model", capabilities->model, sizeof capabilities->model);
    read_sysctl("hw.memsize", &capabilities->memory_bytes, sizeof capabilities->memory_bytes);
    read_sysctl("hw.physicalcpu", &capabilities->physical_cores,
                sizeof capabilities->physical_cores);
    if (!read_sysctl("hw.perflevel0.physicalcpu", &capabilities->performance_cores,
                     sizeof capabilities->performance_cores))
        capabilities->performance_cores = capabilities->physical_cores;
    capabilities->marketing_generation = mac_chip_generation(capabilities->chip_name);

    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    if (device) {
        snprintf(capabilities->gpu_name, sizeof capabilities->gpu_name, "%s",
                 device.name.UTF8String);
        capabilities->metal_apple_family = apple_gpu_family(device);
        capabilities->unified_memory = device.hasUnifiedMemory;
        capabilities->argument_buffers_tier = (int)device.argumentBuffersSupport;
        capabilities->metal_max_buffer_length = device.maxBufferLength;
    } else {
        snprintf(capabilities->gpu_name, sizeof capabilities->gpu_name, "unavailable");
    }

    /* Three drawables measured best for stable ProMotion pacing and is supported by macOS 13.
       No chip-name-specific path is selected for this 2D workload. */
    capabilities->recommended_frames_in_flight = 3;
}

void mac_capabilities_print(const MacCapabilities *capabilities, FILE *stream)
{
    fprintf(stream,
            "Apple Silicon: %s (%s), %d cores (%d performance), %.1f GiB\n"
            "Metal: %s, Apple family %d, unified memory %s, argument buffers tier %d, "
            "max buffer %.1f MiB, %d frames in flight\n",
            capabilities->chip_name, capabilities->model, capabilities->physical_cores,
            capabilities->performance_cores,
            capabilities->memory_bytes / (1024.0 * 1024.0 * 1024.0),
            capabilities->gpu_name, capabilities->metal_apple_family,
            capabilities->unified_memory ? "yes" : "no",
            capabilities->argument_buffers_tier,
            capabilities->metal_max_buffer_length / (1024.0 * 1024.0),
            capabilities->recommended_frames_in_flight);
}
