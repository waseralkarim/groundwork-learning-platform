/* Allocates memory and holds it, for the Machine topic.
 *
 *   eat-memory <allocate_mb> [touch_mb]
 *
 * The second argument is the point. An allocation that is never written costs
 * no physical memory — the kernel does not back a page until something touches
 * it. So `eat-memory 400 50` reserves 400 MiB of address space and occupies
 * 50 MiB of RAM, which is exactly the VSZ-versus-RSS distinction the lab is
 * teaching. With one argument, everything is touched and the two are equal.
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    long alloc_mb = (argc > 1) ? atol(argv[1]) : 100;
    long touch_mb = (argc > 2) ? atol(argv[2]) : alloc_mb;
    if (touch_mb > alloc_mb) touch_mb = alloc_mb;

    size_t alloc_bytes = (size_t)alloc_mb * 1024 * 1024;
    size_t touch_bytes = (size_t)touch_mb * 1024 * 1024;

    char *block = malloc(alloc_bytes);
    if (!block) { fprintf(stderr, "malloc of %ld MiB failed\n", alloc_mb); return 1; }

    for (size_t i = 0; i < touch_bytes; i += 4096) block[i] = 1;

    printf("reserved %ld MiB (VSZ), touched %ld MiB (RSS)\n", alloc_mb, touch_mb);
    printf("only touched pages are backed by real memory\n");
    fflush(stdout);

    for (;;) sleep(3600);
    return 0;
}
