"""
agentwit GUI launcher
`agentwit gui` コマンドで MCP Inspector GUI を起動する。

初回実行時:
  1. GitHub Releases から AppImage/exe/dmg を自動ダウンロード
  2. Linux: ~/.local/share/agentwit/ に配置 + デスクトップ登録
  3. 起動
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

_PACKAGE_DIR = Path(__file__).parent
_REPO = "tokotokokame/agentwit"
_RELEASES_URL = f"https://github.com/{_REPO}/releases/latest"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"

_LOCAL_DIR     = Path.home() / ".local" / "share" / "agentwit"
_LOCAL_APPIMAGE = _LOCAL_DIR / "mcp-inspector.AppImage"
_LOCAL_EXE_WIN  = Path.home() / "AppData" / "Local" / "agentwit" / "mcp-inspector.exe"
_LOCAL_APP_MAC  = Path("/Applications/mcp-inspector.app")
_ICON_PATH      = Path.home() / ".local/share/icons/hicolor/256x256/apps/agentwit.png"
_DESKTOP_PATH   = Path.home() / ".local/share/applications/agentwit-gui.desktop"


def _system() -> str:
    return platform.system()


def _find_existing() -> Path | None:
    """既存バイナリを探す。"""
    candidates = {
        "Linux":   [_LOCAL_APPIMAGE, Path(shutil.which("mcp-inspector") or "")],
        "Darwin":  [_LOCAL_APP_MAC,  Path(shutil.which("mcp-inspector") or "")],
        "Windows": [_LOCAL_EXE_WIN,  Path(shutil.which("mcp-inspector.exe") or "")],
    }
    for p in candidates.get(_system(), []):
        if p and p.exists():
            return p
    return None


def _get_latest_asset_url() -> tuple[str, str] | None:
    """GitHub API から最新リリースのアセットURLを取得する。"""
    suffix_map = {
        "Linux":   "amd64.AppImage",
        "Darwin":  "aarch64.dmg" if platform.machine() == "arm64" else "x64.dmg",
        "Windows": "x64-setup.msi",
    }
    suffix = suffix_map.get(_system())
    if not suffix:
        return None

    try:
        req = urllib.request.Request(
            _API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "agentwit"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json
            data = json.loads(resp.read())
        for asset in data.get("assets", []):
            if asset["name"].endswith(suffix):
                return asset["browser_download_url"], asset["name"]
    except Exception:
        pass
    return None


def _download(url: str, dest: Path) -> bool:
    """プログレスバー付きダウンロード。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        print(f"[agentwit] Downloading {dest.name} ...")

        def _progress(block, block_size, total):
            if total > 0:
                pct = min(block * block_size / total * 100, 100)
                bar = "=" * int(pct / 2)
                print(f"\r  [{bar:<50}] {pct:5.1f}%", end="", flush=True)

        urllib.request.urlretrieve(url, dest, reporthook=_progress)
        print()  # 改行
        return True
    except Exception as e:
        print(f"\n[agentwit] Download failed: {e}", file=sys.stderr)
        return False


def _extract_icon_from_appimage(appimage: Path) -> bool:
    """AppImage からアイコンを抽出して登録する。"""
    try:
        extract_dir = Path("/tmp/agentwit-appimage-extract")
        subprocess.run(
            [str(appimage), "--appimage-extract"],
            cwd="/tmp",
            capture_output=True,
            timeout=30
        )
        extracted = Path("/tmp/squashfs-root")
        icon_src = extracted / "mcp-inspector.png"
        if not icon_src.exists():
            # usr/share/icons 以下を探す
            candidates = list(extracted.glob("usr/share/icons/**/*.png"))
            if candidates:
                icon_src = candidates[0]
            else:
                return False

        _ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, _ICON_PATH)

        # キャッシュ更新
        subprocess.run(
            ["gtk-update-icon-cache", str(_ICON_PATH.parent.parent.parent)],
            capture_output=True
        )
        return True
    except Exception:
        return False


def _register_desktop_linux(appimage: Path) -> None:
    """Linux: .desktop ファイルを作成してデスクトップに登録する。"""
    icon_name = "agentwit" if _ICON_PATH.exists() else str(appimage)

    desktop_content = f"""[Desktop Entry]
Name=agentwit MCP Inspector
Comment=MCP Server監査・デバッグツール
Exec={appimage}
Icon={icon_name}
Type=Application
Categories=Security;Network;Development;
Terminal=false
"""
    _DESKTOP_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DESKTOP_PATH.write_text(desktop_content)

    # デスクトップにもコピー
    desktop_link = Path.home() / "Desktop" / "agentwit-gui.desktop"
    if (Path.home() / "Desktop").exists():
        shutil.copy2(_DESKTOP_PATH, desktop_link)
        desktop_link.chmod(desktop_link.stat().st_mode | stat.S_IXUSR)

    subprocess.run(["update-desktop-database", str(_DESKTOP_PATH.parent)],
                   capture_output=True)
    print("[agentwit] Desktop shortcut registered.")


def _auto_install() -> Path | None:
    """自動ダウンロード＆インストール。成功したらバイナリPathを返す。"""
    result = _get_latest_asset_url()
    if not result:
        print(f"[agentwit] Could not fetch release info from GitHub.", file=sys.stderr)
        print(f"  Manual download: {_RELEASES_URL}")
        return None

    url, name = result

    if _system() == "Linux":
        dest = _LOCAL_APPIMAGE
        if not _download(url, dest):
            return None
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("[agentwit] Extracting icon ...")
        _extract_icon_from_appimage(dest)
        _register_desktop_linux(dest)
        return dest

    elif _system() == "Darwin":
        dest = Path.home() / "Downloads" / name
        if not _download(url, dest):
            return None
        print(f"[agentwit] Downloaded to {dest}")
        print("[agentwit] Opening installer ...")
        subprocess.Popen(["open", str(dest)])
        print("[agentwit] After installation, run 'agentwit gui' again.")
        return None

    elif _system() == "Windows":
        dest = Path.home() / "Downloads" / name
        if not _download(url, dest):
            return None
        print(f"[agentwit] Downloaded to {dest}")
        print("[agentwit] Opening installer ...")
        os.startfile(str(dest))
        print("[agentwit] After installation, run 'agentwit gui' again.")
        return None

    return None


def _launch(binary: Path, args: list[str]) -> int:
    if _system() == "Darwin" and str(binary).endswith(".app"):
        cmd = ["open", str(binary)] + (["--args"] + args if args else [])
    else:
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        cmd = [str(binary)] + args
    try:
        proc = subprocess.Popen(cmd)
        print(f"[agentwit] GUI launched (pid {proc.pid})")
        return 0
    except Exception as e:
        print(f"[agentwit] Failed to launch: {e}", file=sys.stderr)
        return 1


def main(extra_args: list[str] | None = None) -> int:
    args = extra_args or []
    binary = _find_existing()

    if binary is None:
        print("[agentwit] MCP Inspector not found. Installing automatically...")
        binary = _auto_install()
        if binary is None:
            return 1

    return _launch(binary, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
