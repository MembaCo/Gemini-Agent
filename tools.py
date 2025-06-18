# tools.py
# @author: Memba Co.

import os
import ccxt
import time
import pandas as pd
import pandas_ta as ta
import logging
import requests
import ast
from datetime import datetime
from dotenv import load_dotenv
from langchain.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

import config

def str_to_bool(val: str) -> bool:
    """Metin bir değeri boolean'a çevirir."""
    return str(val).lower() in {'y', 'yes', 't', 'true', 'on', '1'}

load_dotenv()
exchange = None
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_exchange(market_type: str = "spot"):
    """Global borsa nesnesini, belirtilen piyasa türü için ayarlar."""
    global exchange
    use_testnet = str_to_bool(os.getenv("USE_TESTNET", "False"))
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    if not api_key or not secret_key:
        raise ValueError("API anahtarları .env dosyasında bulunamadı veya boş.")
        
    config_data = {
        "apiKey": api_key, "secret": secret_key, "options": {"defaultType": market_type.lower()},
        "enableRateLimit": True, 'adjustForTimeDifference': True,
    }
    
    if use_testnet and market_type.lower() == 'future':
        logging.warning("--- BINANCE FUTURES TESTNET KULLANILIYOR ---")
        exchange = ccxt.binance(config_data)
        exchange.set_sandbox_mode(True)
    else:
        exchange = ccxt.binance(config_data)

    try:
        exchange.load_markets()
        logging.info(f"--- Piyasalar, '{market_type.upper()}' pazarı için başarıyla yüklendi. (Sunucu zamanı senkronize edildi)")
    except Exception as e:
        exchange = None
        raise ConnectionError(f"'{market_type.upper()}' piyasaları yüklenirken kritik hata: {e}")

def _get_unified_symbol(symbol_input: str) -> str:
    if not isinstance(symbol_input, str): return "INVALID/SYMBOL"
    base = symbol_input.upper().split(':')[0].replace('/USDT', '')
    if base.endswith('USDT'):
        base = base[:-4]
    return f"{base}/USDT"

def _parse_symbol_timeframe_input(input_str: str) -> tuple[str, str]:
    s = str(input_str).strip()
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    for tf in sorted(valid_timeframes, key=len, reverse=True):
        if s.lower().endswith(tf):
            separator_length = 1 if len(s) > len(tf) and s[-len(tf)-1] in [' ', ',', '-', '_', '@'] else 0
            symbol_part = s[:-len(tf)-separator_length]
            timeframe = tf.upper() if tf == '1M' else tf.lower()
            return _get_unified_symbol(symbol_part), timeframe
    return _get_unified_symbol(s), '1h'

def calculate_pnl(side: str, entry_price: float, close_price: float, amount: float) -> float:
    if not all([side, entry_price, close_price, amount]): return 0.0
    if side.lower() == 'buy': return (close_price - entry_price) * amount
    elif side.lower() == 'sell': return (entry_price - close_price) * amount
    return 0.0

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def _fetch_price_natively(symbol: str) -> float | None:
    if not exchange: return None
    try:
        ticker = exchange.fetch_ticker(_get_unified_symbol(symbol))
        return float(ticker.get("last")) if ticker and ticker.get("last") is not None else None
    except Exception as e:
        logging.warning(f"{symbol} için fiyat çekilirken yeniden denenecek hata: {e}")
        raise

