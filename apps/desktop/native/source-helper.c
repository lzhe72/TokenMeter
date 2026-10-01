#include <CommonCrypto/CommonDigest.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifndef O_NOFOLLOW_ANY
#error macOS O_NOFOLLOW_ANY is required for the source helper
#endif

#define PREVIEW_DEPTH 8
#define PREVIEW_CANDIDATES 1000
#define PREVIEW_ENTRIES 5000
#define PREVIEW_NANOS 2000000000LL
#define PAGE_SIZE 256
#define READ_SIZE 65536
#define MAX_RELATIVE 65535
#define MAX_ROOT 4096

typedef struct {
  char *relative;
  struct stat metadata;
  unsigned char token[16];
} Candidate;
typedef struct {
  Candidate *items;
  size_t length;
  size_t capacity;
} CandidateList;
typedef struct {
  char *relative;
  struct stat metadata;
} DirectorySnapshot;
typedef struct {
  DirectorySnapshot *items;
  size_t length;
  size_t capacity;
} SnapshotList;
typedef struct {
  char *name;
  bool directory;
  struct stat metadata;
} DirectoryEntry;
typedef struct {
  DirectoryEntry *items;
  size_t length;
  size_t capacity;
} EntryList;
typedef struct {
  char *relative;
  int fd;
  DIR *stream;
  EntryList entries;
  size_t next_entry;
  size_t snapshot_index;
  bool ready;
} ScanFrame;
typedef struct {
  CandidateList candidates;
  SnapshotList directories;
  ScanFrame *frames;
  size_t frame_count;
  size_t frame_capacity;
  size_t delivered;
  bool active;
  bool complete;
} Scan;
typedef struct {
  CandidateList candidates;
  SnapshotList directories;
  unsigned int inspected_entries;
  const char *reason;
  struct timespec started;
} Preview;

static char *root_path = NULL;
static int root_fd = -1;
static dev_t root_dev;
static ino_t root_ino;
static Scan scan_state;
static const char *failure = NULL;
static bool emit_audit(const char *action, const char *kind, const char *relative, const struct stat *metadata);
static void free_entries(EntryList *list);

static void fail(const char *code) { if (failure == NULL) failure = code; }
static void error_reply(const char *code) { printf("ERR %s\n", code); fflush(stdout); }

static bool read_exact(int fd, void *target, size_t count) {
  unsigned char *cursor = target;
  while (count > 0) {
    ssize_t n = read(fd, cursor, count);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return false;
    cursor += n;
    count -= (size_t)n;
  }
  return true;
}

static bool write_exact(int fd, const void *source, size_t count) {
  const unsigned char *cursor = source;
  while (count > 0) {
    ssize_t n = write(fd, cursor, count);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return false;
    cursor += n;
    count -= (size_t)n;
  }
  return true;
}

static uint64_t be64(const unsigned char *bytes) {
  uint64_t value = 0;
  for (int i = 0; i < 8; i++) value = (value << 8) | bytes[i];
  return value;
}

static bool canonical_root_syntax(const char *path) {
  if (path[0] != '/') return false;
  if (path[1] == 0) return true;
  const char *component = path + 1;
  for (const char *cursor = component;; cursor++) {
    if (*cursor != '/' && *cursor != 0) continue;
    size_t length = (size_t)(cursor - component);
    if (length == 0 || (length == 1 && component[0] == '.') ||
        (length == 2 && component[0] == '.' && component[1] == '.')) return false;
    if (*cursor == 0) return true;
    component = cursor + 1;
  }
}

static bool safe_utf8(const unsigned char *text) {
  for (size_t i = 0; text[i] != 0;) {
    unsigned char a = text[i];
    if (a < 0x80) { i++; continue; }
    if (a < 0xc2 || a > 0xf4) return false;
    unsigned int need = a < 0xe0 ? 1 : a < 0xf0 ? 2 : 3;
    for (unsigned int j = 1; j <= need; j++) if (text[i + j] == 0 || (text[i + j] & 0xc0) != 0x80) return false;
    unsigned char b = text[i + 1];
    if ((a == 0xe0 && b < 0xa0) || (a == 0xed && b >= 0xa0) ||
        (a == 0xf0 && b < 0x90) || (a == 0xf4 && b >= 0x90)) return false;
    i += need + 1;
  }
  return true;
}

