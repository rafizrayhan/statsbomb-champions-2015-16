"""
Part 1: How did the 2015/16 champions play?
Compare each champion with the average team in its own league.

Input: results/team_match_features_2015_16.csv (from part0, one row per
       team per match, built from StatsBomb open data event files)
Output: printed comparison table and results/part1_champions_vs_league.csv
"""

import os
import pandas as pd

DATA = "results/team_match_features_2015_16.csv"

CHAMPIONS = {
    "Premier League": "Leicester City",
    "La Liga": "Barcelona",
    "Serie A": "Juventus",
    "Ligue 1": "Paris Saint-Germain",
}

# The metrics we compare, with plain-English names
METRICS = {
    "pass_share": "Possession (share of passes)",
    "passes_per_possession": "Passes per possession",
    "pass_completion": "Pass completion (open play)",
    "long_ball_share": "Long balls (share of passes)",
    "cross_share_final_third": "Crosses (share of final-third passes)",
    "counter_share": "Possessions from counter-attacks",
    "ppda": "PPDA (lower = more pressing)",
    "np_shots": "Shots per game (no penalties)",
    "np_xg": "xG per game (no penalties)",
    "np_xg_per_shot": "xG per shot",
}

# Metrics shown as percentages
PERCENT = {"pass_share", "pass_completion", "long_ball_share",
           "cross_share_final_third", "counter_share"}


def main():
    df = pd.read_csv(DATA)

    # Season average for every team (mean of its matches)
    teams = df.groupby(["league", "team"])[list(METRICS)].mean().reset_index()

    rows = []
    for league, champ in CHAMPIONS.items():
        league_teams = teams[teams.league == league]
        champ_row = league_teams[league_teams.team == champ].iloc[0]
        league_avg = league_teams[list(METRICS)].mean()

        for m, name in METRICS.items():
            # Rank within the league: 1 = highest value
            # (for PPDA, 1 = lowest value = most pressing)
            ascending = (m == "ppda")
            rank = int(league_teams[m].rank(ascending=ascending,
                                             method="min")[champ_row.name])
            rows.append({
                "metric": name,
                "champion": champ,
                "league": league,
                "champion_value": champ_row[m],
                "league_average": league_avg[m],
                "rank_in_league": rank,
            })

    out = pd.DataFrame(rows)
    out.to_csv("results/part1_champions_vs_league.csv", index=False)

    # Print a readable table: champion value (league average) [rank]
    def fmt(r):
        m = [k for k, v in METRICS.items() if v == r.metric][0]
        if m in PERCENT:
            return (f"{r.champion_value:.0%} ({r.league_average:.0%}) "
                    f"[{r.rank_in_league}]")
        return (f"{r.champion_value:.2f} ({r.league_average:.2f}) "
                f"[{r.rank_in_league}]")

    out["display"] = out.apply(fmt, axis=1)
    table = out.pivot(index="metric", columns="champion", values="display")
    table = table.loc[list(METRICS.values()), list(CHAMPIONS.values())]
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 30)
    print("Champion value (league average) [rank in league, 1 = highest]\n")
    print(table.to_string())


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    main()
