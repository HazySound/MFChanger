"""폰트 크기 중앙 관리 모듈

모든 UI 파일에서 ctk.CTkFont(size=N) 대신 fm.font(N)을 사용한다.

- init(scale): 앱 시작 시 배율 초기화 (위젯 생성 전에 호출)
- font(size, weight): 배율이 적용된 CTkFont 인스턴스 반환 (캐시됨)
- apply_scale(scale): 실행 중 배율 변경 — 캐시된 모든 폰트 즉시 업데이트
"""

import customtkinter as ctk

_scale: float = 1.0
_font_cache: dict[tuple, ctk.CTkFont] = {}


def init(scale: float):
    """앱 시작 시 1회 호출. 위젯 생성 전에 배율을 초기화한다."""
    global _scale
    _scale = max(0.5, min(3.0, float(scale)))


def font(size: int, weight: str = "normal") -> ctk.CTkFont:
    """배율이 적용된 CTkFont를 반환. 동일한 (size, weight)는 같은 인스턴스를 재사용."""
    key = (size, weight)
    if key not in _font_cache:
        _font_cache[key] = ctk.CTkFont(size=round(size * _scale), weight=weight)
    return _font_cache[key]


def apply_scale(new_scale: float):
    """실행 중 폰트 크기를 즉시 변경. 캐시된 모든 CTkFont 객체를 업데이트한다."""
    global _scale
    _scale = max(0.5, min(3.0, float(new_scale)))
    for (size, weight), f in _font_cache.items():
        f.configure(size=round(size * _scale))