static char *copy_relative(const char *parent, const char *name) {
  size_t parent_len = strlen(parent), name_len = strlen(name);
  if (name_len == 0 || name_len > NAME_MAX || parent_len + name_len + (parent_len ? 1 : 0) > MAX_RELATIVE) {
    fail("path_too_long"); return NULL;
  }
  size_t length = parent_len + name_len + (parent_len ? 1 : 0);
  char *result = malloc(length + 1);
  if (result == NULL) { fail("resource_error"); return NULL; }
  memcpy(result, parent, parent_len);
  if (parent_len) result[parent_len] = '/';
  memcpy(result + parent_len + (parent_len ? 1 : 0), name, name_len + 1);
  return result;
}

static bool same_directory(const struct stat *left, const struct stat *right) {
  return S_ISDIR(right->st_mode) && left->st_dev == right->st_dev && left->st_ino == right->st_ino &&
    left->st_mtimespec.tv_sec == right->st_mtimespec.tv_sec && left->st_mtimespec.tv_nsec == right->st_mtimespec.tv_nsec &&
    left->st_ctimespec.tv_sec == right->st_ctimespec.tv_sec && left->st_ctimespec.tv_nsec == right->st_ctimespec.tv_nsec;
}

static void free_candidates(CandidateList *list) {
  for (size_t i = 0; i < list->length; i++) free(list->items[i].relative);
  free(list->items); memset(list, 0, sizeof(*list));
}
static void free_snapshots(SnapshotList *list) {
  for (size_t i = 0; i < list->length; i++) free(list->items[i].relative);
  free(list->items); memset(list, 0, sizeof(*list));
}
static void clear_scan(void) {
  for (size_t i = 0; i < scan_state.frame_count; i++) {
    if (scan_state.frames[i].stream != NULL) closedir(scan_state.frames[i].stream);
    close(scan_state.frames[i].fd);
    free(scan_state.frames[i].relative);
    free_entries(&scan_state.frames[i].entries);
  }
  free(scan_state.frames); scan_state.frames = NULL;
  scan_state.frame_count = 0; scan_state.frame_capacity = 0;
  free_candidates(&scan_state.candidates); free_snapshots(&scan_state.directories);
  scan_state.delivered = 0; scan_state.active = false; scan_state.complete = false;
}

static bool append_candidate(CandidateList *list, const char *relative, const struct stat *metadata, bool token) {
  if (list->length == list->capacity) {
    size_t next = list->capacity ? list->capacity * 2 : 32;
    if (next < list->capacity || next > SIZE_MAX / sizeof(Candidate)) { fail("resource_error"); return false; }
    Candidate *items = realloc(list->items, next * sizeof(Candidate));
    if (items == NULL) { fail("resource_error"); return false; }
    list->items = items; list->capacity = next;
  }
  char *copy = strdup(relative);
  if (copy == NULL) { fail("resource_error"); return false; }
  Candidate *candidate = &list->items[list->length++];
  candidate->relative = copy; candidate->metadata = *metadata;
  if (token) arc4random_buf(candidate->token, sizeof(candidate->token));
  else memset(candidate->token, 0, sizeof(candidate->token));
  return true;
}

static bool append_snapshot(SnapshotList *list, const char *relative, int fd) {
  struct stat metadata;
  if (fstat(fd, &metadata) != 0 || !S_ISDIR(metadata.st_mode)) { fail("access_denied"); return false; }
  if (list->length == list->capacity) {
    size_t next = list->capacity ? list->capacity * 2 : 16;
    if (next < list->capacity || next > SIZE_MAX / sizeof(DirectorySnapshot)) { fail("resource_error"); return false; }
    DirectorySnapshot *items = realloc(list->items, next * sizeof(DirectorySnapshot));
    if (items == NULL) { fail("resource_error"); return false; }
    list->items = items; list->capacity = next;
  }
  char *copy = strdup(relative);
  if (copy == NULL) { fail("resource_error"); return false; }
  list->items[list->length].relative = copy;
  list->items[list->length].metadata = metadata;
  list->length++;
  return true;
}

static int open_root_again(void) {
  int fd = open(root_path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC);
  if (fd < 0) { fail(errno == EACCES || errno == EPERM ? "access_denied" : "root_changed"); return -1; }
  struct stat metadata;
  if (fstat(fd, &metadata) != 0 || !S_ISDIR(metadata.st_mode) || metadata.st_dev != root_dev || metadata.st_ino != root_ino) {
    close(fd); fail("root_changed"); return -1;
  }
  return fd;
}

