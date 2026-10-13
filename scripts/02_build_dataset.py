"""
02_build_dataset.py
-------------------
Ham verileri (Sofascore maçları + Transfermarkt hoca değişiklikleri + Wikipedia ayrılış şekli)
analiz edilebilir iki tabloya çevirir:

  data/processed/team_matches.csv   -> takım-maç düzeyi (her maç iki satır)
  data/processed/coach_changes.csv  -> sezon içi teknik direktör değişiklikleri (olaylar)

Metrikler
  pts      : gerçek puan (3/1/0)
  xp_xg    : xG tabanlı beklenen puan. İki takımın xG'si bağımsız Poisson ortalaması kabul edilir,
             P(G), P(B) hesaplanır, xP = 3*P(G) + P(B)   ("The sacking illusion" ile aynı mantık)
  xp_odds  : Bahis oranı tabanlı beklenen puan. Oranlar 1/o ile olasılığa çevrilip marj
             normalize edilir, xP = 3*P(G) + P(B). (Piyasanın maç öncesi güç beklentisi.)
"""
import json, math, re, unicodedata, difflib
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- yardımcılar
def pois_pmf(lam, kmax=12):
    k = np.arange(kmax + 1)
    return np.exp(-lam) * lam ** k / np.array([math.factorial(int(i)) for i in k])

def xp_from_xg(xg_for, xg_against):
    if pd.isna(xg_for) or pd.isna(xg_against):
        return np.nan
    a, b = pois_pmf(max(xg_for, 1e-6)), pois_pmf(max(xg_against, 1e-6))
    m = np.outer(a, b)                      # m[i, j] = P(biz i, onlar j)
    p_win, p_draw = np.tril(m, -1).sum(), np.trace(m)
    return 3 * p_win + p_draw

def xp_from_odds(o_win, o_draw, o_loss):
    if any(pd.isna(x) or x <= 1 for x in (o_win, o_draw, o_loss)):
        return np.nan
    inv = np.array([1 / o_win, 1 / o_draw, 1 / o_loss])
    p = inv / inv.sum()
    return 3 * p[0] + p[1]

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(sk|fk|jk|as|spor kulubu|a\.s\.|kulubu)\b", " ", s)
    return re.sub(r"[^a-z]", "", s)

TR_MONTHS = {"Oca": 1, "Şub": 2, "Mar": 3, "Nis": 4, "May": 5, "Haz": 6, "Tem": 7,
             "Ağu": 8, "Eyl": 9, "Eki": 10, "Kas": 11, "Ara": 12}

def parse_tr_date(s):
    d, m, y = s.strip().split()
    return pd.Timestamp(int(y), TR_MONTHS[m], int(d))

# ---------------------------------------------------------------- 1) maçlar
m = pd.DataFrame(json.load(open(RAW / "sofascore_matches.json", encoding="utf-8")))
m = m.drop_duplicates("id")
m["date"] = pd.to_datetime(m["ts"], unit="s", utc=True).dt.tz_convert("Europe/Istanbul").dt.tz_localize(None)
# FotMob xG (Opta) -> birincil xG kaynağı; tek sağlayıcı = sezonlar arası tutarlılık.
# FotMob'da xG olmayan maçlarda Sofascore xG'si kullanılır.
m = m.rename(columns={"xgH": "xgH_ss", "xgA": "xgA_ss"})
fm_path = RAW / "fotmob_xg.json"
m["xgH_fm"] = m["xgA_fm"] = np.nan
if fm_path.exists():
    fm = pd.DataFrame(json.load(open(fm_path, encoding="utf-8")))
    fm = fm[fm["xgH"].notna()].copy()
    fm["t"] = pd.to_datetime(fm["utc"], utc=True).map(lambda x: int(x.timestamp()))
    fm["key"] = fm["home"].map(norm) + "|" + fm["away"].map(norm)
    fm_t = fm["t"].to_numpy()
    for idx, r in m.iterrows():
        cand = fm[np.abs(fm_t - r["ts"]) <= 6 * 3600]
        if cand.empty:
            continue
        key = norm(r["home"]) + "|" + norm(r["away"])
        sc = cand["key"].apply(lambda k: difflib.SequenceMatcher(None, k, key).ratio())
        if sc.max() >= 0.5:
            best = cand.loc[sc.idxmax()]
            m.at[idx, "xgH_fm"], m.at[idx, "xgA_fm"] = best["xgH"], best["xgA"]
    both = m[["xgH_fm", "xgH_ss"]].dropna()
    print(f"FotMob xG eşleşen maç: {m['xgH_fm'].notna().sum()} | FotMob-Sofascore xG korelasyonu "
          f"(ortak {len(both)} maç): {both.corr().iloc[0, 1]:.2f}")
