"""
04_build_dashboard.py
---------------------
data/processed/results.json dosyasını dashboard şablonuna gömer -> dashboard.html
Tarayıcıda çift tıklayarak açılabilir (internet yalnızca yazı tipleri için gerekir).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / "scripts" / "dashboard_template.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "data" / "processed" / "results.json").read_text(encoding="utf-8"))
lc = ROOT / "data" / "processed" / "league_comparison.csv"
if lc.exists():   # 05_league_comparison.py çalıştırıldıysa Türkiye vs 5 büyük lig bölümünü ekle
    import csv
    rows = list(csv.DictReader(open(lc, encoding="utf-8")))
    for r in rows:
        for k, v in r.items():
            if k not in ("league", "lig"):
                r[k] = float(v) if "." in v else int(v)
    data["leagues"] = rows
ext = ROOT / "data" / "processed" / "extensions.json"
if ext.exists():   # 07_extensions.py çalıştırıldıysa kovma tetikleyicileri, şans grupları ve hoca karuseli
    data["ext"] = json.loads(ext.read_text(encoding="utf-8"))
data.pop("periods", None)   # dashboard tek dönem (2016/17–2026/27) olarak gösteriliyor
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
out = ROOT / "dashboard.html"
out.write_text(tpl.replace("/*DATA*/null", payload), encoding="utf-8")
print(f"yazıldı: {out}  ({out.stat().st_size / 1024:.0f} KB)")
