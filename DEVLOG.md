# MFChanger 개발 일지

> 작성일: 2026-04-03  
> 버전: v0.1.0 (개발 중)

---

## 1. 프로젝트 구조

```
MFChanger/
├── main.py                              # 진입점 (pywebview 창 + 로컬 서버)
├── build.py                             # 릴리즈 빌드 (화면 빌드 → exe)
├── version.py                           # 버전 정보
├── config.json                          # 사용자 설정 (자동 생성)
├── history.json                         # 미페 변경 이력 (자동 생성)
├── crest_history.json                   # 크레스트 변경 이력 (자동 생성)
├── manager_history.json                 # 감독 변경 이력 (자동 생성)
├── .cache/
│   ├── spid.json                        # 선수 메타데이터 캐시
│   ├── seasonid.json                    # 시즌 메타데이터 캐시
│   ├── managers_db.json                 # 감독 DB 캐시 (크롤링으로 생성)
│   ├── face_paths.json                  # 데이터센터 미페 경로 캐시 (gitignore)
│   └── uploads/                         # 드롭·붙여넣기 이미지 임시 보관 (실행 시 정리)
├── frontend/                            # 화면 — Svelte 5 + Vite + TypeScript
│   └── src/
│       ├── App.svelte                   # 탭 구조, 업데이트 배너, DB 생성 화면
│       ├── app.css                      # 디자인 토큰 + 공통 스타일
│       ├── lib/                         # 브리지(bridge.ts), 전역 상태, 공통 컴포넌트
│       └── pages/                       # 미페(face/), 크레스트, 감독, 이력(history/), 설정
└── src/
    ├── app/
    │   ├── api.py                       # 화면에서 호출하는 파이썬 API (pywebview js_api)
    │   └── server.py                    # 화면·게임 이미지를 제공하는 로컬 HTTP 서버
    ├── api/
    │   ├── nexon_api.py                 # 메타데이터 프록시 / CDN 클라이언트
    │   └── datacenter.py                # 카드별 실제 미페 경로 (데이터센터 선수검색)
    └── core/
        ├── config.py                    # 설정 관리
        ├── fileops.py                   # 읽기전용 속성, 이미지 정규화 등 공통 파일 처리
        ├── face_changer.py              # 미페 교체 핵심 로직
        ├── face_catalog.py              # 선수 한 명의 미페 후보 전체 (바둑판 모드)
        ├── crest_changer.py             # 크레스트 교체 핵심 로직
        ├── manager_changer.py           # 감독 얼굴 교체 핵심 로직
        ├── manager_db.py                # 감독 DB 빌드/로드
        ├── db_init.py                   # 시작 시 DB 파일 존재 여부 확인 및 생성
        ├── history.py                   # 변경 이력 관리 (미페/크레스트/감독)
        └── updater.py                   # GitHub 자동 업데이트
```

---

## 2. 기술 스택

| 항목 | 내용 |
|------|------|
| 언어 | Python 3.10.11 |
| 창 | pywebview 6.2 (Windows WebView2) |
| 화면 | Svelte 5 + Vite 8 + TypeScript, Pretendard, Lucide 아이콘 |
| HTTP | requests 2.33.1 |
| 이미지 | Pillow 12.2.0 |
| 버전 비교 | packaging 26.0 |
| HTML 파싱 | beautifulsoup4 (데이터센터 크롤링) |

---

## 3. API 조사 결과

### 3.1 Nexon Open API 구조 확인

초기에 베이스 URL을 CDN(`https://fco.dn.nexoncdn.co.kr`)으로 잘못 설정해 **403 Access Denied** 발생.

| 용도 | 베이스 URL | API 키 필요 |
|------|-----------|------------|
| 메타데이터 (spid, season) | `https://open.api.nexon.com` | **필요** (`x-nxopen-api-key` 헤더) |
| 이미지 (CDN) | `https://fco.dn.nexoncdn.co.kr` | **불필요** (공개 CDN) |

→ 두 개의 별도 `requests.Session` 인스턴스로 관리.

### 3.2 주요 엔드포인트

```
GET /static/fconline/meta/spid.json      → 전체 선수 목록 (86,036명)
GET /static/fconline/meta/seasonid.json  → 시즌 정보 (142개)

GET /live/externalAssets/common/playersAction/p{spid}.png  → 미페 이미지
```

### 3.3 파일명 / 경로 규칙

