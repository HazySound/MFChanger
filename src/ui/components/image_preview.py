"""이미지 미리보기 위젯"""

from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

_NORMAL_COLOR = ("gray90", "gray20")
_HOVER_COLOR  = ("#BBDEFB", "#1565C0")
_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class ImagePreview(ctk.CTkFrame):
    """고정 크기의 이미지 미리보기 프레임."""

    def __init__(self, master, size: int = 160, label_text: str = "", **kwargs):
        super().__init__(master, width=size + 16, corner_radius=10, **kwargs)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._size = size
        self._ctk_image: Optional[ctk.CTkImage] = None
        self._has_image = False
        self._placeholder_text = "이미지 없음"

        self._label_top = ctk.CTkLabel(
            self, text=label_text, font=ctk.CTkFont(size=12)
        )
        self._label_top.pack(pady=(8, 4))

        self._container = ctk.CTkFrame(
            self, width=size, height=size, corner_radius=8, fg_color=_NORMAL_COLOR
        )
        self._container.pack(padx=8, pady=(0, 8))
        self._container.pack_propagate(False)

        self._placeholder = ctk.CTkLabel(
            self._container,
            text=self._placeholder_text,
            text_color="gray",
            font=ctk.CTkFont(size=11),
            justify="center",
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

        self._img_label = ctk.CTkLabel(self._container, text="")

    def set_image(self, img: Optional[Image.Image]):
        if img is None:
            self._show_placeholder()
            return
        self._ctk_image = ctk.CTkImage(
            light_image=img, dark_image=img, size=(self._size, self._size),
        )
        self._img_label.configure(image=self._ctk_image)
        self._placeholder.place_forget()
        self._img_label.place(relx=0.5, rely=0.5, anchor="center")
        self._has_image = True

    def _show_placeholder(self):
        self._img_label.place_forget()
        if self._ctk_image is not None:
            self._ctk_image = None
            self._img_label.configure(image=ctk.CTkImage(
                light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                dark_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                size=(1, 1),
            ))
        self._placeholder.configure(text=self._placeholder_text)
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")
        self._has_image = False

    def set_from_path(self, path: Path):
        try:
            img = Image.open(path).convert("RGBA")
            self.set_image(img)
        except Exception:
            self.set_image(None)

    def clear(self):
        self._show_placeholder()

    def set_label(self, text: str):
        self._label_top.configure(text=text)

    # ──────────────────────────────────────────
    # 드래그앤드롭
    # ──────────────────────────────────────────

    def enable_drop(self, callback: Callable[[Path], None]):
        """이미지 파일 드래그앤드롭 활성화."""
        try:
            from src.core import dnd_manager
        except ImportError:
            return

        self._drop_callback = callback
        self._placeholder_text = "이미지를 드롭하거나\n클릭해서 선택"
        self._placeholder.configure(text=self._placeholder_text)

        dnd_manager.register(self._container, callback)


def _parse_drop_paths(data: str) -> list[str]:
    paths: list[str] = []
    data = data.strip()
    while data:
        if data.startswith("{"):
            try:
                end = data.index("}")
                paths.append(data[1:end])
                data = data[end + 1:].strip()
            except ValueError:
                break
        else:
            idx = data.find(" ")
            if idx == -1:
                paths.append(data)
                break
            paths.append(data[:idx])
            data = data[idx + 1:].strip()
    return paths
