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
from distutils.util import strtobool

import config

# ... (Dosyanın üst kısmı aynı, değişiklik yok) ...
load_dotenv()
exchange = None
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_exchange(market_type: str = "spot"):
    """Global borsa nesnesini, belirtilen piyasa türü için ayarlar."""
    global exchange
    use_testnet = strtobool(os.getenv("USE_TESTNET", "False"))
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    if not api_key or not secret_key:
        logging.critical("API anahtarları .env dosyasında bulunamadı! Program sonlandırılıyor.")
        exit()
    config_data = {
        "apiKey": api_key, "secret": secret_key,
        "options": {"defaultType": market_type.lower()},
    }
    if use_testnet:
        logging.warning("--- BINANCE TESTNET KULLANILIYOR ---")
        config_data["options"]["test"] = True
    exchange = ccxt.binance(config_data)
    try:
        exchange.load_markets()
        logging.info(f"--- Piyasalar, '{market_type.upper()}' pazarı için başarıyla yüklendi. ---")
    except Exception as e:
        logging.critical(f"'{market_type.upper()}' piyasaları yüklenirken kritik hata: {e}")
        exchange = None
        exit()

def _get_unified_symbol(symbol_input: str) -> str:
    """Her türlü kullanıcı girdisini ('BTC', 'BTC/USDT') standart formata dönüştürür."""
    # ... (Değişiklik yok) ...
    if not isinstance(symbol_input, str):
        raise TypeError("Sembol girdisi bir metin (string) olmalıdır.")
    cleaned_input = symbol_input.strip().strip("'\"")
    unified_symbol = cleaned_input.upper().split(':')[0]
    if '/' in unified_symbol:
        return unified_symbol
    if unified_symbol.endswith('USDT'):
        base = unified_symbol[:-4]
        return f"{base}/USDT"
    return f"{unified_symbol}/USDT"

def _parse_symbol_timeframe_input(input_str: str) -> (str, str):
    """Girdiden sembol ve zaman aralığını ayrıştırır."""
    # ... (Değişiklik yok) ...
    timeframe = "1h"
    symbol = input_str
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    processed_str = input_str.replace('-', ',').replace(' ', ',')
    if ',' in processed_str:
        parts = [p.strip() for p in processed_str.split(',')]
        symbol = parts[0]
        if len(parts) > 1:
            potential_tf = parts[1]
            if potential_tf.upper() == '1M':
                timeframe = '1M'
            elif potential_tf.lower() in valid_timeframes:
                timeframe = potential_tf.lower()
    return symbol, timeframe

@tool
def get_market_price(symbol: str) -> str:
    """Belirtilen kripto para biriminin anlık piyasa fiyatını alır."""
    # ... (Değişiklik yok) ...
    if not exchange: return "HATA: Borsa bağlantısı başlatılmamış."
    try:
        unified_symbol = _get_unified_symbol(symbol)
        ticker = exchange.fetch_ticker(unified_symbol)
        price = ticker.get("last")
        return f"{unified_symbol} için anlık piyasa fiyatı: {price}" if price is not None else f"HATA: {unified_symbol} için fiyat bilgisi alınamadı."
    except Exception as e:
        logging.error(f"Fiyat alınırken hata oluştu ({symbol} -> {unified_symbol}): {e}")
        return f"HATA: Fiyat alınamadı. Sembol: '{unified_symbol}'. Hata: {e}"