- 미페 파일명: `p{spid}.png` (spid는 9자리 숫자, 예: `p215200104.png`)
- FC온라인 설치 폴더 기본 경로: `C:\Nexon\EA SPORTS(TM) FC ONLINE`
- 미페 파일 저장 위치: `{설치경로}\_cache\live\externalAssets\common\playersAction\`
- CDN URL 경로와 로컬 캐시 폴더 구조가 동일 (`_cache` 폴더가 CDN을 로컬 미러링)

### 3.4 spid 구조

```
spid = {시즌ID(앞 N자리)}{선수ID(뒤 6자리)}
예: 215200104 → 시즌ID=215, 선수ID=200104

시즌ID 추출: int(str(spid)[:-6])
```

### 3.5 이미지 없는 경우

CDN에 이미지 파일이 아예 없는 선수가 존재 (403 반환). 주로 데이터는 있지만 이미지가 업로드되지 않은 구버전 카드. → 검색 결과에서 자동 제외 처리.

---

## 4. 구현된 기능

### 4.1 선수 검색

- `spid.json` 최초 다운로드 후 로컬 캐시 (30일 유효)
- 검색창 입력 시 **300ms 디바운스** 후 로컬 캐시에서 필터링 (API 호출 없음)
- 검색 결과 최대 50건 표시

### 4.2 시즌 분류 및 필터

총 142개 시즌을 키워드 기반으로 8개 대분류로 자동 분류:

| 대분류 | 분류 기준 키워드 |
|--------|----------------|
| TOTY | TOTY, TEAM OF THE YEAR, TOTT |
| TOTS | TOTS, TEAM OF THE SEASON |
| UCL | UCL, UEFA CHAMPIONS LEAGUE |
| PL | PREMIUM LIVE |
| LIVE | LIVE (Premium Live 제외) |
| K리그 | K LEAGUE, KLEAGUE, KFA 등 |
| ICON | ICON |
| 기타 | 위 해당 없음 |

필터 UI: 검색창 옆 **"필터 ▼" 버튼** → 클릭 시 드롭다운 팝업
- 대분류 칩 선택 → 연도 소분류 칩 표시 (복수 선택 가능)
- 필터 적용 중엔 버튼이 파란색 "필터 ●"로 변경
- 팝업 외부 클릭 또는 Esc로 닫기

### 4.3 검색 결과 목록

각 항목 구성:
- 선수 썸네일 (48×48, 비동기 로드)
- 시즌 뱃지 이미지 (22×22, 비동기 로드)
- 선수명, 시즌 약칭, SPID

썸네일/뱃지 비동기 로딩 후 이미지 없는 항목은 자동 제거 + 카운트 실시간 업데이트.

### 4.4 미페 미리보기 토글

선수 선택 시 오른쪽 패널에 미리보기 표시. 상단 세그먼트 버튼으로 두 가지 모드 전환:

| 모드 | 표시 내용 |
|------|---------|
| 공식 미페 | Nexon CDN에서 실시간 다운로드한 원본 이미지 |
| 현재 미페 | 로컬 FC온라인 폴더에 실제 저장된 파일 (수동 변경 포함) |

→ 로컬 파일 없으면 "로컬 파일 없음" 표시.

### 4.5 교체 이미지 선택

- 파일 탐색기로 이미지 선택 (JPG/PNG/BMP/WEBP)
- Ctrl+V 클립보드 이미지 붙여넣기
- 비정방형 이미지 선택 시 경고 표시 (교체 시 중앙 크롭 자동 처리)

### 4.6 미페 교체 실행

1. 설치 경로 유효성 검사
2. 기존 파일 백업 (설정에서 활성화 시)
3. 이미지 PNG 변환 + 비정방형이면 중앙 크롭
4. `p{spid}.png` 로 저장
5. **읽기전용 속성 설정** (`stat.S_IREAD` + Windows `SetFileAttributesW`)

### 4.7 파일 위치 열기

선수 선택 후 "파일 위치 열기" 버튼:
- 파일 존재 시: `explorer /select,"경로"` → 파일 선택 상태로 탐색기 열기
- 파일 없을 시: 미페 폴더 자체를 열기

### 4.8 변경 이력 관리

`history.json`에 저장:
- 변경된 선수명, SPID, 교체 이미지 경로, 변경 일시, 백업 파일 경로
- 이력 탭에서 개별/전체 복원 가능
- 백업 있으면 원본 복원, 없으면 파일 삭제 (게임 재실행 시 CDN 재다운로드)

### 4.9 자동 업데이트

- 앱 시작 시 GitHub Releases API로 최신 버전 확인 (백그라운드)
- 새 버전 있으면 상단 주황색 배너 표시
- 설정 탭에서 수동 업데이트 확인 가능

### 4.10 설정

- FC온라인 설치 경로 (자동 감지 + 수동 지정)
- 백업 활성화 / 백업 폴더 경로
- 시작 시 업데이트 자동 확인 여부
- `config.json`에 저장, 재시작 시 유지

### 4.11 감독 DB 자동 생성

FC Online 데이터센터(`https://fconline.nexon.com/datacenter/manager`)를 BeautifulSoup4로 크롤링해 감독 DB를 자동 생성한다.

