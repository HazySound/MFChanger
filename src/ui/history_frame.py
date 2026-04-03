"""변경 이력 화면 프레임"""

from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from src.core import history, face_changer
from src.core.config import Config
from src.core.face_changer import ChangeRecord


class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(top, text="변경 이력", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        ctk.CTkButton(top, text="새로고침", width=90, command=self.refresh).pack(side="right")
        ctk.CTkButton(
            top, text="전체 복원", width=90,
            fg_color="#F44336", hover_color="#C62828",
            command=self._restore_all
        ).pack(side="right", padx=(0, 8))

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh(self):
        for widget in self._scroll.winfo_children():
            widget.destroy()

        records = history.load_history()
        if not records:
            ctk.CTkLabel(
                self._scroll, text="변경 이력이 없습니다.", text_color="gray"
            ).pack(pady=20)
            return

        for record in records:
            self._add_record_row(record)

    def _add_record_row(self, record: ChangeRecord):
        row = ctk.CTkFrame(self._scroll, corner_radius=8)
        row.pack(fill="x", pady=3)
        row.columnconfigure(1, weight=1)

        spid_label = ctk.CTkLabel(
            row, text=f"p{record.spid}", font=ctk.CTkFont(size=13, weight="bold"), width=90
        )
        spid_label.grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", pady=8)

        ctk.CTkLabel(
            info_frame, text=record.player_name, font=ctk.CTkFont(size=13)
        ).pack(anchor="w")
        ctk.CTkLabel(
            info_frame,
            text=f"변경: {record.changed_at}",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w")

        has_backup = record.backup_path and __import__("pathlib").Path(record.backup_path).exists()
        restore_btn = ctk.CTkButton(
            row,
            text="복원",
            width=70,
            fg_color="#607D8B",
            hover_color="#455A64",
            command=lambda r=record: self._restore_one(r),
        )
        restore_btn.grid(row=0, column=2, padx=8, pady=8)

        if not has_backup:
            restore_btn.configure(
                text="삭제",
                fg_color="#F44336",
                hover_color="#C62828",
            )

    def _restore_one(self, record: ChangeRecord):
        name = record.player_name
        has_backup = record.backup_path and __import__("pathlib").Path(record.backup_path).exists()
        msg = (
            f"'{name}'의 미페를 원본으로 복원하겠습니까?"
            if has_backup
            else f"'{name}'의 교체 파일을 삭제하겠습니까?\n(백업 없음 - 게임 재실행 시 자동 복구됩니다)"
        )
        if not messagebox.askyesno("복원 확인", msg):
            return

        try:
            face_changer.restore_face(record, self._config)
            history.remove_record(record.spid)
            self.refresh()
        except Exception as e:
            messagebox.showerror("복원 실패", str(e))

    def _restore_all(self):
        records = history.load_history()
        if not records:
            messagebox.showinfo("알림", "복원할 이력이 없습니다.")
            return

        if not messagebox.askyesno(
            "전체 복원",
            f"변경된 미페 {len(records)}개를 모두 복원하겠습니까?"
        ):
            return

        errors = []
        for record in records:
            try:
                face_changer.restore_face(record, self._config)
                history.remove_record(record.spid)
            except Exception as e:
                errors.append(f"p{record.spid}: {e}")

        self.refresh()
        if errors:
            messagebox.showerror("일부 복원 실패", "\n".join(errors))
        else:
            messagebox.showinfo("완료", "전체 복원이 완료됐습니다.")
