# config.py
# @author: Memba Co.

# === UYGULAMA VERSİYONU ===
APP_VERSION = "1.1.0"

# === YAPAY ZEKA MODEL AYARI ===
# Botun analiz ve karar verme için kullanacağı Gemini modelini belirtir.
# Hızlı ve verimli analizler için: 'gemini-1.5-flash-latest' (varsayılan)
# Daha derin ve kapsamlı analizler için: 'gemini-1.5-pro-latest'
# Not: Farklı modellerin maliyetleri ve API hız limitleri değişiklik gösterebilir.
GEMINI_MODEL = 'gemini-1.5-flash-latest'

# === ÇOKLU ZAMAN ARALIĞI (MTA) ANALİZİ AYARLARI ===
# True olarak ayarlanırsa, bot analiz yaparken hem kullanıcının girdiği zaman aralığını (giriş için)
# hem de aşağıdaki 'MTA_TREND_TIMEFRAME' aralığını (ana trendi belirlemek için) kullanır.
# Bu, sinyal gücünü ve isabet oranını artırmayı hedefler.
# False ise, sadece kullanıcının girdiği tek zaman aralığı ile standart analiz yapar.
USE_MTA_ANALYSIS = True

# USE_MTA_ANALYSIS = True ise, ana trendin yönünü belirlemek için kullanılacak
# üst zaman aralığını belirtir. Yaygın kullanılan değerler: "1h", "4h", "1d".
MTA_TREND_TIMEFRAME = "4h"

# === CANLI İŞLEM AYARI (DİKKAT!) ===
# Bu ayar, botun GERÇEK para ile işlem yapıp yapmayacağını kontrol eder.
# 'False' olarak ayarlandığında, tüm işlemler simülasyon olarak kalır.
# 'True' olarak ayarlandığında, bot Binance hesabınızda GERÇEK alım-satım emirleri gönderir.
# Bu ayarı değiştirmeden önce risklerin farkında olduğunuzdan emin olun.
LIVE_TRADING = False

# === EMİR TÜRÜ VE STRATEJİSİ AYARLARI ===
# Botun kullanacağı varsayılan emir türünü belirler.
# 'MARKET': Piyasa emri. Hızlıdır ancak fiyatta sapma (slippage) olabilir.
# 'LIMIT': Limit emri. Belirlediğiniz fiyattan veya daha iyisinden işlem yapar, ancak emrin dolması garanti değildir.
DEFAULT_ORDER_TYPE = 'LIMIT'

# True olarak ayarlanırsa ve DEFAULT_ORDER_TYPE 'LIMIT' ise,
# Gemini AI en uygun limit fiyatını belirlemek için destek/direnç analizi yapar.
# False ise, limit fiyatı manuel olarak girilir.
USE_AI_LIMIT_PRICE = True


# === TEMEL AYARLAR ===
# Botun çalışacağı varsayılan piyasa türünü belirtir.
# Geçerli değerler: 'spot' veya 'future'
DEFAULT_MARKET_TYPE = 'future'


# === KALDIRAÇ VE MARJİN AYARLARI ===
# Botun her işlem için kullanacağı kaldıraç oranı.
# DİKKAT: Yüksek kaldıraç, riski önemli ölçüde artırır.
LEVERAGE = 10.0

# Her işlem için ayrılacak marjin (teminat) miktarı (USDT cinsinden).
# Gerçek pozisyon büyüklüğü = TRADE_MARGIN_USDT * LEVERAGE
# Örnek: 10 USDT marjin ve 10x kaldıraç ile 100 USDT'lik bir pozisyon açılır.
TRADE_MARGIN_USDT = 10.0


# === RİSK YÖNETİMİ AYARLARI ===
# Botun Stop-Loss ve Take-Profit seviyelerini nasıl belirleyeceğini seçin.
# True: ATR (Average True Range) göstergesini kullanarak volatiliteye göre dinamik seviyeler belirler. (Tavsiye Edilen)
# False: Sabit yüzdesel değerler kullanır.
USE_ATR_FOR_SLTP = True

# === ATR Tabanlı Risk Yönetimi Ayarları (USE_ATR_FOR_SLTP = True ise kullanılır) ===
# Stop-Loss için ATR çarpanı. Değer ne kadar büyükse, stop o kadar geniş olur.
# Yaygın değerler: 1.5, 2.0, 2.5
ATR_MULTIPLIER_SL = 2.0

# Kâr Al/Zarar Durdur Oranı. Kâr hedefinin, risk alınan mesafeye oranıdır.
# 1.5 demek, her 1 birimlik riske karşılık 1.5 birimlik kâr hedeflendiği anlamına gelir.
RISK_REWARD_RATIO_TP = 1.5


# === POZİSYON YÖNETİMİ AYARLARI ===
# Aynı anda açık olabilecek maksimum işlem sayısını limitler.
MAX_CONCURRENT_TRADES = 3

# === OTOMATİK POZİSYON KONTROLÜ ===
# Arka planda açık pozisyonların ne sıklıkla kontrol edileceğini belirtir (saniye cinsinden).
POSITION_CHECK_INTERVAL_SECONDS = 120

# Proaktif taramanın deneyeceği zaman aralıkları listesi.
# İlkini dener, başarısız olursa bir sonrakine geçer.
PROACTIVE_SCAN_TIMEFRAMES = ["15m", "1h", "4h"]

# === PROAKTİF TARAMA AYARLARI ===
# Proaktif Tarama modunun menüde gösterilip gösterilmeyeceğini belirler.
PROACTIVE_SCAN_ENABLED = True

# Proaktif tarama döngüsünün ne sıklıkla çalışacağını belirtir (saniye cinsinden).
PROACTIVE_SCAN_INTERVAL_SECONDS = 900

# True olarak ayarlanırsa proaktif tarama bir fırsat bulduğunda işlemi OTOMATİK olarak açar.
# False olarak ayarlanırsa proaktif tarama bir fırsat bulduğunda işlemi açmadan önce kullanıcıdan ONAY İSTER.
PROACTIVE_SCAN_AUTO_CONFIRM = False

# === Tarama Stratejisi Ayarları ===
# True: Binance Futures'taki anlık Gainer/Loser listesini tarar.
# False: Aşağıda 'PROACTIVE_SCAN_COIN_LIST' içinde belirttiğiniz sabit listeyi tarar.
PROACTIVE_SCAN_USE_GAINERS_LOSERS = True

# PROACTIVE_SCAN_USE_GAINERS_LOSERS = True ise, en çok yükselen (Gainer) ve
# en çok düşen (Loser) kaç coinin analize dahil edileceğini belirtir.
PROACTIVE_SCAN_TOP_N = 5

# PROACTIVE_SCAN_USE_GAINERS_LOSERS = False ise, botun tarayacağı sabit coin listesi.
PROACTIVE_SCAN_COIN_LIST = ["BTC", "ETH", "SOL", "DOGE", "AVAX"]

# YENİ! Tarama döngüsü ayarı.
# True: Proaktif tarama, siz durdurana kadar 'PROACTIVE_SCAN_INTERVAL_SECONDS' aralığıyla sürekli çalışır.
# False: Proaktif tarama menüden seçildiğinde SADECE BİR KERE çalışır ve sonra menüye geri döner.
PROACTIVE_SCAN_IN_LOOP = False