- `src/core/manager_db.py`: `build_db()` → HTML 파싱 → `managers_db.json` 저장
- 파싱 대상: `div.tbody > div.tr` → `span.rank_coach` 안의 이름, 소속팀, 썸네일 URL
- 썸네일 URL에서 `heads_staff_{id}.png` 패턴으로 감독 ID 추출
- `ensure_db()`: DB 파일 없으면 자동 빌드, 메모리 캐시 `_cache` 재사용
- `search(query, db)`: 이름/팀명 부분 일치, 결과 이름순 정렬
- DB 파일 위치: `.cache/managers_db.json` (기존 spid.json, seasonid.json과 동일 폴더)

### 4.12 감독 얼굴 변경

- `src/core/manager_changer.py`: `replace_manager()`, `restore_to_official()`, `fetch_official_image()`, `load_manager_image()`
- 로컬 파일 경로: `{설치경로}\_cache\live\externalAssets\common\managers\heads_staff_{id}.png`
- CDN URL: `https://fco.dn.nexoncdn.co.kr/live/externalAssets/common/managers/heads_staff_{id}.png`
- 교체/복원 모두 `_set_readonly()` / `_remove_readonly()` 처리 (미페와 동일)
- `ManagerChangeRecord` dataclass: `manager_id, manager_name, team, image_path, changed_at`
- `src/ui/manager_frame.py`: 좌측 검색 패널 + 우측 미리보기/교체 패널 구조
  - 검색은 Enter/버튼으로만 실행, 최대 100건 표시
  - 썸네일 비동기 로드: `ThreadPoolExecutor(max_workers=6)` + `_render_gen` 카운터로 stale 로드 취소
  - 상단 세그먼트 버튼으로 **현재 얼굴** (로컬 파일) / **공식 얼굴** (CDN) 토글
  - 공식 얼굴로 복원 버튼: CDN 다운로드 후 이력에서 해당 기록 제거
- `src/core/history.py` 확장: `load_manager_history()`, `save_manager_history()`, `add_manager_record()`, `find_manager_record()`, `remove_manager_record()`
- `src/ui/history_frame.py` 확장: "감독 변경 이력" 섹션 추가 (썸네일 + 이름/팀/날짜 + 공식 복원 + 삭제 버튼)

### 4.13 시작 시 DB 초기화 오버레이

앱 시작 시 3개 DB 파일(`spid.json`, `seasonid.json`, `managers_db.json`) 중 하나라도 없으면 blocking 오버레이를 띄우고 순서대로 생성한다.

- `src/core/db_init.py`: `check_missing()` → 누락 파일 키 목록 반환, `build_missing(missing, step_cb)` → 단계별 콜백 호출
- `src/ui/app.py`: 시작 시 `check_missing()` → 누락 있으면 `_start_db_init(missing)`, 없으면 업데이트 확인 진행
- `_show_db_overlay()`: 반투명 CTkFrame 오버레이 + 진행 단계 레이블 + 프로그레스바
- `_on_db_step(key, label, fraction)`: fraction=1.0 항목마다 레이블 갱신, 모든 단계 완료 시 오버레이 숨김 후 업데이트 확인 진행

---

## 5. 발생했던 버그 및 수정 이력

### BUG-01: API 403 오류 (베이스 URL 오류)

**증상**: `spid.json` 다운로드 시 403 Access Denied  
**원인**: 메타데이터 엔드포인트를 CDN URL(`fco.dn.nexoncdn.co.kr`)로 요청  
**수정**: 메타데이터는 `open.api.nexon.com`, 이미지는 CDN으로 분리. Session도 두 개로 분리.

---

### BUG-02: CTkLabel `image=None` 에러

**증상**:
```
_tkinter.TclError: image "pyimage1" doesn't exist
```
**원인**: `CTkLabel.configure(image=None, text="이미지 없음")` 호출 시 내부 tkinter 레이블에서 이전 이미지 참조 충돌  
**수정**: `image=None` 전달 금지. 대신 1×1 투명 CTkImage로 교체하고, 플레이스홀더 텍스트는 별도 레이블로 분리해 show/hide 방식으로 처리.