static int open_relative_directory(int parent, const char *relative) {
  int current = dup(parent);
  if (current < 0) { fail("access_denied"); return -1; }
  if (*relative == 0) return current;
  const char *cursor = relative;
  while (*cursor) {
    const char *slash = strchr(cursor, '/');
    size_t length = slash ? (size_t)(slash - cursor) : strlen(cursor);
    if (length == 0 || length > NAME_MAX) { close(current); fail("invalid_relative"); return -1; }
    char component[NAME_MAX + 1]; memcpy(component, cursor, length); component[length] = 0;
    if (strcmp(component, ".") == 0 || strcmp(component, "..") == 0) { close(current); fail("invalid_relative"); return -1; }
    int next = openat(current, component, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC);
    close(current);
    if (next < 0) { fail("tree_changed"); return -1; }
    current = next;
    if (!slash) break;
    cursor = slash + 1;
  }
  return current;
}

static bool validate_snapshots(const SnapshotList *snapshots) {
  int current_root = open_root_again();
  if (current_root < 0) return false;
  for (size_t i = 0; i < snapshots->length; i++) {
    int fd = open_relative_directory(current_root, snapshots->items[i].relative);
    if (fd < 0) { close(current_root); return false; }
    struct stat current;
    bool same = fstat(fd, &current) == 0 && same_directory(&snapshots->items[i].metadata, &current);
    close(fd);
    if (!same) { close(current_root); fail("tree_changed"); return false; }
  }
  close(current_root);
  return true;
}

static bool is_candidate(const char *name) {
  size_t length = strlen(name);
  return length >= 6 && strcmp(name + length - 6, ".jsonl") == 0;
}

static bool elapsed_preview(Preview *preview) {
  struct timespec current;
  if (clock_gettime(CLOCK_MONOTONIC, &current) != 0) { fail("clock_error"); return true; }
  int64_t elapsed = (current.tv_sec - preview->started.tv_sec) * 1000000000LL + current.tv_nsec - preview->started.tv_nsec;
  if (elapsed >= PREVIEW_NANOS) { preview->reason = "timeout"; return true; }
  return false;
}

static bool preview_directory(Preview *preview, int directory, const char *relative, unsigned int depth) {
  if (!append_snapshot(&preview->directories, relative, directory)) return false;
  int duplicate = dup(directory);
  if (duplicate < 0) { fail("access_denied"); return false; }
  DIR *stream = fdopendir(duplicate);
  if (stream == NULL) { close(duplicate); fail("access_denied"); return false; }
  bool proceed = true;
  for (;;) {
    if (elapsed_preview(preview)) { proceed = false; break; }
    errno = 0;
    struct dirent *entry = readdir(stream);
    if (entry == NULL) { if (errno != 0) { fail("access_denied"); proceed = false; } break; }
    if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
    if (preview->inspected_entries == PREVIEW_ENTRIES) { preview->reason = "entry_limit"; proceed = false; break; }
    preview->inspected_entries++;
    if (!safe_utf8((const unsigned char *)entry->d_name)) { fail("invalid_name"); proceed = false; break; }
    struct stat metadata;
    if (fstatat(directory, entry->d_name, &metadata, AT_SYMLINK_NOFOLLOW) != 0) { fail("tree_changed"); proceed = false; break; }
    if (S_ISLNK(metadata.st_mode)) {
      char *rejected = copy_relative(relative, entry->d_name);
      if (rejected == NULL) { proceed = false; break; }
      proceed = emit_audit("rejected", "symlink", rejected, &metadata);
      free(rejected);
      if (!proceed) break;
      continue;
    }
    if (S_ISDIR(metadata.st_mode)) {
      if (depth + 1 >= PREVIEW_DEPTH) {
        char *rejected = copy_relative(relative, entry->d_name);
        if (rejected == NULL) { proceed = false; break; }
        proceed = emit_audit("rejected", "depth_limit", rejected, &metadata);
        free(rejected);
        if (!proceed) break;
        if (preview->reason == NULL) preview->reason = "depth_limit";
        continue;
      }
      char *child = copy_relative(relative, entry->d_name);
      if (child == NULL) { proceed = false; break; }
      int fd = openat(directory, entry->d_name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC);
      if (fd < 0) { free(child); fail("tree_changed"); proceed = false; break; }
      struct stat opened;
      if (fstat(fd, &opened) != 0 || opened.st_dev != metadata.st_dev || opened.st_ino != metadata.st_ino) {
        free(child); close(fd); fail("tree_changed"); proceed = false; break;
      }
      bool child_ok = preview_directory(preview, fd, child, depth + 1);
      close(fd); free(child);
      if (!child_ok) { proceed = false; break; }
    } else if (S_ISREG(metadata.st_mode) && is_candidate(entry->d_name)) {
      char *child = copy_relative(relative, entry->d_name);
      if (child == NULL) { proceed = false; break; }
      bool ok = emit_audit("enumerated", "candidate", child, &metadata) &&
        emit_audit("metadata", "candidate", child, &metadata) &&
        append_candidate(&preview->candidates, child, &metadata, false);
      free(child);
      if (!ok) { proceed = false; break; }
    } else if (!S_ISREG(metadata.st_mode)) {
      char *rejected = copy_relative(relative, entry->d_name);
      if (rejected == NULL) { proceed = false; break; }
      proceed = emit_audit("rejected", "non_regular", rejected, &metadata);
      free(rejected);
      if (!proceed) break;
    }
  }
  closedir(stream);
  return proceed;
}

