"""
PDF içindeki ders tablolarını yapılandırılmış satırlara çevirir.

ÖNEMLİ İLKE: Bir hücrede ne yazıyorsa o alınır. Boş/okunaksız hücreler boş
bırakılır, ASLA tahmin edilerek doldurulmaz. Bir PDF hiç tablo içermiyorsa
ya da tablo bu sezgilerle ayrıştırılamıyorsa, department kaydı
status="parse_error" ile işaretlenir ve kaynak PDF linki kullanıcıya
doğrudan gösterilir (yani veri kaybolmaz, sadece otomatik ayrıştırılamamış
olur - kullanıcı orijinal PDF'e linkten bakabilir).
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

import pdfplumber

# Hacettepe ders programı PDF'lerinde sık görülen sütun başlıkları.
# Bölümden bölüme sıralama/isimlendirme değişebildiği için burada geniş bir
# eşanlamlılar sözlüğü tutuyoruz; eşleşmeyen sütunlar "extra_N" olarak
# olduğu gibi saklanır (veri kaybı olmasın diye).
#
# ÖNEMLİ SIRALAMA: "code_and_name" (örn. "DERS KODU-ŞUBESİ VE ADI" - kod ve
# ders adının BİRLEŞİK tek sütun olduğu format) alaşı, düz "code" alaşından
# ("kod" gibi çok genel bir kelime içerdiği için) ÖNCE kontrol edilmeli;
# aksi halde "kod" kelimesi geçtiği için yanlışlıkla salt "code" sayılıp
# ders adı hiç ayrıştırılmadan kaybolur.
HEADER_ALIASES = {
    "code_and_name": ["kodu-şubesi ve adı", "kodu-subesi ve adi",
                       "kod-şube ve adı", "kodu ve adı"],
    "cross_dept": ["bölüm dışı", "bolum disi", "verildiği bölüm", "bölüm"],
    "code": ["ders kodu", "kod", "ders no", "dersin kodu"],
    "name": ["ders adı", "dersin adı", "ders ismi", "adı"],
    "class_year": ["sınıf", "sinif"],
    "day": ["gün", "gun"],
    "time": ["saat", "saati"],
    "room": ["derslik", "yer", "salon"],
    "instructor": ["öğretim üyesi", "ogretim uyesi", "öğretim elemanı", "hoca",
                   "ders sorumlusu", "sorumlu öğretim üyesi"],
    "capacity": ["kontenjan", "kapasite"],
    "group": ["şube", "sube", "grup"],
}

# "Kod ve Ad" birleşik hücresini ikiye ayırmak için: baştaki ders kodu
# kalıbı (örn. "PSL 111-01", "BYL150", "AİT203-11").
CODE_PREFIX_RE = re.compile(
    r"^([A-ZÇĞİİÖŞÜ]{2,5}\s?\d{3}(?:-\d{1,3})?)\s*(.*)$", re.DOTALL
)


_TR_FOLD = str.maketrans({
    "ı": "i", "İ": "i",
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ç": "c", "Ç": "c",
    "ö": "o", "Ö": "o",
    "ü": "u", "Ü": "u",
})


def _fold(text: str) -> str:
    """Türkçe harfleri ASCII'ye indirger (başlık eşleştirmeyi font/encoding
    farklılıklarına karşı sağlamlaştırmak için)."""
    return text.strip().lower().replace("i̇", "i").translate(_TR_FOLD)


# Alias sözlüğünü de fold'lanmış haliyle önceden hesapla.
_FOLDED_ALIASES = {
    canon: [_fold(a) for a in aliases] for canon, aliases in HEADER_ALIASES.items()
}


def _normalize_header(cell: Optional[str]) -> Optional[str]:
    if not cell:
        return None
    low = _fold(cell)
    for canon, aliases in _FOLDED_ALIASES.items():
        for alias in aliases:
            if alias in low:
                return canon
    return None


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_tables(pdf_path: str) -> list[list[list[str]]]:
    """PDF'teki her sayfadan ham tabloları (satır listeleri) çıkarır."""
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                cleaned = [
                    [(c or "").strip() for c in row]
                    for row in table
                    if any((c or "").strip() for c in row)
                ]
                if cleaned:
                    all_tables.append(cleaned)
    return all_tables


