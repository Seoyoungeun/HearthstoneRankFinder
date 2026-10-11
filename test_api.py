
import requests

url = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"

params = {
    "region": "AP",
    "leaderboardId": "battlegrounds",
    "page": 1
}

response = requests.get(
    url,
    params=params,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=15
)

print("HTTP 상태 코드:", response.status_code)
response.raise_for_status()

data = response.json()

leaderboard = data["leaderboard"]
players = leaderboard["rows"]
pagination = leaderboard["pagination"]

print("전체 페이지:", pagination["totalPages"])
print("첫 페이지 유저 수:", len(players))

for player in players[:10]:
    print(
        player["rank"],
        player["accountid"],
        player["rating"]
    )