m["xg_src"] = np.where(m["xgH_fm"].notna(), "FotMob", np.where(m["xgH_ss"].notna(), "Sofascore", ""))
m["xgH"] = m["xgH_fm"].fillna(m["xgH_ss"])
m["xgA"] = m["xgA_fm"].fillna(m["xgA_ss"])

# Kapanış oranı yoksa açılış oranını kullan
for s in "HDA":
    m[f"o{s}"] = m[f"o{s}"].fillna(m[f"o{s}0"])

rows = []
for r in m.itertuples():
    for side in ("home", "away"):
        h = side == "home"
        gf, ga = (r.hg, r.ag) if h else (r.ag, r.hg)
        xgf, xga = (r.xgH, r.xgA) if h else (r.xgA, r.xgH)
        ow, ol = (r.oH, r.oA) if h else (r.oA, r.oH)
        rows.append(dict(
            match_id=r.id, season=r.season, date=r.date, round=r.round,
            team_id=r.homeId if h else r.awayId, team=r.home if h else r.away,
            opp=r.away if h else r.home, home=int(h), gf=gf, ga=ga,
            pts=3 if gf > ga else (1 if gf == ga else 0),
            xgf=xgf, xga=xga, xp_xg=xp_from_xg(xgf, xga),
            xp_odds=xp_from_odds(ow, r.oD, ol),
        ))
tm_ = pd.DataFrame(rows).sort_values(["team_id", "date"]).reset_index(drop=True)
tm_["n"] = tm_.groupby(["team_id", "season"]).cumcount() + 1      # sezon içi maç sırası
# Takımın en güncel Sofascore adı (isim değişikliklerine karşı team_id ile grupla)
latest = tm_.sort_values("date").groupby("team_id")["team"].last()
latest = latest.replace({"Ankaraspor": "Osmanlıspor"})   # 2016-18'de Süper Lig'deki adıyla göster
tm_["team"] = tm_["team_id"].map(latest)
tm_.to_csv(OUT / "team_matches.csv", index=False)
print(f"team_matches: {len(tm_)} satır, {tm_['match_id'].nunique()} maç, "
      f"xG kapsamı %{100 * tm_['xp_xg'].notna().mean():.0f}, oran kapsamı %{100 * tm_['xp_odds'].notna().mean():.0f}")

# ---------------------------------------------------------------- 2) hoca değişiklikleri
tm_all = pd.DataFrame(json.load(open(RAW / "tm_coach_changes.json", encoding="utf-8")))
tm_all["club"] = tm_all["club"].str.strip()
tm_all["date"] = tm_all["end"].apply(parse_tr_date)   # sezon sonu kayıtları dahil tüm değişiklikler
tm = tm_all[tm_all["sec"] == "in"].copy()

# Transfermarkt kulüp adı -> Sofascore team_id (sezonda oynayan takımlar arasından en yakın isim)
MANUAL = {  # otomatik eşleşmenin zorlandığı adlar
    "Büyükşehir Belediye Erzurumspor": "Erzurumspor FK",
    "İstanbul Başakşehir FK": "Başakşehir",
    "Ankaragücü": "Ankaragücü",
    "Osmanlıspor FK": "Osmanlıspor",         # Sofascore adı "Ankaraspor"; aşağıda Osmanlıspor olarak gösteriliyor
    "Akhisar Belediyespor": "Akhisarspor",
    "Kardemir Karabükspor": "Karabükspor",
}
def map_club(club, season):
    cand = tm_.loc[tm_["season"] == season, ["team_id", "team"]].drop_duplicates()
    names = {norm(t): tid for tid, t in cand.itertuples(index=False)}
    key = norm(MANUAL.get(club, club))
    if key in names:
        return names[key]
    for k, tid in names.items():                 # alt-dize eşleşmesi
        if key and (key in k or k in key):
            return tid
    best = difflib.get_close_matches(key, list(names), n=1, cutoff=0.8)
    return names[best[0]] if best else np.nan

