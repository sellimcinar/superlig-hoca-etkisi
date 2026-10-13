"""
03_analyze.py
-------------
Hoca değişikliğinin etkisi: naif önce/sonra, eşleştirilmiş kontrol grubu (fark içinde fark),
olay çalışması (event study) ve takım bazında özet.

Tasarım ("The sacking illusion", J. Sports Sci. 2026'dan uyarlandı)
  * Olay      : sezon içinde kalıcı teknik direktörün ayrılması (geçici hocanın ayrılması olay sayılmaz).
                Olay anı = hocanın son görev günü; o gün ve öncesi oynanan maçlar "önce".
  * Pencere   : k = 5 ve k = 10 lig maçı (önce ve sonra, aynı sezon içinde).
  * Kontrol   : Aynı sezonda, benzer maç haftasında (±5 maç), son 5 maçta BİREBİR aynı puanı toplamış
                ve [-k, +k] penceresinde hoca değiştirmemiş takımlar. Adaylar arasından maç haftası ve
                piyasa gücü (önceki k maçın oran-xP ortalaması) ve (k=10 için) önceki 10 maçtaki
                puanı en yakın 5 takım seçilir.
                Hiç birebir eşleşme yoksa ±1 puan toleransı kullanılır.
  * Etki (DiD): (sonra - önce)_hoca değiştiren  -  (sonra - önce)_kontrol
  * Belirsizlik: olaylar üzerinden 2000 tekrarlı bootstrap, %95 güven aralığı.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
rng = np.random.default_rng(42)
METRICS = ["pts", "xp_xg", "xp_odds"]
KS = [5, 10]
EVENT_WIN = 10

tmx = pd.read_csv(P / "team_matches.csv", parse_dates=["date"])
cc = pd.read_csv(P / "coach_changes.csv", parse_dates=["date"])
tmx = tmx.sort_values(["team_id", "season", "date"]).reset_index(drop=True)
groups = {k: g.reset_index(drop=True) for k, g in tmx.groupby(["team_id", "season"])}

# Her takım-sezon için "değişiklik tarihleri" (geçici dahil tüm sezon içi değişiklikler)
change_dates = cc.groupby(["team_id", "season"])["date"].apply(list).to_dict()

events = cc[~cc["caretaker_out"]].copy().reset_index(drop=True)
events["event_id"] = np.arange(len(events))

def split_idx(g, d):
    """d tarihinde/öncesinde oynanan son maçın indeksi (0 tabanlı) -> önce = [..i], sonra = [i+1..]"""
    return int((g["date"] < d + pd.Timedelta(days=1)).sum()) - 1

# ---------------------------------------------------------------- olay düzeyi pencereler
ev_rows, es_rows = [], []
for e in events.itertuples():
    g = groups.get((e.team_id, e.season))
    if g is None:
        continue
    i = split_idx(g, e.date)
    base = dict(event_id=e.event_id, season=e.season, team_id=e.team_id, team=e.team, date=e.date,
                out=e.out, inn=e.inn, inRole=e.inRole, manner=e.manner, rankOut=e.rankOut,
                match_no=i + 1, n_season=len(g),
                pre5_pts_sum=g["pts"].iloc[max(0, i - 4): i + 1].sum() if i >= 4 else np.nan)
    # aynı takımın bir sonraki değişikliği (pencere kirlenmesi bayrağı)
    later = [d for d in change_dates.get((e.team_id, e.season), []) if d > e.date]
    nxt = split_idx(g, min(later)) if later else None
    for k in KS:
        ok = i + 1 >= k and len(g) - (i + 1) >= k
        base[f"ok{k}"] = ok
        base[f"contam{k}"] = bool(nxt is not None and nxt - i < k)
        for mtr in METRICS:
            pre = g[mtr].iloc[i - k + 1: i + 1] if ok else pd.Series(dtype=float)
            post = g[mtr].iloc[i + 1: i + 1 + k] if ok else pd.Series(dtype=float)
            base[f"{mtr}_pre{k}"] = pre.mean() if ok and pre.notna().all() else np.nan
            base[f"{mtr}_post{k}"] = post.mean() if ok and post.notna().all() else np.nan
            base[f"d_{mtr}{k}"] = base[f"{mtr}_post{k}"] - base[f"{mtr}_pre{k}"]
    ev_rows.append(base)
    for t in range(-EVENT_WIN, EVENT_WIN + 1):
        if t == 0:
            continue
        j = i + t + (1 if t < 0 else 0)
        if 0 <= j < len(g):
            es_rows.append(dict(event_id=e.event_id, group="Hoca değiştiren", t=t,
                                **{mtr: g[mtr].iloc[j] for mtr in METRICS}))
ev = pd.DataFrame(ev_rows)

# ---------------------------------------------------------------- kontrol havuzu
def candidate_pool(k):
    rows = []
    for (tid, s), g in groups.items():
        cds = change_dates.get((tid, s), [])
        cidx = [split_idx(g, d) for d in cds]
        pts = g["pts"].to_numpy()
        for i in range(max(k, 5) - 1, len(g) - k):
            if any(i - k < c <= i + k for c in cidx):      # pencerede hoca değişikliği yok
                continue
            rows.append(dict(team_id=tid, season=s, i=i, pre5=pts[i - 4: i + 1].sum(),
                             xpo_pre=g["xp_odds"].iloc[i - k + 1: i + 1].mean(),
                             prek=pts[i - k + 1: i + 1].sum()))
    return pd.DataFrame(rows)

def window_means(tid, s, i, k):
    g = groups[(tid, s)]
    out = {}
    for mtr in METRICS:
        pre, post = g[mtr].iloc[i - k + 1: i + 1], g[mtr].iloc[i + 1: i + 1 + k]
        out[f"{mtr}_pre"] = pre.mean() if pre.notna().all() else np.nan
        out[f"{mtr}_post"] = post.mean() if post.notna().all() else np.nan
    return out

N_CTRL = 5
ROUND_TOL = 5
ctrl_rows = []
for k in KS:
    pool = candidate_pool(k)
    for e in ev[ev[f"ok{k}"]].itertuples():
        i = e.match_no - 1
        c = pool[(pool["season"] == e.season) & (pool["team_id"] != e.team_id) & ((pool["i"] - i).abs() <= ROUND_TOL)]
        exact = c[c["pre5"] == e.pre5_pts_sum]
        c = exact if len(exact) else c[(c["pre5"] - e.pre5_pts_sum).abs() <= 1]
        if c.empty:
            continue
        # en yakın kontroller: maç haftası yakınlığı + piyasa gücü (oran-xP) benzerliği
        xpo = getattr(e, f"xp_odds_pre{k}")
        dx = (c["xpo_pre"] - xpo).abs() / 0.08 if pd.notna(xpo) else 0
        prek = getattr(e, f"pts_pre{k}") * k
        dp = (c["prek"] - prek).abs() / 2 if k > 5 else 0      # k=10'da önceki 10 maçın puanı da yakın olsun
        c = c.assign(dist=(c["i"] - i).abs() / ROUND_TOL + dx + dp + rng.random(len(c)) * 0.01).nsmallest(N_CTRL, "dist")
        for cr in c.itertuples():
            wm = window_means(cr.team_id, cr.season, cr.i, k)
            ctrl_rows.append(dict(event_id=e.event_id, k=k, ctrl_team_id=cr.team_id, exact=bool(len(exact)), **wm))
            if k == EVENT_WIN:
                g = groups[(cr.team_id, cr.season)]
                for t in range(-EVENT_WIN, EVENT_WIN + 1):
                    if t == 0:
                        continue
                    j = cr.i + t + (1 if t < 0 else 0)
                    if 0 <= j < len(g):
                        es_rows.append(dict(event_id=e.event_id, group="Kontrol", t=t,
                                            w=1 / len(c), **{mtr: g[mtr].iloc[j] for mtr in METRICS}))
ctrl = pd.DataFrame(ctrl_rows)
es = pd.DataFrame(es_rows)
es["w"] = es["w"].fillna(1.0)

# kontrol ortalamalarını olaylara bağla
for k in KS:
    ck = ctrl[ctrl["k"] == k].groupby("event_id")
    agg = ck[[f"{m}_{p}" for m in METRICS for p in ("pre", "post")]].mean()
    agg.columns = [f"c_{c.replace('_pre', f'_pre{k}').replace('_post', f'_post{k}')}" for c in agg.columns]
    agg[f"n_ctrl{k}"] = ck.size()
    ev = ev.merge(agg, left_on="event_id", right_index=True, how="left")
    for mtr in METRICS:
        ev[f"c_d_{mtr}{k}"] = ev[f"c_{mtr}_post{k}"] - ev[f"c_{mtr}_pre{k}"]
        ev[f"did_{mtr}{k}"] = ev[f"d_{mtr}{k}"] - ev[f"c_d_{mtr}{k}"]

# ---------------------------------------------------------------- özetler
def boot_ci(x, B=2000):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 3:
        return [np.nan, np.nan]
    bs = rng.choice(x, (B, len(x))).mean(1)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]

def r(x, d=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)

def summarize(E, ES):
    """E: olay tablosu (alt küme), ES: olay-zamanı satırları (aynı olaylar)."""
    summary = {}
    for k in KS:
        sub = E[E[f"ok{k}"]]
        s_ = {"n_events": int(len(sub)), "n_matched": int(sub[f"n_ctrl{k}"].notna().sum())}
        for mtr in METRICS:
            v = sub.dropna(subset=[f"{mtr}_pre{k}", f"{mtr}_post{k}"])
            vm = v.dropna(subset=[f"did_{mtr}{k}"])
            s_[mtr] = dict(
                n=int(len(v)),
                pre=r(v[f"{mtr}_pre{k}"].mean()), post=r(v[f"{mtr}_post{k}"].mean()),
                diff=r(v[f"d_{mtr}{k}"].mean()), diff_ci=[r(c) for c in boot_ci(v[f"d_{mtr}{k}"])],
                n_matched=int(len(vm)),
                ctrl_pre=r(vm[f"c_{mtr}_pre{k}"].mean()), ctrl_post=r(vm[f"c_{mtr}_post{k}"].mean()),
                ctrl_diff=r(vm[f"c_d_{mtr}{k}"].mean()),
                did=r(vm[f"did_{mtr}{k}"].mean()), did_ci=[r(c) for c in boot_ci(vm[f"did_{mtr}{k}"])],
                # aynı olaylarda gerçek puan (xP ile birebir kıyas için)
                pts_pre_same=r(v[f"pts_pre{k}"].mean()), pts_post_same=r(v[f"pts_post{k}"].mean()),
            )
        summary[k] = s_

    # olay çalışması: her olay-zamanı için ortalama (kontrol ağırlıklı)
    es_sum = []
    for (grp, t), g in ES.groupby(["group", "t"]):
        row = dict(group=grp, t=int(t), n=int(g["event_id"].nunique()))
        for mtr in METRICS:
            gg = g.dropna(subset=[mtr])
            if gg.empty:
                row[mtr] = None
                continue
            if grp == "Kontrol":   # önce olay içinde ortala, sonra olaylar arası
                per = gg.groupby("event_id").apply(lambda d: np.average(d[mtr], weights=d["w"]), include_groups=False)
            else:
                per = gg.set_index("event_id")[mtr]
            row[mtr] = r(per.mean())
        if grp == "Hoca değiştiren":   # xG'nin olduğu maçlarda puan ortalaması (xP ile birebir kıyas için)
            gx = g.dropna(subset=["xp_xg"])
            row["pts_xgs"], row["n_xg"] = r(gx["pts"].mean()) if len(gx) else None, int(gx["event_id"].nunique())
        es_sum.append(row)

    # takım bazında
    team_rows = []
    for tid, g in E.groupby("team_id"):
        row = dict(team_id=int(tid), team=g["team"].iloc[0], n_changes=int(len(g)),
                   seasons=sorted(set(int(x) for x in g["season"])))
        for k in KS:
            gk = g[g[f"ok{k}"]]
            row[f"n{k}"] = int(len(gk))
            for mtr in METRICS:
                row[f"pre_{mtr}{k}"] = r(gk[f"{mtr}_pre{k}"].mean())
                row[f"post_{mtr}{k}"] = r(gk[f"{mtr}_post{k}"].mean())
                row[f"d_{mtr}{k}"] = r(gk[f"d_{mtr}{k}"].mean())
                row[f"did_{mtr}{k}"] = r(gk[f"did_{mtr}{k}"].mean())
        team_rows.append(row)
    teams = pd.DataFrame(team_rows).sort_values("d_pts5", ascending=False)

    # ayrılış şekline göre
    manner = []
    for k in KS:
        for mn, g in E[E[f"ok{k}"]].groupby("manner"):
            manner.append(dict(k=k, manner=mn, n=int(len(g)), d_pts=r(g[f"d_pts{k}"].mean()),
                               did_pts=r(g[f"did_pts{k}"].mean()), d_xp_xg=r(g[f"d_xp_xg{k}"].mean()),
                               n_xg=int(g[f"d_xp_xg{k}"].notna().sum())))
    return summary, es_sum, teams, manner

# Dönemler: tüm dönem + iki alt dönem (sağlamlık için)
PERIODS = {"all": ("Tümü", lambda d: d["season"] >= 0),
           "p1": ("2016/17–2019/20", lambda d: d["season"] <= 2019),
           "p2": ("2020/21–2026/27", lambda d: d["season"] >= 2020)}
periods = {}
for key, (label, f) in PERIODS.items():
    E = ev[f(ev)]
    ES = es[es["event_id"].isin(E["event_id"])]
    sm, esm, tms, mnr = summarize(E, ES)
    periods[key] = dict(label=label, summary={str(k): v for k, v in sm.items()}, event_study=esm,
                        teams=json.loads(tms.to_json(orient="records", force_ascii=False)), manner=mnr,
                        seasons=sorted(int(x) for x in tmx.loc[f(tmx), "season"].unique()),
                        n_matches=int(tmx.loc[f(tmx), "match_id"].nunique()))
    if key == "all":
        summary, es_sum, teams, manner = sm, esm, tms, mnr

# sezon başına değişiklik sayısı
per_season = events.groupby("season").size().to_dict()

# ---------------------------------------------------------------- kaydet
ev.to_csv(P / "events_analysis.csv", index=False)
teams.to_csv(P / "team_summary.csv", index=False)
pd.DataFrame(es_sum).to_csv(P / "event_study.csv", index=False)

keep = ["event_id", "season", "team", "team_id", "date", "out", "inn", "inRole", "manner", "rankOut",
        "match_no", "n_season", "pre5_pts_sum", "ok5", "ok10", "contam5", "contam10", "n_ctrl5", "n_ctrl10"]
keep += [c for c in ev.columns if any(c.startswith(p) for p in
         ("pts_", "xp_xg_", "xp_odds_", "d_", "did_", "c_pts", "c_xp", "c_d_"))]
evj = ev[keep].copy()
evj["date"] = evj["date"].dt.strftime("%Y-%m-%d")
evj = evj.astype(object).where(evj.notna(), None)
for c in evj.columns:
    if evj[c].dtype == object:
        evj[c] = evj[c].apply(lambda v: round(v, 3) if isinstance(v, float) else v)

xg_cov = tmx.groupby("season")["xp_xg"].apply(lambda s: round(float(s.notna().mean()), 3)).to_dict()
odds_cov = tmx.groupby("season")["xp_odds"].apply(lambda s: round(float(s.notna().mean()), 3)).to_dict()
res = dict(
    generated=pd.Timestamp.now().strftime("%Y-%m-%d"),
    seasons=sorted(int(s) for s in tmx["season"].unique()),
    n_matches=int(tmx["match_id"].nunique()),
    per_season_changes={int(k): int(v) for k, v in per_season.items()},
    coverage=dict(xg={int(k): v for k, v in xg_cov.items()}, odds={int(k): v for k, v in odds_cov.items()}),
    summary={str(k): v for k, v in summary.items()},
    event_study=es_sum,
    teams=json.loads(teams.to_json(orient="records", force_ascii=False)),
    manner=manner,
    events=evj.to_dict(orient="records"),
    periods=periods,
)
def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if np.isnan(o) else round(float(o), 3)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o
json.dump(clean(res), open(P / "results.json", "w", encoding="utf-8"), ensure_ascii=False, default=str, allow_nan=False)

# ---------------------------------------------------------------- konsol raporu
for pk, pv in periods.items():
  for k in KS:
    s = pv["summary"][str(k)]
    print(f"\n=== [{pv['label']}] Pencere k={k} maç | olay: {s['n_events']} (kontrol eşleşen: {s['n_matched']}) ===")
    for mtr, lab in zip(METRICS, ["Puan", "xP (xG)", "xP (oran)"]):
        x = s[mtr]
        if not x["n"]:
            continue
        print(f"{lab:10s} n={x['n']:3d}  önce {x['pre']}  sonra {x['post']}  Δ {x['diff']} {x['diff_ci']} | "
              f"kontrol önce {x['ctrl_pre']} sonra {x['ctrl_post']} Δ {x['ctrl_diff']}  DiD {x['did']} {x['did_ci']}")
print("\nAyrılış şekli:", [x for x in manner if x["k"] == 5])
print("\nTakımlar (Δ puan/maç):")
print(teams[["team", "n_changes", "n5", "d_pts5", "did_pts5", "n10", "d_pts10", "did_pts10"]].to_string(index=False))
