#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

SKIP_UFW=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-ufw)
      SKIP_UFW=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_base_packages() {
  $SUDO apt-get update
  $SUDO apt-get install -y ca-certificates curl gnupg git ufw openssl lsb-release
}

install_docker() {
  if need_cmd docker && $SUDO systemctl is-active --quiet docker; then
    return
  fi

  $SUDO install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
  fi

  local codename
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${codename} stable" \
    | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null

  $SUDO apt-get update
  $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  $SUDO systemctl enable --now docker
}

configure_user_access() {
  if id -nG "$USER" | grep -qw docker; then
    return
  fi

  $SUDO usermod -aG docker "$USER"
  echo "Added $USER to the docker group."
  echo "A new login session is normally required, but deploy scripts can still fall back to sudo docker."
}

configure_ufw() {
  if [[ "$SKIP_UFW" == "true" ]]; then
    return
  fi

  $SUDO ufw allow OpenSSH
  $SUDO ufw allow 80/tcp
  $SUDO ufw allow 443/tcp

  if $SUDO ufw status | grep -q "Status: inactive"; then
    $SUDO ufw --force enable
  fi
}

main() {
  install_base_packages
  install_docker
  configure_user_access
  configure_ufw

  echo
  echo "Bootstrap complete."
  docker --version || true
  docker compose version || true
}

main
