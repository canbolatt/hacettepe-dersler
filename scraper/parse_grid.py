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

Bir hücrenin ham metni genelde şu satırlardan oluşur:
  1. satır : "KOD [- ŞUBE] [(P)/(T) işareti] Ders Adı" (bazen ders adı 2.
             satıra taşar)
  2..N. satır : "ÖĞRETİM ÜYESİ (Derslik)" - öğretim üyesi satırları HEMEN
             HER ZAMAN (neredeyse) tamamen BÜYÜK HARFLİDİR, ders adı
             satırları ise Türkçe başlık düzeninde (ilk harf büyük, gerisi
             küçük) yazılır - bu ayrımı programatik olarak tespit ediyoruz.
  Derslik bilgisi satır sonundaki "(...)" içinde gelir.

Bu kalıp elimizdeki gerçek PDF'ler üzerinde doğrulandı. Yine de %100 garanti
olmadığı için: bölme başarısız/belirsiz olursa alan boş bırakılır, ASLA
tahmin edilerek doldurulmaz; hücrenin tam ham metni de "raw_text" alanında
her zaman saklanır ki hiçbir bilgi kaybolmasın.
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


def _looks_like_instructor_line(line: str) -> bool:
    """Öğretim üyesi satırları bu PDF'lerde neredeyse tamamen BÜYÜK
    HARFLİ; ders adı satırları ise Türkçe başlık biçiminde (ilk harf
    büyük, gerisi küçük) yazılır. Harflerin çoğu büyükse (>%85) bu satırı
    öğretim üyesi olarak kabul ediyoruz."""
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > 0.85


def split_cell_text(raw_text: str) -> dict:
    """Bir gün/saat panosu hücresinin ham metnini kod/ad/öğretim üyesi/
    derslik alanlarına ayırır. Emin olunamayan alan boş (None) bırakılır -
    hiçbir zaman tahmin edilerek doldurulmaz."""
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if not lines:
        return {"code": None, "name": None, "instructor": None, "room": None}

    room = None
    # Son satır TAMAMEN parantez içindeyse ("(Uzaktan Eğitim)" gibi) o
    # doğrudan derslik/lokasyon bilgisidir.
    if re.fullmatch(r"\(.*\)", lines[-1]):
        room = lines[-1][1:-1].strip()
        lines = lines[:-1]
    elif lines:
        # Aksi halde son satırın SONUNDAKİ "(...)" parçası derslik olabilir
        # (örn. "ORKUN ERSOY (Y1-02)").
        m = re.search(r"\(([^()]*)\)\s*$", lines[-1])
        if m:
            room = m.group(1).strip()
            lines[-1] = lines[-1][: m.start()].strip()
            if not lines[-1]:
                lines.pop()

    # Sondan başlayarak, "öğretim üyesi gibi görünen" satırları topla.
    # NOT: bazı ders adları da PDF'te tamamen BÜYÜK HARFLE yazılmış oluyor
    # (örn. "DİL BECERİLERİ I") - bu yüzden bir satır ders KODUYLA
    # başlıyorsa, büyük harfli olsa bile asla öğretim üyesi sayılmaz (kod
    # her zaman hücrenin ilk/ana satırındadır, öğretim üyesi satırında kod
    # olmaz).
    instructor_lines: list[str] = []
    while (
        lines
        and not CODE_PREFIX_RE.match(lines[-1])
        and _looks_like_instructor_line(lines[-1])
    ):
        instructor_lines.insert(0, lines.pop())
    instructor = " ".join(instructor_lines).strip() or None

    if not lines:
        # Bu hücrede kod/ad kalmadı (örn. bir önceki satırın devamı olan
        # yalnızca öğretim üyesi + derslik içeren bir parça).
        return {"code": None, "name": None, "instructor": instructor, "room": room}

    code_match = CODE_PREFIX_RE.match(lines[0])
    if code_match:
        code = code_match.group(1).strip()
        first_line_rest = lines[0][code_match.end():].strip()
    else:
        code = None
        first_line_rest = lines[0]

    name_parts = ([first_line_rest] if first_line_rest else []) + lines[1:]
    name = " ".join(p for p in name_parts if p).strip() or None

    return {"code": code, "name": name, "instructor": instructor, "room": room}


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
                            # dict.fromkeys: ayni hucrede pdfplumber'in iki
                            # kez verdigi birebir ayni metni tekille
                            texts = list(dict.fromkeys(
                                val.strip()
                                for ri in row_indices
                                for val in [grid[ri][col_idx] if col_idx < len(grid[ri]) else None]
                                if val and val.strip()
                            ))
                            if not texts:
                                continue
                            if len(texts) > 1:
                                warnings.append(
                                    f"{day_match} / yy.{sem} / {time_label}: aynı hücrede "
                                    f"{len(texts)} farklı ders bulundu, ayrı ayrı kaydedildi "
                                    f"(muhtemelen bu saatte birden fazla şube/seçmeli ders "
                                    f"aynı anda sunuluyor): "
                                    f"{' | '.join(texts)[:160]!r}"
                                )
                            for raw_text in texts:
                                parsed = split_cell_text(raw_text)
                                records.append({
                                    "day": day_match,
                                    "class_year": sem,
                                    "time": time_label,
                                    "code": parsed["code"],
                                    "name": parsed["name"],
                                    "instructor": parsed["instructor"],
                                    "room": parsed["room"],
                                    "capacity": None,
                                    "raw_text": raw_text,
                                })
    return records, warnings
