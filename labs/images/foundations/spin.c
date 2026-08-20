/* Busy-loop in N threads for a fixed time, sharing one address space.
 *
 * Exists because threads cannot be demonstrated from a shell. Background jobs
 * are separate processes with separate address spaces; the whole point of a
 * thread is that it is a schedulable entity sharing memory with its siblings,
 * and only a real pthread shows that in /proc/PID/task.
 *
 * Each thread also touches a shared counter without a lock, so a lab can
 * observe a lost update rather than be told about one.
 *
 *   spin <threads> <seconds>
 */
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>

static volatile long shared_counter = 0;
static long per_thread_increments = 0;
static int run_seconds = 3;

static long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void *worker(void *arg) {
    long id = (long)arg;
    /* gettid has no glibc wrapper on every version we target, so ask the kernel
     * directly. This is the number that appears in /proc/PID/task. */
    long tid = syscall(SYS_gettid);
    printf("thread %ld tid=%ld\n", id, tid);
    fflush(stdout);

    long deadline = now_ms() + run_seconds * 1000;
    long local = 0;
    while (now_ms() < deadline) {
        for (int i = 0; i < 100000; i++) {
            /* Deliberately unsynchronised: read, add, write. With several
             * threads the increments interleave and updates are lost, which is
             * the point being demonstrated. */
            shared_counter = shared_counter + 1;
        }
        local += 100000;
    }
    __atomic_add_fetch(&per_thread_increments, local, __ATOMIC_SEQ_CST);
    return NULL;
}

int main(int argc, char **argv) {
    int threads = (argc > 1) ? atoi(argv[1]) : 2;
    run_seconds = (argc > 2) ? atoi(argv[2]) : 3;
    if (threads < 1) threads = 1;
    if (threads > 64) threads = 64;

    printf("main pid=%d spawning %d threads for %ds\n", getpid(), threads, run_seconds);
    fflush(stdout);

    pthread_t *ids = calloc((size_t)threads, sizeof(pthread_t));
    for (long i = 0; i < threads; i++) {
        pthread_create(&ids[i], NULL, worker, (void *)i);
    }
    for (int i = 0; i < threads; i++) {
        pthread_join(ids[i], NULL);
    }

    printf("increments attempted: %ld\n", per_thread_increments);
    printf("shared counter:       %ld\n", shared_counter);
    printf("lost updates:         %ld\n", per_thread_increments - shared_counter);
    free(ids);
    return 0;
}
