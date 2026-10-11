import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

import requests
import time

API_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
REGIONS = {"아시아": "AP", "아메리카": "US", "유럽": "EU"}


class RankFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("하스스톤 전장 순위 검색기")
        self.root.geometry("700x480")

        self.nickname_var = tk.StringVar()
        self.region_var = tk.StringVar(value="아시아")
        self.status_var = tk.StringVar(value="닉네임을 입력한 다음 검색을 눌러주세요.")

        # 작업 스레드에서 보내는 메시지는 메인 스레드에서만 화면에 반영
        self.messages = queue.Queue()
        self.stop_event = threading.Event()
        self.searching = False
        self.found_count = 0

        self.build_ui()
        self.root.after(100, self.check_messages)

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame, text="하스스톤 전장 순위 검색기",
            font=("맑은 고딕", 18, "bold")
        ).pack(pady=(0, 18))

        search_bar = ttk.Frame(frame)
        search_bar.pack(fill="x")

        self.nickname_entry = ttk.Entry(
            search_bar, textvariable=self.nickname_var, width=28
        )
        self.nickname_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.nickname_entry.bind("<Return>", lambda event: self.start_search())

        self.region_box = ttk.Combobox(
            search_bar, textvariable=self.region_var,
            values=list(REGIONS), state="readonly", width=9
        )
        self.region_box.pack(side="left", padx=(0, 8))

        self.search_button = ttk.Button(
            search_bar, text="검색", command=self.start_search
        )
        self.search_button.pack(side="left", padx=(0, 5))

        self.stop_button = ttk.Button(
            search_bar, text="중단", command=self.stop_search, state="disabled"
        )
        self.stop_button.pack(side="left")

        ttk.Label(frame, textvariable=self.status_var).pack(
            anchor="w", pady=(15, 8)
        )

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 12))

        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(
            table_frame,
            columns=("rank", "nickname", "rating"),
            show="headings", height=11
        )
        for key, label, width in [
            ("rank", "순위", 100),
            ("nickname", "닉네임", 280),
            ("rating", "MMR", 130),
        ]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, anchor="center")

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.table.yview
        )
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(
            frame, text="공식 전장 순위표 열기",
            command=self.open_website
        ).pack(pady=(15, 0))
        self.nickname_entry.focus_set()

    def start_search(self):
        if self.searching:
            return

        # 공개 순위표에는 배틀태그 번호가 아닌 닉네임만 표시됨
        nickname = self.nickname_var.get().strip().split("#", 1)[0]
        if not nickname:
            self.status_var.set("닉네임을 입력해주세요.")
            return

        region = REGIONS[self.region_var.get()]
        self.found_count = 0
        self.stop_event.clear()
        self.searching = True
        self.search_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress.start(12)
        self.status_var.set("공식 순위표에 연결 중...")

        for item in self.table.get_children():
            self.table.delete(item)

        # 네트워크 통신이 GUI를 멈추게 하지 않도록 스레드 사용
        threading.Thread(
            target=self.fetch_leaderboard,
            args=(nickname, region), daemon=True
        ).start()

    
    def fetch_leaderboard(self, nickname, region):
        start_time = time.perf_counter()  # 시작 시간

        found = 0
        max_workers = 6

        # 특정 페이지의 순위 데이터를 가져오는 함수
        def fetch_page(page):
            if self.stop_event.is_set():
                return None

            response = requests.get(
                API_URL,
                params={
                    "region": region,
                    "leaderboardId": "battlegrounds",
                    "page": page
                },
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json"
                },
                timeout=15
            )

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("서버 응답 형식이 올바르지 않습니다.")

            board = data.get("leaderboard")
            if not isinstance(board, dict):
                raise ValueError("순위표를 읽을 수 없습니다.")

            rows = board.get("rows")
            pagination = board.get("pagination")

            if not isinstance(rows, list):
                raise ValueError("순위 데이터 형식 오류")

            if not isinstance(pagination, dict):
                raise ValueError("페이지 정보 형식 오류")

            return rows, pagination

        # 가져온 페이지에서 닉네임 검색
        def check_players(rows):
            nonlocal found

            for player in rows:
                if not isinstance(player, dict):
                    continue

                account = str(player.get("accountid", ""))

                if account.casefold() == nickname.casefold():
                    found += 1

                    self.messages.put(("match", (
                        player.get("rank", "-"),
                        account,
                        player.get("rating", "-")
                    )))

        try:
            # 1페이지를 가져와 전체 페이지 수 확인
            first_result = fetch_page(1)

            if first_result is None:
                self.messages.put(("cancelled", None))
                return

            rows, pagination = first_result
            total_pages = int(pagination["totalPages"])

            if total_pages < 1:
                raise ValueError("전체 페이지 수가 올바르지 않습니다.")

            check_players(rows)

            completed = 1
            self.messages.put(("progress", (completed, total_pages)))

            # 2페이지부터 최대 4개씩 병렬 요청
            
            # 완료된 작업이 생기면 바로 다음 페이지 요청
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                pending = set()
                next_page = 2

                # 최초 작업 스레드 4개에 페이지 배정
                while next_page <= total_pages and len(pending) < max_workers:
                    future = executor.submit(fetch_page, next_page)
                    pending.add(future)
                    next_page += 1

                # 모든 페이지 조회가 완료될 때까지 반복
                while pending:
                    if self.stop_event.is_set():
                        self.messages.put(("cancelled", None))
                        return

                    # 한 개 이상의 작업 완료를 기다림
                    finished, pending = wait(
                        pending,
                        timeout=0.2,
                        return_when=FIRST_COMPLETED
                    )

                    for future in finished:
                        if self.stop_event.is_set():
                            self.messages.put(("cancelled", None))
                            return

                        # 완료된 페이지 결과 가져오기
                        result = future.result()

                        if result is not None:
                            page_rows, _ = result
                            check_players(page_rows)

                            completed += 1
                            self.messages.put((
                                "progress",
                                (completed, total_pages)
                            ))

                        # 완료된 자리에 다음 페이지 작업 추가
                        if next_page <= total_pages and not self.stop_event.is_set():
                            future = executor.submit(fetch_page, next_page)
                            pending.add(future)
                            next_page += 1

            if self.stop_event.is_set():
                self.messages.put(("cancelled", None))
            else:
                elapsed = time.perf_counter() - start_time

                print(f"스레드 수: {max_workers}")
                print(f"검색 소요 시간: {elapsed:.2f}초")
                print(f"검색 결과: {found}명")
                print("--------------------------")
                self.messages.put(("done", found))

        except Exception as exc:
            self.messages.put(("error", str(exc)))


    def stop_search(self):
        if self.searching:
            self.stop_event.set()
            self.stop_button.configure(state="disabled")
            self.status_var.set("검색을 중단하는 중입니다...")

    def finish_search(self):
        self.searching = False
        self.progress.stop()
        self.search_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def check_messages(self):
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "progress":
                    page, total = payload
                    self.status_var.set(
                        f"{page}/{total}페이지 확인 중 · 일치 결과 {self.found_count}개"
                    )
                elif kind == "match":
                    rank, nickname, rating = payload
                    self.table.insert("", "end", values=(rank, nickname, rating))
                    self.found_count += 1
                elif kind == "done":
                    self.finish_search()
                    self.status_var.set(
                        f"검색 완료: {payload}개 결과 발견" if payload
                        else "공개 전장 순위표에서 일치하는 닉네임이 없습니다."
                    )
                elif kind == "cancelled":
                    self.finish_search()
                    self.status_var.set("검색을 중단했습니다. 표시된 결과는 일부일 수 있습니다.")
                elif kind == "error":
                    self.finish_search()
                    self.status_var.set(f"오류: {payload}")
        except queue.Empty:
            pass

        self.root.after(100, self.check_messages)

    def open_website(self):
        region = REGIONS[self.region_var.get()]
        webbrowser.open(
            "https://hearthstone.blizzard.com/ko-kr/community/leaderboards"
            f"?region={region}&leaderboardId=battlegrounds"
        )


if __name__ == "__main__":
    root = tk.Tk()
    RankFinderApp(root)
    root.mainloop()
