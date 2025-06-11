# tools.py
# @author: Memba Co.

import os
import ccxt
import time
import pandas as pd
import pandas_ta as ta
import logging
import re
from dotenv import load_dotenv
from langchain.tools import tool

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
    Her türlü formattaki sembol girdisini ('BTC', 'btcusdt', 'BTC/USDT', 'BTC/USDT:USDT')
    standart 'BASE/QUOTE' (örn: 'BTC/USDT') formatına dönüştürür.
    """
    if not isinstance(symbol_input, str):
        return "INVALID/SYMBOL"
    
    s = symbol_input.strip().upper()
    
    if ':' in s:
        s = s.split(':')[0]
    
    s = s.replace('/', '')
    
    if s.endswith('USDT'):
        return s[:-4] + '/USDT'
    
    return s + '/USDT'

def _parse_symbol_timeframe_input(input_str: str) -> tuple[str, str]:
    """
    Girdiden sembol ve zaman aralığını daha esnek ve hatasız bir şekilde ayrıştırır.
    """
    s = str(input_str).strip()
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    
    for tf in sorted(valid_timeframes, key=len, reverse=True):
        if s.lower().endswith(tf):
            separator_length = 0
            if len(s) > len(tf):
                char_before_tf = s[-len(tf)-1]
                # ★★★ NIHAI DÜZELTME: Alt çizgi (_) karakteri ayraç olarak eklendi ★★★
                if char_before_tf in [' ', ',', '-', '_']:
                    separator_length = 1
            
            symbol_part = s[:-len(tf)-separator_length]
            timeframe = tf.upper() if tf == '1M' else tf.lower()
            return _get_unified_symbol(symbol_part), timeframe
            
    return _get_unified_symbol(s), '1h'


def _fetch_price_natively(symbol: str) -> float | None:
    """Dahili kullanım için bir sembolün fiyatını doğrudan sayısal olarak çeker."""
    if not exchange: return None
    try:
        unified_symbol = _get_unified_symbol(symbol)
        ticker = exchange.fetch_ticker(unified_symbol)
        return float(ticker.get("last")) if ticker.get("last") is not None else None
    except Exception:
        return None

@tool
def get_wallet_balance(quote_currency: str = "USDT") -> dict:
    """Vadeli işlem cüzdanındaki belirtilen para biriminin (genellikle USDT) toplam bakiyesini alır."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future':
        return {"status": "error", "message": "Bu fonksiyon sadece vadeli işlem modunda çalışır."}
    try:
        balance_data = exchange.fetch_balance()
        total_balance = balance_data.get(quote_currency, {}).get('total', 0.0)
        if total_balance is None: total_balance = 0.0
        return {"status": "success", "balance": float(total_balance)}
    except Exception as e:
        return {"status": "error", "message": f"Bakiye alınamadı. Detay: {e}"}