static int compare_candidate(const void *left, const void *right) {
  const Candidate *a = left, *b = right;
  return strcmp(a->relative, b->relative);
}

static int compare_entry(const void *left, const void *right) {
  const DirectoryEntry *a = left, *b = right;
  size_t i = 0;
  for (;;) {
    unsigned char ac = (unsigned char)a->name[i], bc = (unsigned char)b->name[i];
    if (ac == 0 && a->directory) ac = '/';
    if (bc == 0 && b->directory) bc = '/';
    if (ac != bc) return ac < bc ? -1 : 1;
    if (a->name[i] == 0 || b->name[i] == 0) return 0;
    i++;
  }
}

static void free_entries(EntryList *list) {
  for (size_t i = 0; i < list->length; i++) free(list->items[i].name);
  free(list->items); memset(list, 0, sizeof(*list));
}

static bool append_entry(EntryList *list, const char *name, bool directory, const struct stat *metadata) {
  if (list->length == list->capacity) {
    size_t next = list->capacity ? list->capacity * 2 : 32;
    if (next < list->capacity || next > SIZE_MAX / sizeof(DirectoryEntry)) { fail("resource_error"); return false; }
    DirectoryEntry *items = realloc(list->items, next * sizeof(DirectoryEntry));
    if (items == NULL) { fail("resource_error"); return false; }
    list->items = items; list->capacity = next;
  }
  char *copy = strdup(name);
  if (copy == NULL) { fail("resource_error"); return false; }
  list->items[list->length++] = (DirectoryEntry){.name = copy, .directory = directory, .metadata = *metadata};
  return true;
}

static bool scan_push_frame(int directory, char *relative) {
  if (scan_state.frame_count == scan_state.frame_capacity) {
    size_t next = scan_state.frame_capacity ? scan_state.frame_capacity * 2 : 16;
    if (next < scan_state.frame_capacity || next > SIZE_MAX / sizeof(ScanFrame)) {
      close(directory); free(relative); fail("resource_error"); return false;
    }
    ScanFrame *frames = realloc(scan_state.frames, next * sizeof(ScanFrame));
    if (frames == NULL) { close(directory); free(relative); fail("resource_error"); return false; }
    scan_state.frames = frames; scan_state.frame_capacity = next;
  }
  size_t snapshot_index = scan_state.directories.length;
  if (!append_snapshot(&scan_state.directories, relative, directory)) { close(directory); free(relative); return false; }
  int duplicate = dup(directory);
  if (duplicate < 0) { close(directory); free(relative); fail("access_denied"); return false; }
  DIR *stream = fdopendir(duplicate);
  if (stream == NULL) { close(duplicate); close(directory); free(relative); fail("access_denied"); return false; }
  scan_state.frames[scan_state.frame_count++] = (ScanFrame){
    .relative = relative, .fd = directory, .stream = stream, .snapshot_index = snapshot_index,
  };
  return true;
}

static bool slice_expired(const struct timespec *started) {
  struct timespec now;
  if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) { fail("clock_error"); return true; }
  int64_t elapsed = (now.tv_sec - started->tv_sec) * 1000000000LL + now.tv_nsec - started->tv_nsec;
  return elapsed >= PREVIEW_NANOS;
}

