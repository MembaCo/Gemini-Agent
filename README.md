# Gemini Trading Agent v1.1.0

![Versiyon](https://img.shields.io/badge/versiyon-1.1.0-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet)

Google'ın güçlü Gemini (1.5 Flash & Pro) yapay zeka modellerini ve LangChain framework'ünü kullanarak kripto para piyasalarında (Spot ve Futures) otomatik alım-satım işlemleri yapan gelişmiş bir trading botu.

## Temel Özellikler

- **Yapay Zeka Destekli Analiz:** Google Gemini modellerini kullanarak tekli veya toplu coin analizleri yapabilme.
- **Çoklu Zaman Aralığı Analizi (MTA):** Kısa vadeli giriş sinyallerini, daha yüksek bir zaman dilimindeki ana trend ile teyit ederek alım-satım kararlarının isabetliliğini artırma.
- **Gelişmiş Strateji Motoru:** ADX, RSI, Bollinger Bantları, MACD ve Stokastik gibi birden çok teknik göstergeye dayalı yapılandırılmış alım-satım kuralları.
- **İki Farklı Tarama Modu:**
    - **Manuel Analiz:** İstediğiniz bir kripto parayı anlık olarak analiz edip işlem açma.
    - **Proaktif Tarama (Fırsat Avcısı):** Binance'in "En Çok Yükselenler/Düşenler" listesini veya sizin belirlediğiniz bir coin listesini periyodik olarak tarayarak otomatik işlem fırsatları bulma.
- **Dinamik Risk Yönetimi:** Stop-Loss ve Take-Profit seviyelerini piyasa volatilitesine göre ATR (Average True Range) göstergesiyle dinamik olarak belirleme.
- **Esnek Konfigürasyon:** Tüm strateji, risk ve API ayarlarının `config.py` üzerinden kolayca yönetilmesi.
- **Canlı ve Simülasyon Modu:** Gerçek parayla işlem yapmadan önce stratejilerinizi test edebilmeniz için güvenli simülasyon modu (`LIVE_TRADING=False`).
- **Pozisyon Yönetimi ve Senkronizasyon:** Açık pozisyonları dahili olarak takip etme ve borsa ile senkronize ederek tutarlılığı sağlama.

## Kullanılan Teknolojiler

- **Python 3.10+**
- **LangChain & LangChain Google GenAI:** Yapay zeka ajanı (agent) oluşturma ve LLM entegrasyonu.
- **Google Gemini API:** Analiz ve karar verme süreçleri için.
- **CCXT:** Binance ve diğer borsalarla standartlaştırılmış iletişim için.
- **Pandas & Pandas-TA:** Finansal verileri işlemek ve teknik analiz göstergelerini hesaplamak için.
- **Dotenv:** API anahtarları gibi hassas bilgileri güvenli bir şekilde yönetmek için.

## Kurulum

1.  **Projeyi Klonlayın:**
    ```bash
    git clone [https://github.com/kullanici-adiniz/gemini-trading-agent.git](https://github.com/kullanici-adiniz/gemini-trading-agent.git)
    cd gemini-trading-agent
    ```

2.  **Gerekli Kütüphaneleri Yükleyin:**
    (Sanal bir ortam (virtual environment) kullanmanız şiddetle tavsiye edilir.)
    ```bash
    pip install -r requirements.txt
    ```

3.  **API Anahtarlarını Ayarlayın:**
    Proje dizinindeki `.env.example` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun. Daha sonra bu `.env` dosyasını kendi API anahtarlarınızla doldurun.
    ```
    # .env dosyasının içeriği
    BINANCE_API_KEY="SIZIN_BINANCE_API_KEYINIZ"
    BINANCE_SECRET_KEY="SIZIN_BINANCE_SECRET_KEYINIZ"
    GOOGLE_API_KEY="SIZIN_GEMINI_API_KEYINIZ"
    ...
    ```

4.  **Botu Yapılandırın:**
    `config.py` dosyasını açarak strateji ve risk yönetimi ayarlarınızı (kaldıraç, marjin, işlem modu, MTA ayarları vb.) kendinize göre düzenleyin.
    **ÖNEMLİ:** Bota alışana kadar `LIVE_TRADING` ayarını mutlaka `False` olarak bırakın!

## Kullanım

Tüm ayarları tamamladıktan sonra botu aşağıdaki komutla başlatabilirsiniz:

```bash
python main.py