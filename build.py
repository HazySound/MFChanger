"""릴리즈 빌드 — 화면(frontend) 빌드 후 exe 빌드.

  venv\\Scripts\\python.exe build.py

결과: dist/MFChanger v{버전}.exe
dist 폴더의 다른 파일은 지우지 않는다.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def run(*command: str, cwd: Path = ROOT):
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True, shell=command[0] == "npm")


def main():
    if not (FRONTEND / "node_modules").exists():
        run("npm", "ci", cwd=FRONTEND)
    run("npm", "run", "build", cwd=FRONTEND)

    shutil.rmtree(ROOT / "build", ignore_errors=True)   # PyInstaller 작업 폴더만 정리
    run(sys.executable, "-m", "PyInstaller", "MFChanger.spec", "--clean", "-y")


if __name__ == "__main__":
    main()
