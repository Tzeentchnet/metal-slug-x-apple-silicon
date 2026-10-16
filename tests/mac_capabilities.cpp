#include "mac_capabilities.h"

#include <stdio.h>

int main(void)
{
    struct {
        const char *name;
        int expected;
    } cases[] = {
        {"Apple M1", 1},
        {"Apple M1 Pro", 1},
        {"Apple M3 Max", 3},
        {"Apple M5", 5},
        {"Apple M12 Ultra", 12},
        {"Apple Silicon", 0},
        {"Intel(R) Core(TM)", 0},
        {nullptr, 0},
    };
    for (const auto &test : cases) {
        int actual = mac_chip_generation(test.name);
        if (actual != test.expected) {
            fprintf(stderr, "generation(%s): expected %d, got %d\n",
                    test.name ? test.name : "null", test.expected, actual);
            return 1;
        }
    }
    return 0;
}
