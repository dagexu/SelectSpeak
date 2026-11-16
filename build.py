"""打包成单文件 exe。用法：python build.py"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
ICON = BASE / "assets" / "icon.ico"


def make_icon_file():
    sys.path.insert(0, str(BASE))
    from ui_tray import make_icon

    ICON.parent.mkdir(parents=True, exist_ok=True)
    img = make_icon(256)
    img.save(
        ICON,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"图标已生成: {ICON}")


def build():
    make_icon_file()
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "SelectSpeak",
        "--icon",
        str(ICON),
        "--add-data",
        f"{ICON};assets",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "pandas",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "scipy",
        "--exclude-module",
        "PyQt5",
        "--exclude-module",
        "PySide6",
        "--exclude-module",
        "unittest",
        "--exclude-module",
        "pydoc",
        str(BASE / "main.py"),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=str(BASE), check=True)
    exe = BASE / "dist" / "SelectSpeak.exe"
    if exe.exists():
        print(f"\n打包完成: {exe}  ({exe.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    build()
