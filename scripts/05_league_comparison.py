"""
05_league_comparison.py
-----------------------
Süper Lig ile 5 büyük ligi sezon içi teknik direktör değişikliği sıklığında karşılaştırır.
Kaynak: Transfermarkt "Teknik kadro değişiklikleri" (tüm ligler aynı kaynak, aynı tanım).
Tanım: sezon içinde, görevdeki kalıcı teknik direktörün ayrılması (geçici hocaların ayrılışı hariç).
Sezonlar: 2016/17 - 2025/26 (tamamlanmış 10 sezon).

Çıktı: data/processed/league_comparison.csv ve konsol özeti
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
raw = pd.DataFrame(json.load(open(ROOT / "data/raw/tm_big5_coach_changes.json", encoding="utf-8")))
raw = raw[raw.get("err").isna()] if "err" in raw else raw

NAMES = {"TR1": "Süper Lig", "GB1": "Premier League", "L1": "Bundesliga",
         "ES1": "LaLiga", "IT1": "Serie A", "FR1": "Ligue 1"}
# Lig-sezon başına takım sayısı (Süper Lig değerleri maç verisinden doğrulandı)
FIRST, LAST = 2016, 2025
N_SEASONS = LAST - FIRST + 1
TEAMS = {"TR1": {2016: 18, 2017: 18, 2018: 18, 2019: 18, 2020: 21, 2021: 20, 2022: 19, 2023: 20, 2024: 19, 2025: 18},
         "GB1": dict.fromkeys(range(FIRST, LAST + 1), 20), "L1": dict.fromkeys(range(FIRST, LAST + 1), 18),
         "ES1": dict.fromkeys(range(FIRST, LAST + 1), 20), "IT1": dict.fromkeys(range(FIRST, LAST + 1), 20),
         "FR1": {**dict.fromkeys(range(2016, 2023), 20), 2023: 18, 2024: 18, 2025: 18}}

ev = raw[(raw["sec"] == "in") & (raw["outRole"] == "Teknik Direktör") & (raw["season"].between(FIRST, LAST))].copy()
ev["tenure"] = pd.to_numeric(ev["tenure"].astype(str).str.replace(".", "", regex=False), errors="coerce")

rows = []
for lg, g in ev.groupby("league"):
    team_seasons = sum(TEAMS[lg].values())
    per_club = g.groupby(["season", "club"]).size()
    rows.append(dict(
        league=lg, lig=NAMES[lg],
        changes=len(g),
        per_season=round(len(g) / N_SEASONS, 1),
        per_team_season=round(len(g) / team_seasons, 2),
        pct_clubs_changed=round(100 * len(per_club) / team_seasons, 1),       # sezonda en az 1 değişiklik yapan kulüp %
        pct_clubs_2plus=round(100 * (per_club >= 2).sum() / team_seasons, 1),  # sezonda 2+ değişiklik yapan kulüp %
        median_tenure_days=int(g["tenure"].median()),
        pct_tenure_under_120=round(100 * (g["tenure"] < 120).mean(), 1),      # 4 aydan kısa görev %
    ))
out = pd.DataFrame(rows).sort_values("per_team_season", ascending=False)
out.to_csv(ROOT / "data/processed/league_comparison.csv", index=False)
print(out.to_string(index=False))

by_season = ev.groupby(["league", "season"]).size().unstack(0).rename(columns=NAMES)
# dönem kırılımı: kulüp başına sezon içi değişiklik
for a, b in [(2016, 2019), (2020, 2025)]:
    gg = ev[ev["season"].between(a, b)]
    rate = {NAMES[lg]: round(len(x) / sum(v for s_, v in TEAMS[lg].items() if a <= s_ <= b), 2) for lg, x in gg.groupby("league")}
    print(f"{a}/{str(a + 1)[2:]}–{b}/{str(b + 1)[2:]} kulüp başına sezonda:", rate)
print("\nSezon bazında sezon içi değişiklik sayısı:\n", by_season.to_string())
