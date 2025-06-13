# Gemini Trading Agent v1.6.1

![Versiyon](https://img.shields.io/badge/versiyon-1.3.1-brightgreen) ![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet) ![Status](https://img.shields.io/badge/status-stabil-green)

Google'ın güçlü Gemini yapay zeka modellerini ve LangChain framework'ünü kullanarak kripto para piyasalarında (Spot ve Futures) işlem yapan, gelişmiş risk yönetimi ve kalıcı veritabanı mimarisine sahip bir trading botu. Bu versiyon, kritik hatalardan arındırılmış ve stabil bir çalışma deneyimi sunmaktadır.

## Temel Özellikler

- **Yapay Zeka Destekli Analiz:** Google Gemini modellerini kullanarak tekli, toplu veya Çoklu Zaman Aralığı (MTA) ile derinlemesine analiz yapabilme.
- **Gelişmiş Risk Yönetimi:**
    - **Dinamik Pozisyon Boyutlandırma:** Sermayenin belirli bir yüzdesini riske atarak işlem büyüklüğünü dinamik olarak hesaplar.
    - **İz Süren Zarar Durdur (Trailing Stop-Loss):** Kâra geçen pozisyonlarda kârı kilitlemek için stop-loss seviyesini otomatik olarak ayarlar.
    - **ATR Tabanlı SL/TP:** Piyasa volatilitesine göre Stop-Loss ve Take-Profit seviyelerini dinamik olarak belirler.
- **Kalıcı ve Sağlam Veritabanı Mimarisi:**
    - **SQLite Entegrasyonu:** Anlık pozisyonları ve tüm işlem geçmişini, yeniden başlatmalarda kaybolmayan sağlam bir SQLite veritabanında saklar.
    - **İşlem Geçmişi:** Kapanan her işlemin PNL ve kapanış durumu gibi detaylarını gelecekteki analizler için kaydeder.
- **İki Farklı Tarama Modu:**
    - **Manuel Analiz:** İstediğiniz bir kripto parayı anlık olarak analiz edip işlem açma.
    - **Proaktif Tarama (Fırsat Avcısı):** Binance'in "En Çok Yükselenler/Düşenler" listesini periyodik olarak tarayarak otomatik işlem fırsatları bulma.
- **Sağlamlaştırılmış Ajan-Araç Etkileşimi:** Ajanın (AI) araçları (tools) kullanırken karşılaştığı hataları en aza indiren, yeniden yazılmış ve test edilmiş kod altyapısı.
- **Esnek Konfigürasyon:** Tüm strateji, risk ve API ayarlarının `config.py` üzerinden kolayca yönetilmesi.
- **Canlı ve Simülasyon Modu:** Gerçek parayla işlem yapmadan önce stratejilerinizi test edebilmeniz için güvenli simülasyon modu.

## Kullanılan Teknolojiler

- **Python 3.10+**
- **LangChain & LangChain Google GenAI:** Yapay zeka ajanı oluşturma ve LLM entegrasyonu.
- **Google Gemini API:** Analiz ve karar verme süreçleri için.
- **CCXT:** Binance ve diğer borsalarla standartlaştırılmış iletişim için.
- **Pandas & Pandas-TA:** Finansal verileri işlemek ve teknik analiz göstergelerini hesaplamak için.
- **SQLite3:** Pozisyon ve işlem geçmişi verilerini saklamak için.
- **Dotenv:** API anahtarları gibi hassas bilgileri güvenli bir şekilde yönetmek için.

## Kurulum

1.  **Projeyi Klonlayın:**
    ```bash
    git clone [https://github.com/kullanici-adiniz/gemini-trading-agent.git](https://github.com/kullanici-adiniz/gemini-trading-agent.git)
    cd gemini-trading-agent
    ```

2.  **Gerekli Kütüphaneleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **API Anahtarlarını Ayarlayın:**
    Proje dizinindeki `.env.example` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun ve kendi API anahtarlarınızla doldurun.

4.  **Botu Yapılandırın:**
    `config.py` dosyasını açarak strateji ve risk yönetimi ayarlarınızı (kaldıraç, risk yüzdesi, MTA, Trailing SL vb.) kendinize göre düzenleyin.
    **ÖNEMLİ:** Bota alışana kadar `LIVE_TRADING` ayarını mutlaka `False` olarak bırakın!

## Kullanım

Tüm ayarları tamamladıktan sonra botu aşağıdaki komutla başlatabilirsiniz:

```bash
python main.py