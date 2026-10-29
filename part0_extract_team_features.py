"""
Part 0: Extract team features per match from StatsBomb open data
Leagues: Premier League, La Liga, Serie A, Ligue 1, season 2015/16 (full seasons)

Usage:
    python part0_extract_team_features.py test   -> runs on 3 matches and prints output
    python part0_extract_team_features.py        -> runs on all matches, saves CSV

StatsBomb coordinates: pitch is 120 x 80 (yards). Every event is recorded
from the perspective of the team performing it, attacking left to right.
"""

import os
import json
import sys
import time
import urllib.request
import concurrent.futures as cf

import numpy as np
import pandas as pd

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
TARGET = {"Premier League", "La Liga", "Serie A", "Ligue 1"}
SEASON = "2015/2016"
OUT_CSV = "results/team_match_features_2015_16.csv"

SET_PIECE_PASSES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
LONG_BALL_YARDS = 32  # roughly 30 metres


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

def list_matches():
    comps = get_json(f"{BASE}/competitions.json")
    rows = []
    for c in comps:
        if c["competition_name"] in TARGET and c["season_name"] == SEASON:
            ms = get_json(f"{BASE}/matches/{c['competition_id']}/{c['season_id']}.json")
            for m in ms:
                rows.append({
                    "match_id": m["match_id"],
                    "league": c["competition_name"],
                    "home": m["home_team"]["home_team_name"],
                    "away": m["away_team"]["away_team_name"],
                    "home_id": m["home_team"]["home_team_id"],
                    "away_id": m["away_team"]["away_team_id"],
                    "home_score": m["home_score"],
                    "away_score": m["away_score"],
                })
    return pd.DataFrame(rows)


def secs(e):
    return e["minute"] * 60 + e["second"]


def team_features(events, team, team_id, opp_id):
    # Match on team ID: some team names differ between match and event files
    # (e.g. "Olympique de Marseille" vs "Marseille")
    ev_t = [e for e in events if e.get("team", {}).get("id") == team_id]
    ev_o = [e for e in events if e.get("team", {}).get("id") == opp_id]

    def is_pass(e):
        return e["type"]["name"] == "Pass"

    def open_play(e):
        return e["pass"].get("type", {}).get("name") not in SET_PIECE_PASSES

    passes_t = [e for e in ev_t if is_pass(e)]
    passes_o = [e for e in ev_o if is_pass(e)]
    op_t = [e for e in passes_t if open_play(e)]
    op_o = [e for e in passes_o if open_play(e)]

    # Possession share proxy: share of all passes in the match
    pass_share = len(passes_t) / max(len(passes_t) + len(passes_o), 1)

    # Field tilt: share of final-third open-play passes (start x >= 80)
    ft_t = sum(1 for e in op_t if e["location"][0] >= 80)
    ft_o = sum(1 for e in op_o if e["location"][0] >= 80)
    field_tilt = ft_t / max(ft_t + ft_o, 1)

    # PPDA: opponent open-play passes in their own defensive 60% (x < 72 in
    # their frame) divided by our defensive actions in the matching zone
    # (x >= 48 in our frame). Lower PPDA = more intense pressing.
    opp_passes_zone = sum(1 for e in op_o if e["location"][0] < 72)
    def_actions_zone = 0
    for e in ev_t:
        n = e["type"]["name"]
        if "location" not in e or e["location"][0] < 48:
            continue
        if n == "Interception" or n == "Foul Committed":
            def_actions_zone += 1
        elif n == "Duel" and e.get("duel", {}).get("type", {}).get("name") == "Tackle":
            def_actions_zone += 1
    ppda = opp_passes_zone / max(def_actions_zone, 1)

    # Pressing and defensive height (mean x, our own frame)
    press_x = [e["location"][0] for e in ev_t if e["type"]["name"] == "Pressure"]
    def_x = [e["location"][0] for e in ev_t
             if e["type"]["name"] in {"Interception", "Ball Recovery"}
             or (e["type"]["name"] == "Duel"
                 and e.get("duel", {}).get("type", {}).get("name") == "Tackle")]
    pressures_per_opp_pass = len(press_x) / max(len(passes_o), 1)

    # Passing style on open-play passes
    lengths = [e["pass"]["length"] for e in op_t]
    prog = [e["pass"]["end_location"][0] - e["location"][0] for e in op_t]
    completed = [e for e in op_t if "outcome" not in e["pass"]]
    long_share = np.mean([l >= LONG_BALL_YARDS for l in lengths]) if lengths else np.nan
    final_third_op = [e for e in op_t if e["location"][0] >= 80]
    cross_share = (np.mean([e["pass"].get("cross", False) for e in final_third_op])
                   if final_third_op else np.nan)

    # Possession-level measures (possessions owned by this team)
    poss = {}
    for e in events:
        if e.get("possession_team", {}).get("id") != team_id:
            continue
        poss.setdefault(e["possession"], []).append(e)
    n_poss = len(poss)
    passes_per_poss, speeds, counters = [], [], 0
    for pid, pe in poss.items():
        own = [e for e in pe if e.get("team", {}).get("id") == team_id]
        passes_per_poss.append(sum(1 for e in own if is_pass(e)))
        if pe[0].get("play_pattern", {}).get("name") == "From Counter":
            counters += 1
        xs = [e["location"][0] for e in own if "location" in e]
        dur = secs(pe[-1]) - secs(pe[0])
        if len(own) >= 3 and dur > 0 and xs:
            speeds.append((max(xs) - xs[0]) / dur)

    # Shooting (non-penalty)
    shots = [e for e in ev_t if e["type"]["name"] == "Shot"
             and e["shot"].get("type", {}).get("name") != "Penalty"]
    np_xg = sum(e["shot"].get("statsbomb_xg", 0) for e in shots)

    return {
        "team": team,
        "pass_share": pass_share,
        "field_tilt": field_tilt,
        "ppda": ppda,
        "pressure_height": np.mean(press_x) if press_x else np.nan,
        "def_action_height": np.mean(def_x) if def_x else np.nan,
        "pressures_per_opp_pass": pressures_per_opp_pass,
        "pass_completion": len(completed) / max(len(op_t), 1),
        "avg_pass_length": np.mean(lengths) if lengths else np.nan,
        "avg_pass_progression": np.mean(prog) if prog else np.nan,
        "long_ball_share": long_share,
        "cross_share_final_third": cross_share,
        "passes_per_possession": np.mean(passes_per_poss) if passes_per_poss else np.nan,
        "build_up_speed": np.mean(speeds) if speeds else np.nan,
        "counter_share": counters / max(n_poss, 1),
        "np_shots": len(shots),
        "np_xg": np_xg,
        "np_xg_per_shot": np_xg / len(shots) if shots else np.nan,
    }


