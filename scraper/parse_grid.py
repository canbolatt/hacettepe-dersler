"""
Bazı bölümler (örn. Maden Mühendisliği) ders programını satır-tablo yerine
haftalık GÜN x SAAT matrisi ("pano") şeklinde yayınlıyor. Bu dosyalarda:
  - Sütunlar: [Gün, Sınıf/Yarıyıl, Saat1, Saat2, ..., SaatN]
  - Gün adı hücresi 5 satıra yayılan BİRLEŞİK bir hücre ve içindeki yazı
    90° döndürülmüş (örn. "PAZARTESİ / MONDAY" harfleri alttan üste doğru
    tek tek diziliyor). pdfplumber'ın standart tablo çıkarımı bu hücreyi
    harf harf, ters sırada ve satırlara bölünmüş olarak veriyor.
  - Bir "sınıf/yarıyıl" bloğu (örn. 7. yarıyıl) bazen 2 ham satıra
    yayılıyor (içerik uzun olduğu için) - bu durumda yarıyıl numarası
    sadece bloğun bir satırında görünüyor, diğer satır boş.

GÜVENLİK İLKESİ: Bu format çok değişken olduğu için ders kodu/ders adı/
öğretim üyesi gibi alt alanlara BÖLMEYE ÇALIŞMIYORUZ (yanlış bölme = yanlış
veri riski). Bunun yerine her hücrenin TAM METNİNİ ("raw_text") olduğu gibi
saklıyoruz; sadece arama için işe yarasın diye başta duran ders kodunu
(örn. "MAD 345") emin olduğumuz durumda ayrıca çıkarıyoruz. Gün, yarıyıl ve
saat bilgisi tablodaki KONUMDAN geldiği için bunlar güvenilir.
"""
from __future__ import annotations

import re
from typing import Optional

import pdfplumber

TIME_RANGE_RE = re.compile(r"^\d{1,2}:\d{2}\s*-\s*\d{1,2}[:.]\d{2}$")
CODE_PREFIX_RE = re.compile(
    r"^([A-ZÇĞİİÖŞÜ]{2,5}\s?\d{3}(?:\s*-\s*[^\s].{0,15}?)?)(?=\s|\n|$)"
)

# Türkçe gün adları - döndürülmüş metni "PAZARTESİ", "SALI" vb. ile
# eşleştirebilmek için (harf çantası / bag-of-letters karşılaştırmasıyla,
# çünkü döndürülmüş metinde ekstra boşluk/karakter kayması olabiliyor).
DAY_NAMES = ["PAZARTESİ", "SALI", "ÇARŞAMBA", "PERŞEMBE", "CUMA", "CUMARTESİ", "PAZAR"]


def _decode_rotated_day(page, x0: float, x1: float, top: float, bottom: float) -> str:
    """Belirtilen dikdörtgen içindeki karakterleri dikey konuma (top) göre
    sıralayıp TERS ÇEVİRİR - bu PDF'lerde döndürülmüş gün adı metni bu
    şekilde doğru okunuyor (elle doğrulandı: "YADNOM / İSETRAZAP" ters
    çevrilince "PAZARTESİ / MONDAY" oluyor)."""
    chars = [
        c for c in page.chars
        if x0 <= c["x0"] < x1 and top <= c["top"] < bottom and c["text"].strip()
    ]
    chars.sort(key=lambda c: c["top"])
    raw = "".join(c["text"] for c in chars)
    return raw[::-1].strip()


def _is_header_row(row: list) -> bool:
    return bool(row) and len(row) > 1 and row[1] and ".ms" in str(row[1]).strip().lower()


