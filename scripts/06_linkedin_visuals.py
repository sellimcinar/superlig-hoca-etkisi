"""
06_linkedin_visuals.py
----------------------
LinkedIn için 4:5 (1080x1350) kaydırmalı görseller üretir (Türkçe).
Çıktı: linkedin/tr/slide_1..8.png, linkedin/tr/carousel_tr.pdf

Tüm sayılar data/processed/ altındaki analiz çıktılarından okunur; elle yazılmış sayı yok.
Yazı tipleri: Barlow Condensed + Source Sans 3 (fonts/ klasöründe; yoksa sistem yazı tipi).
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"

for d in [ROOT / "fonts", Path.home() / ".fonts"]:
    for f in d.glob("*.ttf") if d.exists() else []:
        try:
            fm.fontManager.addfont(str(f))
        except Exception:
            pass
fams = {f.name for f in fm.fontManager.ttflist}
DISPLAY = "Barlow Condensed" if "Barlow Condensed" in fams else "DejaVu Sans"
BODY = "Source Sans 3" if "Source Sans 3" in fams else "DejaVu Sans"

C = dict(bg="#f4f6f2", surface="#fdfdfb", ink="#121611", ink2="#4a5147", muted="#80867c",
         grid="#e3e6de", axis="#c3c8bb", accent="#1d6b47", wash="#e9eee6",
         treat="#2a78d6", ctrl="#eb6834", xp="#1baf7a", hl="#e34948", other="#b7bdb1")

res = json.load(open(P / "results.json", encoding="utf-8"))
S5 = res["summary"]["5"]
es = pd.read_csv(P / "event_study.csv")
lc = pd.read_csv(P / "league_comparison.csv")
n_events = sum(res["per_season_changes"].values())
PER = res.get("periods", {})
did_p1 = PER.get("p1", {}).get("summary", {}).get("5", {}).get("pts", {}).get("did")
did_p2 = PER.get("p2", {}).get("summary", {}).get("5", {}).get("pts", {}).get("did")
n_matches = res["n_matches"]
tr = lc[lc.league == "TR1"].iloc[0]
b5 = lc[lc.league != "TR1"]
R = lambda v: int(v + 0.5)          # yarımı yukarı yuvarla (dashboard ile aynı)
EXT = json.load(open(P / "extensions.json", encoding="utf-8"))   # 07_extensions.py çıktısı
XA, XB, XC = EXT["A"], EXT["B"], EXT["C"]
eff = {r["var"]: r for r in XA["modelxg"]["effects"]}
bs = XA["before_sack"]
N_PAGES = 8

def num(v, d=2, lang="tr", sign=False):
    s = f"{abs(v):.{d}f}"
    if lang == "tr":
        s = s.replace(".", ",")
    if sign:
        s = ("+" if v > 0 else "−" if v < 0 else "±") + s
    elif v < 0:
        s = "−" + s
    return s

import textwrap
Tt_all = es[es.group == "Hoca değiştiren"].sort_values("t")
pt_last = float(Tt_all.loc[Tt_all.t == -1, "pts"].iloc[0]); pt_first = float(Tt_all.loc[Tt_all.t == 1, "pts"].iloc[0])
xg_from = XA["modelxg"]["seasons"][0]
XG_SEASONS = f"{xg_from}/{str(xg_from + 1)[2:]}+"

T = {
 "tr": dict(
   eyebrow="SÜPER LİG · 2016/17 – 2026/27",
   foot="Veri: Sofascore, FotMob (Opta xG), Transfermarkt",
   swipe="Kaydır →",
   s1_title="Süper Lig'de hoca kovmak\ngerçekten etkili mi?",
   s1_sub=f"Gerçek puan, xG ve bahis oranları kullanılarak {n_events} sezon içi hoca değişikliği ve {n_matches} maç analiz edildi.",
   s1_q=["Yeni hoca gelince takım gerçekten düzeliyor mu?",
         "Yoksa takım zaten düzelecek miydi?",
         "Yönetimler hocayı neye bakarak gönderiyor?",
         "Türkiye'de hocalara ne kadar zaman tanınıyor?"],
   s1_spark=f"Hoca değiştiren takımların maç başına ortalama puanı, değişiklikten önceki ve sonraki 10 maç",
   s1_lo=f"{num(pt_last, 2)} · son maç", s1_hi=f"{num(pt_first, 2)} · yeni hocayla ilk maç",
   s2_title="Hoca değişti, takım düzeldi\naslında değişmeseydi de düzelecekti",
   s2_cap="Mavi çizgi: hocasını değiştirenler, turuncu çizgi: aynı sezonda aynı kötü seriyi yaşayıp hocasını tutanlar. Değişiklik öncesi ve sonrası 10 maç incelendi.",
   treat="Hoca değiştirenler", ctrl="Hocasını tutanlar",
   xlab="Değişikliğe göre maç sırası", newcoach="Yeni hoca",
   s2_period=f"2016–2026 · gerçek hoca etkisi {num(S5['pts']['did'], 2, 'tr', True)} puan/maç",
   s2_k1=("Görünen etki", "yeni hocayla ilk 5 maç"), s2_k2=("Hoca değişmeseydi", "hocasını tutan takımlar"),
   s2_k3=("Gerçek hoca etkisi", "aradaki fark (puan/maç)"),
   s3_title="Çöküş çoğunlukla kötü\noyundan değil, şanssızlıktan",
   s3_cap=f"Değişiklik öncesi ve sonrası 10 maçta takımların aldığı gerçek puanlar ile hak ettiği puanlar (xG verisi olan maçlar, {XG_SEASONS}).",
   pts="Gerçek puan", xpl="xG'ye göre hak edilen puan (xP)",
   s3_pre="Son 5 maç", s3_post="Yeni hocayla ilk 5 maç",
   s3_note="Puan xP'nin çok altına düşüyor, xP ise yerinde duruyor.\nYeni hoca gelince puan xP'ye geri dönüyor: ortalamaya dönüş.",
   s4_title="Türkiye'de hocaya\nzaman yok",
   s4_cap="Sezon içinde görevden ayrılan teknik direktör sayısı, kulüp başına sezonda (2016/17 – 2025/26, Transfermarkt).",
   s4_stats=[(f"%{R(tr.pct_clubs_changed)}", "kulüp her sezon en az bir kez\nhoca değiştiriyor",
              f"5 büyük lig: %{R(b5.pct_clubs_changed.min())}–{R(b5.pct_clubs_changed.max())}"),
             (f"%{R(tr.pct_clubs_2plus)}", "kulüp aynı sezonda iki ya da\ndaha fazla hoca değiştiriyor",
              f"5 büyük lig: %{R(b5.pct_clubs_2plus.min())}–{R(b5.pct_clubs_2plus.max())}"),
             (f"{int(tr.median_tenure_days)} gün", "giden hocanın görev süresi\n(medyan)",
              f"5 büyük lig: {int(b5.median_tenure_days.min())}–{int(b5.median_tenure_days.max())} gün")],
   sa_title="Yönetimler skora bakıyor,\noyuna değil. Peki gönderilme\nriskini ne artırıyor?",
   sa_cap=f"Lojistik regresyon ile xG'li sezonlar ({XG_SEASONS}) ve {XA['modelxg']['sacks']} kovma incelendi.",
   sa_labels={"pts5": "Son 5 maçta 0,5 puan/maç\ndaha az almak", "xp_xg5": "xG'ye göre 0,5 puan/maç\ndaha kötü oynamak",
              "xp_odds5": "Bahis beklentisinin 0,5\npuan/maç düşük olması", "lost": "Son maçı kaybetmek"},
   sa_ns="etkisiz", sa_one="etkisiz (×1)",
   sa_stats=[(f"%{R(bs['share_unlucky'] * 100)}", "kovulan hocanın son 5 maçında puan,\nxG'nin hak ettirdiğinin altındaydı",
              f"puan {num(bs['pts5'], 2, 'tr')}, xG'ye göre hak edilen {num(bs['xp_xg5'], 2, 'tr')} (maç başına)"),
             (f"%{R(bs['share_lost_last'] * 100)}", "kovulan hoca son maçını\nkaybetmişti",
              f"ligdeki tüm maçlarda kaybetme oranı %{R(bs['league_lost_rate'] * 100)}")],
   sb_title="Hoca kim olursa olsun,\nşanssız takım toparlanır",
   sb_sub="\"Yeni hoca etkisi\" neredeyse tamamen önceki şanssızlıktan geliyor.\nGerçek hoca etkisi hiçbir grupta olumlu değil.",
   sb_cap="Kovulma öncesi 5 maçta bahis beklentisinin ne kadar altında kalındığına göre üç eşit gruba ayrıldı.",
   sb_naive="Görünen etki", sb_did="Gerçek hoca etkisi",
   sb_groups=["En şanssız\nüçte bir", "Orta", "Beklentiye\nyakın"], sb_unit="puan/maç",
   sc_title="Kovulan hoca çoğunlukla\nTürkiye'de kalıyor",
   sc_cap="2016/17'den bu yana Süper Lig'de en çok görev alan hocalar (aynı kulübe dönüşler dahil).",
   sc_bar=lambda n, c: f"{n} görev · {c} kulüp",
   sc_stats=[(f"%{R(XC['rehired'] * 100)}", "sezon ortasında gönderilen hoca\nsonra yine Süper Lig'de iş buluyor",
              f"%{R(XC['rehired_other'] * 100)}'si başka kulüpte, %{R(XC['rehired_same'] * 100)}'i aynı kulübe dönerek"),
             (f"{int(XC['median_days'])} gün", "yeni işe kadar geçen süre\n(medyan)",
              f"{XC['coaches_3plus']} hoca 10 yılda 3 ya da daha fazla görev aldı")],
   s5_title="Özetle",
   s5_points=[
     ("Kovmak sihirli değnek değil.", f"Görünen etki {num(S5['pts']['diff'], lang='tr', sign=True)} puan/maç, ama hoca değişmeseydi de takım {num(S5['pts']['ctrl_diff'], lang='tr', sign=True)} toparlanacaktı. Gerçek hoca etkisi: {num(S5['pts']['did'], lang='tr', sign=True)}."),
     ("Kriz çoğu zaman şanssızlık.", f"Kovulmadan önceki 5 maçta takımlar maç başına {num(S5['xp_xg']['pts_pre_same'], lang='tr')} puan alırken xG'ye göre {num(S5['xp_xg']['pre'], lang='tr')} hak ediyor."),
     ("Yönetimler şansı cezalandırıyor.", f"Kovma kararını son maçların puanı belirliyor; xG'ye göre ne kadar iyi oynandığının ek etkisi yok. Kovulan hocaların %{R(bs['share_unlucky'] * 100)}'ü şanssızdı."),
     ("Türkiye sabırsız.", f"Kulüp başına sezon içi hoca değişikliği 5 büyük ligin yaklaşık {num(tr.per_team_season / b5.per_team_season.mean(), 1, 'tr')} katı. Gönderilen hocaların %{R(XC['rehired_other'] * 100)}'sı başka bir Süper Lig kulübünde yeniden iş buluyor."),
   ],
   s5_method="Yöntem: \"Hoca değişmeseydi\" = aynı sezonda son 5 maçta birebir aynı puanı toplayıp hocasını tutan\ntakımların toparlanması. Gerçek hoca etkisi = görünen etki − hoca değişmeseydi (fark içinde fark).\nxP: xG'den Poisson modeliyle. \"The sacking illusion\" (J. Sports Sciences, 2026) çalışmasından uyarlandı.",
   s5_cta="İnteraktif dashboard ve kod: gönderideki linkte",
   lg_names={"TR1": "Süper Lig", "GB1": "Premier League", "L1": "Bundesliga", "ES1": "LaLiga", "IT1": "Serie A", "FR1": "Ligue 1"},
 ),
}

W, H, DPI = 10.8, 13.5, 200

def canvas(t, i, n=N_PAGES):
    fig = plt.figure(figsize=(W, H), dpi=DPI, facecolor=C["bg"])
    fig.text(0.074, 0.955, t["eyebrow"], family=BODY, weight="semibold", size=13, color=C["ink2"])
    fig.text(0.926, 0.955, f"{i}/{n}", family=BODY, weight="semibold", size=13, color=C["muted"], ha="right")
    fig.add_artist(plt.Line2D([0.074, 0.926], [0.052, 0.052], color=C["axis"], lw=0.8))
    fig.text(0.074, 0.028, t["foot"], family=BODY, size=11.5, color=C["muted"])
    return fig

def title(fig, text, y=0.905):
    fig.text(0.074, y, text, family=DISPLAY, weight="bold", size=50, color=C["ink"], va="top", linespacing=0.98)

def caption(fig, text, y, width=88):
    """Grafiğin altındaki açıklama (gri, küçük)."""
    fig.text(0.074, y, textwrap.fill(text, width), family=BODY, size=14.5, color=C["muted"], va="top", linespacing=1.35)

def style_ax(ax):
    ax.set_facecolor(C["surface"])
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(C["axis"])
    ax.tick_params(colors=C["muted"], labelsize=13, length=0)
    ax.grid(axis="y", color=C["grid"], lw=1)
    ax.set_axisbelow(True)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_family(BODY)

def xpos(t):
    return t + 0.5 if t < 0 else t - 0.5

def event_lines(ax, series, lang, t):
    for name, col, df, key in series:
        for part in (df[df.t < 0], df[df.t > 0]):
            ax.plot([xpos(v) for v in part.t], part[key], color=col, lw=2.6, solid_capstyle="round", solid_joinstyle="round")
        last = df.iloc[-1]
        ax.scatter([xpos(last.t)], [last[key]], s=70, color=col, edgecolor=C["surface"], linewidth=2, zorder=5)
    ax.axvline(0, color=C["ink2"], lw=1.4)
    ax.axvspan(0, 10, color=C["wash"], zorder=0)
    ax.text(0.15, 0.98, t["newcoach"], transform=ax.get_xaxis_transform(), family=BODY, weight="semibold", size=13, color=C["ink2"], va="top")
    ticks = [-10, -5, -1, 1, 5, 10]
    ax.set_xticks([xpos(v) for v in ticks], [("+" if v > 0 else "") + str(v) for v in ticks])
    ax.set_xlim(-9.9, 9.9)
    ax.set_xlabel(t["xlab"], family=BODY, size=13, color=C["muted"], labelpad=8)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: num(v, 1, lang)))
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_family(BODY)

def legend_row(fig, items, y):
    x = 0.074
    for name, col in items:
        fig.add_artist(plt.Line2D([x, x + 0.03], [y + 0.004, y + 0.004], color=col, lw=3.2, solid_capstyle="round"))
        fig.text(x + 0.04, y, name, family=BODY, size=15, color=C["ink2"], va="center")
        x += 0.04 + 0.0105 * len(name) + 0.04

def kpi(fig, x, y, label, value, sub, col):
    fig.add_artist(plt.Circle((x + 0.006, y + 0.052), 0.0055, color=col, transform=fig.transFigure))
    fig.text(x + 0.02, y + 0.052, label, family=BODY, weight="semibold", size=15, color=C["ink2"], va="center")
    fig.text(x, y - 0.006, value, family=DISPLAY, weight="semibold", size=58, color=C["ink"], va="center")
    fig.text(x, y - 0.058, sub, family=BODY, size=13, color=C["muted"], va="center")

def stat_rows(fig, stats, y, col, gap=0.035, step=0.088):
    """Büyük sayı + yanında açıklama. Açıklama, en geniş sayının hemen sağından başlar."""
    r = fig.canvas.get_renderer(); nums = []
    for i, (big, _, _) in enumerate(stats):
        nums.append(fig.text(0.074, y - i * step, big, family=DISPLAY, weight="bold", size=48, color=col, va="center"))
    right = max(tx.get_window_extent(renderer=r).x1 for tx in nums) / fig.bbox.width
    xl = right + gap
    for i, (_, lab, cmp) in enumerate(stats):
        yy = y - i * step
        fig.text(xl, yy + 0.012, lab, family=BODY, weight="semibold", size=16, color=C["ink"], va="center", linespacing=1.25)
        fig.text(xl, yy - 0.032, cmp, family=BODY, size=14, color=C["muted"], va="center")

def slide1(t, lang):
    fig = canvas(t, 1)
    fig.text(0.074, 0.86, t["s1_title"], family=DISPLAY, weight="bold", size=66, color=C["ink"], va="top", linespacing=0.95)
    fig.text(0.074, 0.665, textwrap.fill(t["s1_sub"], 58), family=BODY, size=20, color=C["ink2"], va="top", linespacing=1.4)
    y = 0.515
    for i, q in enumerate(t["s1_q"]):
        fig.text(0.074, y, f"{i + 1}", family=DISPLAY, weight="bold", size=40, color=C["accent"], va="center")
        fig.text(0.13, y, q, family=BODY, weight="semibold", size=21, color=C["ink"], va="center")
        y -= 0.07
    # mini grafik: hoca değiştiren takımların puanı, değişiklikten 10 maç önce ve sonra
    fig.text(0.074, 0.255, t["s1_spark"], family=BODY, size=13.5, color=C["muted"], va="center")
    ax = fig.add_axes([0.074, 0.105, 0.852, 0.12]); ax.axis("off")
    for part in (Tt_all[Tt_all.t < 0], Tt_all[Tt_all.t > 0]):
        ax.plot([xpos(v) for v in part.t], part.pts, color=C["treat"], lw=3, solid_capstyle="round")
    ax.axvline(0, color=C["ink2"], lw=1.2)
    ax.set_xlim(-9.9, 9.9); ax.set_ylim(0.1, 1.75)
    ax.scatter([xpos(-1), xpos(1)], [pt_last, pt_first], s=60, color=C["treat"], edgecolor=C["bg"], linewidth=2, zorder=5)
    ax.text(xpos(-1) - 0.35, pt_last, t["s1_lo"], ha="right", va="center", family=BODY, size=13, weight="semibold", color=C["ink2"])
    ax.text(xpos(1) + 0.35, pt_first - 0.18, t["s1_hi"], ha="left", va="top", family=BODY, size=13, weight="semibold", color=C["ink2"])
    ax.text(0.15, 1.72, t["newcoach"], va="top", family=BODY, size=12.5, weight="semibold", color=C["ink2"])
    ax.text(xpos(-10), 0.1, "−10 maç", va="bottom", family=BODY, size=12, color=C["muted"])
    ax.text(xpos(10), 0.1, "+10 maç", ha="right", va="bottom", family=BODY, size=12, color=C["muted"])
    fig.text(0.926, 0.07, t["swipe"], family=BODY, weight="semibold", size=16, color=C["accent"], ha="right", va="center")
    return fig

def slide2(t, lang):
    fig = canvas(t, 2)
    title(fig, t["s2_title"])
    ax = fig.add_axes([0.11, 0.42, 0.80, 0.35]); style_ax(ax)
    Cc = es[es.group == "Kontrol"].sort_values("t")
    event_lines(ax, [(t["treat"], C["treat"], Tt_all, "pts"), (t["ctrl"], C["ctrl"], Cc, "pts")], lang, t)
    ax.set_ylim(0.2, 1.75)
    caption(fig, t["s2_cap"], 0.355)
    p = S5["pts"]
    kpi(fig, 0.074, 0.18, t["s2_k1"][0], num(p["diff"], 2, lang, True), t["s2_k1"][1], C["treat"])
    kpi(fig, 0.37, 0.18, t["s2_k2"][0], num(p["ctrl_diff"], 2, lang, True), t["s2_k2"][1], C["ctrl"])
    kpi(fig, 0.665, 0.18, t["s2_k3"][0], num(p["did"], 2, lang, True), t["s2_k3"][1], C["accent"])
    fig.text(0.074, 0.074, t["s2_period"], family=BODY, size=14, weight="semibold", color=C["ink2"], va="center")
    return fig

def slide3(t, lang):
    fig = canvas(t, 3)
    title(fig, t["s3_title"])
    legend_row(fig, [(t["pts"], C["treat"]), (t["xpl"], C["xp"])], 0.775)
    ax = fig.add_axes([0.11, 0.44, 0.80, 0.31]); style_ax(ax)
    event_lines(ax, [(t["pts"], C["treat"], Tt_all, "pts_xgs"), (t["xpl"], C["xp"], Tt_all, "xp_xg")], lang, t)
    ax.set_ylim(0.2, 1.75)
    caption(fig, t["s3_cap"], 0.375)
    x = S5["xp_xg"]
    for i, (lab, a, b) in enumerate([(t["s3_pre"], x["pts_pre_same"], x["pre"]), (t["s3_post"], x["pts_post_same"], x["post"])]):
        x0 = 0.074 + i * 0.456
        fig.text(x0, 0.275, lab, family=BODY, weight="semibold", size=15, color=C["ink2"])
        fig.text(x0, 0.215, num(a, 2, lang), family=DISPLAY, weight="semibold", size=56, color=C["treat"], va="center")
        fig.text(x0 + 0.135, 0.215, "vs", family=BODY, size=16, color=C["muted"], va="center")
        fig.text(x0 + 0.18, 0.215, num(b, 2, lang), family=DISPLAY, weight="semibold", size=56, color=C["xp"], va="center")
    fig.text(0.074, 0.12, t["s3_note"], family=BODY, size=15.5, color=C["ink2"], va="center", linespacing=1.35)
    return fig

def slide_sack(t, lang):
    fig = canvas(t, 4)
    title(fig, t["sa_title"])
    order = ["pts5", "xp_xg5", "xp_odds5", "lost"]
    ax = fig.add_axes([0.37, 0.40, 0.50, 0.29]); ax.set_facecolor(C["bg"])
    ax.set_xscale("log"); ax.set_xlim(0.3, 14); ax.set_ylim(len(order) - 0.4, -0.6)
    for v in [0.5, 1, 2, 5, 10]:
        ax.axvline(v, color=C["ink2"] if v == 1 else C["grid"], lw=1.5 if v == 1 else 1, zorder=0)
    for i, k in enumerate(order):
        r = eff[k]; sig = r["p"] < 0.05; col = C["treat"] if sig else C["muted"]
        ax.plot([max(0.3, r["lo"]), min(14, r["hi"])], [i, i], color=col, lw=3, solid_capstyle="round")
        ax.scatter([r["or_"]], [i], s=130, color=col, edgecolor=C["bg"], linewidth=2.5, zorder=5)
        lab = "×" + num(r["or_"], 2, lang) + ("" if sig else f"  ({t['sa_ns']})")
        ax.text(min(14, r["hi"]) * 1.12, i, lab, va="center", family=BODY, weight="bold" if sig else "normal",
                size=16 if sig else 14, color=C["ink"] if sig else C["muted"])
    ax.tick_params(length=0, labelsize=13, colors=C["muted"])
    ax.set_yticks(range(len(order)), [t["sa_labels"][k] for k in order])
    for lab in ax.get_yticklabels():
        lab.set_family(BODY); lab.set_size(15); lab.set_color(C["ink"]); lab.set_linespacing(1.2)
    ax.set_xticks([0.5, 1, 2, 5, 10], ["×" + num(v, 1 if v < 1 else 0, lang) for v in [0.5, 1, 2, 5, 10]])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    for lab in ax.get_xticklabels():
        lab.set_family(BODY)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.text(1.06, -0.55, t["sa_one"], family=BODY, size=12.5, color=C["ink2"], va="bottom")
    caption(fig, t["sa_cap"], 0.345)
    stat_rows(fig, t["sa_stats"], 0.25, C["treat"])
    return fig

def slide_groups(t, lang):
    fig = canvas(t, 5)
    title(fig, t["sb_title"])
    fig.text(0.074, 0.775, t["sb_sub"], family=BODY, size=17, color=C["ink2"], va="top", linespacing=1.35)
    legend_row(fig, [(t["sb_naive"], C["treat"]), (t["sb_did"], C["accent"])], 0.675)
    ax = fig.add_axes([0.11, 0.30, 0.80, 0.35]); style_ax(ax)
    G = XB["groups"]; x = np.arange(len(G)); w = 0.3
    for j, (key, ck, col) in enumerate([("naive", "naive_ci", C["treat"]), ("did", "did_ci", C["accent"])]):
        vals = [g[key] for g in G]; xs = x + (j - 0.5) * (w + 0.04)
        ax.bar(xs, vals, width=w, color=col, zorder=3)
        for xi, g in zip(xs, G):
            lo, hi = g[ck]
            ax.plot([xi, xi], [lo, hi], color=C["ink2"], lw=1.6, zorder=4)
            v = g[key]
            ax.text(xi, (hi + 0.04) if v >= 0 else (lo - 0.05), num(v, 2, lang, True), ha="center",
                    va="bottom" if v >= 0 else "top", family=BODY, weight="bold", size=15, color=C["ink"])
    ax.axhline(0, color=C["axis"], lw=1.5, zorder=2)
    ax.set_xticks(x, t["sb_groups"])
    for lab in ax.get_xticklabels():
        lab.set_family(BODY); lab.set_size(15); lab.set_color(C["ink"]); lab.set_weight("semibold")
    lo = min(min(g["did_ci"][0], g["naive_ci"][0]) for g in G); hi = max(g["naive_ci"][1] for g in G)
    ax.set_ylim(lo - 0.22, hi + 0.2)
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.2))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: num(v, 1, lang, abs(v) > 1e-9) if abs(v) > 1e-9 else num(0, 1, lang)))
    for lab in ax.get_yticklabels():
        lab.set_family(BODY)
    ax.set_ylabel(t["sb_unit"], family=BODY, size=13, color=C["muted"])
    caption(fig, t["sb_cap"], 0.205)
    return fig

def slide4(t, lang):
    fig = canvas(t, 6)
    title(fig, t["s4_title"])
    ax = fig.add_axes([0.30, 0.50, 0.56, 0.27]); ax.set_facecolor(C["bg"])
    d = lc.sort_values("per_team_season")
    cols = [C["hl"] if l == "TR1" else C["other"] for l in d.league]
    ax.barh(range(len(d)), d.per_team_season, color=cols, height=0.62)
    for i, (v, l) in enumerate(zip(d.per_team_season, d.league)):
        ax.text(v + 0.02, i, num(v, 2, lang), va="center", family=BODY, weight="bold" if l == "TR1" else "semibold",
                size=17 if l == "TR1" else 15, color=C["ink"] if l == "TR1" else C["ink2"])
    ax.set_yticks(range(len(d)), [t["lg_names"][l] for l in d.league])
    for lab, l in zip(ax.get_yticklabels(), d.league):
        lab.set_family(BODY); lab.set_size(17 if l == "TR1" else 15)
        lab.set_weight("bold" if l == "TR1" else "normal"); lab.set_color(C["ink"] if l == "TR1" else C["ink2"])
    ax.tick_params(length=0); ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.axvline(0, color=C["axis"], lw=1)
    ax.set_xlim(0, d.per_team_season.max() * 1.2)
    caption(fig, t["s4_cap"], 0.465)
    stat_rows(fig, t["s4_stats"], 0.35, C["hl"])
    return fig

def slide_carousel(t, lang):
    fig = canvas(t, 7)
    title(fig, t["sc_title"])
    top = XC["top"][:8][::-1]
    ax = fig.add_axes([0.36, 0.46, 0.50, 0.30]); ax.set_facecolor(C["bg"])
    ax.barh(range(len(top)), [r["stints"] for r in top], color=C["treat"], height=0.62)
    for i, r in enumerate(top):
        ax.text(r["stints"] + 0.12, i, t["sc_bar"](r["stints"], r["clubs"]), va="center", family=BODY, size=14, color=C["ink2"])
    ax.set_yticks(range(len(top)), [r["inn"] for r in top])
    for lab in ax.get_yticklabels():
        lab.set_family(BODY); lab.set_size(15); lab.set_color(C["ink"]); lab.set_weight("semibold")
    ax.tick_params(length=0); ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.axvline(0, color=C["axis"], lw=1)
    ax.set_xlim(0, max(r["stints"] for r in top) * 1.55)
    caption(fig, t["sc_cap"], 0.425)
    stat_rows(fig, t["sc_stats"], 0.31, C["treat"])
    return fig

def slide5(t, lang):
    fig = canvas(t, 8)
    fig.text(0.074, 0.905, t["s5_title"], family=DISPLAY, weight="bold", size=56, color=C["ink"], va="top")
    y = 0.79
    for i, (head, body) in enumerate(t["s5_points"]):
        fig.text(0.074, y, str(i + 1), family=DISPLAY, weight="bold", size=46, color=C["accent"], va="top")
        fig.text(0.14, y - 0.004, head, family=DISPLAY, weight="semibold", size=32, color=C["ink"], va="top")
        fig.text(0.14, y - 0.048, textwrap.fill(body, 64), family=BODY, size=16.5, color=C["ink2"], va="top", linespacing=1.38)
        y -= 0.135
    fig.add_artist(plt.Line2D([0.074, 0.926], [0.235, 0.235], color=C["axis"], lw=0.8))
    fig.text(0.074, 0.215, t["s5_method"], family=BODY, size=13, color=C["muted"], va="top", linespacing=1.45)
    fig.text(0.074, 0.105, t["s5_cta"], family=BODY, weight="bold", size=19, color=C["accent"], va="center")
    return fig

for lang, t in T.items():
    out = ROOT / "linkedin" / lang
    out.mkdir(parents=True, exist_ok=True)
    figs = [f(t, lang) for f in (slide1, slide2, slide3, slide_sack, slide_groups, slide4, slide_carousel, slide5)]
    with PdfPages(out / f"carousel_{lang}.pdf") as pdf:
        for i, fig in enumerate(figs, 1):
            fig.savefig(out / f"slide_{i}.png", dpi=DPI, facecolor=C["bg"])
            pdf.savefig(fig, facecolor=C["bg"])
            plt.close(fig)
    print("yazıldı:", out)
