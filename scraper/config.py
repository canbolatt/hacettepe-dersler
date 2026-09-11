"""
Bölüm kayıt defteri (registry).

Her bölüm için buraya bir kayıt eklenir. Yeni bir bölüm eklemek istediğinde
yapman gereken TEK şey: bu listeye yeni bir dict eklemek (ya da Claude'a
"şu bölümü de ekle" demek, o ekler).

Alanlar:
  id            : dosya adlarında ve URL'lerde kullanılan kısa kod
  name          : ekranda görünecek isim
  faculty       : fakülte adı
  homepage      : bölümün ana sayfası (duyuruların bulunduğu yer)
  duyuru_pages  : duyuru/ders programı arşiv sayfası varsa (opsiyonel, ekstra tarama için)
  expected_term : bu dönem aranan program (örn. "2026-2027" + "Güz") - discover.py
                  bu ifadeleri duyuru başlıklarında arayarak doğru PDF'i seçmeye çalışır
  known_pdf     : ÖNCEDEN İNSAN TARAFINDAN DOĞRULANMIŞ pdf linki (opsiyonel).
                  Doldurulursa discover.py önce bunu dener; boşsa otomatik arar.
                  known_pdf'in "verified_on" tarihi mutlaka olmalı - bu, linkin
                  ne zaman elle kontrol edildiğini gösterir, ders programının
                  güncellik tarihi DEĞİLDİR (o bilgi PDF'in kendisinden / duyuru
                  metninden okunur).
  parser        : hangi tablo ayrıştırma stratejisinin kullanılacağı
                  ("generic" ya da bölüme özel bir fonksiyon adı)
"""

DEPARTMENTS = [
    {
        "id": "psikoloji",
        "name": "Psikoloji",
        "faculty": "Edebiyat Fakültesi",
        "homepage": "https://psikoloji.hacettepe.edu.tr/",
        "duyuru_pages": ["https://psikoloji.hacettepe.edu.tr/"],
        "expected_term": {"years": "2026-27", "yariyil": ["Güz", "GÜZ"]},
        "known_pdf": {
            "url": "https://fs.hacettepe.edu.tr/psikoloji/dosyalar/Ders%20programlar%C4%B1/2026-27%20L%C4%B0SANS%20PANO.pdf",
            "verified_on": "2026-09-11",
            "note": "Bölüm sayfasındaki duyurudan alındı; duyuru metninde "
                    "'Güncelleme 9.09.2026 11:20' yazıyordu.",
        },
        "parser": "generic",
    },
    {
        "id": "maden-muhendisligi",
        "name": "Maden Mühendisliği",
        "faculty": "Mühendislik Fakültesi",
        "homepage": "https://maden.hacettepe.edu.tr/",
        "duyuru_pages": ["https://maden.hacettepe.edu.tr/tr/lisans_ders_programi-16"],
        "expected_term": {"years": "2627", "yariyil": ["G", "Güz", "GÜZ"]},
        "known_pdf": {
            "url": "https://fs.hacettepe.edu.tr/maden/dosyalar/dersprogrami/2627G-Program.pdf",
            "verified_on": "2026-09-11",
            "note": "Bölüm sayfasında 'Güncelleme Tarihi: 11.09.2026' ile "
                    "yayınlanmış 2026-2027 Güz programı.",
        },
        # Bu bölüm ders programını satır-tablo değil, GÜN x SAAT matrisi
        # ("pano") şeklinde yayınlıyor - bkz. scraper/parse_grid.py
        "parser": "grid",
    },
    {
        "id": "matematik",
        "name": "Matematik",
        "faculty": "Fen Fakültesi",
        "homepage": "https://mat.hacettepe.edu.tr/",
        "duyuru_pages": ["https://mat.hacettepe.edu.tr/duyurular.html"],
        "expected_term": {"years": "2026-2027", "yariyil": ["G.D.", "Güz"]},
        # DİKKAT: 11.09.2026 itibarıyla 2026-2027 Güz lisans ders programı
        # HENÜZ YAYINLANMAMIŞ. Aşağıdaki link bir önceki döneme (2025-2026)
        # ait - bu yüzden known_pdf olarak DEĞİL, "last_known_stale_pdf"
        # olarak işaretliyoruz ki build.py bunu asla "güncel" diye sunmasın.
        "known_pdf": None,
        "last_known_stale_pdf": {
            "url": "https://mat.hacettepe.edu.tr/duyurular/2025-2026-G.D.-Ders-Programi.pdf",
            "term": "2025-2026 Güz",
            "verified_on": "2026-09-11",
            "note": "2026-2027 Güz programı yayınlanana kadar sadece referans amaçlı.",
        },
        "parser": "generic",
    },
]

# Genel HTTP ayarları
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "HacettepeDersProgramiTarayici/1.0 (+iletisim icin repo README'sine bakiniz)"
)
REQUEST_TIMEOUT = 30
