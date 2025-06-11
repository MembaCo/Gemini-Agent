# config.py
# @author: Memba Co.

# === UYGULAMA VERSİYONU ===
APP_VERSION = "1.3.1"

# === YAPAY ZEKA MODEL AYARI ===
# Botun analiz ve karar verme için kullanacağı Gemini modelini belirtir.
# Hızlı ve verimli analizler için: 'gemini-1.5-flash-latest' (varsayılan) gemini-2.5-flash-preview-05-20  # Hızlı analizler için
# Daha derin ve kapsamlı analizler için: 'gemini-1.5-pro-latest'
# Not: Farklı modellerin maliyetleri ve API hız limitleri değişiklik gösterebilir.
GEMINI_MODEL = 'gemini-2.0-flash'

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
LIVE_TRADING = True

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


# === KALDIRAÇ AYARLARI ===
# Botun her işlem için kullanacağı kaldıraç oranı.
# DİKKAT: Yüksek kaldıraç, riski önemli ölçüde artırır.
LEVERAGE = 10.0

# === RİSK YÖNETİMİ AYARLARI ===
# --- Dinamik Pozisyon Büyüklüğü ---
# Her işlemde, toplam vadeli işlem cüzdanı bakiyesinin yüzde kaçının riske edileceğini belirtir.
# Örnek: Bakiye 1000 USDT, RISK_PER_TRADE_PERCENT 2.0 ise, her işlemde maksimum 20 USDT'lik bir kayıp göze alınır.
# Pozisyon büyüklüğü, bu risk miktarına ve stop-loss mesafesine göre dinamik olarak hesaplanır.
RISK_PER_TRADE_PERCENT = 2.0
# TRADE_MARGIN_USDT = 10.0 # Bu ayar artık kullanılmıyor, yerine RISK_PER_TRADE_PERCENT geldi.

# --- Stop-Loss ve Take-Profit Ayarları ---
USE_ATR_FOR_SLTP = True
ATR_MULTIPLIER_SL = 2.0
RISK_REWARD_RATIO_TP = 1.5

# --- İz Süren Zarar Durdur (Trailing Stop-Loss) ---
# True olarak ayarlanırsa, pozisyon kâra geçtiğinde stop-loss seviyesini otomatik olarak yukarı çeker.
USE_TRAILING_STOP_LOSS = True

# Pozisyonun, giriş fiyatından yüzde kaç kâra geçtiğinde Trailing SL'in aktif olacağını belirtir.
# Örnek: 1.5 ise, pozisyon %1.5 kâra ulaştığında stop-loss'u takip etmeye başlar.
TRAILING_STOP_ACTIVATION_PERCENT = 1.5

# === POZİSYON YÖNETİMİ AYARLARI ===
# Aynı anda açık olabilecek maksimum işlem sayısını limitler.
MAX_CONCURRENT_TRADES = 3
DATABASE_FILE = "trades.db" # Veritabanı dosyasının adı
POSITION_CHECK_INTERVAL_SECONDS = 120

# === PROAKTİF TARAMA AYARLARI ===
# Proaktif taramanın deneyeceği zaman aralıkları listesi.
PROACTIVE_SCAN_TIMEFRAMES = ["15m", "1h", "4h"]
PROACTIVE_SCAN_ENABLED = True
PROACTIVE_SCAN_INTERVAL_SECONDS = 900
PROACTIVE_SCAN_AUTO_CONFIRM = False
PROACTIVE_SCAN_USE_GAINERS_LOSERS = True
PROACTIVE_SCAN_TOP_N = 5
PROACTIVE_SCAN_COIN_LIST = ["BTC", "ETH", "SOL", "DOGE", "AVAX"]
PROACTIVE_SCAN_IN_LOOP = False