"""
Part 4b: How quickly did the champions score after winning the ball?

StatsBomb's counter-attack tag is narrow, so instead we measure speed directly.
For every goal from open play (no set pieces, penalties or own goals, using the
same definitions as part 3), we count:
  - seconds from the start of the possession to the goal
  - number of passes in the possession before the goal

A "fast goal" here = scored within 15 seconds of winning the ball.
We repeat this for all open-play shots, which gives a larger sample than goals.

Uses the event files downloaded in part 2 (data/events/).
Output: printed table, results/part4_champion_shots.csv, figures/part4_goal_speed.png
Needs:  results/part4_league_baseline.csv from part4a_league_baseline.py
"""

import json
import os
import time
import urllib.request

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
EVENT_DIR = "data/events"
CHAMPIONS = {
    "Leicester City": (2, 27),
    "Barcelona": (11, 27),
    "Juventus": (12, 27),
    "Paris Saint-Germain": (7, 27),
}
SHORT = {"Leicester City": "Leicester", "Paris Saint-Germain": "PSG"}
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


def collect():
    rows = []
    for team, (comp_id, season_id) in CHAMPIONS.items():
        for m in get_json(f"{BASE}/matches/{comp_id}/{season_id}.json"):
            sides = {m["home_team"]["home_team_name"]: m["home_team"]["home_team_id"],
                     m["away_team"]["away_team_name"]: m["away_team"]["away_team_id"]}
            if team not in sides:
                continue
            team_id = sides[team]
            with open(os.path.join(EVENT_DIR, f"{m['match_id']}.json")) as f:
                events = json.load(f)

            # Start time and pass count of each possession
            start, passes = {}, {}
            for e in events:
                key = (e["period"], e["possession"])
                start.setdefault(key, secs(e))
                if e["type"]["name"] == "Pass" and e.get("team", {}).get("id") == team_id:
                    passes[key] = passes.get(key, 0) + 1
                if e["type"]["name"] != "Shot" or e["team"]["id"] != team_id:
                    continue
                if e["shot"].get("type", {}).get("name") == "Penalty":
                    continue
                seconds = secs(e) - start[key]
                pattern = e["play_pattern"]["name"]
                if pattern in SET_PIECE_PATTERNS and seconds <= SET_PIECE_SECONDS:
                    continue  # set piece, excluded (same rule as part 3)
                rows.append({"team": team, "match_id": m["match_id"],
                             "goal": e["shot"]["outcome"]["name"] == "Goal",
                             "seconds": seconds, "passes": passes.get(key, 0),
                             "xg": e["shot"].get("statsbomb_xg", 0)})
    df = pd.DataFrame(rows)
    df.to_csv("results/part4_champion_shots.csv", index=False)
    return df


def summarise(df):
    def block(d):
        return pd.Series({
            "count": len(d),
            "median seconds": d.seconds.median(),
            "median passes": d.passes.median(),
            f"share within {FAST_SECONDS}s": (d.seconds <= FAST_SECONDS).mean(),
        })

    goals = df[df.goal].groupby("team").apply(block, include_groups=False).loc[list(CHAMPIONS)]
    shots = df.groupby("team").apply(block, include_groups=False).loc[list(CHAMPIONS)]
    for name, t in [("Open-play GOALS", goals), ("Open-play SHOTS (larger sample)", shots)]:
        show = t.copy()
        show["count"] = show["count"].astype(int)
        show[f"share within {FAST_SECONDS}s"] = (show[f"share within {FAST_SECONDS}s"] * 100).round(0).astype(int).astype(str) + "%"
        print(f"\n{name}")
        print(show.to_string())
    return goals


# ---------- chart ----------
SURFACE, INK, INK_2, INK_3 = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
GRID, FAST_ZONE = "#e6e5e1", "#f1f0ec"
BLUE, ORANGE = "#2a78d6", "#eb6834"
CAP = 60  # goals slower than 60 s are drawn at the right edge