def extract_grid_courses(pdf_path: str) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    warnings: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            found = page.find_tables()
            for table in found:
                grid = table.extract()
                if not grid or len(grid) < 3:
                    continue
                header = grid[0]
                # Bu tabloyu "gün x saat" panosu olarak tanı: 2. sütun
                # başlığı ".mS" (sınıf/yarıyıl) ve kalan sütunlar saat
                # aralığı ("08:40-9:30" gibi) olmalı.
                time_cols = {}
                for ci, cell in enumerate(header[2:], start=2):
                    if cell and TIME_RANGE_RE.match(cell.strip()):
                        time_cols[ci] = cell.strip()
                if len(time_cols) < 3:
                    continue  # bu bir gün/saat panosu değil, atla

                col0_x0, col0_x1 = table.rows[0].cells[0][0], table.rows[0].cells[0][2]

                body_rows = [
                    (ri, row, table.rows[ri])
                    for ri, row in enumerate(grid)
                    if not _is_header_row(row)
                ]
                if not body_rows or len(body_rows) % 5 != 0:
                    warnings.append(
                        f"Gün panosu tablosu bulundu ama satır sayısı "
                        f"(5'in katı olması beklenirdi: {len(body_rows)}) "
                        f"beklenmedik - bu tablo atlandı, elle kontrol edilmeli."
                    )
                    continue

                block_size = 5
                for b in range(0, len(body_rows), block_size):
                    block = body_rows[b:b + block_size]
                    top = block[0][2].bbox[1]
                    bottom = block[-1][2].bbox[3]
                    day_name = _decode_rotated_day(page, col0_x0, col0_x1, top, bottom)
                    day_match = next((d for d in DAY_NAMES if d in day_name.upper()), None)
                    if not day_match:
                        warnings.append(
                            f"Gün adı çözülemedi (ham: {day_name!r}); bu blok "
                            f"'{day_name or 'BİLİNMİYOR'}' etiketiyle kaydedildi."
                        )
                        day_match = day_name or "BİLİNMİYOR"

                    # Yarıyıl/sınıf numarası boş olan satırlar, içeriği 2
                    # ham satıra taşan bir üst yarıyılın DEVAMI olabilir -
                    # ama üstteki mi ALTTAKİ mi olduğu içerikten kesin
                    # anlaşılamıyor (PDF'in görsel satır yüksekliği farkı
                    # yüzünden). Emin olamadığımız durumda TAHMİN ETMEK
                    # yerine bu satırı iki olası yarıyıla da "belirsiz"
                    # olarak işaretliyoruz.
                    sem_values = [(row[1] or "").strip() for _ri, row, _r in block]
                    sem_assignment: list[str] = []
                    for i, val in enumerate(sem_values):
                        if val:
                            sem_assignment.append(val)
                            continue
                        prev_val = next(
                            (v for v in reversed(sem_values[:i]) if v), None
                        )
                        next_val = next(
                            (v for v in sem_values[i + 1:] if v), None
                        )
                        if prev_val and next_val and prev_val != next_val:
                            sem_assignment.append(f"{prev_val} veya {next_val} (belirsiz)")
                            warnings.append(
                                f"{day_match} bloğunda bir satırın yarıyılı kesin "
                                f"belirlenemedi (yy.{prev_val} ile yy.{next_val} "
                                f"arasında) - ilgili ders(ler) 'belirsiz' olarak işaretlendi."
                            )
                        else:
                            sem_assignment.append(prev_val or next_val or "?")

                    sem_rows: dict[str, list[int]] = {}
                    for (ri, _row, _rowobj), sem in zip(block, sem_assignment):
                        sem_rows.setdefault(sem, []).append(ri)

                    for sem, row_indices in sem_rows.items():
                        for col_idx, time_label in time_cols.items():
                            texts = []
                            for ri in row_indices:
                                row = grid[ri]
                                val = row[col_idx] if col_idx < len(row) else None
                                if val and val.strip():
                                    texts.append(val.strip())
                            if not texts:
                                continue
                            combined = " | ".join(dict.fromkeys(texts))  # tekrarları at
                            code_match = CODE_PREFIX_RE.match(combined)
                            code = code_match.group(1).strip() if code_match else None
                            if " | " in combined:
                                warnings.append(
                                    f"{day_match} / yy.{sem} / {time_label}: aynı hücrede "
                                    f"birden fazla ders olabilir, elle ayrılmalı: "
                                    f"{combined[:120]!r}"
                                )
                            records.append({
                                "day": day_match,
                                "class_year": sem,
                                "time": time_label,
                                "code": code,
                                "name": combined,  # tam metin - hiçbir şey kaybolmasın
                                "room": None,
                                "instructor": None,
                                "capacity": None,
                            })
    return records, warnings