static bool scan_load_entries(ScanFrame *frame, const struct timespec *started, bool *yielded) {
  *yielded = false;
  for (;;) {
    if (slice_expired(started)) { *yielded = failure == NULL; return failure == NULL; }
    errno = 0;
    struct dirent *entry = readdir(frame->stream);
    if (entry == NULL) { if (errno != 0) { fail("access_denied"); return false; } break; }
    if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
    if (!safe_utf8((const unsigned char *)entry->d_name)) { fail("invalid_name"); return false; }
    struct stat metadata;
    if (fstatat(frame->fd, entry->d_name, &metadata, AT_SYMLINK_NOFOLLOW) != 0) { fail("tree_changed"); return false; }
    if (S_ISLNK(metadata.st_mode)) {
      char *rejected = copy_relative(frame->relative, entry->d_name);
      if (rejected == NULL) return false;
      bool ok = emit_audit("rejected", "symlink", rejected, &metadata);
      free(rejected);
      if (!ok) return false;
      continue;
    }
    bool is_dir = S_ISDIR(metadata.st_mode);
    if (!is_dir && !S_ISREG(metadata.st_mode)) {
      char *rejected = copy_relative(frame->relative, entry->d_name);
      if (rejected == NULL) return false;
      bool ok = emit_audit("rejected", "non_regular", rejected, &metadata);
      free(rejected);
      if (!ok) return false;
      continue;
    }
    if (!is_dir && !is_candidate(entry->d_name)) continue;
    if (!is_dir) {
      char *enumerated = copy_relative(frame->relative, entry->d_name);
      if (enumerated == NULL) return false;
      bool ok = emit_audit("enumerated", "candidate", enumerated, &metadata);
      free(enumerated);
      if (!ok) return false;
    }
    if (!append_entry(&frame->entries, entry->d_name, is_dir, &metadata)) return false;
  }
  closedir(frame->stream); frame->stream = NULL;
  struct stat after;
  if (fstat(frame->fd, &after) != 0 ||
      !same_directory(&scan_state.directories.items[frame->snapshot_index].metadata, &after)) {
    fail("tree_changed"); return false;
  }
  qsort(frame->entries.items, frame->entries.length, sizeof(DirectoryEntry), compare_entry);
  frame->ready = true;
  return true;
}

static bool scan_next_candidate(const struct timespec *started, bool *emitted, bool *yielded) {
  *emitted = false;
  *yielded = false;
  while (scan_state.frame_count > 0) {
    if (slice_expired(started)) { *yielded = failure == NULL; return failure == NULL; }
    ScanFrame *frame = &scan_state.frames[scan_state.frame_count - 1];
    if (!frame->ready) {
      if (!scan_load_entries(frame, started, yielded)) return false;
      if (*yielded) return true;
    }
    if (frame->next_entry == frame->entries.length) {
      close(frame->fd); free(frame->relative); free_entries(&frame->entries);
      scan_state.frame_count--;
      continue;
    }
    DirectoryEntry *entry = &frame->entries.items[frame->next_entry++];
    char *child = copy_relative(frame->relative, entry->name);
    if (child == NULL) return false;
    if (entry->directory) {
      int fd = openat(frame->fd, entry->name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC);
      if (fd < 0) { free(child); fail("tree_changed"); return false; }
      struct stat opened;
      if (fstat(fd, &opened) != 0 || opened.st_dev != entry->metadata.st_dev || opened.st_ino != entry->metadata.st_ino) {
        close(fd); free(child); fail("tree_changed"); return false;
      }
      if (!scan_push_frame(fd, child)) return false;
      continue;
    }
    struct stat current;
    if (fstatat(frame->fd, entry->name, &current, AT_SYMLINK_NOFOLLOW) != 0 || !S_ISREG(current.st_mode) ||
        current.st_dev != entry->metadata.st_dev || current.st_ino != entry->metadata.st_ino) {
      free(child); fail("tree_changed"); return false;
    }
    bool ok = emit_audit("metadata", "candidate", child, &current) &&
      append_candidate(&scan_state.candidates, child, &current, true);
    free(child);
    if (!ok) return false;
    *emitted = true;
    return true;
  }
  return true;
}

static char *base64(const char *text) {
  static const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  size_t length = strlen(text), encoded = ((length + 2) / 3) * 4;
  char *out = malloc(encoded + 1);
  if (out == NULL) return NULL;
  size_t cursor = 0;
  for (size_t i = 0; i < length; i += 3) {
    uint32_t chunk = (uint32_t)(unsigned char)text[i] << 16;
    if (i + 1 < length) chunk |= (uint32_t)(unsigned char)text[i + 1] << 8;
    if (i + 2 < length) chunk |= (unsigned char)text[i + 2];
    out[cursor++] = alphabet[(chunk >> 18) & 63];
    out[cursor++] = alphabet[(chunk >> 12) & 63];
    if (i + 1 < length) out[cursor++] = alphabet[(chunk >> 6) & 63];
    if (i + 2 < length) out[cursor++] = alphabet[chunk & 63];
  }
  out[cursor] = 0;
  return out;
}