tm["team_id"] = [map_club(c, s) for c, s in zip(tm["club"], tm["season"])]
unmapped = tm[tm["team_id"].isna()]
if len(unmapped):
    print("UYARI eşleşmeyen kulüpler:", unmapped[["season", "club"]].drop_duplicates().values.tolist())
tm = tm.dropna(subset=["team_id"])
tm["team_id"] = tm["team_id"].astype(int)
tm["team"] = tm["team_id"].map(latest)

# Wikipedia'dan ayrılış şekli (kovulma / istifa / karşılıklı anlaşma)
wk = pd.DataFrame(json.load(open(RAW / "wiki_managerial_changes.json", encoding="utf-8")))
wk["out_norm"] = wk["Outgoing manager"].apply(norm)
wk["manner"] = wk["Manner of departure"]
wk["wdate"] = pd.to_datetime(wk["Date of vacancy"], format="%d %B %Y", errors="coerce")

def manner_for(row):
    cand = wk[wk["out_norm"].apply(lambda s: norm(row["out"]).endswith(s[-6:]) or s.endswith(norm(row["out"])[-6:]))]
    if cand.empty:
        return "Bilinmiyor"
    cand = cand.assign(dd=(cand["wdate"] - row["date"]).abs()).sort_values("dd")
    if pd.isna(cand.iloc[0]["dd"]) or cand.iloc[0]["dd"].days > 10:
        return "Bilinmiyor"
    return cand.iloc[0]["manner"]

tm["manner_raw"] = tm.apply(manner_for, axis=1)
def manner_tr(s):
    s = str(s).lower()
    if "sack" in s: return "Kovuldu"
    if "resign" in s: return "İstifa"
    if "mutual" in s or "consent" in s or "agreement" in s: return "Karşılıklı anlaşma"
    if "interim" in s or "caretaker" in s: return "Geçici dönem sonu"
    if s == "bilinmiyor": return "Bilinmiyor"
    return "Diğer"
tm["manner"] = tm["manner_raw"].apply(manner_tr)
tm["caretaker_out"] = tm["outRole"].ne("Teknik Direktör")
# Transfermarkt bazen geçici hocayı giderken "Teknik Direktör" diye listeliyor. Bu yüzden hocanın bu kulübe
# EN SON hangi rolle geldiğine bakılır (sezon sonu/yaz kayıtları dahil, böylece yazın kalıcıya terfi eden
# geçici hoca doğru sınıflanır). En son geliş "Geçici" ise ya da kayıt aynı kişiden aynı kişiye ise olay sayılmaz.
def last_arrival_role(r):
    a = tm_all[(tm_all["club"] == r["club"]) & (tm_all["inn"] == r["out"]) & (tm_all["date"] < r["date"])]
    return a.sort_values("date").iloc[-1]["inRole"] if len(a) else ""
tm["arrival_role"] = tm.apply(last_arrival_role, axis=1)
tm["caretaker_out"] |= tm["arrival_role"].str.contains("Geçici", na=False) | (tm["out"] == tm["inn"])
tm["caretaker_in"] = tm["inRole"].str.contains("Geçici", na=False)

cc = tm[["season", "team_id", "team", "club", "date", "out", "outRole", "inn", "inRole",
         "rankOut", "tenure", "manner", "manner_raw", "caretaker_out", "caretaker_in"]]
cc = cc.sort_values(["date", "team"]).reset_index(drop=True)
cc.to_csv(OUT / "coach_changes.csv", index=False)
print(f"coach_changes: {len(cc)} sezon içi değişiklik ({(~cc['caretaker_out']).sum()} kalıcı hoca ayrılışı)")
print(cc["manner"].value_counts().to_string())