---

### BUG-03: 람다 클로저 변수 해제 오류

**증상**:
```
NameError: free variable 'e' referenced before assignment in enclosing scope
```
**원인**: Python 3.10에서 `except ... as e` 블록 종료 후 `e`가 스코프에서 삭제되는데, 이를 람다에서 참조  
**수정**: 람다 외부에서 `msg = str(e)` 로 미리 복사 후 람다 default 인자로 캡처.
```python
# 수정 전
except Exception as e:
    self.after(0, lambda: label.configure(text=f"오류: {e}"))

# 수정 후
except Exception as e:
    msg = str(e)
    self.after(0, lambda m=msg: label.configure(text=f"오류: {m}"))
```

---

### BUG-04: 이미지 리사이즈 중복으로 화질 저하

**증상**: 미페 미리보기 이미지가 뭉개지고 픽셀화되어 표시  
**원인**: `get_player_image()`에서 다운로드 즉시 `(160,160)`으로 resize 후 캐시 저장 → `ImagePreview`에서 또 한번 thumbnail 처리 → 2회 리사이즈로 품질 열화  
**수정**: `get_player_image()`는 원본 PIL Image 그대로 캐시. 표시 크기는 `CTkImage(size=(w,h))` 파라미터로만 제어.

---

### BUG-05: 드롭다운 geometry 포맷 오류

**증상**:
```
_tkinter.TclError: bad geometry specifier "300+1354+631"
```
**원인**: `self.geometry(f"{self.WIDTH}+{ax}+{ay}")` → tkinter geometry는 `WxH+x+y` 형식이 필요한데 `x` 구분자 없이 `W+x+y`로 잘못 작성  
**수정**: `_build()` 호출 후 `winfo_reqheight()`로 실제 높이 측정, `f"{self.WIDTH}x{h}+{ax}+{ay}"` 형식 사용.

---

### BUG-06: FilterDropdown에서 `winfo_toplevel()` 호출 시 TypeError

**증상**:
```
TypeError: 'FilterDropdown' object is not callable
```
**원인**: `FilterDropdown`은 `tk.Toplevel` 서브클래스. 자신의 `winfo_toplevel()`을 호출하면 자기 자신이 반환됨 → tkinter 내부가 이 Toplevel 객체를 루트 창으로 인식하고 callable로 호출 시도 → TypeError  
**수정**: 생성 시 메인 앱 창(`main_window`)을 직접 인자로 받아 저장. 외부 클릭 바인딩도 `main_window`에 직접 설정. `nametowidget(".")`으로 루트 창 안전하게 획득.

---

### BUG-07: pyc 캐시로 인한 수정 미반영

**증상**: 소스 수정 후 재실행해도 동일 에러 반복 (구버전 코드 실행)  
**원인**: `__pycache__`에 저장된 `.pyc` 바이트코드 파일이 갱신되지 않아 이전 버전 실행  
**수정**: `find ... -name "*.pyc" -delete` 로 캐시 전체 삭제 후 재실행.

---

### BUG-08: 감독 탭 추가 후 앱 전체가 심각하게 느려짐

**증상**: 감독 탭 추가 후 모든 UI 조작이 수초~수십초 지연, 사실상 사용 불가  
**원인**: `StringVar.trace_add("write", ...)` 로 검색창 입력 때마다 `_render_list()` 호출 → DB 전체(~600건) 렌더링 → 동시에 600개 썸네일 로드 스레드 생성  
**수정**: `trace_add` 제거. 검색 실행을 Enter 키 / 검색 버튼 클릭으로만 한정. 결과 최대 100건. `_render_gen` 카운터로 stale 썸네일 로드 취소.

```python
# 잘못된 방식 — 입력 때마다 수백 개 스레드 생성
self._search_var.trace_add("write", lambda *_: self._do_search())

# 수정된 방식 — Enter/버튼으로만 실행
self._entry.bind("<Return>", lambda e: self._do_search())
self._search_btn.configure(command=self._do_search)
```

---

### BUG-09: cv2.imread가 한글 경로에서 None 반환

**증상**: `cv2.imread("D:/박시몬/...")` 반환값이 None, 이미지 로드 실패  
**원인**: Windows에서 OpenCV의 `cv2.imread`는 유니코드(한글/CJK) 경로를 지원하지 않음  
**수정**: `np.fromfile` + `cv2.imdecode` 조합으로 우회:

```python
def _cv2_read(path, flags=cv2.IMREAD_UNCHANGED):
    arr = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(arr, flags)
```