@tool
def update_stop_loss_order(symbol: str, side: str, amount: float, new_stop_price: float) -> str:
    """Bir pozisyon için mevcut stop-loss emirlerini iptal eder ve yenisini oluşturur."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    if not config.LIVE_TRADING:
        return f"Simülasyon: {symbol} için SL emri {new_stop_price} olarak güncellendi."
    
    unified_symbol = _get_unified_symbol(symbol)
    try:
        open_orders = exchange.fetch_open_orders(unified_symbol)
        stop_orders = [o for o in open_orders if o.get('type') in ['stop_market', 'stop'] and o.get('reduceOnly')]
        for order in stop_orders:
            exchange.cancel_order(order['id'], unified_symbol)
        
        opposite_side = 'sell' if side == 'buy' else 'buy'
        formatted_amount = exchange.amount_to_precision(unified_symbol, amount)
        if new_stop_price > 0:
            params_sl = {'stopPrice': new_stop_price, 'reduceOnly': True}
            exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, formatted_amount, None, params_sl)
            return f"Başarılı: {unified_symbol} için SL emri {new_stop_price} olarak güncellendi."
        else:
            return "Hata: Geçersiz yeni stop-loss fiyatı."
    except Exception as e:
        return f"HATA: SL güncellenemedi. Detay: {e}"

@tool
def get_market_price(symbol: str) -> str:
    """Belirtilen kripto para biriminin anlık piyasa fiyatını alır."""
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    try:
        unified_symbol = _get_unified_symbol(symbol)
        price = _fetch_price_natively(unified_symbol)
        return f"{unified_symbol} için anlık piyasa fiyatı: {price}" if price is not None else f"HATA: {unified_symbol} için fiyat bilgisi alınamadı."
    except Exception as e:
        return f"HATA: Fiyat alınamadı. Sembol: '{symbol}'. Hata: {e}"

@tool
def get_technical_indicators(symbol_and_timeframe: str) -> dict:
    """
    Belirtilen sembol ve zaman aralığı için teknik göstergeleri hesaplar
    ve sonuçları bir SÖZLÜK (dictionary) olarak döndürür.
    """
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    try:
        symbol, timeframe = _parse_symbol_timeframe_input(symbol_and_timeframe)
        
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        if not bars or len(bars) < 50:
            raise ValueError(f"İndikatör hesaplaması için yetersiz veri ({len(bars)} mum).")
        
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
            return {"status": "error", "message": f"{symbol} için indikatör hesaplanamadı (NaN)."}
        return {"status": "success", "data": indicators}
    except Exception as e:
        return {"status": "error", "message": f"Teknik gösterge alınamadı. Detay: {e}"}

@tool
def get_atr_value(symbol_and_timeframe: str) -> dict:
    """
    Belirtilen sembol ve zaman aralığı için ATR (Average True Range) değerini hesaplar
    ve sonucu bir SÖZLÜK (dictionary) olarak döndürür.
    """
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
        return {"status": "error", "message": f"ATR alınamadı. Detay: {e}"}

def get_top_gainers_losers(top_n: int = 5) -> list:
    """
    Binance Futures piyasasındaki 24 saatlik değişime göre en çok değer kazanan ve kaybeden
    ilk 'top_n' adet coini TEK BİR API ÇAĞRISI ile verimli bir şekilde alır.
    """
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return []
    try:
        all_tickers_data = exchange.fapiPublicGetTicker24hr()
        if not all_tickers_data: return []
        processed_tickers = []
        for ticker in all_tickers_data:
            symbol = ticker.get('symbol')
            if not symbol or not symbol.endswith('USDT'): continue
            price_change_percent = ticker.get('priceChangePercent')
            last_price = ticker.get('lastPrice')
            if price_change_percent is not None and last_price is not None:
                try:
                    processed_tickers.append({
                        'symbol': _get_unified_symbol(symbol),
                        'percentage': float(price_change_percent),
                        'price': float(last_price)
                    })
                except (ValueError, TypeError): continue
        if not processed_tickers: return []
        processed_tickers.sort(key=lambda item: item['percentage'], reverse=True)
        return processed_tickers[:top_n] + processed_tickers[-top_n:]
    except Exception as e:
        logging.error(f"Gainer/Loser listesi alınırken hata: {e}")
        return []

@tool
def execute_trade_order(symbol: str, side: str, amount: float, price: float = None, stop_loss: float = None, take_profit: float = None, leverage: float = None) -> str:
    """Alım/satım emri gönderir. SL/TP emirlerini bekleme yapmadan hemen arkasından gönderir."""
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
def get_open_positions_from_exchange(tool_input: str = "") -> list:
    """Borsadaki mevcut açık vadeli işlem pozisyonlarını çeker."""
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return []
    try:
        all_positions = exchange.fetch_positions(params={'type': config.DEFAULT_MARKET_TYPE})
        return [p for p in all_positions if p.get('contracts') and float(p['contracts']) != 0]
    except Exception as e:
        logging.error(f"Borsadan pozisyonlar alınırken hata oluştu: {e}")
        return []