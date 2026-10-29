"""
Part 4a: League baseline for goal speed

Same measure as part 4b, but for every team in the four leagues, so each
champion can be compared with the rest of its own league.

Event files are streamed (not saved) to avoid storing ~1,500 large files.
Output: results/part4_all_teams_shots.csv (one row per open-play shot, every team)
        results/part4_league_baseline.csv
        printed comparison: champion vs rest of league, and champion's rank
"""

import os
import json
import time
import urllib.request
import concurrent.futures as cf

import pandas as pd

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
LEAGUES = {"Premier League": (2, 27), "La Liga": (11, 27),
           "Serie A": (12, 27), "Ligue 1": (7, 27)}
CHAMPIONS = {"Premier League": "Leicester City", "La Liga": "Barcelona",
             "Serie A": "Juventus", "Ligue 1": "Paris Saint-Germain"}
SET_PIECE_PATTERNS = {"From Corner", "From Free Kick", "From Throw In"}
SET_PIECE_SECONDS = 10
FAST_SECONDS = 15


def get_json(url, retries=6):
    """Download and parse a JSON file, waiting and retrying if GitHub
    rate-limits the request (HTTP 429) or the connection drops."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt * 2)  # 2, 4, 8, 16, 32 seconds

def secs(e):
    return e["minute"] * 60 + e["second"]


def match_shots(league, m):
    """Open-play shots for both teams in one match (same rules as part 4b)."""
    events = get_json(f"{BASE}/events/{m['match_id']}.json")
    names = {m["home_team"]["home_team_id"]: m["home_team"]["home_team_name"],
             m["away_team"]["away_team_id"]: m["away_team"]["away_team_name"]}
    start, passes, rows = {}, {}, []
    for e in events:
        key = (e["period"], e["possession"])
        start.setdefault(key, secs(e))
        tid = e.get("team", {}).get("id")
        if e["type"]["name"] == "Pass":
            passes[(key, tid)] = passes.get((key, tid), 0) + 1
        if e["type"]["name"] != "Shot":
            continue
        if e["shot"].get("type", {}).get("name") == "Penalty":
            continue
        seconds = secs(e) - start[key]
        if e["play_pattern"]["name"] in SET_PIECE_PATTERNS and seconds <= SET_PIECE_SECONDS:
            continue
        rows.append({"league": league, "team": names[tid], "match_id": m["match_id"],
                     "goal": e["shot"]["outcome"]["name"] == "Goal",
                     "seconds": seconds, "passes": passes.get((key, tid), 0)})
    return rows


def main():
    jobs = []
    for league, (cid, sid) in LEAGUES.items():
        for m in get_json(f"{BASE}/matches/{cid}/{sid}.json"):
            jobs.append((league, m))
    print(f"Matches to process: {len(jobs)}")

    rows, failed = [], []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(match_shots, lg, m): m["match_id"] for lg, m in jobs}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                rows.extend(f.result())
            except Exception as err:
                failed.append((futs[f], str(err)))
            if i % 250 == 0:
                print(f"  processed {i}/{len(jobs)}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv("results/part4_all_teams_shots.csv", index=False)
    if failed:
        print("Failed:", failed)

    df["fast"] = df.seconds <= FAST_SECONDS
    print(f"\nShare within {FAST_SECONDS}s: champion vs rest of its league")
    out = []
    for league, champ in CHAMPIONS.items():
        d = df[df.league == league]
        c, rest = d[d.team == champ], d[d.team != champ]
        # Rank among the 20 teams by share of open-play shots within 15 s
        team_share = d.groupby("team").fast.mean().sort_values(ascending=False)
        rank = list(team_share.index).index(champ) + 1
        out.append({
            "league": league, "champion": champ,
            "champ goals fast": c[c.goal].fast.mean(),
            "rest goals fast": rest[rest.goal].fast.mean(),
            "rest goals median s": rest[rest.goal].seconds.median(),
            "champ shots fast": c.fast.mean(),
            "rest shots fast": rest.fast.mean(),
            "champ rank (shots fast)": rank,
        })
    out = pd.DataFrame(out).set_index("champion")
    out.to_csv("results/part4_league_baseline.csv")
    show = out.copy()
    for col in ["champ goals fast", "rest goals fast", "champ shots fast", "rest shots fast"]:
        show[col] = (show[col] * 100).round(0).astype(int).astype(str) + "%"
    print(show.to_string())


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    main()
