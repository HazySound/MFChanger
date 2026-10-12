"""선수 한 명이 가질 수 있는 미페 파일 전체 목록 (바둑판 모드).

인게임에서는 카드마다 보여줄 미페를 직접 고를 수 있어서, 데이터센터의 기본 경로만으로는
사용자가 실제로 보고 있는 파일을 알 수 없다. 후보를 전부 보여주고 사용자가 고르게 한다.
  - 대갈 미페:   players/p{pid}.png
  - 공통 미페:   playersAction/p{pid}_{연도}.png
  - 카드 미페:   playersAction/p{spid}.png, playersAction/p{spid}_{연도}.png
"""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from src.api import datacenter, nexon_api

FaceKind = Literal["head", "common", "card"]

# 로컬/데이터센터에서 근거를 못 찾아도 CDN에 직접 확인해 볼 공통 미페 연도
_PROBE_YEARS = ("24", "25", "26")
_SUFFIX_RE = re.compile(r"^p(\d+)_(\d{2})\.png$")


@dataclass
class FaceFile:
    relative: str
    kind: FaceKind
    spid: Optional[int] = None        # 카드 미페일 때 해당 카드
    year: Optional[str] = None        # 연도 접미사 (_25 → "25")
    default_for: list[int] = field(default_factory=list)   # 이 파일이 기본 미페인 카드
    cached: bool = False              # 게임 캐시 폴더에 받아져 있는지


def _local_suffixed(action_dir: Path, ids: set[int]) -> set[tuple[int, str]]:
    """게임 캐시의 p{id}_{연도}.png 중 ids에 해당하는 것."""
    found = set()
    for path in action_dir.glob("p*_*.png"):
        m = _SUFFIX_RE.match(path.name)
        if m and int(m[1]) in ids:
            found.add((int(m[1]), m[2]))
    return found


def list_faces(pid: int, player_name: str, card_spids: list[int], assets_dir: Path) -> list[FaceFile]:
    defaults = datacenter.card_paths(pid, player_name)
    suffixed = _local_suffixed(assets_dir / "playersAction", {pid, *card_spids})
    for rel in defaults.values():
        m = _SUFFIX_RE.match(Path(rel).name)
        if m:
            suffixed.add((int(m[1]), m[2]))

    candidates = [FaceFile(f"players/p{pid}.png", "head")]
    common_years = {year for owner, year in suffixed if owner == pid} | set(_PROBE_YEARS)
    candidates += [
        FaceFile(f"playersAction/p{pid}_{year}.png", "common", year=year)
        for year in sorted(common_years, reverse=True)
    ]
    for spid in sorted(card_spids, reverse=True):
        candidates.append(FaceFile(f"playersAction/p{spid}.png", "card", spid=spid))
        candidates += [
            FaceFile(f"playersAction/p{spid}_{year}.png", "card", spid=spid, year=year)
            for owner, year in sorted(suffixed, reverse=True) if owner == spid
        ]

    for face in candidates:
        face.default_for = sorted(s for s, rel in defaults.items() if rel == face.relative)
        face.cached = (assets_dir / face.relative).exists()

    # 캐시에 없고 기본 미페도 아닌 후보만 CDN에 존재 여부를 확인
    unknown = [f.relative for f in candidates if not f.cached and not f.default_for]
    with ThreadPoolExecutor(max_workers=12) as pool:
        on_cdn = {rel for rel, ok in zip(unknown, pool.map(nexon_api.cdn_exists, unknown)) if ok}
    return [f for f in candidates if f.cached or f.default_for or f.relative in on_cdn]
