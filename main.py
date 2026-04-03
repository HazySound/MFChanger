"""MFChanger - FC온라인 미니페이스 변경 프로그램"""

import sys
import os

# PyInstaller 빌드 시 경로 처리
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from src.ui.app import App


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
