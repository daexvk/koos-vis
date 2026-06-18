#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: sudo $0 /absolute/path/to/dist/koos-back [service_user]"
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage
    exit 1
fi

APP_DIR="$1"
SERVICE_USER="${2:-$(id -un "${SUDO_USER:-$USER}")}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${APP_DIR}" != /* ]]; then
    echo "APP_DIR must be an absolute path: ${APP_DIR}" >&2
    exit 1
fi

if [[ ! -x "${APP_DIR}/koos-back" ]]; then
    echo "Executable not found: ${APP_DIR}/koos-back" >&2
    exit 1
fi

if [[ ! -f "${APP_DIR}/config/koos-back.json" ]]; then
    echo "Config not found: ${APP_DIR}/config/koos-back.json" >&2
    exit 1
fi

install_unit() {
    local template="$1"
    local target="$2"
    sed \
        -e "s|__APP_DIR__|${APP_DIR}|g" \
        -e "s|__USER__|${SERVICE_USER}|g" \
        "${template}" > "${target}"
    chmod 0644 "${target}"
}

install_unit \
    "${ROOT_DIR}/packaging/systemd/koos-back.service.template" \
    /etc/systemd/system/koos-back.service
install_unit \
    "${ROOT_DIR}/packaging/systemd/koos-subset-watch.service.template" \
    /etc/systemd/system/koos-subset-watch.service

systemctl daemon-reload

echo "Installed systemd units:"
echo "  /etc/systemd/system/koos-back.service"
echo "  /etc/systemd/system/koos-subset-watch.service"
echo
echo "Enable and start:"
echo "  sudo systemctl enable --now koos-back"
echo "  sudo systemctl enable --now koos-subset-watch"
