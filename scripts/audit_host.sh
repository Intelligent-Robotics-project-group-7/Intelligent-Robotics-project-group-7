#!/usr/bin/env bash
set -eo pipefail
date -u --iso-8601=seconds
hostname
cat /etc/os-release
uname -a
id
nproc
free -h
df -h /
systemd-detect-virt
lspci | grep -Ei 'vga|3d|display'
lsusb
docker version
docker image ls --no-trunc
