/* TC-TM002-LIMIT-01: invoke the production preview algorithm with test adapters. */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static int test_clock_gettime(clockid_t clock, struct timespec *result);
static int test_open(const char *path, int flags);
static int test_openat(int fd, const char *path, int flags);
static ssize_t test_read(int fd, void *buffer, size_t count);
static int test_fstat(int fd, struct stat *metadata);
static int test_dup(int fd);
static int test_close(int fd);
static DIR *test_fdopendir(int fd);
static struct dirent *test_readdir(DIR *stream);
static int test_closedir(DIR *stream);
static int test_fstatat(int fd, const char *name, struct stat *metadata, int flags);

#define clock_gettime test_clock_gettime
#define open test_open
#define openat test_openat
#define read test_read
#define fstat test_fstat
#define dup test_dup
#define close test_close
#define fdopendir test_fdopendir
#define readdir test_readdir
#define closedir test_closedir
#define fstatat test_fstatat
#define main production_source_helper_main
#include "../native/source-helper.c"
#undef main
#undef close
#undef dup
#undef fstat
#undef read
#undef openat
#undef open
#undef fstatat
#undef closedir
#undef readdir
#undef fdopendir
#undef clock_gettime

typedef struct {
  unsigned int next;
  struct dirent entry;
} TestDirectory;

enum { SYNTHETIC_FD = 1234 };
static const char *const names[] = {"A1.jsonl", "A2.jsonl"};
static const int64_t ticks_ns[] = {0, 1999000000LL, 2001000000LL};
static unsigned int clock_calls;
static unsigned int open_calls;
static unsigned int openat_calls;
static unsigned int read_calls;
static unsigned int fstat_calls;
static unsigned int dup_calls;
static unsigned int close_calls;
static unsigned int directory_opens;
static unsigned int directory_closes;
static unsigned int readdir_calls;
static unsigned int stat_calls;
static unsigned int unexpected_calls;

static int test_clock_gettime(clockid_t clock, struct timespec *result) {
  if (clock != CLOCK_MONOTONIC || clock_calls >= sizeof(ticks_ns) / sizeof(ticks_ns[0])) {
    unexpected_calls++; errno = EINVAL; return -1;
  }
  int64_t tick = ticks_ns[clock_calls++];
  result->tv_sec = (time_t)(tick / 1000000000LL);
  result->tv_nsec = (long)(tick % 1000000000LL);
  return 0;
}

static int test_open(const char *path, int flags) {
  open_calls++;
  if (strcmp(path, "synthetic-root") != 0 ||
      flags != (O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC)) {
    unexpected_calls++; errno = ENOENT; return -1;
  }
  return SYNTHETIC_FD;
}

static int test_openat(int fd, const char *path, int flags) {
  (void)fd; (void)path; (void)flags;
  openat_calls++; unexpected_calls++; errno = EPERM; return -1;
}

static ssize_t test_read(int fd, void *buffer, size_t count) {
  (void)fd; (void)buffer; (void)count;
  read_calls++; unexpected_calls++; errno = EPERM; return -1;
}

static int test_fstat(int fd, struct stat *metadata) {
  fstat_calls++;
  if (fd != SYNTHETIC_FD) { unexpected_calls++; errno = EBADF; return -1; }
  memset(metadata, 0, sizeof(*metadata));
  metadata->st_mode = S_IFDIR | 0700;
  metadata->st_dev = root_dev;
  metadata->st_ino = root_ino;
  metadata->st_mtimespec.tv_sec = 1700000000;
  return 0;
}

static int test_dup(int fd) {
  dup_calls++;
  if (fd != SYNTHETIC_FD) { unexpected_calls++; errno = EBADF; return -1; }
  return SYNTHETIC_FD;
}

static int test_close(int fd) {
  close_calls++;
  if (fd != SYNTHETIC_FD) { unexpected_calls++; errno = EBADF; return -1; }
  return 0;
}

static DIR *test_fdopendir(int fd) {
  if (fd != SYNTHETIC_FD) { unexpected_calls++; errno = EBADF; return NULL; }
  TestDirectory *stream = calloc(1, sizeof(*stream));
  if (stream == NULL) return NULL;
  directory_opens++;
  return (DIR *)stream;
}

static struct dirent *test_readdir(DIR *opaque) {
  TestDirectory *stream = (TestDirectory *)opaque;
  readdir_calls++;
  if (stream->next >= sizeof(names) / sizeof(names[0])) return NULL;
  memset(&stream->entry, 0, sizeof(stream->entry));
  const char *name = names[stream->next++];
  memcpy(stream->entry.d_name, name, strlen(name) + 1);
  return &stream->entry;
}

static int test_closedir(DIR *opaque) {
  TestDirectory *stream = (TestDirectory *)opaque;
  free(stream);
  directory_closes++;
  return test_close(SYNTHETIC_FD);
}

static int test_fstatat(int fd, const char *name, struct stat *metadata, int flags) {
  (void)fd;
  stat_calls++;
  if (flags != AT_SYMLINK_NOFOLLOW || strcmp(name, names[0]) != 0) {
    unexpected_calls++; errno = ENOENT; return -1;
  }
  memset(metadata, 0, sizeof(*metadata));
  metadata->st_mode = S_IFREG | 0600;
  metadata->st_dev = root_dev;
  metadata->st_ino = 101;
  metadata->st_size = 25;
  metadata->st_mtimespec.tv_sec = 1700000000;
  metadata->st_mtimespec.tv_nsec = 123456789;
  return 0;
}

int main(void) {
  root_path = "synthetic-root";
  root_fd = SYNTHETIC_FD;
  root_dev = 7;
  root_ino = 77;
  preview_reply();
  fprintf(stderr,
    "HARNESS clock=%u open=%u openat=%u read=%u fstat=%u dup=%u close=%u fdopendir=%u readdir=%u fstatat=%u closedir=%u unexpected=%u names=2\n",
    clock_calls, open_calls, openat_calls, read_calls, fstat_calls, dup_calls,
    close_calls, directory_opens, readdir_calls, stat_calls, directory_closes, unexpected_calls);
  return clock_calls == 3 && open_calls == 2 && openat_calls == 0 && read_calls == 0 &&
    fstat_calls == 4 && dup_calls == 2 &&
    close_calls == 4 && directory_opens == 1 && readdir_calls == 1 &&
    stat_calls == 1 && directory_closes == 1 && unexpected_calls == 0 ? 0 : 5;
}