@tool
def get_market_price(symbol: str) -> str:
    """Belirtilen kripto para biriminin anlık piyasa fiyatını alır."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    try:
        price = _fetch_price_natively(_get_unified_symbol(symbol))
        return f"{symbol} için anlık piyasa fiyatı: {price}" if price is not None else f"HATA: {symbol} için fiyat bilgisi alınamadı."
    except Exception as e:
        return f"HATA: Fiyat alınamadı. Sembol: '{symbol}'. Hata: {e}"

@tool
@retry(wait=wait_exponential(multiplier=1, min=4, max=15), stop=stop_after_attempt(3))
def get_technical_indicators(params_str: str) -> dict:
    """
    Metin olarak verilen bir sözlüğü (örn: "{'symbol': 'BTC/USDT', 'timeframe': '1h'}")
    işleyerek teknik göstergeleri hesaplar. Bu, yapay zeka ajanının metin tabanlı
    çıktılarıyla uyumluluğu artırır.
    """
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    try:
        params = ast.literal_eval(params_str)
        if not isinstance(params, dict): raise ValueError("Girdi bir sözlüğe dönüştürülemedi.")
    except (ValueError, SyntaxError) as e:
        return {"status": "error", "message": f"Geçersiz girdi formatı: {params_str}. Hata: {e}"}

    symbol = params.get('symbol')
    timeframe = params.get('timeframe')
    if not symbol or not timeframe: return {"status": "error", "message": "'symbol' ve 'timeframe' gereklidir."}
    
    try:
        logging.info(f"  [TI Tool] Adım 2a: OHLCV verisi çekiliyor ({symbol}, {timeframe})...")
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        logging.info(f"  [TI Tool] Adım 2b: OHLCV verisi çekildi, {len(bars) if bars else 0} mum alındı.")
        if not bars or len(bars) < 50: return {"status": "error", "message": f"Yetersiz veri ({len(bars) if bars else 0} mum)."}
        
        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(inplace=True)
        if len(df) < 50: return {"status": "error", "message": f"Temizlendikten sonra yetersiz veri ({len(df)} mum)."}

        logging.info(f"  [TI Tool] Adım 2c: Teknik analiz hesaplamaları (pandas-ta) yapılıyor...")
        df.ta.rsi(append=True); df.ta.macd(append=True); df.ta.bbands(append=True); df.ta.stoch(append=True); df.ta.adx(append=True)
        logging.info(f"  [TI Tool] Adım 2d: Hesaplamalar tamamlandı.")

        last_row = df.iloc[-1]
        indicators = {
            "rsi": last_row.get('RSI_14'), "macd_line": last_row.get('MACD_12_26_9'), "macd_signal": last_row.get('MACDs_12_26_9'),
            "bband_lower": last_row.get('BBL_20_2.0'), "bband_middle": last_row.get('BBM_20_2.0'), "bband_upper": last_row.get('BBU_20_2.0'),
            "stoch_k": last_row.get('STOCHk_14_3_3'), "stoch_d": last_row.get('STOCHd_14_3_3'), "adx": last_row.get('ADX_14')
        }
        for key, value in indicators.items():
            if value is not None and pd.isna(value): indicators[key] = None
        
        return {"status": "success", "data": indicators}
    except Exception as e:
        logging.error(f"Teknik gösterge alınırken beklenmedik hata ({symbol}, {timeframe}): {e}", exc_info=True)
        return {"status": "error", "message": f"Beklenmedik hata: {e}"}

@tool
def execute_trade_order(params: dict) -> str:
    """Alım/satım emri ve ilişkili SL/TP emirlerini borsaya gönderir."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    symbol, side, amount = params.get('symbol'), params.get('side'), params.get('amount')
    if not all([symbol, side, amount]): return "HATA: 'symbol', 'side' ve 'amount' parametreleri zorunludur."

    unified_symbol = _get_unified_symbol(symbol)
    try:
        formatted_amount = exchange.amount_to_precision(unified_symbol, amount)
        price = params.get('price')
        formatted_price = exchange.price_to_precision(unified_symbol, price) if price is not None else None
    except Exception as e: return f"Hata: Miktar/fiyat formatlanamadı. {e}"

    if not config.LIVE_TRADING: return f"Simülasyon emri başarılı: {side} {formatted_amount} {unified_symbol}"
    
    try:
        leverage = params.get('leverage')
        if leverage and exchange.options.get('defaultType') == 'future': exchange.set_leverage(int(leverage), unified_symbol)
        
        order_type = config.DEFAULT_ORDER_TYPE.lower()
        if order_type == 'limit' and formatted_price: exchange.create_limit_order(unified_symbol, side, float(formatted_amount), float(formatted_price))
        else: exchange.create_market_order(unified_symbol, side, float(formatted_amount))
        
        stop_loss, take_profit = params.get('stop_loss'), params.get('take_profit')
        if stop_loss and take_profit and exchange.options.get('defaultType') == 'future':
            opposite_side = 'sell' if side == 'buy' else 'buy'
            time.sleep(0.5)
            try: exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, float(formatted_amount), None, {'stopPrice': stop_loss, 'reduceOnly': True})
            except Exception as sl_e: logging.error(f"SL EMRİ GÖNDERİLEMEDİ: {sl_e}")
            try: exchange.create_order(unified_symbol, 'TAKE_PROFIT_MARKET', opposite_side, float(formatted_amount), None, {'stopPrice': take_profit, 'reduceOnly': True})
            except Exception as tp_e: logging.error(f"TP EMRİ GÖNDERİLEMEDİ: {tp_e}")
        
        return f"İşlem emri ({side} {formatted_amount} {unified_symbol}) başarıyla gönderildi."
    except Exception as e: return f"HATA: İşlem sırasında beklenmedik bir hata oluştu: {e}"

