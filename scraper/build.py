# -*- coding: utf-8 -*-
"""
Ana orkestratör: her bölüm için
  1) PDF linkini bul (known_pdf ya da otomatik keşif)
  2) PDF'i indir
  3) Tablo(lar)ı ayrıştır
  4) data/courses.json içine, KAYNAK LİNKİYLE BİRLİKTE yaz

Çalıştırma:  python -m scraper.build
Çıktı:       data/courses.json  (site/data/courses.json'a da kopyalanır)

Hiçbir aşamada veri uydurulmaz. Bir bölüm için PDF bulunamazsa/indirilemezse/
ayrıştırılamazsa, o bölüm ilgili "status" ile (not_found / fetch_error /
parse_error) boş courses listesiyle kaydedilir; kullanıcı arayüzünde bu
açıkça "veri yok, kaynağa bakınız" olarak gösterilir.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

import requests

from .config import DEPARTMENTS, USER_AGENT, REQUEST_TIMEOUT
from .discover import discover_pdf
from .parse_pdf import extract_tables, tables_to_courses, sha256_of_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SITE_DATA_DIR = os.path.join(ROOT, "site", "data")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _download(url: str, dest_path: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        if "pdf" not in resp.headers.get("Content-Type", "").lower() and not url.lower().endswith(".pdf"):
            return False, f"Beklenmeyen içerik türü: {resp.headers.get('Content-Type')}"
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        return True, ""
    except requests.RequestException as e:
        return False, str(e)


def process_department(dept: dict, tmp_dir: str) -> dict:
    record = {
        "id": dept["id"],
        "name": dept["name"],
        "faculty": dept["faculty"],
        "homepage": dept["homepage"],
        "last_checked": _now_iso(),
        "status": "unknown",
        "source_pdf_url": None,
        "source_pdf_sha256": None,
        "note": "",
        "courses": [],
        "warnings": [],
    }

    discovery = discover_pdf(dept)
    record["note"] = discovery.note

    if discovery.status == "not_found":
        stale = dept.get("last_known_stale_pdf")
        record["status"] = "not_published"
        if stale:
            record["note"] += (
                f" Bu dönem için henüz yayın yok. Son bilinen (ESKİ, {stale['term']}) "
                f"program referans olarak: {stale['url']}"
            )
            record["last_known_stale_pdf"] = stale
        return record

    if discovery.status == "error":
        record["status"] = "fetch_error"
        return record

    pdf_url = discovery.url
    record["source_pdf_url"] = pdf_url
    dest = os.path.join(tmp_dir, f"{dept['id']}.pdf")
    ok, err = _download(pdf_url, dest)
    if not ok:
        record["status"] = "fetch_error"
        record["note"] += f" | İndirme hatası: {err}"
        return record

    record["source_pdf_sha256"] = sha256_of_file(dest)

    try:
        tables = extract_tables(dest)
        courses, warnings = tables_to_courses(tables)
    except Exception as e:  # noqa: BLE001 - hepsini yakala, veri kaybetme
        record["status"] = "parse_error"
        record["note"] += f" | Ayrıştırma hatası: {e}"
        return record

    record["warnings"] = warnings
    record["courses"] = courses
    record["status"] = "ok" if courses else "parse_error"
    if not courses:
        record["note"] += " | PDF indirildi ama hiç ders satırı çıkarılamadı."
    return record


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SITE_DATA_DIR, exist_ok=True)

    departments_out = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for dept in DEPARTMENTS:
            print(f"[{dept['id']}] işleniyor...", file=sys.stderr)
            rec = process_department(dept, tmp_dir)
            print(f"[{dept['id']}] -> {rec['status']} "
                  f"({len(rec['courses'])} ders)", file=sys.stderr)
            departments_out.append(rec)

    output = {
        "generated_at": _now_iso(),
        "departments": departments_out,
    }

    out_path = os.path.join(DATA_DIR, "courses.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    shutil.copyfile(out_path, os.path.join(SITE_DATA_DIR, "courses.json"))
    print(f"Yazıldı: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