static bool emit_audit(const char *action, const char *kind, const char *relative, const struct stat *metadata) {
  char *name = base64(relative);
  if (name == NULL) { fail("resource_error"); return false; }
  printf("AUDIT %s %s %s %" PRIu64 " %" PRIu64 "\n", action, kind, name,
    (uint64_t)metadata->st_dev, (uint64_t)metadata->st_ino);
  free(name);
  return true;
}

static void hex_bytes(const unsigned char *input, size_t length, char *output) {
  static const char digits[] = "0123456789abcdef";
  for (size_t i = 0; i < length; i++) { output[2 * i] = digits[input[i] >> 4]; output[2 * i + 1] = digits[input[i] & 15]; }
  output[2 * length] = 0;
}

static void file_digest(const struct stat *metadata, char output[65]) {
  char input[160];
  int length = snprintf(input, sizeof(input), "tm002-file-id-v1:%" PRIu64 ":%" PRIu64 ":%" PRIu64 ":%" PRIu64,
    (uint64_t)root_dev, (uint64_t)root_ino,
    (uint64_t)metadata->st_dev, (uint64_t)metadata->st_ino);
  unsigned char digest[CC_SHA256_DIGEST_LENGTH];
  CC_SHA256(input, (CC_LONG)length, digest);
  hex_bytes(digest, sizeof(digest), output);
}

static bool emit_candidate(const Candidate *candidate, bool token) {
  char *name = base64(candidate->relative);
  if (name == NULL) { fail("resource_error"); return false; }
  char digest[65], token_hex[33];
  file_digest(&candidate->metadata, digest);
  if (token) hex_bytes(candidate->token, sizeof(candidate->token), token_hex);
  else strcpy(token_hex, "-");
  printf("ITEM %s %" PRId64 " %" PRId64 " %ld %s %s\n", name, (int64_t)candidate->metadata.st_size,
    (int64_t)candidate->metadata.st_mtimespec.tv_sec, candidate->metadata.st_mtimespec.tv_nsec, digest, token_hex);
  free(name);
  return true;
}

static void preview_reply(void) {
  Preview preview = {0}; failure = NULL;
  int current_root = open_root_again();
  if (current_root < 0) { error_reply(failure); return; }
  if (clock_gettime(CLOCK_MONOTONIC, &preview.started) != 0) fail("clock_error");
  if (failure == NULL) preview_directory(&preview, current_root, "", 0);
  close(current_root);
  if (failure == NULL) validate_snapshots(&preview.directories);
  if (failure != NULL) error_reply(failure);
  else {
    qsort(preview.candidates.items, preview.candidates.length, sizeof(Candidate), compare_candidate);
    if (preview.reason == NULL && preview.candidates.length > PREVIEW_CANDIDATES) preview.reason = "candidate_limit";
    size_t visible = preview.candidates.length < PREVIEW_CANDIDATES ? preview.candidates.length : PREVIEW_CANDIDATES;
    printf("PREVIEW %s %u %zu\n", preview.reason ? preview.reason : "complete", preview.inspected_entries, visible);
    for (size_t i = 0; i < visible; i++) emit_candidate(&preview.candidates.items[i], false);
    printf("END\n"); fflush(stdout);
  }
  free_candidates(&preview.candidates); free_snapshots(&preview.directories);
}

static void emit_page(void) {
  failure = NULL;
  if (!scan_state.active || scan_state.complete) { error_reply("invalid_scan"); return; }
  if (!validate_snapshots(&scan_state.directories)) { clear_scan(); error_reply(failure); return; }
  struct timespec started;
  if (clock_gettime(CLOCK_MONOTONIC, &started) != 0) { clear_scan(); error_reply("clock_error"); return; }
  bool time_slice = false;
  size_t lookahead_target = scan_state.delivered + PAGE_SIZE;
  while (scan_state.candidates.length <= lookahead_target && scan_state.frame_count > 0) {
    if (slice_expired(&started)) { time_slice = failure == NULL; break; }
    bool emitted = false;
    bool yielded = false;
    if (!scan_next_candidate(&started, &emitted, &yielded)) break;
    if (yielded) { time_slice = true; break; }
  }
  if (failure != NULL) { const char *code = failure; clear_scan(); error_reply(code); return; }
  size_t available = scan_state.candidates.length - scan_state.delivered;
  size_t count = available < PAGE_SIZE ? available : PAGE_SIZE;
  size_t end = scan_state.delivered + count;
  if (!validate_snapshots(&scan_state.directories)) { clear_scan(); error_reply(failure); return; }
  bool complete = scan_state.frame_count == 0 && end == scan_state.candidates.length;
  printf("PAGE %u %zu %s\n", complete ? 1U : 0U, count, complete ? "complete" : time_slice ? "time_slice" : "continue");
  for (size_t i = scan_state.delivered; i < end; i++) emit_candidate(&scan_state.candidates.items[i], true);
  printf("END\n"); fflush(stdout);
  scan_state.delivered = end;
  scan_state.complete = complete;
}