@tool
@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def get_atr_value(symbol_and_timeframe: str) -> dict:
    """Belirtilen sembol ve zaman aralığı için ATR (Average True Range) değerini hesaplar."""
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    try:
        symbol, timeframe = _parse_symbol_timeframe_input(symbol_and_timeframe)
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        if not bars or len(bars) < 20: raise ValueError(f"ATR için yetersiz veri ({len(bars)} mum).")
        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col])
        atr = df.ta.atr()
        if atr is None or atr.empty: raise ValueError("ATR hesaplaması başarısız oldu.")
        last_atr = atr.iloc[-1]
        if pd.isna(last_atr): raise ValueError("Hesaplanan ATR değeri NaN.")
        return {"status": "success", "value": last_atr}
    except Exception as e:
        logging.error(f"ATR alınırken hata: {e}")
        raise

@tool
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def get_funding_rate(symbol: str) -> dict:
    """Belirtilen vadeli işlem sembolü için anlık fonlama oranını yapısal formatta alır."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return {"status": "error", "message": "Fonlama oranı sadece vadeli işlemlerde mevcuttur."}
    unified_symbol = _get_unified_symbol(symbol)
    try:
        rate_data = exchange.fetch_funding_rate(unified_symbol)
        return { "status": "success", "funding_rate": rate_data.get('fundingRate', 0.0) }
    except Exception as e: return {"status": "error", "message": f"HATA: {unified_symbol} için fonlama oranı alınamadı: {e}"}

@tool
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def get_order_book_depth(symbol: str) -> dict:
    """Emir defteri derinliğini ve alış/satış hacim oranını yapısal bir formatta alır."""
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    unified_symbol = _get_unified_symbol(symbol)
    try:
        order_book = exchange.fetch_order_book(unified_symbol, limit=20)
        total_bid_volume_usdt = sum(price * size for price, size in order_book['bids'])
        total_ask_volume_usdt = sum(price * size for price, size in order_book['asks'])
        bid_ask_ratio = total_bid_volume_usdt / total_ask_volume_usdt if total_ask_volume_usdt > 0 else float('inf')
        return {"status": "success", "total_bid_usdt": round(total_bid_volume_usdt, 2), "total_ask_usdt": round(total_ask_volume_usdt, 2), "bid_ask_ratio": round(bid_ask_ratio, 2)}
    except Exception as e: return {"status": "error", "message": f"HATA: {unified_symbol} için emir defteri alınamadı: {e}"}

@tool
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def get_latest_news(symbol: str) -> str:
    """Belirtilen bir kripto para sembolü için CryptoPanic API'sinden en son haber başlıklarını çeker."""
    api_key = os.getenv("CRYPTOPANIC_API_KEY")
    if not api_key: return "Haber analizi için CryptoPanic API anahtarı .env dosyasında bulunamadı."
    base_currency = _get_unified_symbol(symbol).split('/')[0]
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={api_key}&currencies={base_currency}&public=true"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('results'): return f"{base_currency} için güncel bir haber bulunamadı."
        headlines = []
        for news_item in data['results'][:config.NEWS_HEADLINE_COUNT]:
            title, votes = news_item.get('title'), news_item.get('votes', {})
            sentiment_str = f" (👍{votes.get('liked', 0)} / 👎{votes.get('disliked', 0)} / 😆{votes.get('lol', 0)})"
            headlines.append(f"- {title}{sentiment_str}")
        return "En son haberler:\n" + "\n".join(headlines)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403: return "HATA: Haberler alınamadı (403 Forbidden). API anahtarınızı kontrol edin."
        return f"HATA: Haberler alınırken HTTP hatası oluştu: {e}"
    except Exception as e: return f"HATA: Haberler işlenirken beklenmedik bir hata oluştu: {e}"

@tool
@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def get_wallet_balance(quote_currency: str = "USDT") -> dict:
    """Vadeli işlem cüzdanındaki belirtilen para biriminin (varsayılan: USDT) toplam bakiyesini alır."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return {"status": "error", "message": "Bu fonksiyon sadece vadeli işlem modunda çalışır."}
    try:
        balance_data = exchange.fetch_balance()
        total_balance = balance_data.get(quote_currency, {}).get('total', 0.0)
        if total_balance is None: total_balance = 0.0
        return {"status": "success", "balance": float(total_balance)}
    except Exception as e:
        logging.error(f"Bakiye alınırken hata: {e}")
        raise

@tool
@retry(wait=wait_exponential(multiplier=1, min=5, max=20), stop=stop_after_attempt(3))
def get_open_positions_from_exchange(tool_input: str = "") -> list:
    """Borsadaki mevcut açık vadeli işlem pozisyonlarını çeker."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return []
    try:
        all_positions = exchange.fetch_positions_risk()
        return [p for p in all_positions if p.get('contracts') and float(p['contracts']) != 0]
    except Exception as e:
        logging.error(f"Borsadan pozisyonlar alınırken hata oluştu: {e}")
        raise

