#include "benchmark.h"

#include <time.h>

NgBenchmark ng_benchmark;

uint64_t ng_benchmark_now(void)
{
    return clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
}

void ng_benchmark_reset(int enabled)
{
    ng_benchmark = (NgBenchmark){.enabled = enabled};
}
