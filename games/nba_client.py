import requests

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
TODAY_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/",
}

def get_json(url: str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

def fetch_schedule():
    return get_json(SCHEDULE_URL)

def fetch_today_scoreboard():
    return get_json(TODAY_SCOREBOARD_URL)
