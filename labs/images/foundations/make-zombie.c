/* Creates a zombie deliberately, for the Processes topic.
 *
 * In C rather than shell because bash reaps its own background children
 * automatically — `( exit 0 ) &` never leaves a zombie behind. A zombie needs a
 * parent that forks and genuinely never calls wait(), which is exactly the bug
 * this lab teaches.
 */
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>

int main(void) {
    pid_t pid = fork();
    if (pid < 0) { perror("fork"); return 1; }

    if (pid == 0) {
        /* The child exits at once. Its exit status now sits in the process
         * table waiting for a parent that will never collect it. */
        _exit(0);
    }

    printf("parent %d forked child %d and will never reap it\n", getpid(), pid);
    printf("find it with: ps -eo pid,ppid,stat,comm | awk '$3 ~ /^Z/'\n");
    fflush(stdout);

    for (;;) sleep(3600);   /* deliberately never calls wait() */
    return 0;
}
