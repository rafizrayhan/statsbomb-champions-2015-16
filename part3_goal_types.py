"""
Part 3: How did the 2015/16 champions score their goals?

Every StatsBomb event carries a "play_pattern": how the possession started
(regular play, counter-attack, corner, free kick, throw-in, and so on).
For each goal we take the play pattern of the shot, then group them:

  Open play       Regular Play, From Goal Kick, From Keeper, From Kick Off, Other
  Counter-attack  From Counter
  Corner          From Corner     } only if the goal came within 10 seconds
  Free kick       From Free Kick  } of the restart; slower moves that started
  Throw-in        From Throw In   } from a set piece count as open play
  Penalty         shots of type Penalty
  Own goal        "Own Goal For" events credited to the champion

Uses the event files downloaded in part 2 (data/events/).
Output: printed table, results/part3_goal_types.csv, figures/part3_goal_types.png
"""

import json
import os
import time
import urllib.request

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
EVENT_DIR = "data/events"

CHAMPIONS = {
    "Leicester City": ("Premier League", 2, 27),
    "Barcelona": ("La Liga", 11, 27),
    "Juventus": ("Serie A", 12, 27),
    "Paris Saint-Germain": ("Ligue 1", 7, 27),
}
SHORT = {"Leicester City": "Leicester", "Paris Saint-Germain": "PSG"}
ORDER = ["Open play", "Counter-attack", "Corner", "Free kick", "Throw-in",
         "Penalty", "Own goal"]
GROUP = {"Regular Play": "Open play", "From Goal Kick": "Open play",
         "From Keeper": "Open play", "From Kick Off": "Open play",
         "Other": "Open play", "From Counter": "Counter-attack",
         "From Corner": "Corner", "From Free Kick": "Free kick",
         "From Throw In": "Throw-in"}
SET_PIECES = {"Corner", "Free kick", "Throw-in"}
SET_PIECE_SECONDS = 10


def secs(e):
    return e["minute"] * 60 + e["second"]


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

def collect():
    rows, checks = [], []
    for team, (league, comp_id, season_id) in CHAMPIONS.items():
        matches = get_json(f"{BASE}/matches/{comp_id}/{season_id}.json")
        scored_per_results = 0
        for m in matches:
            if team not in (m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]):
                continue
            home = m["home_team"]["home_team_name"] == team
            team_id = m["home_team"]["home_team_id"] if home else m["away_team"]["away_team_id"]
            scored_per_results += m["home_score"] if home else m["away_score"]

            with open(os.path.join(EVENT_DIR, f"{m['match_id']}.json")) as f:
                events = json.load(f)
            # Time each possession started (events are in order, period by period)
            poss_start = {}
            for e in events:
                poss_start.setdefault((e["period"], e["possession"]), secs(e))
            for e in events:
                if e.get("team", {}).get("id") != team_id:
                    continue
                t = e["type"]["name"]
                if t == "Shot" and e["shot"]["outcome"]["name"] == "Goal":
                    if e["shot"].get("type", {}).get("name") == "Penalty":
                        kind = "Penalty"
                    else:
                        kind = GROUP.get(e["play_pattern"]["name"], "Open play")
                        delay = secs(e) - poss_start[(e["period"], e["possession"])]
                        if kind in SET_PIECES and delay > SET_PIECE_SECONDS:
                            kind = "Open play"
                    rows.append({"team": team, "match_id": m["match_id"], "type": kind,
                                 "player": e.get("player", {}).get("name")})
                elif t == "Own Goal For":
                    rows.append({"team": team, "match_id": m["match_id"],
                                 "type": "Own goal", "player": None})
        checks.append((team, scored_per_results))
    df = pd.DataFrame(rows)

    # Check: goals found in events should equal goals in the match results
    print("Check against match results (shootout goals are not involved here)")
    for team, n in checks:
        found = (df.team == team).sum()
        print(f"  {team:22s} events: {found:3d}  results: {n:3d}  "
              f"{'OK' if found == n else 'MISMATCH'}")
    return df


def summarise(df):
    counts = pd.crosstab(df.type, df.team).reindex(index=ORDER, columns=list(CHAMPIONS),
                                                   fill_value=0)
    shares = counts / counts.sum()
    table = counts.astype(str) + " (" + (shares * 100).round(0).astype(int).astype(str) + "%)"
    table.loc["Total"] = counts.sum().astype(str)
    print("\nGoals by how the move started: count (share of team's goals)\n")
    print(table.to_string())
    set_pieces = counts.loc[["Corner", "Free kick", "Throw-in"]].sum() / counts.sum()
    print("\nSet pieces excluding penalties (corner + free kick + throw-in): " +
          ", ".join(f"{SHORT.get(t, t)} {v:.0%}" for t, v in set_pieces.items()))
    out = counts.join(shares.add_suffix(" share"))
    out.to_csv("results/part3_goal_types.csv")
    return counts, shares


# ---------- chart ----------
SURFACE, INK, INK_2, INK_3 = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
TRACK = "#eeede9"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def chart(counts, shares):
    for f in font_manager.findSystemFonts():
        if "Inter" in f:
            font_manager.fontManager.addfont(f)
    plt.rcParams.update({"font.family": "Inter", "text.color": INK,
                         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})

    y = list(range(len(ORDER)))[::-1]
    xmax = shares.values.max() * 1.25
    fig, axes = plt.subplots(1, 4, figsize=(14, 5.6), sharey=True)
    for ax, team in zip(axes, CHAMPIONS):
        colour = ORANGE if team == "Leicester City" else BLUE
        s, c = shares[team], counts[team]
        ax.barh(y, [xmax] * len(y), height=0.62, color=TRACK, zorder=1)
        ax.barh(y, s.values, height=0.62, color=colour, zorder=2)
        for yi, share, n in zip(y, s.values, c.values):
            ax.text(share + xmax * 0.02, yi, f"{share:.0%}  ({n})", va="center",
                    fontsize=9, color=INK_2, zorder=3)
        ax.set_xlim(0, xmax)
        ax.set_xticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        ax.set_title(SHORT.get(team, team), loc="left", fontsize=12,
                     fontweight="bold", color=colour, pad=20)
        ax.text(0, 1.02, f"{int(c.sum())} league goals", transform=ax.transAxes,
                fontsize=9, color=INK_3)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(ORDER, fontsize=10, color=INK_2)

    fig.text(0.015, 0.97, "How did the 2015/16 champions score their goals?",
             fontsize=16, fontweight="bold", va="top")
    fig.text(0.015, 0.905, "Share of each team's league goals by how the move started. "
             "Set pieces = goal within 10 seconds of the corner, free kick or throw-in. "
             "Goals in brackets.", fontsize=10, color=INK_2, va="top")
    fig.text(0.015, 0.02, "Data: StatsBomb open data, 2015/16 league matches. Move type "
             "from StatsBomb's play pattern of the possession.", fontsize=8, color=INK_3)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.74, bottom=0.08, wspace=0.12)
    fig.savefig("figures/part3_goal_types.png", dpi=200)
    print("\nSaved figures/part3_goal_types.png")


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    goals = collect()
    c, s = summarise(goals)
    chart(c, s)
