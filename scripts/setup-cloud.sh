#!/usr/bin/env bash
# Debian 13 / amd64 Codex cloud setup. Does not modify system packages.
set -euo pipefail
cd /workspace/Camera-PTZ-Control
python3 -m venv /workspace/ptz-venv
/workspace/ptz-venv/bin/python -m pip install --cache-dir /workspace/ptz-pip-cache -r requirements-dev.txt -r requirements-gamepad.txt
if [[ ! -f /workspace/ptz-system/root/usr/lib/x86_64-linux-gnu/libvlc.so.5 ]]; then
  [[ "$(dpkg --print-architecture)" == amd64 ]] || { echo 'Cloud helper requires Debian amd64.' >&2; exit 1; }
  task_apt=/workspace/ptz-system
  mkdir -p "$task_apt/lists/partial" "$task_apt/cache/archives/partial" "$task_apt/apt.conf.d" "$task_apt/root"
  cat > "$task_apt/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
SOURCES
  apt_options=(-o "Dir::Etc::parts=$task_apt/apt.conf.d" -o "Dir::Etc::sourcelist=$task_apt/sources.list" -o Dir::Etc::sourceparts=-
    -o "Dir::State::lists=$task_apt/lists" -o "Dir::Cache=$task_apt/cache" -o "Dir::Log=$task_apt" -o "APT::Sandbox::User=$(id -un)" -o Debug::NoLocking=1)
  /usr/bin/apt-get "${apt_options[@]}" update
  /usr/bin/apt-get "${apt_options[@]}" --download-only install -y --no-install-recommends libvlc5 vlc-plugin-base vlc-plugin-video-output
  for package in "$task_apt"/cache/archives/*.deb; do
    dpkg-deb -x "$package" "$task_apt/root"
  done
fi
# Retain signature, package hash and HTTPS verification through APT above.
. scripts/cloud-env.sh
QT_QPA_PLATFORM=offscreen /workspace/ptz-venv/bin/python -m pytest -q
