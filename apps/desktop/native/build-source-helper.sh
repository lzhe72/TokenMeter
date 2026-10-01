#!/bin/sh
set -eu
umask 077
if [ "$#" -ne 1 ]; then
  exit 64
fi
output=$1
case "$output" in
  /*) ;;
  *) exit 64 ;;
esac
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
/usr/bin/clang -std=c11 -D_DARWIN_C_SOURCE -O2 -Wall -Wextra -Werror \
  -fstack-protector-strong -o "$output" "$script_dir/source-helper.c"
chmod 0755 "$output"
