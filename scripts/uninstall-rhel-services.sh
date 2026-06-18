#!/usr/bin/env bash
set -euo pipefail

systemctl disable --now koos-subset-watch 2>/dev/null || true
systemctl disable --now koos-back 2>/dev/null || true

rm -f /etc/systemd/system/koos-subset-watch.service
rm -f /etc/systemd/system/koos-back.service

systemctl daemon-reload

echo "Removed KOOS systemd units."
