# Hacettepe Açılan Dersler

Hacettepe Üniversitesi'nde bölümlerin ayrı ayrı PDF olarak yayınladığı
ders programlarını tek bir aranabilir web sitesinde toplayan sistem.

**Şu anki durum:** Pilot olarak 3 bölüm var — Psikoloji, Maden Mühendisliği,
Matematik. İşe yararsa yeni bölümler kolayca eklenir (bkz. aşağıda).

Bu proje tamamen otomatik çalışacak şekilde tasarlandı: bir bölüm PDF'ini
her güncellediğinde, sistem bunu kendi kendine fark edip web sitesini
günceller. **Hiçbir aşamada veri uydurulmaz** — bir PDF bulunamaz ya da
otomatik okunamazsa, o bölüm için "veri yok" gösterilir ve kaynağa doğrudan
link verilir; asla tahmini/yanlış bir ders bilgisi gösterilmez.

---

## Bunu nasıl canlıya alırsın (kod bilmene gerek yok)

Bu adımların tamamı tarayıcıdan, tıkla-kopyala-yapıştır seviyesinde.
Toplam 10 dakikanı alır.

### 1. Ücretsiz bir GitHub hesabı aç
[github.com/signup](https://github.com/signup) adresine git, e-postanla
ücretsiz bir hesap oluştur.

### 2. Yeni bir "repository" (depo) oluştur
- Sağ üstteki **+** işaretine tıkla → **New repository**
- İsim ver: örneğin `hacettepe-dersler`
- **Public** seçili kalsın (GitHub Pages'in ücretsiz sürümü bunu ister)
- **Create repository**'ye tıkla

### 3. Bu klasördeki dosyaları yükle
- Oluşturduğun boş depo sayfasında **"uploading an existing file"** linkine tıkla
- Bu projedeki **tüm dosya ve klasörleri** (bu README dahil) sürükleyip bırak
  - Not: `.github` klasörü gizli görünebilir; dosya gezgininde gizli
    dosyaları göster seçeneğini aç, ya da GitHub'ın web arayüzünde klasör
    sürükleyip bırakma bunu otomatik algılar.
- Alt kısımda "Commit changes" yazan yeşil butona tıkla

### 4. GitHub Pages'i aç
- Depoda **Settings** sekmesine git
- Sol menüden **Pages**'i seç
- "Build and deployment" → **Source** kısmında **GitHub Actions**'ı seç

### 5. Otomasyonu ilk kez çalıştır
- Depoda **Actions** sekmesine git
- Soldan **"Ders programlarını güncelle"** iş akışını seç
- Sağ üstten **"Run workflow"** → **Run workflow** butonuna tıkla
- ~2-3 dakika sonra yeşil tik görünecek; bu, sistemin PDF'leri çekip
  siteyi güncellediği anlamına gelir

### 6. Siteni aç
Settings → Pages sayfasında üstte site adresin yazacak, örneğin:
`https://kullanici-adin.github.io/hacettepe-dersler/`

Bundan sonra sistem **her gün otomatik olarak** (varsayılan: TR saatiyle
09:00) bölüm sitelerini kontrol edip PDF değiştiyse veriyi güncelleyecek.
Senin hiçbir şey yapmana gerek yok.

---

## Bir bölüm eklemek/çıkarmak istersen

Tek yapman gereken bana (Claude'a) bölümün adını söylemek — ben
`scraper/config.py` dosyasına doğru bilgiyi (bölüm sayfası, PDF linki)
elle doğrulayıp ekler, sana güncellenmiş dosyayı veririm; sen de GitHub'da
o dosyayı değiştirip "Commit changes" dersin. Kod yazmana gerek yok.

## Neden bazı bölümler "veri yok" gösteriyor olabilir?

- **`not_published`**: Bölüm bu dönemin programını henüz yayınlamamış
  (örn. bu prototip kurulurken Matematik bölümü 2026-2027 Güz programını
  henüz yayınlamamıştı — otomasyon her gün tekrar kontrol edip yayınlanır
  yayınlanmaz yakalayacak).
- **`fetch_error`**: PDF linkine o an ulaşılamadı (sunucu geçici olarak
  yanıt vermiyor olabilir) — bir sonraki otomatik çalıştırmada tekrar
  denenir.
- **`parse_error`**: PDF indirildi ama tablo yapısı otomatik ayrıştırma
  mantığıyla eşleşmedi (bölümler PDF'lerini birbirinden çok farklı
  formatlarda hazırlıyor). Bu durumda kaynağa link verilir; bana haber
  verirsen o bölüme özel bir ayrıştırma mantığı yazarım.

## Teknik yapı (meraklısına)

```
scraper/config.py    Bölüm kayıt defteri — yeni bölüm buraya eklenir
scraper/discover.py  Bölüm sitesinden güncel PDF linkini bulur
scraper/parse_pdf.py PDF tablolarını yapılandırılmış veriye çevirir
scraper/build.py     Hepsini birleştirip data/courses.json üretir
site/                Statik, framework'süz website (HTML/CSS/JS)
.github/workflows/   Günlük otomatik çalıştırma + GitHub Pages yayını
```

Veri her zaman `source_pdf_url` (ve varsa `source_pdf_sha256`, indirilen
dosyanın parmak izi) ile birlikte saklanır — yani her ders satırının hangi
PDF'ten, ne zaman çekildiği her an geriye izlenebilir.
