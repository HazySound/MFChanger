# MFChanger 개발 일지

> 작성일: 2026-04-03  
> 버전: v0.1.0 (개발 중)

---

## 1. 프로젝트 구조

```
MFChanger/
├── main.py                              # 진입점
├── version.py                           # 버전 정보 (v0.1.0)
├── requirements.txt                     # 의존성 목록
├── api_key.txt                          # Nexon Open API 키 (gitignore 대상)
├── config.json                          # 사용자 설정 (자동 생성)
├── history.json                         # 미페 변경 이력 (자동 생성)
├── REQUIREMENTS.md                      # 기획 요구사항 문서
├── DEVLOG.md                            # 본 개발 일지
├── .cache/
│   ├── spid.json                        # 선수 메타데이터 캐시 (30일)
│   └── seasonid.json                    # 시즌 메타데이터 캐시 (30일)
└── src/
    ├── api/
    │   └── nexon_api.py                 # Nexon/CDN API 클라이언트
    ├── core/
    │   ├── config.py                    # 설정 관리
    │   ├── face_changer.py              # 미페 교체 핵심 로직
    │   ├── history.py                   # 변경 이력 관리
    │   └── updater.py                   # GitHub 자동 업데이트
    └── ui/
        ├── app.py                       # 메인 앱 윈도우 (탭 구조)
        ├── main_frame.py                # 미페 변경 메인 화면
        ├── settings_frame.py            # 설정 화면
        ├── history_frame.py             # 변경 이력 화면
        └── components/
            ├── image_preview.py         # 이미지 미리보기 위젯
            ├── player_list.py           # 선수 검색 + 결과 목록
            └── filter_panel.py          # 드롭다운 필터 팝업
```

---

## 2. 기술 스택

| 항목 | 내용 |
|------|------|
| 언어 | Python 3.10.11 |
| GUI | CustomTkinter 5.2.2 |
| HTTP | requests 2.33.1 |
| 이미지 | Pillow 12.2.0 |
| 버전 비교 | packaging 26.0 |

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

## 6. 설계 결정 사항

### 6.1 선수 데이터 로컬 캐싱 전략
86,036명 전체 데이터를 앱 시작 시 1회 로드 후 메모리에 상주. 검색은 100% 로컬 필터링으로 API 호출 없음. 30일 이후 갱신 (Nexon 이용약관 의무).

### 6.2 이미지 메모리 캐시 상한
선수 이미지: 최대 100개 메모리 캐시 (LRU 방식, 가장 오래된 항목 제거).  
시즌 뱃지: 142개 전체 캐시 (소용량이라 상한 없음).

### 6.3 UI 비동기 처리
API/파일 IO는 전부 `threading.Thread(daemon=True)`로 분리. UI 업데이트는 반드시 `self.after(0, callback)` 로 메인 스레드에서 실행.

### 6.4 API 키 관리 현황
현재 `api_key.txt`에 저장, 개인이 직접 발급. 타인에게 배포 시 사용성 문제 있음. 추후 `spid.json`을 GitHub 릴리즈에 번들로 포함하는 방식으로 전환 고려 중.

---

## 7. 미구현 / 추후 과제

| 항목 | 상태 | 비고 |
|------|------|------|
| 팀별 필터 | 미구현 | API에 팀 정보 없음. 데이터센터 스크래핑 필요 - 복잡도 대비 효용 낮아 보류 |
| spid.json GitHub 번들 배포 | 미구현 | API 키 없이도 동작 가능하게 - 추후 배포 전 결정 필요 |
| 드래그앤드롭 이미지 입력 | 미구현 | `tkinterdnd2` 라이브러리 필요, 현재 Ctrl+V로 대체 |
| PyInstaller 패키징 | 미구현 | 기능 완성 후 진행 |
| GitHub Actions 자동 빌드/배포 | 미구현 | 릴리즈 파이프라인 구성 필요 |
| 설정 화면 API 키 입력란 | 미구현 | 현재 파일로만 관리 |
