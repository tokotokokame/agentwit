#!/usr/bin/env bash
# agentwit VPS environment survey — READ ONLY. Changes nothing.
# Run on the host that runs the MCP server (e.g. as the agentwit service user).
#   bash survey_vps.sh
set -u

line(){ printf '\n== %s ==\n' "$1"; }
have(){ command -v "$1" >/dev/null 2>&1; }

line "host / user"
id
uname -a
[ -r /etc/os-release ] && . /etc/os-release && echo "os: ${PRETTY_NAME:-unknown}"

line "python"
for p in python3 python3.12 python3.11 python3.10; do
  have "$p" && echo "$p -> $("$p" -V 2>&1)"
done
have python3 && python3 - <<'PY'
import sys
print("default python3:", sys.version.split()[0])
PY

line "pip / venv / pipx (PEP 668?)"
have pip3 && echo "pip3: $(pip3 --version 2>&1)" || echo "pip3: not found"
have pipx && echo "pipx: $(pipx --version 2>&1)" || echo "pipx: not found"
python3 -c "import venv" 2>/dev/null && echo "venv module: ok" || echo "venv module: MISSING (apt install python3-venv)"
if [ -f /usr/lib/python3*/EXTERNALLY-MANAGED ] 2>/dev/null; then
  echo "PEP 668: externally-managed (use a venv or pipx; pip --user needs --break-system-packages)"
else
  echo "PEP 668: not externally-managed"
fi

line "ports (need proxy 8765, console 8799 free; MCP upstream 3000 reachable)"
if have ss; then
  ss -ltnp 2>/dev/null | grep -E ':(3000|8765|8799)\b' || echo "none of 3000/8765/8799 listening"
elif have netstat; then
  netstat -ltnp 2>/dev/null | grep -E ':(3000|8765|8799)\b' || echo "none of 3000/8765/8799 listening"
fi
if have curl; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:3000/ 2>/dev/null)
  echo "MCP :3000 loopback probe -> HTTP ${code:-no-response}"
fi

line "systemd (user services for the daemon)"
if have systemctl; then
  systemctl --user show-environment >/dev/null 2>&1 && echo "systemd --user: available" || echo "systemd --user: NOT available in this shell (needs a real login session or lingering)"
  have loginctl && loginctl show-user "$(id -un)" 2>/dev/null | grep -i Linger || echo "linger: unknown (enable with: sudo loginctl enable-linger $(id -un))"
else
  echo "systemctl: not found"
fi

line "existing agentwit state"
if [ -d "$HOME/.agentwit" ]; then
  ls -la "$HOME/.agentwit"
  echo "perms home: $(stat -c '%a' "$HOME/.agentwit" 2>/dev/null)"
  [ -f "$HOME/.agentwit/secrets.env" ] && echo "secrets.env perms: $(stat -c '%a' "$HOME/.agentwit/secrets.env" 2>/dev/null)"
else
  echo "no ~/.agentwit yet (fresh install)"
fi
have agentwit && echo "agentwit on PATH: $(command -v agentwit) ($(agentwit --version 2>&1))" || echo "agentwit: not installed"

line "disk / memory headroom"
df -h "$HOME" 2>/dev/null | tail -1
free -h 2>/dev/null | sed -n '1,2p'

line "egress (pip needs PyPI; agentwit itself only needs loopback + webhook/SMTP)"
if have curl; then
  curl -s -o /dev/null -w 'pypi.org -> %{http_code}\n' --max-time 5 https://pypi.org/simple/ 2>/dev/null || echo "pypi.org: unreachable"
fi

echo; echo "== survey done (nothing was changed) =="
