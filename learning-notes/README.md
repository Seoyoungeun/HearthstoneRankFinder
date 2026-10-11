# HearthstoneRankFinder 개발 학습 노트

> **프로젝트:** 하스스톤 전장 순위 검색기 (Windows Desktop App)  
> **학습 목적:** 프로그램을 직접 만들면서 이해한 개념, 설계 이유, 시행착오를 기록한다.  
> **프로젝트 저장소:** [HearthstoneRankFinder](https://github.com/Seoyoungeun/HearthstoneRankFinder)  
> **기준 버전:** v1.0.0 (2026-10)

이 문서는 사용자에게 프로그램 사용법을 설명하는 **최상위 `README.md`와는 별개**로, 개발 과정에서 배운 내용을 복습하기 위한 개인 학습 기록이다.

## 1. 프로젝트에서 구현한 것

하스스톤 공식 전장 리더보드의 공개 데이터를 조회해 **닉네임과 일치하는 플레이어의 순위(Rank), 닉네임, 점수(Rating/MMR)**를 Windows 창에서 보여주는 프로그램을 만들었다.

- **Python**으로 전체 프로그램 작성
- **Tkinter / ttk**로 검색창·버튼·진행률·결과 표 구성
- **requests**로 홈페이지의 순위 데이터 요청
- **threading + queue.Queue**로 UI 작업과 네트워크 작업 분리
- **ThreadPoolExecutor**로 여러 페이지 병렬 조회
- **threading.Event**로 검색 중단 요청 전달
- 모든 공개 페이지를 조회해 **같은 닉네임의 여러 결과** 확인
- **PyInstaller**로 Windows 실행 파일(EXE) 생성
- **Git / GitHub**로 소스 관리하고 **GitHub Releases**에 EXE 배포

### 데이터 흐름

```text
[사용자가 검색 버튼 클릭]
          │
          ▼
[메인 스레드: start_search()]
          │ 새로운 검색 관리 스레드 생성
          ▼
[검색 관리 스레드: fetch_leaderboard()]
          │ 1페이지 요청 → totalPages 파악
          ▼
[ThreadPoolExecutor: 최대 6개 페이지 동시 요청]
          │ 완료된 페이지부터 nickname 비교
          ▼
[queue.Queue: progress / match / done / error / cancelled]
          │
          ▼
[메인 스레드: check_messages()]
          │
          ▼
[Tkinter 결과 표·상태 메시지 갱신]
```

> **현재 방식:** 검색할 때마다 순위 데이터를 새로 가져온다. 미리 전체 데이터를 로컬 DB나 JSON으로 저장하는 **캐싱 방식은 아직 구현하지 않았다.**

---

## 2. Tkinter와 ttk: Windows GUI 만들기

**GUI(Graphical User Interface)**는 버튼, 입력창, 표 등 눈으로 조작하는 화면이다.

- `tkinter`: Python 기본 GUI 라이브러리
- `ttk`: Tkinter 위젯의 테마/스타일이 적용된 버전 (`ttk.Entry`, `ttk.Button`, `ttk.Treeview` 등)
- `tk.Tk()`: 프로그램의 최상위 창 생성
- `root.mainloop()`: 클릭·키 입력·화면 갱신 등의 이벤트를 계속 처리
- `command=self.start_search`: 버튼을 누르면 함수 호출. **괄호 `()`를 붙이지 않는다.**

```python
root = tk.Tk()
app = RankFinderApp(root)
root.mainloop()
```

`StringVar`는 입력창·상태 라벨과 값을 연동할 때 사용했다.

```python
self.nickname_var = tk.StringVar()
self.status_var = tk.StringVar(value="닉네임을 입력해주세요.")
```

**배운 점:** 화면을 만드는 코드와 오래 걸리는 통신 작업을 메인 스레드에 함께 넣으면 화면이 멈출 수 있다.

## 3. HTTP 요청, JSON, 페이지네이션

공식 리더보드 페이지가 사용하는 데이터 요청 경로에 `requests`로 접근했다.

```python
response = requests.get(
    API_URL,
    params={
        "region": "AP",
        "leaderboardId": "battlegrounds",
        "page": 1,
    },
    timeout=15,
)
response.raise_for_status()
data = response.json()
```

- `GET`: 서버로부터 정보를 가져오는 HTTP 요청
- `params`: 쿼리 문자열로 전달할 조건 (`region`, `leaderboardId`, `page`)
- `timeout`: 요청이 무한히 기다리지 않도록 시간 제한
- `raise_for_status()`: 4xx/5xx 응답일 때 오류를 발생시켜 문제를 확인
- `response.json()`: JSON 응답을 Python `dict`/`list`로 변환
- `rows`: 페이지에 실린 플레이어 목록
- `pagination["totalPages"]`: 전체 페이지 수

### 페이지네이션이란?

순위 데이터가 많아 서버에서 **1페이지, 2페이지, ...**로 나누어 전달하는 방식이다. 전체 페이지 수를 코드에 `80`처럼 고정하지 않고, 첫 응답에서 읽는다.

```python
first_rows, pagination = fetch_page(1)
total_pages = int(pagination["totalPages"])
```

따라서 80페이지가 81페이지로 늘어나도 **다음 검색에서 응답이 제공하는 페이지 수를 기준으로** 자동 조회할 수 있다. 다만 검색 도중 순위표가 바뀌면 첫 페이지에서 읽은 수를 기준으로 진행한다.

> **주의:** `leaderboardsData`는 홈페이지에서 사용하는 내부 데이터 경로로, 안정성이 보장되는 공개 API라고 단정하면 안 된다. 홈페이지의 응답 구조가 바뀌면 코드를 수정해야 할 수 있다.

## 4. 메인 스레드와 작업 스레드

### 왜 스레드를 나누었을까?

`requests.get()`은 응답이 올 때까지 기다리는 **블로킹 I/O**다. 이것을 Tkinter 메인 스레드에서 직접 실행하면 버튼, 화면 갱신까지 멈출 수 있다.

```python
threading.Thread(
    target=self.fetch_leaderboard,
    args=(nickname, region),
    daemon=True,
).start()
```

- **메인 스레드:** Tkinter 창과 사용자 입력 처리
- **검색 관리 스레드:** 서버 요청과 페이지 검색을 관리
- **스레드 풀 작업자:** 개별 페이지의 HTTP 요청을 병렬 처리
- `daemon=True`: 검색 관리 스레드를 데몬으로 설정 (종료 정책과 실제 진행 중 요청의 정리는 별개로 고려해야 한다)

**배운 점:** 스레드의 주목적은 단순히 속도를 높이는 것뿐 아니라, **느린 네트워크 작업 중에도 GUI의 응답성을 유지하는 것**이다.

## 5. queue.Queue: 스레드 사이의 안전한 메시지 전달

Tkinter 위젯을 작업 스레드에서 직접 변경하지 않고, 작업 결과를 큐에 넣어 **메인 스레드가 화면을 갱신**하도록 했다.

```python
# 검색 관리 스레드
self.messages.put(("match", (rank, nickname, rating)))

# 메인 스레드
kind, payload = self.messages.get_nowait()
if kind == "match":
    rank, nickname, rating = payload
    self.table.insert("", "end", values=(rank, nickname, rating))
```

- `put()`: 메시지 넣기
- `get_nowait()`: 있으면 꺼내고, 없으면 `queue.Empty` 예외
- **FIFO:** 먼저 들어온 메시지부터 처리
- `queue.Queue`: 여러 스레드가 접근할 때 동기화를 지원

```python
self.root.after(100, self.check_messages)
```

`after(100, ...)`는 **100ms 후에 메인 스레드에서 큐를 다시 확인하도록 예약**하는 코드다. **서버에 0.1초마다 요청한다는 의미가 아니다.**

주로 사용한 메시지 종류:

| 메시지 | 의미 |
|---|---|
| `progress` | 완료한 페이지 수 / 전체 페이지 수 |
| `match` | 닉네임 일치 결과 |
| `done` | 전체 페이지 검색 완료 |
| `cancelled` | 사용자 중단 요청으로 검색 종료 |
| `error` | 통신·데이터 처리 예외 |

## 6. threading.Event: 검색 중단

```python
self.stop_event = threading.Event()

# 검색 시작 시
self.stop_event.clear()

# 중단 버튼 클릭 시
self.stop_event.set()

# 작업 스레드에서 확인
if self.stop_event.is_set():
    self.messages.put(("cancelled", None))
    return
```

`Event`는 스레드를 강제로 죽이지 않는다. 작업 코드가 `is_set()`으로 **중단 요청을 협력적으로 확인**하는 구조다. 이미 진행 중인 HTTP 요청은 응답하거나 타임아웃될 때까지 남을 수 있다.

```python
if self.stop_event.wait(0.15):
    # 대기 중 중단 신호를 받았을 때만 실행
    return
```

`wait(0.15)`는 **최대 0.15초 기다리는 것**이지, **0.15초마다 HTTP 요청을 보내는 것**이 아니다. 초기 버전에서는 페이지 또는 요청 묶음 사이의 간격을 두는 데 사용했다.

## 7. ThreadPoolExecutor: 병렬 크롤링

### 처음 만든 순차 방식

```text
1페이지 요청 및 응답 → 2페이지 요청 및 응답 → 3페이지 ...
```

요청 하나가 오래 걸리면 뒤의 요청도 모두 지연되었다.

### 첫 번째 병렬 방식: 묶음 처리

```text
(2, 3, 4, 5페이지를 동시 요청)
      ↓ 모두 완료될 때까지 대기
(6, 7, 8, 9페이지를 동시 요청)
```

묶음에서 가장 느린 요청 때문에 다른 작업 스레드들이 놀 수 있었다.

### 개선한 방식: 완료 즉시 다음 작업 보충

```python
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

with ThreadPoolExecutor(max_workers=6) as executor:
    pending = set()
    next_page = 2

    # 최초 작업 제출
    while next_page <= total_pages and len(pending) < 6:
        pending.add(executor.submit(fetch_page, next_page))
        next_page += 1

    while pending:
        finished, pending = wait(
            pending,
            timeout=0.2,
            return_when=FIRST_COMPLETED,
        )
        for future in finished:
            result = future.result()  # 오류가 났다면 여기서 다시 발생
            # result의 rows를 검사하고 진행률 갱신

            if next_page <= total_pages:
                pending.add(executor.submit(fetch_page, next_page))
                next_page += 1
```

> 위 코드는 **핵심 원리를 발췌한 예시**다. 실제 구현에서는 `stop_event`, `None` 결과 처리, 응답 검증, `Queue` 메시지 전송을 함께 유지해야 한다.

- `max_workers=6`: 최대 6개의 작업자가 동시에 요청을 수행
- `executor.submit()`: 함수를 작업 스레드에 제출하고 `Future` 반환
- `Future`: 아직 완료되지 않았거나 완료된 작업의 결과를 나타내는 객체
- `wait(..., FIRST_COMPLETED)`: 작업 중 하나 이상이 끝나면 반환
- `future.result()`: 완료된 작업의 반환값 또는 발생한 예외를 받음
- `pending`: 진행 중인 `Future`들을 관리하는 집합
- `timeout=0.2`: **완료된 작업을 최대 0.2초 기다리는 옵션**이지 HTTP 요청 주기가 아님

**주의:** 동시 요청을 늘리면 서버에 부담을 줄 수 있다. 응답 지연, 타임아웃, `429 Too Many Requests`를 관찰하고 동시 요청 수를 조절해야 한다.

## 8. 닉네임 검색과 동명이인

```python
if account.casefold() == nickname.casefold():
    found += 1
    self.messages.put(("match", (rank, account, rating)))
```

- `casefold()`: 영어 대소문자 차이를 완화해 문자열 비교
- `found`: 발견한 일치 결과 수
- `nonlocal found`: `fetch_leaderboard()` 내부에 정의한 `check_players()`가 바깥 함수의 지역 변수를 수정할 수 있게 함

처음에는 닉네임을 하나 찾으면 `return`하는 방식을 검토했다. 하지만 **같은 닉네임의 다른 플레이어를 놓칠 수 있어** 채택하지 않았다. 현재는 마지막 페이지까지 확인해 공개 순위표의 동명이인을 모두 찾는다.

> 공개 순위표에 `BattleTag#숫자` 전체 식별자가 나타나지 않는다면, 동일한 표시 닉네임을 가진 플레이어를 정확히 구분하기는 어렵다.

## 9. 실제 측정한 성능과 해석

개발 중 수집한 측정값:

| 동시 요청 수 | 검색 시간 | 비고 |
|---:|---:|---|
| 4 | 39.22초 | 검색 결과 수 미기록 |
| 4 | 70.19초 | 1명 |
| 6 | 47.28초 | 1명 |
| 8 | 42.37초 | 1명 |

- 동일한 4개 설정에서도 **39.22초와 70.19초**로 편차가 컸다.
- 요청 수를 늘렸다고 반드시 비례해서 빨라지는 것은 아니다.
- 서버 응답 시간과 네트워크 상태가 성능에 큰 영향을 줄 수 있다.
- 최종 구현에서는 **6개 작업자**를 선택했다. 이는 개발 중 선택한 설정이며, 위의 적은 측정값만으로 **객관적으로 최적**이라고 결론 내릴 수는 없다.

향후에는 동일 조건에서 설정별 **3~5회 이상 반복 측정**하고 평균, 중앙값, 실패율을 함께 비교하고 싶다.

```python
import time

start_time = time.perf_counter()
# 전체 검색 작업
elapsed = time.perf_counter() - start_time
print(f"검색 소요 시간: {elapsed:.2f}초")
```

## 10. 해결한 오류와 시행착오

### ① `ModuleNotFoundError: No module named 'requests'`

**원인:** 현재 프로젝트의 `.venv`에 requests가 설치되지 않음.

```powershell
.\.venv\Scripts\python.exe -m pip install requests
```

**배운 점:** 가상환경마다 설치된 패키지가 다르므로, 실행에 사용하는 Python에 설치해야 한다.

### ② `AttributeError: RankFinderApp ... has no attribute 'stop_search'`

**원인 후보:** 메서드가 클래스 바깥에 있거나 들여쓰기가 잘못됐거나, 저장·실행한 파일이 다른 경우.

```python
class RankFinderApp:
    def start_search(self):
        ...

    def fetch_leaderboard(self, nickname, region):
        ...

    def stop_search(self):  # 다른 메서드와 동일한 4칸 들여쓰기
        ...
```

**배운 점:** Python에서는 들여쓰기가 함수의 소속과 실행 범위를 결정한다.

### ③ 병렬화 후 1페이지 부근에서 갑자기 중단

**확인한 원인:** 코드를 교체하는 과정에서 아래 두 줄이 불필요하게 남아 있었다.

```python
self.messages.put(("cancelled", None))
return
```

다음 페이지 작업을 제출한 직후에 이 코드가 실행되어 검색이 종료되었다. 잘못 남은 두 줄을 제거하여 해결했다.

**배운 점:** 기존 코드를 일부 교체할 때 **남은 중단·종료 로직**까지 확인해야 한다.

### ④ Git 오류: `remote origin already exists`

이미 원격 저장소가 지정되어 있을 때 `git remote add origin`을 다시 실행해서 발생했다.

```powershell
git remote -v
git remote set-url origin https://github.com/Seoyoungeun/HearthstoneRankFinder.git
```

**배운 점:** `git remote add`는 새 연결, `git remote set-url`은 기존 연결 주소 변경이다.

## 11. Git / GitHub로 버전 관리

기본 순서:

```powershell
git status
git add .
git commit -m "Describe changes"
git push origin main
```

주요 개념:

| 용어 | 의미 |
|---|---|
| Repository | 프로젝트의 코드와 기록을 보관하는 저장소 |
| `git init` | 로컬 Git 저장소 초기화 |
| `git add` | 커밋할 변경 파일을 스테이징 |
| `git commit` | 현재 변경 내역을 하나의 기록으로 저장 |
| `git remote` | 연결된 GitHub 주소 관리 |
| `git push` | 로컬 커밋을 원격 저장소로 업로드 |
| `.gitignore` | 가상환경·빌드 결과 등 Git에서 제외할 경로 지정 |
| Release / Tag | 사용자에게 특정 버전의 실행 파일을 배포할 때 사용 |

`.venv/`, `build/`, `dist/`, `__pycache__/` 등은 일반적으로 소스 코드 저장소에서 제외하고, **실행 파일은 GitHub Releases의 Assets**에 별도로 올렸다.

## 12. Windows EXE 빌드 및 배포

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name HearthstoneRankFinder main.py
```

- `--onefile`: 단일 EXE 생성
- `--windowed`: GUI 실행 시 별도 콘솔 창 숨김
- `--name`: EXE 파일 이름 지정
- 결과물: `dist/HearthstoneRankFinder.exe`

**주의:** `--windowed` 빌드에서는 콘솔 출력인 `print()`를 사용자에게 보여주지 않는다. 따라서 검색 시간과 오류를 화면에 표시하거나 로그 파일에 기록하면 배포 후 문제 확인에 도움이 된다.

배포 과정:

```text
소스 코드 커밋·push → GitHub Releases → v1.0.0 태그
→ EXE 첨부 → Publish release
```

## 13. 앞으로 개선하고 싶은 점

- [ ] 데이터 캐싱: 전체 순위 데이터를 한 번 수집하고 일정 시간 재사용
- [ ] 완료된 데이터만 캐시에 반영하고 중간 실패 시 기존 캐시 보존
- [ ] 검색 결과를 순위 오름차순으로 정렬 (병렬 응답은 순서가 보장되지 않음)
- [ ] 네트워크 요청과 닉네임 검색을 GUI 코드에서 분리하여 테스트 용이성 개선

## 14. 이번 프로젝트에서 얻은 핵심 교훈

1. **GUI의 반응성을 지키기 위해 네트워크 작업을 별도 스레드로 분리**해야 한다.
2. **Queue는 스레드 사이의 결과 전달용**이고, 화면 변경은 메인 스레드가 담당한다.
3. **Event는 중단 신호**이지, 작업을 즉시 강제 종료하는 기능이 아니다.
4. **페이지네이션과 JSON 구조**를 이해해야 순위표 전체를 올바르게 조회할 수 있다.
5. **스레드 수보다 작업 배정 방식과 서버 응답 편차**가 성능에 큰 영향을 줄 수 있다.
6. **속도 개선이 정확성을 해치면 안 된다.** 첫 일치 결과에서 종료하면 동명이인을 놓친다.
7. **작은 변경을 테스트하고 측정한 뒤 배포**하는 개발 흐름의 중요성을 경험했다.
8. Python으로 만든 프로그램을 **EXE로 패키징하고 GitHub에서 배포하는 전체 과정**을 경험했다.

---
