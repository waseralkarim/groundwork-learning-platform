/* Allocate and touch memory, then fork children that share it.
 *
 * Exists to make RSS double-counting visible. After the fork, every child maps
 * the same physical pages copy-on-write, so each one reports the full amount as
 * resident — and summing RSS across them produces a number several times larger
 * than the memory actually in use. PSS divides each shared page between its
 * sharers and comes out right.
 *
 * Written in C because this cannot be shown from a shell: the demonstration
 * depends on a real fork sharing real page-table entries.
 *
 *   share-pages <megabytes> <children>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>

int main(int argc, char **argv) {
    size_t mb = (argc > 1) ? (size_t)atoi(argv[1]) : 50;
    int children = (argc > 2) ? atoi(argv[2]) : 4;
    size_t bytes = mb * 1024 * 1024;

    char *block = malloc(bytes);
    if (!block) {
        fprintf(stderr, "share-pages: could not allocate %zu MB\n", mb);
        return 1;
    }

    /* Touch every page so it is genuinely resident before forking. An untouched
     * mapping would share nothing, because there is nothing there yet. */
    for (size_t i = 0; i < bytes; i += 4096) {
        block[i] = (char)(i & 0xff);
    }

    printf("parent %d holding %zu MB\n", getpid(), mb);
    fflush(stdout);

    for (int i = 0; i < children; i++) {
        pid_t pid = fork();
        if (pid == 0) {
            /* Read the block so the child definitely maps it, but never write:
             * a write would trigger copy-on-write and the pages would stop
             * being shared, which is the opposite of the point. */
            volatile char sink = 0;
            for (size_t j = 0; j < bytes; j += 4096) {
                sink = block[j];
            }
            (void)sink;
            printf("child %d sharing\n", getpid());
            fflush(stdout);
            pause();
            _exit(0);
        }
    }

    printf("ready\n");
    fflush(stdout);
    pause();
    return 0;
}
