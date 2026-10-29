"""
Part 1 chart: where each 2015/16 champion ranked in its own league

Input:  results/part1_champions_vs_league.csv (from part1_compare_champions.py)
Output: figures/part1_champions_ranks.png
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

CHAMPIONS = ["Leicester City", "Barcelona", "Juventus", "Paris Saint-Germain"]
SHORT = {"Leicester City": "Leicester", "Paris Saint-Germain": "PSG"}
LEAGUE = {"Leicester City": "Premier League", "Barcelona": "La Liga",
          "Juventus": "Serie A", "Paris Saint-Germain": "Ligue 1"}

# Shorter metric names for the chart, in display order (top to bottom)
LABELS = {
    "Possession (share of passes)": "Possession",
    "Passes per possession": "Passes per possession",
    "Pass completion (open play)": "Pass completion",
    "Long balls (share of passes)": "Long balls",
    "Crosses (share of final-third passes)": "Crosses",
    "Possessions from counter-attacks": "Counter-attacks",
    "PPDA (lower = more pressing)": "Pressing intensity",
    "Shots per game (no penalties)": "Shots per game",
    "xG per game (no penalties)": "xG per game",
    "xG per shot": "xG per shot",
}

# Colours
SURFACE, INK, INK_2, INK_3 = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
TRACK = "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"

for f in font_manager.findSystemFonts():
    if "Inter" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "text.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def ordinal(n):
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def main():
    df = pd.read_csv("results/part1_champions_vs_league.csv")
    metrics = list(LABELS)
    y = list(range(len(metrics)))[::-1]  # first metric at the top

    fig, axes = plt.subplots(1, 4, figsize=(14, 6.4), sharey=True)
    for ax, team in zip(axes, CHAMPIONS):
        colour = ORANGE if team == "Leicester City" else BLUE
        d = df[df.champion == team].set_index("metric").loc[metrics]

        # Grey track from 20th to 1st, then a dot at the champion's rank
        ax.hlines(y, 20, 1, color=TRACK, lw=6, capstyle="round", zorder=1)
        ax.scatter(d.rank_in_league, y, s=150, color=colour,
                   edgecolor=SURFACE, linewidth=2, zorder=3)
        for yi, r in zip(y, d.rank_in_league):
            ax.text(r, yi + 0.38, ordinal(int(r)), ha="center", fontsize=8,
                    color=INK_2)

        ax.set_xlim(21, 0)  # 1st on the right
        ax.set_ylim(-0.7, len(metrics) - 0.2)
        ax.set_xticks([20, 10, 1])
        ax.set_xticklabels(["20th", "10th", "1st"], fontsize=8, color=INK_3)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(f"{SHORT.get(team, team)}\n", loc="left", fontsize=12,
                     fontweight="bold", color=colour)
        ax.text(0, 1.015, LEAGUE[team], transform=ax.transAxes, fontsize=9,
                color=INK_3)

    axes[0].set_yticks(y)
    axes[0].set_yticklabels([LABELS[m] for m in metrics], fontsize=10, color=INK_2)

    fig.text(0.015, 0.965, "Three possession giants and one outsider: "
             "how the 2015/16 champions ranked in their own leagues",
             fontsize=15, fontweight="bold", va="top")
    fig.text(0.015, 0.915, "Rank among the 20 teams in each league. Right = highest "
             "in the league. Pressing intensity uses PPDA, so 1st = presses most.",
             fontsize=10, color=INK_2, va="top")
    fig.text(0.015, 0.015, "Data: StatsBomb open data, 2015/16. "
             "Shots and xG exclude penalties.", fontsize=8, color=INK_3)
    fig.subplots_adjust(left=0.15, right=0.98, top=0.78, bottom=0.1, wspace=0.12)
    fig.savefig("figures/part1_champions_ranks.png", dpi=200)
    print("Saved figures/part1_champions_ranks.png")


os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)


if __name__ == "__main__":
    main()
