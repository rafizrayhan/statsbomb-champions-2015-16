"""
Part 2: Where did the 2015/16 champions win the ball back?

Steps
1. Download the event file for every match each champion played
   (saved in data/events/ so part 3 can reuse them).
2. Keep the events where the champion won the ball:
   - Ball Recovery (not marked as a failed recovery)
   - Interception that won the ball
   - Tackle that won the ball
3. Print simple numbers: ball wins per game, average height, share by third.
4. Draw one pitch per champion with a heatmap of where they won the ball.

StatsBomb coordinates: pitch is 120 x 80. Every event is recorded from the
perspective of the team doing it, attacking left to right, so x = 0 is the
champion's own goal line and x = 120 is the opponent's goal line.
"""

import json
import os
import time
import urllib.request

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from mplsoccer import VerticalPitch

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
EVENT_DIR = "data/events"

# (competition_id, season_id) for 2015/16
CHAMPIONS = {
    "Leicester City": ("Premier League", 2, 27),
    "Barcelona": ("La Liga", 11, 27),
    "Juventus": ("Serie A", 12, 27),
    "Paris Saint-Germain": ("Ligue 1", 7, 27),
}
SHORT = {"Leicester City": "Leicester", "Paris Saint-Germain": "PSG"}

# Outcomes StatsBomb uses when an interception or tackle wins the ball
WON = {"Won", "Success", "Success In Play", "Success Out"}


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

def load_events(match_id):
    """Read a match's events from disk, downloading it the first time."""
    path = os.path.join(EVENT_DIR, f"{match_id}.json")
    if not os.path.exists(path):
        events = get_json(f"{BASE}/events/{match_id}.json")
        with open(path, "w") as f:
            json.dump(events, f)
    with open(path) as f:
        return json.load(f)


def champion_matches(team, comp_id, season_id):
    """Match IDs and team ID for every match the champion played."""
    matches = get_json(f"{BASE}/matches/{comp_id}/{season_id}.json")
    ids, team_id = [], None
    for m in matches:
        for side in ("home_team", "away_team"):
            if m[side][f"{side}_name"] == team:
                ids.append(m["match_id"])
                team_id = m[side][f"{side}_id"]
    return ids, team_id


def is_ball_win(e):
    t = e["type"]["name"]
    if t == "Ball Recovery":
        return not e.get("ball_recovery", {}).get("recovery_failure", False)
    if t == "Interception":
        return e["interception"]["outcome"]["name"] in WON
    if t == "Duel" and e["duel"].get("type", {}).get("name") == "Tackle":
        return e["duel"].get("outcome", {}).get("name") in WON
    return False


def collect():
    os.makedirs(EVENT_DIR, exist_ok=True)
    rows, opp_passes = [], {}
    for team, (league, comp_id, season_id) in CHAMPIONS.items():
        opp_passes[team] = 0
        ids, team_id = champion_matches(team, comp_id, season_id)
        print(f"{team}: {len(ids)} matches")
        for mid in ids:
            for e in load_events(mid):
                # Count the opponent's passes, to put ball wins on a fair scale
                if e["type"]["name"] == "Pass" and e.get("team", {}).get("id") != team_id:
                    opp_passes[team] += 1
                # Match on team ID, not name (names differ between files)
                if e.get("team", {}).get("id") == team_id and is_ball_win(e):
                    rows.append({"team": team, "match_id": mid,
                                 "type": e["type"]["name"],
                                 "x": e["location"][0], "y": e["location"][1]})
    df = pd.DataFrame(rows)
    df.to_csv("results/part2_ball_wins.csv", index=False)
    return df, pd.Series(opp_passes)


def summarise(df, opp_passes):
    def third(x):
        return "Defensive third" if x < 40 else ("Middle third" if x < 80 else "Attacking third")

    df["third"] = df.x.apply(third)
    games = df.groupby("team").match_id.nunique()
    summary = pd.DataFrame({
        "Ball wins per game": df.groupby("team").size() / games,
        "Opponent passes per game": opp_passes / games,
        "Ball wins per 100 opponent passes": df.groupby("team").size() / opp_passes * 100,
        "Average height (m from own goal)": df.groupby("team").x.mean() * 0.9144,
    })
    shares = pd.crosstab(df.team, df.third, normalize="index")
    summary = summary.join(shares[["Defensive third", "Middle third", "Attacking third"]])
    summary = summary.loc[list(CHAMPIONS)]
    print("\nWhere the champions won the ball back")
    fmt = summary.copy()
    fmt.iloc[:, 0:4] = fmt.iloc[:, 0:4].astype(float).round(1)
    for c in ["Defensive third", "Middle third", "Attacking third"]:
        fmt[c] = (summary[c] * 100).round(0).astype(int).astype(str) + "%"
    print(fmt.to_string())
    print("\nBall wins by type (per game)")
    print((pd.crosstab(df.team, df.type).div(games, axis=0)).loc[list(CHAMPIONS)].round(1).to_string())
    return summary


