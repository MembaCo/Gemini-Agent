# tools.py
# @author: Memba Co.

import os
import ccxt
import time
import pandas as pd
import pandas_ta as ta
import logging
from dotenv import load_dotenv
from langchain.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

import config

def str_to_bool(val: str) -> bool:
    """Metin bir değeri boolean'a çevirir."""
    val = str(val).lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    else:
        raise ValueError(f"Geçersiz doğruluk değeri: {val}")

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
        logging.critical("API anahtarları .env dosyasında bulunamadı! Program sonlandırılıyor.")
        exit()
    config_data = {
        "apiKey": api_key, "secret": secret_key,
        "options": {"defaultType": market_type.lower()},
        "enableRateLimit": True,
    }
    
    if use_testnet and market_type.lower() == 'future':
        logging.warning("--- BINANCE FUTURES TESTNET KULLANILIYOR ---")
        exchange = ccxt.binance(config_data)
        exchange.set_sandbox_mode(True)
    else:
        exchange = ccxt.binance(config_data)

    try:
        exchange.load_markets()
        logging.info(f"--- Piyasalar, '{market_type.upper()}' pazarı için başarıyla yüklendi. ---")
    except Exception as e:
        logging.critical(f"'{market_type.upper()}' piyasaları yüklenirken kritik hata: {e}")
        exchange = None
        exit()

def _get_unified_symbol(symbol_input: str) -> str:
    """
    Her türlü formattaki sembol girdisini ('BTC', 'btcusdt', 'BTC/USDT')
    standart 'BASE/QUOTE' (örn: 'BTC/USDT') formatına dönüştürür.
    """
    if not isinstance(symbol_input, str):
        return "INVALID/SYMBOL"
    
    base = symbol_input.upper().split(':')[0].replace('/USDT', '').replace('USDT', '')
    return f"{base}/USDT"

def _parse_symbol_timeframe_input(input_str: str) -> tuple[str, str]:
    """Girdiden sembol ve zaman aralığını daha esnek ve hatasız bir şekilde ayrıştırır."""
    s = str(input_str).strip()
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    for tf in sorted(valid_timeframes, key=len, reverse=True):
        if s.lower().endswith(tf):
            separator_length = 1 if len(s) > len(tf) and s[-len(tf)-1] in [' ', ',', '-', '_'] else 0
            symbol_part = s[:-len(tf)-separator_length]
            timeframe = tf.upper() if tf == '1M' else tf.lower()
            return _get_unified_symbol(symbol_part), timeframe
    return _get_unified_symbol(s), '1h'

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def _fetch_price_natively(symbol: str) -> float | None:
    """Dahili kullanım için bir sembolün fiyatını doğrudan sayısal olarak çeker."""
    if not exchange: return None
    try:
        ticker = exchange.fetch_ticker(_get_unified_symbol(symbol))
        return float(ticker.get("last")) if ticker and ticker.get("last") is not None else None
    except Exception as e:
        logging.warning(f"{symbol} için fiyat çekilirken yeniden denenecek hata: {e}")
        raise

