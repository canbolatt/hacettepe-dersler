# -*- coding: utf-8 -*-
"""
Bölüm sayfalarını tarayıp "ders programı" PDF linklerini otomatik bulmaya
çalışır. Bir bölüm config.py'de "known_pdf" ile geldiyse (insan tarafından
doğrulanmış), önce onu dener; yoksa/erişilemezse otomatik keşfe düşer.

Otomatik keşif kuralları:
- Sayfadaki tüm <a href> etiketlerini tara.
- Link metninde veya href'inde "ders program" / "ders programı" / "pano"
  gibi anahtar kelimeler ve config'teki expected_term parçaları aranır.
- .pdf ile bitmeyen linkler elenir.
- Birden fazla aday varsa, dönem etiketiyle en çok eşleşen ve (bulunabiliyorsa)
  en yeni tarihli olan seçilir.
- HİÇBİR ZAMAN tahminle link uydurulmaz: eşleşme yoksa "not_found" döner.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import USER_AGENT, REQUEST_TIMEOUT


@dataclass
class DiscoveryResult:
    status: str  # "known" | "found" | "not_found" | "error"
    url: Optional[str] = None
    matched_text: Optional[str] = None
    note: str = ""


KEYWORDS = ["ders program", "ders programı", "ders proğramı", "pano", "haftalık program"]


def _fetch(url: str) -> Optional[str]:
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException:
        return None


def _score_link(text: str, href: str, expected_term: dict) -> int:
    haystack = f"{text} {href}".lower()
    score = 0
    if any(k in haystack for k in KEYWORDS):
        score += 5
    years = expected_term.get("years", "")
    if years and years.lower().replace("-", "") in haystack.replace("-", ""):
        score += 3
    for y in expected_term.get("yariyil", []):
        if y.lower() in haystack:
            score += 2
    if haystack.strip().endswith(".pdf"):
        score += 1
    return score


def discover_pdf(department: dict) -> DiscoveryResult:
    known = department.get("known_pdf")
    if known:
        return DiscoveryResult(
            status="known",
            url=known["url"],
            note=f"config.py içinde insan tarafından doğrulanmış link "
                 f"(verified_on={known['verified_on']}).",
        )

    candidates = []
    pages = department.get("duyuru_pages") or [department["homepage"]]
    for page_url in pages:
        html = _fetch(page_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            if not href.lower().split("?")[0].endswith(".pdf"):
                continue
            score = _score_link(text, href, department["expected_term"])
            if score > 0:
                full_url = urljoin(page_url, href)
                candidates.append((score, full_url, text))

    if not candidates:
        return DiscoveryResult(
            status="not_found",
            note="Duyuru sayfalarında beklenen döneme ait bir ders programı "
                 "PDF'i bulunamadı. Elle kontrol edilmeli.",
        )

    candidates.sort(key=lambda c: c[0], reverse=True)
    best_score, best_url, best_text = candidates[0]
    return DiscoveryResult(
        status="found",
        url=best_url,
        matched_text=best_text,
        note=f"Otomatik keşifle bulundu (skor={best_score}). "
             f"İlk çalıştırmada mutlaka elle doğrulanmalı.",
    )
