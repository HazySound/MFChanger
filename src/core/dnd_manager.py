"""Windows DnD 관리자 - queue 기반 GIL 안전 WM_DROPFILES + UIPI 우회"""

import ctypes
import ctypes.wintypes
import queue
from pathlib import Path
from typing import Callable

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

# HWND → (old_proc, new_proc_obj, _wnd_proc_func) 저장 (GC 방지)
_hooks: dict = {}

# WndProc → 메인 스레드로 HDROP 전달용 큐
_drop_queue: queue.Queue = queue.Queue()

# 폴링용 루트 위젯
_root_ref = None

WM_DROPFILES = 0x0233
GWL_WNDPROC  = -4
MSGFLT_ALLOW = 1

_user32  = ctypes.windll.user32
_shell32 = ctypes.windll.shell32

_WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)
_user32.GetWindowLongPtrW.restype  = ctypes.c_ssize_t
_user32.GetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongPtrW.restype  = ctypes.c_ssize_t
_user32.SetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.CallWindowProcW.restype    = ctypes.c_ssize_t
_user32.CallWindowProcW.argtypes   = [
    ctypes.c_ssize_t, ctypes.wintypes.HWND,
    ctypes.wintypes.UINT, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
_shell32.DragAcceptFiles.argtypes  = [ctypes.wintypes.HWND, ctypes.wintypes.BOOL]
_shell32.DragQueryFileW.restype    = ctypes.wintypes.UINT
_shell32.DragQueryFileW.argtypes   = [
    ctypes.wintypes.HANDLE, ctypes.wintypes.UINT,
    ctypes.wintypes.LPWSTR, ctypes.wintypes.UINT,
]
_shell32.DragFinish.argtypes       = [ctypes.wintypes.HANDLE]
_user32.ChangeWindowMessageFilterEx.restype  = ctypes.wintypes.BOOL
_user32.ChangeWindowMessageFilterEx.argtypes = [
    ctypes.wintypes.HWND, ctypes.wintypes.UINT,
    ctypes.wintypes.DWORD, ctypes.c_void_p,
]


def init(root_widget) -> bool:
    """루트 위젯 저장 및 큐 폴링 시작."""
    global _root_ref
    _root_ref = root_widget
    root_widget.after(50, _process_queue)
    return True


def _process_queue():
    """메인 스레드에서 드롭 큐를 처리 (GIL 안전)."""
    try:
        while True:
            hdrop_int, callback = _drop_queue.get_nowait()
            _on_drop(hdrop_int, callback)
    except queue.Empty:
        pass
    finally:
        if _root_ref is not None:
            _root_ref.after(50, _process_queue)


def register(widget, callback: Callable[[Path], None]):
    """위젯과 그 모든 하위 캔버스에 WM_DROPFILES 훅 설치."""
    _hook_recursive(widget, callback)


def _hook_recursive(widget, callback):
    canvas = getattr(widget, '_canvas', None)
    if canvas is not None:
        _install(canvas, callback)
    _install(widget, callback)
    try:
        for child in widget.winfo_children():
            _hook_recursive(child, callback)
    except Exception:
        pass


def _install(widget, callback: Callable[[Path], None]):
    try:
        hwnd_val = widget.winfo_id()
        if hwnd_val == 0 or hwnd_val in _hooks:
            return

        old_proc = _user32.GetWindowLongPtrW(hwnd_val, GWL_WNDPROC)

        def _wnd_proc(hw, msg, wp, lp):
            if msg == WM_DROPFILES:
                # WndProc가 Explorer 스레드에서 호출될 수 있으므로
                # ctypes Shell32 함수를 직접 호출하지 않고 큐에 넣는다.
                # int(wp)는 순수 Python 연산 — GIL 해제 없음.
                _drop_queue.put_nowait((int(wp), callback))
                return 0
            return _user32.CallWindowProcW(old_proc, hw, msg, wp, lp)

        new_proc = _WNDPROCTYPE(_wnd_proc)
        new_addr = ctypes.cast(new_proc, ctypes.c_void_p).value

        # UIPI 우회: 관리자 권한으로 실행될 때 Explorer(낮은 권한)의
        # WM_DROPFILES 메시지가 차단되지 않도록 허용
        _user32.ChangeWindowMessageFilterEx(hwnd_val, WM_DROPFILES, MSGFLT_ALLOW, None)
        _user32.ChangeWindowMessageFilterEx(hwnd_val, 0x0049, MSGFLT_ALLOW, None)  # WM_COPYGLOBALDATA

        _shell32.DragAcceptFiles(hwnd_val, True)
        _user32.SetWindowLongPtrW(hwnd_val, GWL_WNDPROC, new_addr)

        _hooks[hwnd_val] = (old_proc, new_proc, _wnd_proc)
    except Exception:
        pass


def _on_drop(hdrop_wp: int, callback: Callable[[Path], None]):
    """메인 스레드에서만 호출됨 — ctypes 사용 안전."""
    path = None
    try:
        hdrop = ctypes.wintypes.HANDLE(hdrop_wp)
        count = _shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        if count:
            buf = ctypes.create_unicode_buffer(1024)
            _shell32.DragQueryFileW(hdrop, 0, buf, 1024)
            path = Path(buf.value)
    finally:
        _shell32.DragFinish(ctypes.wintypes.HANDLE(hdrop_wp))

    if path and path.suffix.lower() in _ALLOWED_EXTS:
        callback(path)