# ---------- chart ----------
SURFACE, INK, INK_2, INK_3 = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
BLUE, ORANGE = "#2a78d6", "#eb6834"
# Neutral grey ramp so the team-coloured average lines stay visible
SEQ = LinearSegmentedColormap.from_list(
    "seq", ["#f4f3f0", "#e2e1dc", "#c9c8c2", "#a8a7a1", "#86857f"])


def chart(df, summary):
    for f in font_manager.findSystemFonts():
        if "Inter" in f:
            font_manager.fontManager.addfont(f)
    plt.rcParams.update({"font.family": "Inter", "text.color": INK,
                         "figure.facecolor": SURFACE})

    pitch = VerticalPitch(pitch_type="statsbomb", line_color="#c9c8c2", linewidth=1,
                          pitch_color=SURFACE, line_zorder=2)
    fig, axes = pitch.draw(nrows=1, ncols=4, figsize=(14, 6.5))

    # Same colour scale for all four: share of the team's ball wins per zone
    bins = (3, 1)  # thirds of the pitch
    stats = [pitch.bin_statistic(df[df.team == t].x, df[df.team == t].y,
                                 statistic="count", bins=bins, normalize=True)
             for t in CHAMPIONS]
    vmax = max(s["statistic"].max() for s in stats)

    for ax, team, st in zip(axes, CHAMPIONS, stats):
        colour = ORANGE if team == "Leicester City" else BLUE
        pitch.heatmap(st, ax=ax, cmap=SEQ, vmin=0, vmax=vmax,
                      edgecolor=SURFACE, linewidth=1.5)
        # Big labels; white text on dark cells, dark text on light cells
        for val, cx, cy in zip(st["statistic"].ravel(), st["cx"].ravel(), st["cy"].ravel()):
            dark = val / vmax > 0.75
            # Placed in the right-hand channel to keep clear of pitch markings
            pitch.annotate(f"{val:.0%}", (cx, cy + 27), ax=ax, ha="center", va="center",
                           fontsize=17, fontweight="bold",
                           color="white" if dark else INK, zorder=5)
        # Dashed line at the average height of ball wins
        avg_x = df[df.team == team].x.mean()
        pitch.lines(avg_x, 0, avg_x, 80, ax=ax, color=colour, lw=2.5,
                    linestyle="--", zorder=4)
        ax.text(1.0, avg_x / 120, f"{avg_x * 0.9144:.0f} m", transform=ax.transAxes,
                fontsize=8.5, color=colour, ha="left", va="center", fontweight="bold")
        s = summary.loc[team]
        ax.set_title(f"{SHORT.get(team, team)}", fontsize=13, fontweight="bold",
                     color=colour, loc="left", pad=24)
        ax.text(0, 1.015, f"{s['Ball wins per 100 opponent passes']:.0f} ball wins "
                f"per 100 opponent passes", transform=ax.transAxes, fontsize=8.5,
                color=INK_3)

    fig.text(0.02, 0.98, "Where did the 2015/16 champions win the ball back?",
             fontsize=16, fontweight="bold", va="top")
    fig.text(0.02, 0.928, "Share of each team's ball wins (recoveries, interceptions, "
             "won tackles) in each third. Attacking upwards. Dashed line = average "
             "height, in metres from own goal.",
             fontsize=10, color=INK_2, va="top")
    fig.text(0.02, 0.02, "Data: StatsBomb open data, 2015/16 league matches.",
             fontsize=8, color=INK_3)
    fig.subplots_adjust(left=0.02, right=0.96, top=0.72, bottom=0.06, wspace=0.18)
    fig.savefig("figures/part2_ball_recoveries.png", dpi=200)
    print("\nSaved figures/part2_ball_recoveries.png")


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    data, opp = collect()
    summary = summarise(data, opp)
    chart(data, summary)