---

## 6. 설계 결정 사항

### 6.1 선수 데이터 로컬 캐싱 전략
86,036명 전체 데이터를 앱 시작 시 1회 로드 후 메모리에 상주. 검색은 100% 로컬 필터링으로 API 호출 없음. 30일 이후 갱신 (Nexon 이용약관 의무).

### 6.2 이미지 메모리 캐시 상한
선수 이미지: 최대 100개 메모리 캐시 (LRU 방식, 가장 오래된 항목 제거).  
시즌 뱃지: 142개 전체 캐시 (소용량이라 상한 없음).

### 6.3 UI 비동기 처리
pywebview는 화면의 API 호출을 호출마다 별도 스레드에서 실행하므로 네트워크·파일 작업을 그대로 수행한다. 화면은 Promise로 결과를 받고, 진행률(DB 생성·업데이트 다운로드)은 파이썬이 `window.state.progress`를 갱신해 전달한다.

### 6.4 API 키 관리 현황
현재 `api_key.txt`에 저장, 개인이 직접 발급. 타인에게 배포 시 사용성 문제 있음. 추후 `spid.json`을 GitHub 릴리즈에 번들로 포함하는 방식으로 전환 고려 중.

### 6.5 감독 변경 이력: 스택 누적 vs 덮어쓰기

미페/크레스트 이력은 변경할 때마다 스택으로 쌓는다. 감독은 같은 ID에 대한 기존 기록을 덮어쓴다.

**이유**: 미페는 백업 파일이 실제로 존재하고 순차 복원이 의미 있다. 감독은 백업 파일을 생성하지 않기 때문에 이력이 쌓여도 중간 시점으로 복원할 방법이 없다. 복원은 항상 CDN에서 공식 얼굴을 내려받는 것으로 처리된다. 따라서 가장 최근 적용 기록 1건만 유지한다.

**적용**: `history.add_manager_record(record)` 는 동일 `manager_id`의 기존 레코드를 먼저 찾아 제거한 뒤 새 레코드를 추가한다.

---

### 6.6 미페 교체 대상: 데이터센터 경로 (v0.4.1)

카드마다 게임이 기본으로 쓰는 미페 파일은 넥슨 서버가 정한다. CDN에 `playersAction/p{spid}.png`가 있어도 게임은 `players/p{pid}.png`(대갈)나 `playersAction/p{pid}_25.png`(공통)를 쓰는 경우가 많다. 파일 존재 여부로는 판별할 수 없어, 데이터센터 선수검색 결과의 이미지 경로를 정답으로 쓴다(인게임 테스트로 검증). `playersActionHigh`/`playersHigh`는 확인한 화면에서 쓰이지 않아 교체하지 않는다.

여러 카드가 같은 파일을 쓰면 카드별로 따로 바꿀 수 없으므로 교체 전에 함께 바뀌는 카드를 알린다.

### 6.7 전체 미페(바둑판) 모드 (v0.5.0)

인게임에서 카드별로 미페를 직접 고를 수 있어 기본 경로만으로는 사용자가 보는 파일을 알 수 없다. 선수 한 명의 후보(대갈 / 공통 연도별 / 카드 전용)를 게임 캐시·데이터센터·CDN 확인으로 모아 보여주고 사용자가 고르게 한다.

### 6.8 화면 구조: pywebview + Svelte (v0.5.0)

CustomTkinter를 걷어내고 웹 기술로 화면을 다시 만들었다. 핵심 로직(`src/core`, `src/api`)은 그대로 두고 `src/app/api.py`가 화면용 API를, `src/app/server.py`가 빌드된 화면과 게임 이미지를 제공한다. 8만 명이 넘는 선수 목록은 브리지 직렬화 부담을 피해 HTTP로 받는다. 게임 파일 이미지 주소에는 수정 시각을 붙여 교체 직후에도 웹뷰 캐시 대신 새 이미지를 받는다.

---

## 7. 미구현 / 추후 과제

| 항목 | 상태 | 비고 |
|------|------|------|
| 팀별 필터 | 미구현 | API에 팀 정보 없음. 데이터센터 스크래핑 필요 - 복잡도 대비 효용 낮아 보류 |
| spid.json GitHub 번들 배포 | 미구현 | API 키 없이도 동작 가능하게 - 추후 배포 전 결정 필요 |
| GitHub Actions 자동 빌드/배포 | 미구현 | 릴리즈 파이프라인 구성 필요 |
| 설정 화면 API 키 입력란 | 미구현 | 현재 파일로만 관리 |