def tables_to_courses(tables: list[list[list[str]]]) -> tuple[list[dict], list[str]]:
    """
    Ham tabloları ders kayıtlarına çevirir.
    Dönüş: (courses, warnings)
    """
    courses: list[dict] = []
    warnings: list[str] = []
    current_class_year = None
    last_col_map: Optional[dict] = None  # önceki tablonun sütun eşlemesi
    seen_keys: set[tuple] = set()  # aynı dersin iki kez eklenmesini önlemek için
    duplicate_count = 0

    for table in tables:
        header_row = table[0]
        col_map = {i: _normalize_header(c) for i, c in enumerate(header_row)}
        matched_cols = sum(1 for v in col_map.values() if v)

        rows_to_process = table[1:]  # varsayılan: ilk satır gerçek başlık

        if matched_cols < 2:
            # Başlık satırı tanınamadı. İki olasılık var:
            #  a) Bu "1. Sınıf" gibi bir bölüm başlığı - veri değil.
            #  b) Bu, önceki tablonun sayfa sonunda kesilip devam eden hali -
            #     PDF çoğu zaman başlığı her sayfada TEKRARLAMIYOR, bu yüzden
            #     pdfplumber bu tablonun ilk (gerçekte VERİ olan) satırını
            #     yanlışlıkla "başlık" sanıyor.
            # (b) durumunu, sütun sayısı bir önceki tanınan tabloyla AYNIYSA
            # kabul ediyoruz - bu durumda o satırı da veri olarak işliyoruz
            # (atlamıyoruz), çünkü aksi halde gerçek ders satırları sessizce
            # kaybolur.
            first_cell = " ".join(c for c in header_row if c).strip()
            m = re.search(r"(\d)\s*\.?\s*sınıf", first_cell, re.IGNORECASE)
            if m:
                current_class_year = m.group(1)
                continue
            elif last_col_map is not None and len(header_row) == len(
                [k for k in last_col_map]
            ):
                col_map = last_col_map
                rows_to_process = table  # başlık satırı yok, hepsi veri
                warnings.append(
                    f"Başlıksız devam tablosu bulundu, önceki tablonun sütun "
                    f"düzeni ile devam ediliyor (ilk satır: "
                    f"{first_cell[:80]!r})."
                )
            else:
                warnings.append(
                    f"Tanınmayan tablo başlığı, atlandı: {first_cell[:80]!r}"
                )
                continue
        else:
            last_col_map = col_map

        for row in rows_to_process:
            record = {"class_year": current_class_year}
            extras = {}
            for i, cell in enumerate(row):
                key = col_map.get(i)
                if key == "code_and_name":
                    # "PSL 111-01 GENEL PSİKOLOJİ" gibi birleşik hücreyi
                    # kod + ad olarak ikiye ayır. Satır kaydırmasından
                    # (\n) gelen boşlukları tek boşluğa indirger, ki ders
                    # adı düzgün tek satır olsun.
                    flat = " ".join((cell or "").split())
                    m = CODE_PREFIX_RE.match(flat)
                    if m:
                        record["code"] = m.group(1).strip()
                        record["name"] = m.group(2).strip() or None
                    else:
                        # Kod kalıbı tanınamadı - veri UYDURMA, olduğu
                        # gibi "name" alanına koy, kodu boş bırak.
                        record["name"] = flat or None
                elif key == "cross_dept":
                    if cell and cell.strip():
                        record["cross_dept"] = cell.strip()
                elif key:
                    record[key] = cell
                elif cell:
                    extras[f"extra_col_{i}"] = cell

            if record.get("cross_dept"):
                # Kullanıcı isteği: bu dersler başka bölümün öğrencilerine
                # açılan / bölüm dışına verilen derslerdir - Sınıf yerine
                # bunu açıkça belirt. Orijinal "hangi bölüme" bilgisi
                # kaybolmasın diye extra'da da saklanır.
                extras["hedef_bolum"] = record.pop("cross_dept")
                record["class_year"] = "Bölüm dışına verilen ders"

            if extras:
                record["extra"] = extras
            # En az ders kodu ya da ders adından biri yoksa muhtemelen
            # gerçek bir ders satırı değildir (örn. alt toplam/boşluk satırı).
            if record.get("code") or record.get("name"):
                # Aynı ders (kod+gün+saat+derslik+öğretim üyesi hepsi birebir
                # aynı) daha önce eklendiyse bu satır muhtemelen bir sayfa
                # geçişinde tabloların üst üste binmesinden kaynaklanan bir
                # TEKRARDIR, gerçek ikinci bir ders değildir - atla. (Aynı
                # dersin aynı anda aynı yerde iki kez okutulması gerçek
                # hayatta anlamsız olduğu için bu güvenli bir varsayım.)
                def _norm(v: Optional[str]) -> str:
                    # Karşılaştırma için: boşluk/satır kaydırmaları tekleştir,
                    # saat ayracı olarak kullanılan "." ve ":" birbirinin
                    # aynısı sayılsın (kaynak PDF ikisini de karışık kullanıyor).
                    v = " ".join((v or "").split())
                    return re.sub(r"(?<=\d)\.(?=\d)", ":", v).strip().lower()

                dedup_key = (
                    _norm(record.get("code")),
                    _norm(record.get("day")),
                    _norm(record.get("time")),
                    _norm(record.get("room")),
                    _norm(record.get("instructor")),
                )
                if dedup_key in seen_keys:
                    duplicate_count += 1
                    continue
                seen_keys.add(dedup_key)
                courses.append(record)

    if duplicate_count:
        warnings.append(
            f"{duplicate_count} tekrarlanan ders satırı (muhtemelen sayfa "
            f"geçişi kaynaklı) elendi, sayıma dahil edilmedi."
        )

    return courses, warnings