@tool
@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def get_wallet_balance(quote_currency: str = "USDT") -> dict:
    """Vadeli işlem cüzdanındaki belirtilen para biriminin (USDT) toplam bakiyesini alır."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future':
        return {"status": "error", "message": "Bu fonksiyon sadece vadeli işlem modunda çalışır."}
    try:
        balance_data = exchange.fetch_balance()
        total_balance = balance_data.get(quote_currency, {}).get('total', 0.0)
        if total_balance is None: total_balance = 0.0
        return {"status": "success", "balance": float(total_balance)}
    except Exception as e:
        logging.error(f"Bakiye alınırken hata: {e}")
        raise

@tool
def update_stop_loss_order(symbol: str, side: str, amount: float, new_stop_price: float) -> str:
    """(DÜZELTİLDİ) Bir pozisyon için mevcut stop-loss emirlerini iptal eder ve yenisini oluşturur. Take-Profit emirlerine dokunmaz."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
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
        if new_stop_price > 0:
            params_sl = {'stopPrice': new_stop_price, 'reduceOnly': True}
            exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, formatted_amount, None, params_sl)
            return f"Başarılı: {unified_symbol} için yeni SL emri {new_stop_price} olarak oluşturuldu."
        else:
            return "Hata: Geçersiz yeni stop-loss fiyatı."
    except Exception as e:
        logging.error(f"HATA: SL güncellenemedi. Detay: {e}", exc_info=True)
        return f"HATA: SL güncellenemedi. Detay: {e}"


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
def get_technical_indicators(symbol_and_timeframe: str) -> dict:
    """Belirtilen sembol ve zaman aralığı için teknik göstergeleri hesaplar."""
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    
    symbol, timeframe = _parse_symbol_timeframe_input(symbol_and_timeframe)
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        if not bars or len(bars) < 50:
            return {"status": "error", "message": f"İndikatör hesaplaması için yetersiz veri ({len(bars)} mum)."}
        
        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col])

        df.ta.rsi(append=True)
        df.ta.macd(append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.stoch(append=True)
        df.ta.adx(append=True)

        last_row = df.iloc[-1]
        indicators = {
            "rsi": last_row.get('RSI_14'), "macd_line": last_row.get('MACD_12_26_9'),
            "macd_signal": last_row.get('MACDs_12_26_9'), "bband_lower": last_row.get('BBL_20_2.0'),
            "bband_middle": last_row.get('BBM_20_2.0'), "bband_upper": last_row.get('BBU_20_2.0'),
            "stoch_k": last_row.get('STOCHk_14_3_3'), "stoch_d": last_row.get('STOCHd_14_3_3'),
            "adx": last_row.get('ADX_14')
        }
        if any(value is None or pd.isna(value) for value in indicators.values()):
            return {"status": "error", "message": f"İndikatör hesaplanamadı (NaN). Sembol: {symbol}"}
        
        return {"status": "success", "data": indicators}
    
    except ccxt.NetworkError as e:
        logging.error(f"Ağ hatası ({symbol_and_timeframe}): {e}")
        raise 
    except Exception as e:
        logging.error(f"Teknik gösterge alınırken beklenmedik hata ({symbol_and_timeframe}): {e}")
        return {"status": "error", "message": f"Beklenmedik hata: {e}"}

@tool
@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def get_atr_value(symbol_and_timeframe: str) -> dict:
    """Belirtilen sembol ve zaman aralığı için ATR değerini hesaplar."""
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    try:
        symbol, timeframe = _parse_symbol_timeframe_input(symbol_and_timeframe)
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        if not bars or len(bars) < 20:
             raise ValueError(f"ATR için yetersiz veri ({len(bars)} mum).")
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

@tool
def execute_trade_order(symbol: str, side: str, amount: float, price: float = None, stop_loss: float = None, take_profit: float = None, leverage: float = None) -> str:
    """Alım/satım emri gönderir. SL/TP emirlerini hemen arkasından gönderir."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    unified_symbol = _get_unified_symbol(symbol)
    try:
        formatted_amount = exchange.amount_to_precision(unified_symbol, amount)
        formatted_price = exchange.price_to_precision(unified_symbol, price) if price is not None else None
    except Exception as e:
         return f"Hata: {unified_symbol} için miktar/fiyat formatlanamadı. {e}"

    if not config.LIVE_TRADING:
        return f"Simülasyon emri başarılı: {side} {formatted_amount} {unified_symbol}"
    
    try:
        if leverage and exchange.options.get('defaultType') == 'future':
            exchange.set_leverage(int(leverage), unified_symbol)
        
        order_type = config.DEFAULT_ORDER_TYPE.lower()
        if order_type == 'limit' and formatted_price:
            order = exchange.create_limit_order(unified_symbol, side, float(formatted_amount), float(formatted_price))
        else:
            order = exchange.create_market_order(unified_symbol, side, float(formatted_amount))
        
        if stop_loss and take_profit and exchange.options.get('defaultType') == 'future':
            opposite_side = 'sell' if side == 'buy' else 'buy'
            time.sleep(0.5)
            try:
                sl_params = {'stopPrice': stop_loss, 'reduceOnly': True}
                exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, float(formatted_amount), None, sl_params)
            except Exception as sl_e: logging.error(f"SL EMRİ GÖNDERİLEMEDİ: {sl_e}")
            try:
                tp_params = {'stopPrice': take_profit, 'reduceOnly': True}
                exchange.create_order(unified_symbol, 'TAKE_PROFIT_MARKET', opposite_side, float(formatted_amount), None, tp_params)
            except Exception as tp_e: logging.error(f"TP EMRİ GÖNDERİLEMEDİ: {tp_e}")
        
        return f"İşlem emri ({side} {formatted_amount} {unified_symbol}) başarıyla gönderildi."
    except Exception as e:
        return f"HATA: İşlem sırasında beklenmedik bir hata oluştu: {e}"

@tool
@retry(wait=wait_exponential(multiplier=1, min=5, max=20), stop=stop_after_attempt(3))
def get_open_positions_from_exchange(tool_input: str = "") -> list:
    """Borsadaki mevcut açık vadeli işlem pozisyonlarını çeker."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return []
    try:
        all_positions = exchange.fetch_positions(params={'type': config.DEFAULT_MARKET_TYPE})
        return [p for p in all_positions if p.get('contracts') and float(p['contracts']) != 0]
    except Exception as e:
        logging.error(f"Borsadan pozisyonlar alınırken hata oluştu: {e}")
        raise

@tool
def cancel_all_open_orders(symbol: str) -> str:
    """Belirtilen bir sembol için tüm açık emirleri (SL/TP dahil) iptal eder."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    if not config.LIVE_TRADING:
        return f"Simülasyon: {symbol} için tüm açık emirler iptal edildi."

    unified_symbol = _get_unified_symbol(symbol)
    try:
        exchange.cancel_all_orders(unified_symbol)
        logging.info(f"İPTAL: {unified_symbol} için tüm açık emirler başarıyla iptal edildi.")
        return f"Başarılı: {unified_symbol} için tüm açık emirler iptal edildi."
    except Exception as e:
        logging.error(f"HATA: {unified_symbol} için açık emirler iptal edilemedi. Detay: {e}")
        return f"HATA: {unified_symbol} için emirler iptal edilemedi."