@tool
def get_technical_indicators(symbol_and_timeframe: str) -> dict:
    """
    Belirtilen sembol ve zaman aralığı için teknik göstergeleri hesaplar
    ve sonuçları bir SÖZLÜK (dictionary) olarak döndürür.
    """
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    try:
        symbol, timeframe = _parse_symbol_timeframe_input(symbol_and_timeframe)
        unified_symbol = _get_unified_symbol(symbol)
        
        # === DEĞİŞİKLİK BURADA ===
        # Daha fazla geçmiş veri talep ederek NaN hatası alma olasılığını azaltıyoruz.
        bars = exchange.fetch_ohlcv(unified_symbol, timeframe=timeframe, limit=200)
        
        # İndikatörlerin en uzunu ~26 periyotluk olduğu için en az 50 mum verisi olmasını kontrol edelim.
        if not bars or len(bars) < 50:
            raise ValueError(f"İndikatör hesaplaması için yetersiz veri ({len(bars)} mum).")
        
        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        df.ta.rsi(append=True)
        df.ta.macd(append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.stoch(append=True)
        df.ta.adx(append=True)

        last_row = df.iloc[-1]
        
        indicators = {
            "rsi": last_row.get('RSI_14'),
            "macd_line": last_row.get('MACD_12_26_9'),
            "macd_signal": last_row.get('MACDs_12_26_9'),
            "bband_lower": last_row.get('BBL_20_2.0'),
            "bband_middle": last_row.get('BBM_20_2.0'),
            "bband_upper": last_row.get('BBU_20_2.0'),
            "stoch_k": last_row.get('STOCHk_14_3_3'),
            "stoch_d": last_row.get('STOCHd_14_3_3'),
            "adx": last_row.get('ADX_14')
        }

        if any(value is None or pd.isna(value) for value in indicators.values()):
            # Bu uyarı hala görünebilir, ancak artık daha az sıklıkta olmalı.
            logging.warning(f"{unified_symbol} için indikatör hesaplaması 'NaN' sonucu verdi. Muhtemelen coinin geçmişi yetersiz.")
            return {"status": "error", "message": f"{unified_symbol} için indikatör hesaplanamadı (NaN)."}

        return {"status": "success", "data": indicators}

    except Exception as e:
        logging.error(f"Teknik göstergeler hesaplanırken hata oluştu ({symbol_and_timeframe}): {e}")
        return {"status": "error", "message": f"Teknik gösterge alınamadı. Detay: {e}"}

@tool
def get_atr_value(symbol_and_timeframe: str) -> dict:
    """
    Belirtilen sembol ve zaman aralığı için ATR (Average True Range) değerini hesaplar
    ve sonucu bir SÖZLÜK (dictionary) olarak döndürür.
    """
    # ... (Bu fonksiyonda da limiti artıralım) ...
    if not exchange: return {"status": "error", "message": "Borsa bağlantısı başlatılmamış."}
    try:
        symbol, timeframe = _parse_symbol_timeframe_input(symbol_and_timeframe)
        unified_symbol = _get_unified_symbol(symbol)
        
        bars = exchange.fetch_ohlcv(unified_symbol, timeframe=timeframe, limit=200) # Limit artırıldı
        if not bars or len(bars) < 20: # ATR için daha az veri yeterli
             raise ValueError(f"ATR için yetersiz veri ({len(bars)} mum).")

        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col])
        
        atr = df.ta.atr()
        if atr is None or atr.empty: raise ValueError("ATR hesaplaması başarısız oldu.")
        
        last_atr = atr.iloc[-1]
        if pd.isna(last_atr): raise ValueError("Hesaplanan ATR değeri NaN.")

        return {"status": "success", "value": last_atr}
    except Exception as e:
        logging.error(f"ATR değeri hesaplanırken hata oluştu ({symbol_and_timeframe}): {e}")
        return {"status": "error", "message": f"ATR alınamadı. Detay: {e}"}

# --- Dosyanın geri kalanı aynı kalabilir ---

