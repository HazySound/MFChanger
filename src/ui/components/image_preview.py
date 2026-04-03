"""이미지 미리보기 위젯"""

from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image


class ImagePreview(ctk.CTkFrame):
    """고정 크기의 이미지 미리보기 프레임."""

    def __init__(self, master, size: int = 160, label_text: str = "", **kwargs):
        super().__init__(master, width=size + 16, corner_radius=10, **kwargs)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._size = size
        self._ctk_image: Optional[ctk.CTkImage] = None
        self._has_image = False

        self._label_top = ctk.CTkLabel(
            self, text=label_text, font=ctk.CTkFont(size=12)
        )
        self._label_top.pack(pady=(8, 4))

        # 이미지를 담을 고정 크기 컨테이너
        self._container = ctk.CTkFrame(
            self, width=size, height=size, corner_radius=8, fg_color=("gray90", "gray20")
        )
        self._container.pack(padx=8, pady=(0, 8))
        self._container.pack_propagate(False)

        # 플레이스홀더 텍스트 (이미지 없을 때)
        self._placeholder = ctk.CTkLabel(
            self._container,
            text="이미지 없음",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # 이미지 레이블 (항상 존재, 이미지 있을 때만 표시)
        self._img_label = ctk.CTkLabel(self._container, text="")
        # 처음에는 숨김

    def set_image(self, img: Optional[Image.Image]):
        """PIL Image를 받아 미리보기에 표시. None이면 플레이스홀더 표시."""
        if img is None:
            self._show_placeholder()
            return

        # 원본 이미지를 그대로 CTkImage에 넘기고, size 파라미터로 표시 크기만 제어
        # (픽셀 데이터는 원본 해상도 유지 → 깨짐 없음)
        self._ctk_image = ctk.CTkImage(
            light_image=img,
            dark_image=img,
            size=(self._size, self._size),
        )
        self._img_label.configure(image=self._ctk_image)
        self._placeholder.place_forget()
        self._img_label.place(relx=0.5, rely=0.5, anchor="center")
        self._has_image = True

    def _show_placeholder(self):
        self._img_label.place_forget()
        # 이전 이미지 참조 해제
        if self._ctk_image is not None:
            self._ctk_image = None
            self._img_label.configure(image=ctk.CTkImage(
                light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                dark_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                size=(1, 1),
            ))
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
