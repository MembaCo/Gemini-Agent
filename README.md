# Gemini Trading Agent v1.8.0

![Versiyon](https://img.shields.io/badge/versiyon-1.9.0-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet) ![Status](https://img.shields.io/badge/status-stabil-green)

Gemini Trading Agent, Google'ın en gelişmiş yapay zeka modellerinden biri olan Gemini'yi kullanarak kripto para piyasalarında stratejik kararlar alan ve bu kararları uygulayan modern bir trading botudur. Proje, sadece teknik göstergelere bağlı kalmak yerine; teknik analizi, piyasa duyarlılığını ve en güncel haberleri birleştirerek piyasalara bütünsel bir bakış açısı sunar. Gelişmiş risk yönetimi modülleri, kalıcı veritabanı mimarisi ve interaktif kontrol mekanizmaları ile donatılmıştır.

🌟 Temel Özellikler
🧠 Çok Yönlü Yapay Zeka Analizi:

Teknik Analiz: Fiyat grafikleri üzerinden Çoklu Zaman Aralığı (MTA) analizi yaparak ana trendleri ve kısa vadeli giriş noktalarını belirler.

Duyarlılık Analizi: Fonlama oranları (Funding Rates) ve emir defteri derinliği (Order Book Depth) gibi verilerle anlık piyasa iştahını ve yatırımcı psikolojisini ölçer.

Temel Analiz (Haber Duyarlılığı): CryptoPanic API'si üzerinden en son haberleri okur. Piyasayı olumsuz etkileyebilecek (FUD, hack, regülasyon vb.) haberler durumunda, riskli işlemlerden kaçınarak sermayeyi korur.

🛡️ Gelişmiş Risk Yönetimi:

Dinamik Pozisyon Boyutlandırma: Toplam sermayenin önceden belirlenmiş bir yüzdesini riske atarak her işlem için pozisyon büyüklüğünü dinamik olarak hesaplar.

ATR Tabanlı SL/TP: Piyasa volatilitesini ölçen ATR (Average True Range) göstergesine göre Stop-Loss ve Take-Profit seviyelerini dinamik olarak belirler.

İz Süren Zarar Durdur (Trailing Stop-Loss): Kâra geçen pozisyonlarda kârı kilitlemek ve zararı en aza indirmek için stop-loss seviyesini otomatik olarak yukarı taşır.

Kısmi Kâr Alma (Partial Take-Profit): 1R (risk mesafesi) hedefine ulaşıldığında pozisyonun bir kısmını otomatik kapatarak kârı realize eder ve kalan pozisyonun riskini sıfırlar (Breakeven).

🎛️ Kullanıcı Kontrolü ve Etkileşim:

Ajan Karar Onayı: Yapay zekanın "Pozisyonu Kapat" tavsiyelerinden sonra, işlem yapmadan önce terminal üzerinden manuel onay alınmasını sağlayan güvenlik mekanizması. (config.py üzerinden otomatikleştirilebilir).

İnteraktif Telegram Kontrolü: /status, /analiz, /tara ve /pozisyonlar gibi komutlarla botu uzaktan yönetme ve doğrudan Telegram arayüzü üzerinden pozisyon kapatma imkanı.

💾 Kalıcı ve Sağlam Veritabanı Mimarisi:

SQLite Entegrasyonu: Tüm aktif pozisyonları ve kapanan işlemlerin geçmişini (PNL, giriş/çıkış fiyatları, kapanış nedeni vb.) yeniden başlatmalarda kaybolmayan sağlam bir SQLite veritabanında saklar.

🔭 İki Farklı Tarama Modu:

Manuel Analiz: Belirlediğiniz bir kripto parayı anlık olarak analiz edip işlem açma.

Proaktif Tarama (Fırsat Avcısı): Binance'in "En Çok Yükselenler/Düşenler" listesini ve sizin belirlediğiniz bir beyaz listeyi periyodik olarak tarayarak otomatik işlem fırsatları arama.

⚙️ Esnek Konfigürasyon:

Tüm strateji (MTA, Risk/Ödül oranı), risk (RISK_PER_TRADE_PERCENT) ve API ayarlarının config.py dosyası üzerinden kolayca yönetilmesi.

📊 Web Arayüzü:

Botun performansını, kâr/zarar durumunu ve tüm işlem geçmişini grafiksel olarak görselleştiren basit bir web panosu.

🛠️ Kullanılan Teknolojiler
Dil: Python 3.10+

Yapay Zeka: Google Gemini API, LangChain & LangChain Google GenAI

Borsa Entegrasyonu: CCXT

Veri Analizi & TA: Pandas & Pandas-TA

Veritabanı: SQLite3

Bot/Arayüz: python-telegram-bot (v22+), Flask

Yardımcılar: python-dotenv, Tenacity

🚀 Kurulum ve Başlatma
1. Projeyi Klonlayın
git clone [https://github.com/MembaCo/Gemini-Agent.git](https://github.com/MembaCo/Gemini-Agent.git)
cd Gemini-Agent

2. Gerekli Kütüphaneleri Yükleyin
pip install -r requirements.txt

3. API Anahtarlarını Ayarlayın
Proje dizinindeki .env.example dosyasını kopyalayarak .env adında yeni bir dosya oluşturun ve kendi API anahtarlarınızla doldurun.

.env dosya örneği:

# Google AI Studio'dan alınan Gemini API anahtarı
GOOGLE_API_KEY="AIzaSyXXXXXXXXXXXXXXXXXXX"

# Binance API Anahtarları
BINANCE_API_KEY="YOUR_BINANCE_API_KEY"
BINANCE_SECRET_KEY="YOUR_BINANCE_SECRET_KEY"

# Haber analizi için (isteğe bağlı)
CRYPTOPANIC_API_KEY="YOUR_CRYPTOPANIC_API_KEY"

# Telegram Bot için (isteğe bağlı)
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID"

# Testnet kullanmak için "true" yapın
USE_TESTNET="false"

# Ajan loglarını detaylı görmek için "true" yapın
AGENT_VERBOSE="true"

ÖNEMLİ: Bota alışana kadar LIVE_TRADING ayarını config.py dosyasından False olarak bırakmanız şiddetle tavsiye edilir!

4. Botu Başlatın
Tüm ayarları tamamladıktan sonra botu aşağıdaki komutla başlatabilirsiniz:

python main.py

📜 Sorumluluk Reddi
Bu proje yalnızca eğitim ve araştırma amaçlıdır. Finansal tavsiye niteliği taşımaz. Kripto para ticareti yüksek risk içerir ve tüm sermayenizi kaybetmenize neden olabilir. Bu yazılımın kullanılmasından kaynaklanabilecek herhangi bir finansal kayıptan yazar veya katkıda bulunanlar sorumlu tutulamaz. Her zaman kendi araştırmanızı yapın ve asla kaybetmeyi göze alamayacağınız parayla işlem yapmayın.