# Source this file before running Python in the Codex cloud workspace.
export PTZ_SYSTEM_ROOT=/workspace/ptz-system/root
export LD_LIBRARY_PATH="$PTZ_SYSTEM_ROOT/usr/lib/x86_64-linux-gnu:$PTZ_SYSTEM_ROOT/usr/lib/x86_64-linux-gnu/vlc${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHON_VLC_LIB_PATH="$PTZ_SYSTEM_ROOT/usr/lib/x86_64-linux-gnu/libvlc.so.5"
export VLC_PLUGIN_PATH="$PTZ_SYSTEM_ROOT/usr/lib/x86_64-linux-gnu/vlc/plugins"
export APPDATA=/workspace/ptz-user
export XDG_CONFIG_HOME=/workspace/ptz-user
export XDG_CACHE_HOME=/workspace/ptz-user/cache
export PATH="$PTZ_SYSTEM_ROOT/usr/bin:$PATH"
mkdir -p "$APPDATA" "$XDG_CACHE_HOME"

export XDG_RUNTIME_DIR=/workspace/ptz-user/runtime
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