def chart(df, goals):
    for f in font_manager.findSystemFonts():
        if "Inter" in f:
            font_manager.fontManager.addfont(f)
    plt.rcParams.update({"font.family": "Inter", "text.color": INK,
                         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})

    # League baseline from part4a_league_baseline.py (run that first)
    base = pd.read_csv("results/part4_league_baseline.csv", index_col="champion")

    fig, ax = plt.subplots(figsize=(12.5, 5.6))
    rng = np.random.default_rng(1)
    teams = list(CHAMPIONS)
    ax.axvspan(0, FAST_SECONDS, color=FAST_ZONE, zorder=0)
    ax.text(FAST_SECONDS / 2, len(teams) - 0.45, f"Within {FAST_SECONDS} s",
            ha="center", fontsize=9, color=INK_3)

    for i, team in enumerate(teams):
        yrow = len(teams) - 1 - i
        colour = ORANGE if team == "Leicester City" else BLUE
        g = df[(df.team == team) & df.goal]
        x = np.minimum(g.seconds.values, CAP)
        y = yrow + rng.uniform(-0.22, 0.22, len(x))
        ax.scatter(x, y, s=46, color=colour, edgecolor=SURFACE, linewidth=1.2,
                   alpha=0.9, zorder=3)
        med = g.seconds.median()
        ax.plot([med, med], [yrow - 0.32, yrow + 0.32], color=INK, lw=2, zorder=4)
        # Grey line = median for the rest of the champion's league
        rest_med = base.loc[team, "rest goals median s"]
        ax.plot([rest_med, rest_med], [yrow - 0.32, yrow + 0.32], color=INK_3,
                lw=2, ls=(0, (2, 1.5)), zorder=4)
        share = goals.loc[team, f"share within {FAST_SECONDS}s"]
        rest = base.loc[team, "rest goals fast"]
        rank = int(base.loc[team, "champ rank (shots fast)"])
        ax.text(CAP + 3, yrow + 0.12, f"{share:.0%} fast  (rest of league {rest:.0%})",
                va="center", fontsize=9, color=INK_2, fontweight="semibold")
        ax.text(CAP + 3, yrow - 0.16, f"{rank}{'st' if rank == 1 else 'th'} of 20 in "
                f"{base.loc[team, 'league']} for fast shots",
                va="center", fontsize=8.5, color=INK_3)

    ax.set_yticks(range(len(teams)))
    ax.set_yticklabels([SHORT.get(t, t) for t in teams][::-1], fontsize=11,
                       fontweight="bold")
    for lab, team in zip(ax.get_yticklabels(), teams[::-1]):
        lab.set_color(ORANGE if team == "Leicester City" else BLUE)
    ax.set_xlim(-1, CAP + 1)
    ax.set_xticks([0, 15, 30, 45, 60])
    ax.set_xticklabels(["0 s", "15 s", "30 s", "45 s", "60 s+"], fontsize=9, color=INK_3)
    ax.set_ylim(-0.6, len(teams) - 0.3)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlabel("Seconds from winning the ball to scoring", fontsize=10, color=INK_2)

    fig.text(0.015, 0.97, "How quickly did the 2015/16 champions score?",
             fontsize=16, fontweight="bold", va="top")
    fig.text(0.015, 0.905, "Each dot is an open-play goal (no set pieces, penalties or "
             "own goals). Black line = team median. Grey dashed line = median for the "
             "rest of its league.", fontsize=10, color=INK_2, va="top")
    fig.text(0.015, 0.02, "Data: StatsBomb open data, 2015/16 league matches. Time measured "
             "from the start of the scoring team's possession.", fontsize=8, color=INK_3)
    fig.subplots_adjust(left=0.1, right=0.74, top=0.8, bottom=0.17)
    fig.savefig("figures/part4_goal_speed.png", dpi=200)
    print("\nSaved figures/part4_goal_speed.png")


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    data = collect()
    g = summarise(data)
    chart(data, g)
