# Hamilelik Hatırlatma Otomasyonu — Kurulum Kılavuzu

Bu sistem, eşinize WhatsApp üzerinden otomatik olarak:
- Saat 9:00 – 23:59 arası **her saat başı su içme** hatırlatması gönderir
- Her gün saat 21:00'da **tansiyon ölçüm** hatırlatması gönderir
- Cevap gelmezse **5 dakika sonra tekrar** hatırlatır
- "Ertele" / "X saat ertele" yazıldığında erteler
- Sizin bilgisayarınız/telefonunuz **kapalı olsa bile** çalışır (bulut tabanlı)

---

## Genel Mimari

```
[GitHub Actions]  -- her 5 dk -->  [reminder.py]  --> [Green-API]  --> [WhatsApp]
       ^                                  |                                 |
       |                                  v                                 v
       +-----[state.json (durum)]<---[mesajları oku]<---[eşinizin cevabı]---+
```

GitHub Actions her 5 dakikada bir Python script'i çalıştırır. Script:
1. Eşinizin WhatsApp'tan gelen yeni mesajlarını okur (Green-API üzerinden)
2. "İçtim", "Ertele", "120/80" gibi cevapları algılar, durumu günceller
3. Sıradaki hatırlatma için zaman geldiyse mesaj gönderir
4. Durum bilgisini `state.json`'a yazıp repo'ya commit eder

---

## ADIM 1 — Green-API Hesabı Aç ve WhatsApp Bağla

Green-API, sizin WhatsApp hesabınızı bir API'ye dönüştüren ücretsiz bir servis. Sizin numaranızdan eşinize mesaj gönderir.

> **Önemli:** Bu otomasyonu sizin kendi WhatsApp numaranızla bağlayacağız. Yani mesajlar sizden eşinize gidiyormuş gibi görünecek (zaten sizin adınıza). Mümkünse otomasyon için **ayrı bir telefon numarası** kullanmanız önerilir (örn. eski bir hat veya sanal numara) — çünkü Green-API'ye bağlı olduğunuz süre boyunca o numaranın WhatsApp Web'i sürekli aktif olur ve telefon uygulamasından kullanırken çakışma yaşayabilirsiniz. Ama tek numaranız da olur.

1. https://green-api.com adresine gidin → **"Free Trial"** veya **"Sign up"** tıklayın
2. E-posta ile kayıt olun (alpermoter@gmail.com kullanabilirsiniz)
3. Giriş yaptıktan sonra **"Console"** veya **"Instances"** sayfasına gidin
4. **"Create"** veya **"Add new instance"** butonuna basın
5. Ücretsiz tier'ı (Developer plan) seçin — günde 100 mesaj/hat yeterlidir (15 su + 1 tansiyon + tekrarlar ~30-50 mesaj/gün)
6. Yeni instance açıldığında size verilecek:
   - **idInstance** (örn: `1101234567`) — bunu not alın
   - **apiTokenInstance** (örn: `abc123def456...`) — bunu da not alın
7. **"Show QR"** veya **"QR Code"** sekmesine geçin
8. Otomasyona ayırdığınız telefondan WhatsApp'ı açın → **Ayarlar → Bağlı Cihazlar → Cihaz Bağla** → QR kodu okutun
9. "Authorized" / "Yetkili" yazısını gördüğünüzde bağlantı kuruldu

### Test edin (opsiyonel ama tavsiye edilir):

Green-API panelinde **"Send Message"** test sayfasına gidin, eşinizin numarasını şu formatta girin: `905551234567` (başında `+` veya boşluk olmadan, ülke kodu dahil). "Test mesajı" yazıp gönderin. Eşinize ulaşırsa Green-API doğru çalışıyor demektir.

---

## ADIM 2 — GitHub Reposu Oluştur

1. https://github.com adresine girin → **"+"** → **"New repository"**
2. Repo adı: `hamilelik-hatirlatma` (ya da istediğiniz isim)
3. **Private** seçin (state.json zaman damgaları içerir, gizli kalsın)
4. "Create repository" butonuna basın
5. Açılan sayfada **"uploading an existing file"** linkine tıklayın
6. Bu klasördeki **tüm dosyaları** (klasör yapısıyla birlikte) sürükleyip bırakın:
   - `reminder.py`
   - `requirements.txt`
   - `state.json`
   - `KURULUM.md`
   - `.gitignore`
   - `.github/workflows/reminder.yml` ← bu klasör yapısını **mutlaka** koruyun

   > Sürükle-bırak alt klasörleri korumayabilir. Eğer `.github/workflows/` klasör yapısı bozulursa: önce GitHub'da repo içinde **Add file → Create new file** ile `.github/workflows/reminder.yml` yolunu yazıp (eğik çizgi koyunca klasör otomatik oluşur) içeriğini kopyala-yapıştır yapın.

7. "Commit changes" deyin.

---

## ADIM 3 — GitHub Secrets Ekle

Şifreleri kodun içine yazmayacağız — GitHub'ın güvenli **Secrets** alanına ekleyeceğiz.

1. Repo'nun ana sayfasında **Settings** sekmesine girin
2. Sol menüden **Secrets and variables → Actions**
3. **"New repository secret"** butonuna 3 kez ayrı ayrı basıp şu üçünü ekleyin:

| İsim | Değer |
|---|---|
| `GREEN_API_INSTANCE` | Green-API'den aldığınız idInstance (örn: `1101234567`) |
| `GREEN_API_TOKEN` | Green-API'den aldığınız apiTokenInstance |
| `TARGET_PHONE` | Eşinizin numarası — başında **+ veya boşluk olmadan**, ülke kodu dahil (örn: `905551234567`) |

---

## ADIM 4 — İlk Çalıştırma (Elle Test)

1. Repo'da **Actions** sekmesine gidin
2. Sol menüde **"Hamilelik Hatirlatma"** workflow'unu seçin
3. Sağ üstte **"Run workflow"** → **"Run workflow"** butonuna basın
4. Birkaç saniye sonra çalışmaya başlar. Logları açıp adım adım takip edebilirsiniz.

İlk çalıştırma saatine göre:
- **Saat 9:00 – 23:59 arasında** çalıştırırsanız: O saatin su hatırlatması eşinize gider 🎉
- **Saat 21:00 sonrasında** çalıştırırsanız: Tansiyon hatırlatması da gider
- **Diğer saatlerde**: Hiç mesaj gitmez (script "saat dışı" der ve çıkar) — bu **doğru davranıştır**

---

## ADIM 5 — Otomatik Çalışmayı Doğrula

Kurulum bittikten sonra workflow her 5 dakikada otomatik çalışır. İlk gün:
- 9:00'da ilk su hatırlatması eşinize gitmeli
- Eş "içtim" yazınca 9-10 arası tekrar gönderilmemeli
- Eş hiçbir şey yazmazsa 9:05'te tekrar mesaj gitmeli
- 21:00'da tansiyon mesajı gitmeli

GitHub Actions cron'u bazen 5-10 dakika geç çalışabilir (GitHub'ın yoğunluğuna bağlı) — bu **normaldir**.

---

## Eşinizin Kullanabileceği Cevaplar

| Eşinizin yazacağı | Sistem ne yapar |
|---|---|
| `içtim` / `Tamam` / `Ok` / `Evet` / `Bitti` | Su hatırlatmasını o saatlik kapatır |
| `ölçtüm` / `120/80` / `115-75` | Tansiyon hatırlatmasını bugünlük kapatır |
| `ertele` | Aktif hatırlatmayı **1 saat** öteler |
| `2 saat ertele` | 2 saat öteler (sayı değişebilir) |
| `30 dakika ertele` | 30 dk öteler |

Türkçe karakter ve büyük/küçük harf önemli değil — `İÇTİM`, `ictim`, `İçtim` hepsi çalışır.

---

## Sorun Giderme

**Mesaj gitmiyor?**
- GitHub Actions sekmesinde son çalışmanın logunu açın. Hata mesajı varsa görürsünüz.
- Green-API panelinde instance "Authorized" durumda mı kontrol edin (telefon WhatsApp'tan çıkış yapmadıysa OK).
- `TARGET_PHONE` formatı doğru mu? `+90` veya boşluk **olmamalı**, sadece `905551234567`.

**Aynı hatırlatma defalarca geliyor?**
- Eşiniz "içtim" yazdı ama sistem algılamadı olabilir. Türkçe karakter sorun değil ama "ic tim" gibi araya boşluk girerse okuyamaz.

**Saat doğru değil?**
- Script Türkiye saatine sabit. Sunucu UTC çalışsa da Python tarafında `Europe/Istanbul` zaman dilimi kullanılıyor.

**Mesajları durdurmak istiyorum (örn. doktor randevusu sırasında)?**
- Repo → Actions → "Hamilelik Hatirlatma" → sağ üstte üç nokta → **"Disable workflow"** deyin.
- Sonra tekrar açmak için aynı yerden **"Enable workflow"**.

**Hatırlatma metnini değiştirmek istiyorum?**
- `reminder.py` içinde `decide_water` ve `decide_bp` fonksiyonlarındaki mesaj metinlerini düzenleyin, repo'ya commit edin.

---

## Maliyet Özeti

| Servis | Ücret |
|---|---|
| GitHub (private repo) | Ücretsiz |
| GitHub Actions | Ücretsiz (ayda 2000 dakika, biz ~150 dk kullanırız) |
| Green-API | Ücretsiz (Developer plan, günde 100 mesajla limitli — yeterli) |

**Toplam aylık maliyet: 0 ₺**

---

## Güvenlik Notları

- API anahtarlarınız GitHub Secrets'ta şifreli saklanır, kodda görünmez
- Repo'yu **Private** yaptığınız sürece `state.json`'daki zaman damgaları kimseye görünmez
- Green-API hesabınızı 2FA ile koruyun
- Sizin WhatsApp'ınız Green-API'ye bağlı kaldığı sürece o numarayı başka bir cihazda da kullanabilirsiniz (WhatsApp çoklu cihaz destekler)

---

## Sonraki Adımlar (İsterseniz)

- Vitamin/ilaç hatırlatması ekleyebiliriz — sadece `reminder.py`'a yeni bir `decide_vitamin()` fonksiyonu eklemek yeterli
- Doktor randevusu yaklaştığında özel mesaj
- Eşinizin "iyi hissetmiyorum" gibi yazdığı durumlarda size de bildirim
- Günlük özet (kaç bardak su içti, tansiyon ne çıktı) — state'i log'layıp gece raporu

İhtiyaç olursa söyleyin, eklerim.
