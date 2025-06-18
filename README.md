# Gemini Trading Agent v2.2.0

![Versiyon](https://img.shields.io/badge/versiyon-2.2.0-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet) ![Status](https://img.shields.io/badge/status-stabil-green)

Gemini Trading Agent, Google'ın gelişmiş yapay zeka modeli Gemini'yi kullanarak kripto para piyasalarında stratejik kararlar alan ve bu kararları uygulayan modern bir trading botudur. Proje, sadece teknik göstergelere bağlı kalmak yerine; teknik analizi, piyasa duyarlılığını ve en güncel haberleri birleştirerek bütünsel bir bakış açısı sunar. Gelişmiş risk yönetimi modülleri, kalıcı veritabanı mimarisi ve çoklu arayüz (Web, CLI, Telegram) üzerinden tam kontrol imkanı ile donatılmıştır.

---

## 🌟 Temel Özellikler

### 🧠 Çok Yönlü Yapay Zeka Analizi
- **Teknik Analiz:** Fiyat grafikleri üzerinden Çoklu Zaman Aralığı (MTA) analizi yaparak ana trendleri ve kısa vadeli giriş noktalarını belirler.
- **Duyarlılık Analizi:** Fonlama oranları (Funding Rates) ve emir defteri derinliği (Order Book Depth) gibi verilerle anlık piyasa iştahını ölçer.
- **Temel Analiz (Haber Duyarlılığı):** CryptoPanic API'si üzerinden en son haberleri okur. Piyasayı olumsuz etkileyebilecek (FUD, hack, regülasyon vb.) haberler durumunda, riskli işlemlerden kaçınarak sermayeyi korur.
- **Esnek Veri İşleme:** Analiz sırasında bazı teknik göstergeler hesaplanamasa bile (NaN), yapay zeka eldeki mevcut verilerle karar verebilme yeteneğine sahiptir.

### 🛡️ Gelişmiş Risk Yönetimi
- **Dinamik Pozisyon Boyutlandırma:** Toplam sermayenin `config.py`'da belirlenmiş bir yüzdesini riske atarak her işlem için pozisyon büyüklüğünü dinamik olarak hesaplar.
- **ATR Tabanlı SL/TP:** Piyasa volatilitesini ölçen ATR (Average True Range) göstergesine göre Stop-Loss ve Take-Profit seviyelerini dinamik olarak belirler.
- **İz Süren Zarar Durdur (Trailing Stop-Loss):** Kâra geçen pozisyonlarda kârı kilitlemek için stop-loss seviyesini otomatik olarak yukarı taşıyan arka plan kontrolcüsü.
- **Kısmi Kâr Alma (Partial Take-Profit):** 1R (risk mesafesi) gibi hedeflere ulaşıldığında pozisyonun bir kısmını otomatik kapatarak kârı realize eder ve kalan pozisyonun riskini sıfırlar (Breakeven).

### 🎛️ Çoklu Arayüz ile Tam Kontrol
- **İnteraktif Web Arayüzü (Dashboard):**
    - `Flask` ve `SocketIO` ile geliştirilmiş, anlık veri akışı sağlayan modern bir arayüz.
    - Toplam Kâr/Zarar, kazanma oranı gibi istatistiklerin ve P&L grafiğinin canlı takibi.
    - Açık pozisyonları listeleme, manuel olarak kapatma ve **tek tuşla yeniden analiz etme**.
    - Proaktif taramayı başlatma ve tarama sürecini canlı olarak izleme.
    - Fırsat bulunduğunda onaylama/reddetme pencereleri.
- **Telegram Botu Entegrasyonu:**
    - `/pozisyonlar`, `/analiz` gibi komutlarla botu uzaktan yönetme.
    - İnteraktif butonlar ile pozisyonları yeniden analiz etme veya kapatma onayı.
    - Yeni açılan ve kapanan işlemler için anlık bildirimler.
- **Terminal Arayüzü (CLI):**
    - Klasik bir menü üzerinden tüm temel bot fonksiyonlarını (analiz, pozisyon yönetimi, tarama) çalıştırma imkanı.

### 🔭 Akıllı Fırsat Tarama (Fırsat Avcısı)
- Binance'in "En Çok Yükselenler/Düşenler" listesini ve kullanıcı tanımlı bir "Beyaz Liste"yi periyodik olarak tarayarak otomatik işlem fırsatları arar.
- Hacim filtresi gibi ayarlar sayesinde sadece likit piyasalarda işlem yapılmasını sağlar.

### 💾 Sağlam ve Kalıcı Mimari
- **SQLite Veritabanı:** Tüm aktif pozisyonları ve kapanan işlemlerin geçmişini (PNL, giriş/çıkış fiyatları vb.) yeniden başlatmalarda kaybolmayan sağlam bir SQLite veritabanında saklar.
- **Modüler Kod Yapısı:** `core`, `tools`, `database`, `config` gibi ayrı modüller sayesinde kodun okunabilirliği ve bakımı kolaydır.
- **Dayanıklı API Çağrıları:** `tenacity` kütüphanesi ile ağ hatalarına veya geçici API sorunlarına karşı dayanıklı, yeniden deneme mekanizmasına sahip araçlar.

---

## 🛠️ Kullanılan Teknolojiler
- **Dil:** Python 3.10+
- **Yapay Zeka:** Google Gemini API, LangChain
- **Borsa Entegrasyonu:** CCXT
- **Web Arayüzü:** Flask, Flask-SocketIO, Waitress
- **Veri Analizi & TA:** Pandas, Pandas-TA
- **Veritabanı:** SQLite3
- **Bot/Bildirim:** python-telegram-bot
- **Yardımcılar:** python-dotenv, tenacity, requests

---

## 🚀 Kurulum ve Başlatma

1.  **Projeyi Klonlayın**
    ```bash
    git clone [PROJE_URL'NİZ]
    cd [PROJE_KLASÖRÜ]
    ```

2.  **Gerekli Kütüphaneleri Yükleyin**
    ```bash
    pip install -r requirements.txt
    ```

3.  **API Anahtarlarını Ayarlayın**
    `.env.example` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun ve kendi API anahtarlarınızla doldurun.
    ```dotenv
    # Google AI Studio'dan alınan Gemini API anahtarı
    GOOGLE_API_KEY="AIzaSyXXXXXXXXXXXXXXXXXXX"

    # Binance API Anahtarları
    BINANCE_API_KEY="YOUR_BINANCE_API_KEY"
    BINANCE_SECRET_KEY="YOUR_BINANCE_SECRET_KEY"
    
    # Haber analizi için (isteğe bağlı)
    CRYPTOPANIC_API_KEY="YOUR_CRYPTOPANIC_API_KEY"

    # Telegram Bot için
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID"

    # Web Arayüzü için şifre
    DASHBOARD_PASSWORD="YOUR_DASHBOARD_PASSWORD"

    # Testnet kullanmak için "true" yapın
    USE_TESTNET="false"

    # Ajan loglarını detaylı görmek için "true" yapın
    AGENT_VERBOSE="true"
    ```

4.  **Strateji ve Ayarları Yapılandırın**
    İşlem stratejinizi, risk yönetimi parametrelerinizi ve diğer ayarları `config.py` dosyasından düzenleyin.

5.  **Botu Başlatın**
    Tüm ayarları tamamladıktan sonra botu tek bir komutla başlatabilirsiniz. Bu komut, arka plan kontrolcülerini, web arayüzünü ve Telegram botunu otomatik olarak başlatacaktır.
    ```bash
    python main.py
    ```
    - **Web Arayüzü:** Tarayıcınızda `http://localhost:5001` adresini açın.
    - **Telegram Botu:** Botunuza `/start` komutunu gönderin.
    - **CLI:** Komutları terminal üzerinden kullanın.

---

## 📜 Sorumluluk Reddi
Bu proje yalnızca eğitim ve araştırma amaçlıdır. Finansal tavsiye niteliği taşımaz. Kripto para ticareti yüksek risk içerir ve tüm sermayenizi kaybetmenize neden olabilir. Bu yazılımın kullanılmasından kaynaklanabilecek herhangi bir finansal kayıptan yazar veya katkıda bulunanlar sorumlu tutulamaz.