@tool
def cancel_all_open_orders(symbol: str) -> str:
    """Belirtilen bir sembol için tüm açık emirleri (SL/TP dahil) iptal eder."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    if not config.LIVE_TRADING: return f"Simülasyon: {symbol} için tüm açık emirler iptal edildi."
    unified_symbol = _get_unified_symbol(symbol)
    try:
        exchange.cancel_all_orders(unified_symbol)
        logging.info(f"İPTAL: {unified_symbol} için tüm açık emirler başarıyla iptal edildi.")
        return f"Başarılı: {unified_symbol} için tüm açık emirler iptal edildi."
    except Exception as e:
        logging.error(f"HATA: {unified_symbol} için açık emirler iptal edilemedi. Detay: {e}")
        return f"HATA: {unified_symbol} için emirler iptal edilemedi."

@tool
def update_stop_loss_order(params: dict) -> str:
    """Bir pozisyon için mevcut stop-loss emirlerini iptal eder ve yenisini oluşturur."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."

    symbol = params.get('symbol')
    side = params.get('side')
    amount = params.get('amount')
    new_stop_price = params.get('new_stop_price')

    if not all([symbol, side, amount, new_stop_price]):
        return "HATA: 'symbol', 'side', 'amount' ve 'new_stop_price' parametreleri gereklidir."
    
    if not config.LIVE_TRADING:
        return f"Simülasyon: {symbol} için SL emri {new_stop_price} olarak güncellendi."
    
    unified_symbol = _get_unified_symbol(symbol)
    try:
        open_orders = exchange.fetch_open_orders(unified_symbol)
        stop_orders_to_cancel = [
            order for order in open_orders 
            if 'stop' in order.get('type', '').lower() and order.get('reduceOnly')
        ]
        
        logging.info(f"{unified_symbol} için iptal edilecek {len(stop_orders_to_cancel)} adet stop emri bulundu.")
        for order in stop_orders_to_cancel:
            exchange.cancel_order(order['id'], unified_symbol)
            logging.info(f"Stop emri {order['id']} ({order['type']}) iptal edildi.")
        
        time.sleep(0.5)

        opposite_side = 'sell' if side == 'buy' else 'buy'
        formatted_amount = exchange.amount_to_precision(unified_symbol, amount)
        params_sl = {'stopPrice': new_stop_price, 'reduceOnly': True}
        exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, formatted_amount, None, params_sl)
        return f"Başarılı: {unified_symbol} için yeni SL emri {new_stop_price} olarak oluşturuldu."

    except Exception as e:
        logging.error(f"HATA: SL güncellenemedi. Detay: {e}", exc_info=True)
        return f"HATA: SL güncellenemedi. Detay: {e}"

@tool
@retry(wait=wait_exponential(multiplier=1, min=5, max=20), stop=stop_after_attempt(3))
def get_top_gainers_losers(top_n: int, min_volume_usdt: int) -> list:
    """24s değişime ve işlem hacmine göre en çok kazanan/kaybedenleri alır."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return []
    try:
        all_tickers_data = exchange.fapiPublicGetTicker24hr()
        if not all_tickers_data: return []
        
        processed_tickers = []
        for ticker in all_tickers_data:
            symbol = ticker.get('symbol')
            if not symbol or not symbol.endswith('USDT'): continue
            
            try:
                quote_volume = float(ticker.get('quoteVolume', 0))
                price = float(ticker.get('lastPrice', 0))
                price_change_percent = float(ticker.get('priceChangePercent', 0))

                if price > 0 and quote_volume > min_volume_usdt:
                    processed_tickers.append({
                        'symbol': _get_unified_symbol(symbol),
                        'percentage': price_change_percent,
                        'price': price
                    })
            except (ValueError, TypeError):
                continue
        
        if not processed_tickers: return []
        processed_tickers.sort(key=lambda item: item['percentage'], reverse=True)
        
        gainers = processed_tickers[:top_n]
        losers = processed_tickers[-top_n:]
        return gainers + losers
    except Exception as e:
        logging.error(f"Gainer/Loser listesi alınırken hata: {e}")
        raise