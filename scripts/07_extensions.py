"""
07_extensions.py
----------------
Ana analizin üç uzantısı:

  A) Yönetimler neye tepki veriyor?  (sonuç odaklı karar yanlılığı / outcome bias)
     Takım-maç paneli: her maçtan sonra "hoca bu maçtan sonra gönderildi mi?" (0/1).
     Lojistik regresyon. Son 5 maçın puanı, xG'ye göre hak edilen puan (xP-xG), bahis beklentisi
     (xP-oran), son maçı kaybetmek ve sezon içi maç sırası birlikte modele girer.
     Soru: puan sabitken, oyunun kalitesi (xG) kovma kararını etkiliyor mu?

  B) "Şanssızlık kovması" ile "haklı kovma"
     Kovmalar, öncesindeki 5 maçta bahis beklentisinin ne kadar altında kalındığına göre üç eşit gruba
     bölünür; her grupta naif sıçrama ve kontrole göre fark (DiD). xG'li sezonlarda ayrıca
     "xG'ye göre gerçekten kötü oynuyordu" ayrımı.

  C) Hoca karuseli
     Süper Lig'de her kalıcı göreve geliş bir "görev" sayılır (aynı kulübe dönüşler de ayrı görev).
     Sezon içinde gönderilen hocaların ne kadarının yeniden Süper Lig'de iş bulduğu (başka kulüp /
     aynı kulübe dönüş) ve hoca-kulüp ağı.

Çıktı: data/processed/extensions.json (+ konsol özeti). Bağımlılık: pandas, numpy.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P, RAW = ROOT / "data" / "processed", ROOT / "data" / "raw"
rng = np.random.default_rng(7)
r3 = lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)

def boot(x, B=2000):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 3:
        return [None, None]
    b = rng.choice(x, (B, len(x))).mean(1)
    return [r3(np.percentile(b, 2.5)), r3(np.percentile(b, 97.5))]

def logit(y, X, names, iters=50):
    """Newton-Raphson (IRLS) ile lojistik regresyon; katsayı, standart hata, p değeri."""
    X = np.column_stack([np.ones(len(X)), X]); y = np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b)); W = p * (1 - p)
        H = X.T @ (X * W[:, None]); g = X.T @ (y - p)
        step = np.linalg.solve(H, g); b += step
        if np.abs(step).max() < 1e-10:
            break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    from math import erf, sqrt
    pval = [2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2)))) for z in b / se]
    return pd.DataFrame({"coef": b, "se": se, "p": pval}, index=["sabit"] + names)

# ================================================================ A) kovma tetikleyicileri
tmx = pd.read_csv(P / "team_matches.csv", parse_dates=["date"]).sort_values(["team_id", "season", "date"])
cc = pd.read_csv(P / "coach_changes.csv", parse_dates=["date"])
ev = cc[~cc["caretaker_out"]]
tmx["sack"] = 0
for e in ev.itertuples():
    g = tmx[(tmx.team_id == e.team_id) & (tmx.season == e.season) & (tmx.date < e.date + pd.Timedelta(days=1))]
    if len(g):
        tmx.loc[g.index[-1], "sack"] = 1
grp = tmx.groupby(["team_id", "season"])
for c in ["pts", "xp_odds", "xp_xg"]:
    tmx[f"{c}5"] = grp[c].transform(lambda s: s.rolling(5, min_periods=5).mean())
tmx["lost"] = (tmx["pts"] == 0).astype(int)
tmx["luck5"] = tmx["pts5"] - tmx["xp_odds5"]

# Model 1 (10 sezon, oran tabanlı): beklentinin altında kalmak + beklentinin kendisi
m1d = tmx.dropna(subset=["pts5", "xp_odds5"])
M1_VARS = ["pts5", "xp_odds5", "lost", "n"]
m1 = logit(m1d["sack"], m1d[M1_VARS].values, M1_VARS)
# Model 2 (xG'li sezonlar): puan sabitken xG'nin ek etkisi var mı?
m2d = tmx.dropna(subset=["pts5", "xp_odds5", "xp_xg5"])
M2_VARS = ["pts5", "xp_xg5", "xp_odds5", "lost", "n"]
m2 = logit(m2d["sack"], m2d[M2_VARS].values, M2_VARS)

def odds_rows(m, data, names_tr):
    """Okunabilir etki: sürekli değişkenler için maç başına 0,5 puan DÜŞÜŞ, ikili için var/yok."""
    rows = []
    for v, lab in names_tr.items():
        b, se, p = m.loc[v, "coef"], m.loc[v, "se"], m.loc[v, "p"]
        k = 1.0 if v == "lost" else -0.5
        lo, hi = sorted([np.exp(k * (b - 1.96 * se)), np.exp(k * (b + 1.96 * se))])
        rows.append(dict(var=v, label=lab, coef=r3(b), se=r3(se), p=r3(p), or_=r3(np.exp(k * b)), lo=r3(lo), hi=r3(hi)))
    return rows

LAB = {"pts5": "Son 5 maçın puanı", "xp_xg5": "xG'ye göre hak edilen puan", "xp_odds5": "Bahis beklentisi (takım gücü)",
       "lost": "Son maçı kaybetmek"}
sacked = m2d[m2d["sack"] == 1]
A = dict(
    model10=dict(n=int(len(m1d)), sacks=int(m1d["sack"].sum()), seasons=[int(m1d.season.min()), int(m1d.season.max())],
                 effects=odds_rows(m1, m1d, {k: LAB[k] for k in ["pts5", "xp_odds5", "lost"]})),
    modelxg=dict(n=int(len(m2d)), sacks=int(m2d["sack"].sum()), seasons=[int(m2d.season.min()), int(m2d.season.max())],
                 effects=odds_rows(m2, m2d, {k: LAB[k] for k in ["pts5", "xp_xg5", "xp_odds5", "lost"]})),
    before_sack=dict(n=int(len(sacked)), pts5=r3(sacked.pts5.mean()), xp_xg5=r3(sacked.xp_xg5.mean()),
                     xp_odds5=r3(sacked.xp_odds5.mean()), share_unlucky=r3((sacked.pts5 < sacked.xp_xg5).mean()),
                     share_lost_last=r3(sacked.lost.mean()), league_lost_rate=r3(m2d.lost.mean())),
    base_rate=r3(m1d["sack"].mean()),
)

# ================================================================ B) şans gruplarına göre etki
e = pd.read_csv(P / "events_analysis.csv")
d = e[e["ok5"]].copy()
d["luck"] = d["pts_pre5"] - d["xp_odds_pre5"]
d = d.dropna(subset=["luck"])
d["grp"] = pd.qcut(d["luck"], 3, labels=["En şanssız üçte bir", "Orta", "Beklentiye yakın"])
B_groups = []
for g, x in d.groupby("grp", observed=True):
    B_groups.append(dict(group=str(g), n=int(len(x)), luck_min=r3(x.luck.min()), luck_max=r3(x.luck.max()),
                         luck_mean=r3(x.luck.mean()), pre=r3(x.pts_pre5.mean()), post=r3(x.pts_post5.mean()),
                         naive=r3(x.d_pts5.mean()), naive_ci=boot(x.d_pts5),
                         did=r3(x.did_pts5.mean()), did_ci=boot(x.did_pts5), n_did=int(x.did_pts5.notna().sum())))
dx = d.dropna(subset=["xp_xg_pre5"]).copy()
dx["perf"] = dx["xp_xg_pre5"] - dx["xp_odds_pre5"]          # oyunun kalitesi - piyasa beklentisi
THR = -0.15
B_xg = []
for lab, x in [("xG'ye göre gerçekten kötü oynuyordu", dx[dx.perf < THR]), ("Oyunu beklenti civarındaydı", dx[dx.perf >= THR])]:
    B_xg.append(dict(group=lab, n=int(len(x)), naive=r3(x.d_pts5.mean()), naive_ci=boot(x.d_pts5),
                     did=r3(x.did_pts5.mean()), did_ci=boot(x.did_pts5), d_xp_xg=r3(x.d_xp_xg5.mean())))
B = dict(groups=B_groups, xg_split=B_xg, xg_threshold=THR)

# ================================================================ C) hoca karuseli
TRM = {"Oca": 1, "Şub": 2, "Mar": 3, "Nis": 4, "May": 5, "Haz": 6, "Tem": 7, "Ağu": 8, "Eyl": 9, "Eki": 10, "Kas": 11, "Ara": 12}
tm = pd.DataFrame(json.load(open(RAW / "tm_coach_changes.json", encoding="utf-8")))
tm = tm[tm.get("league", pd.Series("TR1", index=tm.index)).fillna("TR1") == "TR1"].copy()
tm["club"] = tm["club"].str.strip()
tm["d"] = tm["end"].apply(lambda s: pd.Timestamp(int(s.split()[2]), TRM[s.split()[1]], int(s.split()[0])))
# Görev = kulübün kalıcı teknik direktörü olmak. Geçici hocanın kalıcıya terfisi de bir görev başlangıcıdır;
# kalıcı hocadan aynı kalıcı hocaya kayıtlar (sözleşme yenileme vb.) görev sayılmaz.
arr = tm[(tm["inRole"] == "Teknik Direktör") & (tm["inn"] != "")].copy()
arr = arr[~((arr["out"] == arr["inn"]) & (arr["outRole"] == "Teknik Direktör"))]
# Kulüp adlarını kısalt (görsel için)
SHORT = {"Fenerbahçe SK": "Fenerbahçe", "Galatasaray SK": "Galatasaray", "Beşiktaş JK": "Beşiktaş",
         "İstanbul Başakşehir FK": "Başakşehir", "Gençlerbirliği SK": "Gençlerbirliği",
         "Büyükşehir Belediye Erzurumspor": "Erzurumspor", "Akhisar Belediyespor": "Akhisarspor",
         "Kardemir Karabükspor": "Karabükspor", "Osmanlıspor FK": "Osmanlıspor", "Altay SK": "Altay",
         "Ankaragücü": "Ankaragücü", "Çaykur Rizespor": "Rizespor", "Fatih Karagümrük": "Karagümrük"}
arr["club_s"] = arr["club"].map(lambda c: SHORT.get(c, c))
stints = arr.groupby(["inn", "inId"]).agg(stints=("club", "size"), clubs=("club", "nunique"),
                                          returns=("club", lambda s: int(len(s) - s.nunique()))).reset_index()
stints = stints.sort_values(["stints", "clubs"], ascending=False)

# Sezon içi gönderilen kalıcı hocalar sonra ne oldu?
dep = cc[~cc["caretaker_out"]].copy()
dep["club"] = dep["club"].str.strip()
def after(r):
    nxt = arr[(arr["inn"] == r["out"]) & (arr["d"] > r["date"])].sort_values("d")
    if nxt.empty:
        return pd.Series({"rehired": False, "same_club": False, "days": np.nan})
    n = nxt.iloc[0]
    return pd.Series({"rehired": True, "same_club": n["club"] == r["club"], "days": (n["d"] - r["date"]).days})
dep = pd.concat([dep, dep.apply(after, axis=1)], axis=1)
dep_hist = dep[dep["date"] <= pd.Timestamp("2025-06-30")]       # yeniden iş bulmaya en az bir yaz süresi tanı
pairs = arr.groupby(["inn", "club_s"]).size()
C = dict(
    n_dismissed=int(len(dep_hist)),
    rehired=r3(dep_hist["rehired"].mean()),
    rehired_other=r3((dep_hist["rehired"] & ~dep_hist["same_club"]).mean()),
    rehired_same=r3((dep_hist["rehired"] & dep_hist["same_club"]).mean()),
    median_days=r3(dep_hist.loc[dep_hist.rehired, "days"].median()),
    n_coaches=int(len(stints)), n_stints=int(stints["stints"].sum()),
    coaches_3plus=int((stints["stints"] >= 3).sum()),
    pairs_returned=int((pairs >= 2).sum()),
    top=json.loads(stints.head(15).to_json(orient="records", force_ascii=False)),
)
# Ağ: en çok görev alan 12 hoca ve kulüpleri (her görev ayrı kenar, sezonuyla)
top_names = list(stints.head(12)["inn"])
edges = arr[arr["inn"].isin(top_names)].sort_values("d")
C["network"] = dict(
    coaches=[dict(name=n, stints=int(stints.loc[stints.inn == n, "stints"].iloc[0])) for n in top_names],
    clubs=sorted(edges["club_s"].unique().tolist(), key=lambda c: -int((edges["club_s"] == c).sum())),
    edges=[dict(coach=r.inn, club=r.club_s, season=int(r.season) if r.sec == "in" else int(r.season) + 1,
                year=int(r.d.year)) for r in edges.itertuples()],
)

out = dict(A=A, B=B, C=C)
json.dump(out, open(P / "extensions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ================================================================ konsol özeti
print("A) Kovma tetikleyicileri — xG'li sezonlar (n=%d maç, %d kovma)" % (A["modelxg"]["n"], A["modelxg"]["sacks"]))
print(m2.round(3).to_string())
for r in A["modelxg"]["effects"]:
    print(f"   {r['label']:32s} oran x{r['or_']}  [{r['lo']}, {r['hi']}]  p={r['p']}")
print("   10 sezon modeli:")
print(m1.round(3).to_string())
print("   Kovulmadan önce:", A["before_sack"])
print("\nB) Şans gruplarına göre:")
for g in B_groups:
    print(f"   {g['group']:22s} n={g['n']:3d} şans [{g['luck_min']}, {g['luck_max']}]  naif {g['naive']} {g['naive_ci']}  DiD {g['did']} {g['did_ci']}")
for g in B_xg:
    print(f"   {g['group']:36s} n={g['n']:3d}  naif {g['naive']}  DiD {g['did']} {g['did_ci']}  xG-xP Δ {g['d_xp_xg']}")
print("\nC) Hoca karuseli:", {k: v for k, v in C.items() if k not in ("top", "network")})
print(stints.head(12).to_string(index=False))
