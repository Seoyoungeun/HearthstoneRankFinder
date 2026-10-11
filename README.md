# Hearthstone Battlegrounds Rank Finder

하스스톤 **전장(Battlegrounds)** 공식 리더보드에서 플레이어의 닉네임을 검색해 **순위(Rank)**와 **평점(Rating/MMR)**을 보여주는 Windows 데스크톱 프로그램입니다.

Python의 **Tkinter**로 화면을 만들고, `requests`와 `ThreadPoolExecutor`를 이용해 공개 순위표를 병렬로 조회합니다.

> 이 프로젝트는 개인이 제작한 비공식 도구이며 Blizzard Entertainment와 제휴하거나 공식적으로 승인받은 프로그램이 아닙니다.

## 주요 기능

- **닉네임 검색**: 대소문자를 구분하지 않고 공개 리더보드에서 일치하는 닉네임 검색
- **서버 선택**: 아시아(AP), 아메리카(US), 유럽(EU)
- **순위 정보 표시**: 순위, 닉네임, 전장 평점(MMR)
- **동명이인 검색**: 같은 닉네임을 가진 플레이어가 있을 경우 모두 표시
- **병렬 데이터 조회**: 최대 6개 작업 스레드로 서로 다른 순위표 페이지 요청
- **진행 상황 및 중단**: 조회 중 진행 페이지 수와 검색 결과를 표시하고 중단 요청 지원
- **Windows EXE 배포**: Python을 별도로 설치하지 않고 실행 가능

## 다운로드 및 사용법 (Windows)

1. [Releases 페이지](https://github.com/Seoyoungeun/HearthstoneRankFinder/releases)에서 최신 버전을 선택합니다.
2. **Assets**에서 `HearthstoneRankFinder.exe` 파일을 다운로드합니다.
3. 다운로드한 EXE를 더블클릭해 실행합니다.
4. 닉네임을 입력하고 서버를 선택한 뒤 **검색** 버튼을 누릅니다.
5. 검색 결과 목록에서 **순위 / 닉네임 / MMR**을 확인합니다.

인터넷 연결이 필요하며, 프로그램은 **공개 리더보드에 등록된 플레이어**만 검색할 수 있습니다. 검색 대상이 없거나 서버 응답이 지연되면 전체 순위표 조회에 시간이 걸릴 수 있습니다.

## 소스 코드로 실행하기

**요구 사항:** Windows, Python 3.11 이상 (Tkinter 포함), 인터넷 연결

PowerShell에서 저장소 폴더를 연 뒤 다음 명령어를 실행합니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

`requirements.txt` 내용:

```text
requests>=2.32,<3
```

## 실행 파일 직접 빌드

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name HearthstoneRankFinder main.py
```

빌드 결과는 `dist/HearthstoneRankFinder.exe`에 생성됩니다. 배포용 실행 파일은 Git 저장소에 직접 추가하기보다 **GitHub Releases**에 첨부하는 것을 권장합니다.

## 동작 방식

1. 검색 버튼을 클릭하면 Tkinter 메인 스레드와 별도로 검색 관리 스레드를 시작합니다.
2. 블리자드 리더보드의 첫 페이지를 요청해 `totalPages`를 확인합니다.
3. 이후 최대 **6개 작업 스레드**에서 여러 페이지를 병렬 조회하며, 완료된 작업부터 다음 페이지를 요청합니다.
4. 각 페이지의 `accountid`를 닉네임과 비교하고 일치하는 결과를 큐(`queue.Queue`)로 메인 스레드에 전달합니다.
5. 모든 공개 페이지를 조회하면 검색을 종료합니다. 중단 버튼을 누르면 진행 중인 요청이 마무리되는 대로 종료를 시도합니다.

**참고:** 현재 버전은 검색할 때마다 리더보드 데이터를 요청하며, 전체 순위를 로컬 데이터베이스에 저장해 재사용하는 캐시 기능은 없습니다.

## 사용 시 유의사항

- 순위 및 MMR 정보는 블리자드 공식 웹사이트에서 공개한 데이터에 의존합니다.
- 사용 중인 리더보드 데이터 경로는 웹사이트 내부 엔드포인트로, 구조가 변경되면 검색 기능이 동작하지 않을 수 있습니다.
- 시즌 변경이나 조회 중 순위표 갱신에 따라 결과가 달라질 수 있습니다.
- 같은 닉네임의 서로 다른 플레이어를 구분하는 배틀태그 숫자는 공개 순위 데이터만으로 확인할 수 없을 수 있습니다.
- 개인이 제작하고 디지털 서명하지 않은 EXE는 Windows에서 보안 경고가 표시될 수 있습니다. 다운로드 출처를 확인한 후 실행하세요.

## 기술 스택

- **Language**: Python
- **GUI**: Tkinter / ttk
- **HTTP**: requests
- **Concurrency**: threading, `concurrent.futures.ThreadPoolExecutor`
- **Packaging**: PyInstaller

## 향후 개선 아이디어

- 전체 리더보드의 로컬 캐시 및 주기적 갱신
- 검색 소요 시간의 GUI 표시
- 검색 결과 정렬 및 내보내기
- GUI 디자인 개선

## 면책 안내

Hearthstone 및 Battlegrounds 관련 상표는 각각의 권리자에게 귀속됩니다. 본 프로젝트는 공개 리더보드 조회를 돕기 위한 비공식 개인 프로젝트입니다.