def process_match(row):
    events = get_json(f"{BASE}/events/{row['match_id']}.json")
    out = []
    for team, opp, tid, oid, venue in [
            (row["home"], row["away"], row["home_id"], row["away_id"], "home"),
            (row["away"], row["home"], row["away_id"], row["home_id"], "away")]:
        f = team_features(events, team, tid, oid)
        f.update({"match_id": row["match_id"], "league": row["league"],
                  "opponent": opp, "venue": venue,
                  "goals_for": row["home_score"] if venue == "home" else row["away_score"],
                  "goals_against": row["away_score"] if venue == "home" else row["home_score"]})
        out.append(f)
    return out


def main(mode):
    matches = list_matches()
    print(f"Matches found: {len(matches)}")
    print(matches.groupby("league").size().to_string(), "\n")

    if mode == "test":
        matches = matches.groupby("league").head(1).head(3)

    rows, failed = [], []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(process_match, r): r["match_id"] for _, r in matches.iterrows()}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            try:
                rows.extend(fut.result())
            except Exception as err:
                failed.append((futs[fut], str(err)))
            if mode == "full" and i % 100 == 0:
                print(f"  processed {i}/{len(futs)}", flush=True)

    df = pd.DataFrame(rows)
    lead = ["match_id", "league", "team", "opponent", "venue", "goals_for", "goals_against"]
    df = df[lead + [c for c in df.columns if c not in lead]]

    if mode == "test":
        pd.set_option("display.width", 200)
        print(df.set_index(["league", "team"]).drop(columns=["match_id"]).T.round(2).to_string())
    else:
        df.to_csv(OUT_CSV, index=False)
        print(f"\nSaved {len(df)} team-match rows to {OUT_CSV}")
    if failed:
        print(f"Failed matches: {failed}")


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "full")