def get_top_gainers_losers(top_n: int = 5) -> list:
    """
    Binance Futures piyasasındaki en çok değer kazanan ve kaybeden coinleri alır.
    """
    # ... (Değişiklik yok) ...
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future':
        logging.error("HATA: Gainer/Loser fonksiyonu sadece 'future' piyasası modunda çalışır.")
        return [] 
    
    logging.info(f"Binance Futures Gainer/Loser listesi ve tüm fiyatlar çekiliyor (Top {top_n})...")
    logging.warning("Mevcut 'get_top_gainers_losers' metodu tüm ticker'ları çektiği için verimsizdir. API limitlerini etkileyebilir.")
    try:
        all_tickers = exchange.fetch_tickers()
        if not all_tickers:
            logging.warning("API'den hiç ticker verisi alınamadı.")
            return []
        processed_tickers = []
        for symbol, ticker in all_tickers.items():
            unified_symbol = symbol.split(':')[0]
            if not unified_symbol.endswith('/USDT'):
                continue
            raw_percentage = ticker.get('info', {}).get('priceChangePercent')
            price = ticker.get('last')
            if raw_percentage is not None and price is not None:
                try:
                    percentage = float(raw_percentage)
                    processed_tickers.append({'symbol': unified_symbol, 'percentage': percentage, 'price': float(price)})
                except (ValueError, TypeError):
                    continue
        if not processed_tickers:
            logging.error("İşlenebilecek formatta (priceChangePercent) bir veri bulunamadı.")
            return []
        processed_tickers.sort(key=lambda item: item['percentage'], reverse=True)
        gainers = processed_tickers[:top_n]
        losers = processed_tickers[-top_n:]
        return gainers + losers
    except Exception as e:
        logging.error(f"Gainer/Loser listesi alınırken kritik hata oluştu: {e}", exc_info=True)
        return []

@tool
def execute_trade_order(symbol: str, side: str, amount: float, price: float = None, stop_loss: float = None, take_profit: float = None, leverage: float = None) -> str:
    """Alım/satım emri gönderir. SL/TP emirlerini bekleme yapmadan hemen arkasından gönderir."""
    # ... (Değişiklik yok) ...
    if not exchange:
        return "HATA: Borsa bağlantısı başlatılmamış."

    unified_symbol = _get_unified_symbol(symbol)
    formatted_amount = exchange.amount_to_precision(unified_symbol, amount)

    if not config.LIVE_TRADING:
        logging.info(f"--- İŞLEM SİMÜLASYONU: Sembol={symbol}, Yön={side}, Miktar={formatted_amount}, Fiyat={price}, SL={stop_loss}, TP={take_profit} ---")
        return f"Simülasyon emri başarılı: {side} {formatted_amount} {unified_symbol}"

    logging.warning(f"🔥🔥🔥 CANLI İŞLEM BAŞLATILIYOR: {unified_symbol} | {side.upper()} | {formatted_amount} 🔥🔥🔥")
    try:
        if leverage and exchange.options.get('defaultType') == 'future':
            logging.info(f"Kaldıraç ayarlanıyor: {int(leverage)}x, Sembol: {unified_symbol}")
            exchange.set_leverage(int(leverage), unified_symbol)
        
        if price:
            logging.info(f"Limit Emir Gönderiliyor: Miktar={formatted_amount}, Fiyat={price}")
            order = exchange.create_limit_order(unified_symbol, side, formatted_amount, price)
        else:
            logging.info(f"Piyasa Emri Gönderiliyor: Miktar={formatted_amount}")
            order = exchange.create_market_order(unified_symbol, side, formatted_amount)
        
        logging.info(f"+++ CANLI GİRİŞ EMRİ BAŞARILI: {order['id']} +++")
        
        if stop_loss and take_profit:
            opposite_side = 'sell' if side == 'buy' else 'buy'
            try:
                sl_params = {'stopPrice': stop_loss, 'reduceOnly': True}
                exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, formatted_amount, None, sl_params)
                logging.info(f"+++ ZARAR DURDUR (SL) EMRİ BAŞARILI: {stop_loss} +++")
            except Exception as sl_e:
                logging.error(f"--- HATA: SL EMRİ GÖNDERİLEMEDİ: {sl_e} ---")
            
            try:
                tp_params = {'stopPrice': take_profit, 'reduceOnly': True}
                exchange.create_order(unified_symbol, 'TAKE_PROFIT_MARKET', opposite_side, formatted_amount, None, tp_params)
                logging.info(f"+++ KAR AL (TP) EMRİ BAŞARILI: {take_profit} +++")
            except Exception as tp_e:
                logging.error(f"--- HATA: TP EMRİ GÖNDERİLEMEDİ: {tp_e} ---")
        
        return f"Giriş emri ({side} {formatted_amount} {unified_symbol}) başarıyla gönderildi."
    except Exception as e:
        logging.error(f"İşlem sırasında beklenmedik bir hata oluştu ({symbol}): {e}", exc_info=True)
        return f"HATA: İşlem sırasında beklenmedik bir hata oluştu: {e}"