static void begin_reply(void) {
  clear_scan(); failure = NULL;
  int current_root = open_root_again();
  if (current_root < 0) { error_reply(failure); return; }
  char *empty = strdup("");
  bool ok = empty != NULL;
  if (!ok) { close(current_root); fail("resource_error"); }
  else ok = scan_push_frame(current_root, empty);
  if (ok) ok = validate_snapshots(&scan_state.directories);
  if (!ok || failure != NULL) { const char *code = failure ? failure : "scan_failed"; clear_scan(); error_reply(code); return; }
  scan_state.active = true;
  emit_page();
}

static Candidate *find_candidate(const char *token) {
  if (strlen(token) != 32) return NULL;
  char expected[33];
  for (size_t i = 0; i < scan_state.delivered; i++) {
    hex_bytes(scan_state.candidates.items[i].token, 16, expected);
    if (strcmp(expected, token) == 0) return &scan_state.candidates.items[i];
  }
  return NULL;
}

static void read_reply(const char *command) {
  failure = NULL;
  char token[33], extra;
  uint64_t offset; unsigned int maximum;
  if (!scan_state.active || sscanf(command, "R %32s %" SCNu64 " %u %c", token, &offset, &maximum, &extra) != 3 ||
      maximum > READ_SIZE || offset > INT64_MAX) { error_reply("invalid_request"); return; }
  Candidate *candidate = find_candidate(token);
  if (candidate == NULL) { error_reply("invalid_token"); return; }
  if (!validate_snapshots(&scan_state.directories)) { clear_scan(); error_reply(failure); return; }
  char *relative = candidate->relative, *slash = strrchr(relative, '/');
  char *parent = NULL;
  const char *name = relative;
  if (slash != NULL) {
    size_t length = (size_t)(slash - relative);
    parent = malloc(length + 1);
    if (parent == NULL) { error_reply("resource_error"); return; }
    memcpy(parent, relative, length); parent[length] = 0; name = slash + 1;
  }
  int current_root = open_root_again();
  if (current_root < 0) { free(parent); error_reply(failure); return; }
  int directory = open_relative_directory(current_root, parent ? parent : "");
  close(current_root);
  free(parent);
  if (directory < 0) { error_reply(failure); return; }
  struct stat before, opened;
  bool safe = fstatat(directory, name, &before, AT_SYMLINK_NOFOLLOW) == 0 && S_ISREG(before.st_mode) &&
    before.st_dev == candidate->metadata.st_dev && before.st_ino == candidate->metadata.st_ino &&
    before.st_size == candidate->metadata.st_size &&
    before.st_mtimespec.tv_sec == candidate->metadata.st_mtimespec.tv_sec && before.st_mtimespec.tv_nsec == candidate->metadata.st_mtimespec.tv_nsec &&
    before.st_ctimespec.tv_sec == candidate->metadata.st_ctimespec.tv_sec && before.st_ctimespec.tv_nsec == candidate->metadata.st_ctimespec.tv_nsec;
  if (!safe) { close(directory); error_reply("file_changed"); return; }
  int file = openat(directory, name, O_RDONLY | O_NOFOLLOW_ANY | O_CLOEXEC);
  close(directory);
  if (file < 0) { error_reply("file_changed"); return; }
  safe = fstat(file, &opened) == 0 && S_ISREG(opened.st_mode) && opened.st_dev == before.st_dev && opened.st_ino == before.st_ino &&
    opened.st_size == before.st_size && opened.st_mtimespec.tv_sec == before.st_mtimespec.tv_sec &&
    opened.st_mtimespec.tv_nsec == before.st_mtimespec.tv_nsec && opened.st_ctimespec.tv_sec == before.st_ctimespec.tv_sec &&
    opened.st_ctimespec.tv_nsec == before.st_ctimespec.tv_nsec;
  if (!safe) { close(file); error_reply("file_changed"); return; }
  unsigned char bytes[READ_SIZE];
  ssize_t count = pread(file, bytes, maximum, (off_t)offset);
  struct stat after;
  safe = count >= 0 && fstat(file, &after) == 0 && S_ISREG(after.st_mode) &&
    after.st_dev == before.st_dev && after.st_ino == before.st_ino && after.st_size == before.st_size &&
    after.st_mtimespec.tv_sec == before.st_mtimespec.tv_sec && after.st_mtimespec.tv_nsec == before.st_mtimespec.tv_nsec &&
    after.st_ctimespec.tv_sec == before.st_ctimespec.tv_sec && after.st_ctimespec.tv_nsec == before.st_ctimespec.tv_nsec;
  close(file);
  if (!safe) { error_reply(count < 0 ? "access_denied" : "file_changed"); return; }
  if (!validate_snapshots(&scan_state.directories)) { clear_scan(); error_reply(failure); return; }
  if (!emit_audit("open_read", "candidate", candidate->relative, &after)) { error_reply(failure); return; }
  printf("READ %zd\n", count); fflush(stdout);
  if (count > 0 && !write_exact(3, bytes, (size_t)count)) _exit(1);
}

