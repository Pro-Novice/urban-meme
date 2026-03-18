#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [rhel|ubuntu|mac] [output_dir]"
  exit 1
}

OS_ARG="${1:-}"
OUT_DIR="${2:-deps_snapshot}"

detect_os() {
  local uname_out
  uname_out="$(uname -s)"
  if [[ "$uname_out" == "Darwin" ]]; then
    echo "mac"
    return
  fi
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    case "${ID:-}" in
      ubuntu|debian) echo "ubuntu" ;;
      rhel|centos|rocky|almalinux|fedora) echo "rhel" ;;
      *) echo "unknown" ;;
    esac
    return
  fi
  echo "unknown"
}

if [[ -z "$OS_ARG" ]]; then
  OS_ARG="$(detect_os)"
fi

case "$OS_ARG" in
  ubuntu|rhel|mac) ;;
  *) usage ;;
esac

mkdir -p "$OUT_DIR"

echo "== System info ==" | tee "$OUT_DIR/system.txt"
uname -a | tee -a "$OUT_DIR/system.txt"
if [[ "$OS_ARG" == "mac" ]]; then
  sw_vers | tee -a "$OUT_DIR/system.txt"
else
  [[ -f /etc/os-release ]] && cat /etc/os-release | tee -a "$OUT_DIR/system.txt"
fi

if [[ "$OS_ARG" == "ubuntu" ]]; then
  echo "== Exporting apt packages ==" | tee "$OUT_DIR/apt.txt"
  dpkg-query -W -f='${Package}=${Version}\n' | sort > "$OUT_DIR/apt-packages.txt"
elif [[ "$OS_ARG" == "rhel" ]]; then
  echo "== Exporting rpm packages ==" | tee "$OUT_DIR/rpm.txt"
  rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' | sort > "$OUT_DIR/rpm-packages.txt"
else
  if command -v brew >/dev/null 2>&1; then
    echo "== Exporting brew packages ==" | tee "$OUT_DIR/brew.txt"
    brew list --formula > "$OUT_DIR/brew-formulas.txt"
    brew list --cask > "$OUT_DIR/brew-casks.txt"
    brew bundle dump --file="$OUT_DIR/Brewfile" --force
  else
    echo "brew not found" | tee "$OUT_DIR/brew.txt"
  fi
fi

if [[ -f package.json ]]; then
  echo "== Exporting npm packages ==" | tee "$OUT_DIR/npm.txt"
  npm ls --all --json > "$OUT_DIR/npm-tree.json" || true
  cp package.json "$OUT_DIR/package.json"
  [[ -f package-lock.json ]] && cp package-lock.json "$OUT_DIR/package-lock.json"
  [[ -f yarn.lock ]] && cp yarn.lock "$OUT_DIR/yarn.lock"
fi

if command -v docker >/dev/null 2>&1; then
  echo "== Exporting docker info ==" | tee "$OUT_DIR/docker.txt"
  docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | sort > "$OUT_DIR/docker-images.txt"
  docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | sort > "$OUT_DIR/docker-containers.txt"
  docker info > "$OUT_DIR/docker-info.txt" || true
fi

echo "✅ Export complete: $OUT_DIR"
