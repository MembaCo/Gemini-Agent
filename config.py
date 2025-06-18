# @author: Memba Co.

# === UYGULAMA VERSİYONU ===
# v2.2.0, WebSockets entegrasyonu ve mimari iyileştirmeleri içerir.
APP_VERSION = "2.2.0" 

# === YAPAY ZEKA MODEL AYARI ===
GEMINI_MODEL = 'gemini-1.5-flash' # veya kullandığınız diğer model

# === AJAN AYARLARI ===
# Ajan'ın 'KAPAT' tavsiyesi verdiğinde, kullanıcı onayı olmadan pozisyonu otomatik olarak kapatıp kapatmayacağını belirler.
AGENT_CLOSE_AUTO_CONFIRM = False
# Ajanın bir görevi tamamlarken yapabileceği maksimum adım sayısı.
AGENT_MAX_ITERATIONS = 8

# === STRATEJİ AYARLARI ===
USE_MTA_ANALYSIS = True
MTA_TREND_TIMEFRAME = "4h"

# HABER ANALİZİ AYARI
USE_NEWS_ANALYSIS = False
# CryptoPanic API'sinden çekilecek maksimum haber başlığı sayısı
NEWS_HEADLINE_COUNT = 3 

# === CANLI İŞLEM AYARI (DİKKAT!) ===
LIVE_TRADING = True

# === EMİR TÜRÜ VE STRATEJİSİ AYARLARI ===
DEFAULT_ORDER_TYPE = 'LIMIT'
USE_AI_LIMIT_PRICE = True

# === TEMEL AYARLAR ===
DEFAULT_MARKET_TYPE = 'future'

# === KALDIRAÇ AYARLARI ===
LEVERAGE = 10.0

# === RİSK YÖNETİMİ AYARLARI ===
RISK_PER_TRADE_PERCENT = 5.0

# --- Stop-Loss Ayarları ---
USE_ATR_FOR_SLTP = True 
ATR_MULTIPLIER_SL = 2.0 

# === KÂR ALMA STRATEJİLERİ ===
RISK_REWARD_RATIO_TP = 2.0 
USE_TRAILING_STOP_LOSS = True
TRAILING_STOP_ACTIVATION_PERCENT = 1.5
USE_PARTIAL_TP = True 
PARTIAL_TP_TARGET_RR = 1.0 
PARTIAL_TP_CLOSE_PERCENT = 50.0 

# === POZİSYON YÖNETİMİ AYARLARI ===
MAX_CONCURRENT_TRADES = 5
DATABASE_FILE = "trades.db"
POSITION_CHECK_INTERVAL_SECONDS = 120

# === TELEGRAM BİLDİRİM AYARLARI ===
TELEGRAM_ENABLED = True

# === WEB ARAYÜZÜ AYARLARI ===
# False ise, web arayüzünde proaktif tarama sonucu bulunan fırsatlar için bir onay penceresi çıkar.
WEB_AUTO_CONFIRM_OPPORTUNITY = False

# === PROAKTİF TARAMA AYARLARI ===
PROACTIVE_SCAN_ENABLED = True
PROACTIVE_SCAN_INTERVAL_SECONDS = 900
PROACTIVE_SCAN_IN_LOOP = False # Döngüsel tarama henüz web'de tam desteklenmiyor.
PROACTIVE_SCAN_USE_GAINERS_LOSERS = True
PROACTIVE_SCAN_TOP_N = 10
PROACTIVE_SCAN_MIN_VOLUME_USDT = 1000000
PROACTIVE_SCAN_BLACKLIST = ["SHIB", "PEPE", "MEME"]
PROACTIVE_SCAN_WHITELIST = ["BTC", "ETH", "SOL"]
PROACTIVE_SCAN_MTA_ENABLED = True
PROACTIVE_SCAN_ENTRY_TIMEFRAME = "15m"
PROACTIVE_SCAN_TREND_TIMEFRAME = "4h"