@tool
def get_open_positions_from_exchange(tool_input: str = "") -> list:
    """Borsadaki mevcut açık vadeli işlem pozisyonlarını çeker."""
    # ... (Değişiklik yok) ...
    if not exchange or config.DEFAULT_MARKET_TYPE != 'future': return []
    try:
        params = {'type': config.DEFAULT_MARKET_TYPE}
        all_positions = exchange.fetch_positions(params=params)
        open_positions = [p for p in all_positions if p.get('contracts') is not None and float(p.get('contracts')) != 0]
        return open_positions
    except Exception as e:
        logging.error(f"Borsadan pozisyonlar alınırken hata oluştu: {e}")
        return []

@tool
def get_open_orders(symbol: str) -> list:
    """Belirtilen bir sembol için borsadaki mevcut açık emirleri (SL/TP dahil) çeker."""
    # ... (Değişiklik yok) ...
    if not exchange:
        logging.error("get_open_orders: Borsa bağlantısı başlatılmamış.")
        return []
    try:
        unified_symbol = _get_unified_symbol(symbol)
        open_orders = exchange.fetch_open_orders(unified_symbol)
        simplified_orders = []
        for order in open_orders:
            simplified_orders.append({
                'id': order.get('id'),
                'type': order.get('type', '').lower(),
                'side': order.get('side'),
                'price': order.get('price'),
                'stopPrice': order.get('stopPrice'),
                'amount': order.get('amount')
            })
        return simplified_orders
    except Exception as e:
        logging.error(f"Açık emirler alınırken hata oluştu ({symbol}): {e}")
        return []

@tool
def update_sl_tp_orders(symbol: str, side: str, amount: float, new_stop_loss: float = None, new_take_profit: float = None) -> str:
    """Bir pozisyon için mevcut SL/TP emirlerini iptal eder ve yenilerini oluşturur."""
    # ... (Değişiklik yok) ...
    if not exchange or not config.LIVE_TRADING:
        return "HATA: Bu araç sadece canlı işlem modunda çalışır."
    
    logging.info(f"--- SL/TP GÜNCELLEME SÜRECİ BAŞLATILDI: {symbol} ---")
    unified_symbol = _get_unified_symbol(symbol)
    try:
        open_orders = exchange.fetch_open_orders(unified_symbol)
        stop_orders = [o for o in open_orders if o.get('type') in ['stop_market', 'take_profit_market']]
        
        for order in stop_orders:
            try:
                exchange.cancel_order(order['id'], unified_symbol)
                logging.info(f"Mevcut {order.get('type')} emri ({order['id']}) iptal edildi.")
            except Exception as e:
                logging.error(f"Emir ({order['id']}) iptal edilirken hata: {e}")
        
        opposite_side = 'sell' if side == 'buy' else 'buy'
        formatted_amount = exchange.amount_to_precision(unified_symbol, amount)
        
        if new_stop_loss and new_stop_loss > 0:
            params_sl = {'stopPrice': new_stop_loss, 'reduceOnly': True}
            exchange.create_order(unified_symbol, 'STOP_MARKET', opposite_side, formatted_amount, None, params_sl)
            logging.info(f"+++ YENİ ZARAR DURDUR (SL) EMRİ AYARLANDI: {new_stop_loss} +++")
        
        if new_take_profit and new_take_profit > 0:
            params_tp = {'stopPrice': new_take_profit, 'reduceOnly': True}
            exchange.create_order(unified_symbol, 'TAKE_PROFIT_MARKET', opposite_side, formatted_amount, None, params_tp)
            logging.info(f"+++ YENİ KAR AL (TP) EMRİ AYARLANDI: {new_take_profit} +++")
            
        return "SL/TP emirleri başarıyla güncellendi."
    except Exception as e:
        logging.critical(f"SL/TP güncellenirken kritik bir hata oluştu: {e}")
        return f"HATA: SL/TP güncellenemedi. Manuel kontrol gerekebilir! Detay: {e}"