static bool read_command(char *buffer, size_t capacity) {
  size_t length = 0;
  while (length + 1 < capacity) {
    char byte;
    ssize_t read_count = read(STDIN_FILENO, &byte, 1);
    if (read_count < 0 && errno == EINTR) continue;
    if (read_count <= 0) return false;
    if (byte == '\n') { buffer[length] = 0; return true; }
    buffer[length++] = byte;
  }
  return false;
}

int main(void) {
  signal(SIGPIPE, SIG_IGN);
  unsigned char length_bytes[4];
  if (!read_exact(STDIN_FILENO, length_bytes, 4)) return 1;
  uint32_t length = (uint32_t)length_bytes[0] << 24 | (uint32_t)length_bytes[1] << 16 |
    (uint32_t)length_bytes[2] << 8 | length_bytes[3];
  if (length == 0 || length > MAX_ROOT) { error_reply("invalid_root"); return 1; }
  root_path = malloc((size_t)length + 1);
  if (root_path == NULL) { error_reply("resource_error"); return 1; }
  if (!read_exact(STDIN_FILENO, root_path, length)) return 1;
  root_path[length] = 0;
  if (!canonical_root_syntax(root_path) || memchr(root_path, 0, length) != NULL ||
      !safe_utf8((const unsigned char *)root_path)) {
    error_reply("invalid_root"); return 1;
  }
  unsigned char expected_flag;
  if (!read_exact(STDIN_FILENO, &expected_flag, 1) || (expected_flag != 0 && expected_flag != 1)) return 1;
  unsigned char expected[16] = {0};
  if (expected_flag == 1 && !read_exact(STDIN_FILENO, expected, sizeof(expected))) return 1;
  root_fd = open(root_path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW_ANY | O_CLOEXEC);
  if (root_fd < 0) { error_reply(errno == EACCES || errno == EPERM ? "access_denied" : "invalid_root"); return 1; }
  struct stat root_metadata;
  if (fstat(root_fd, &root_metadata) != 0 || !S_ISDIR(root_metadata.st_mode)) { error_reply("invalid_root"); return 1; }
  root_dev = root_metadata.st_dev; root_ino = root_metadata.st_ino;
  if (expected_flag == 1 && ((uint64_t)root_dev != be64(expected) || (uint64_t)root_ino != be64(expected + 8))) {
    error_reply("root_changed"); return 1;
  }
  printf("OK %" PRIu64 " %" PRIu64 "\n", (uint64_t)root_dev, (uint64_t)root_ino); fflush(stdout);
  char command[128];
  while (read_command(command, sizeof(command))) {
    if (strcmp(command, "P") == 0) preview_reply();
    else if (strcmp(command, "B") == 0) begin_reply();
    else if (strcmp(command, "N") == 0) emit_page();
    else if (strcmp(command, "C") == 0) { clear_scan(); printf("CANCELLED\n"); fflush(stdout); }
    else if (strncmp(command, "R ", 2) == 0) read_reply(command);
    else error_reply("invalid_request");
  }
  clear_scan(); close(root_fd); free(root_path);
  return 0;
}
