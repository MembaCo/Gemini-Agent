# main.py (HABER ANALİZİ EKLENMİŞ TAM SÜRÜM)
# @author: Memba Co.

import os
import json
import time
import threading
import logging
import subprocess
import sys
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

# GÜNCELLENDİ: Yeni haber aracı import edildi
from tools import (
    get_market_price, get_technical_indicators, execute_trade_order,
    initialize_exchange, get_open_positions_from_exchange, get_atr_value,
    _get_unified_symbol, get_top_gainers_losers, _fetch_price_natively,
    str_to_bool, get_wallet_balance, update_stop_loss_order,
    cancel_all_open_orders, get_funding_rate, get_order_book_depth, calculate_pnl,
    get_latest_news # <--- YENİ ARAÇ
)
import config
import database
from notifications import send_telegram_message, format_open_position_message, format_close_position_message, format_partial_tp_message

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "Gemini Trading Agent")

BLACKLISTED_SYMBOLS = {}

try:
    llm = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, temperature=0.1)
    # GÜNCELLENDİ: Ajanın araç listesine yeni fonksiyonlar eklendi
    agent_tools = [get_market_price, get_technical_indicators, get_funding_rate, get_order_book_depth, get_latest_news]
    prompt_template = hub.pull("hwchase17/react")
    agent = create_react_agent(llm=llm, tools=agent_tools, prompt=prompt_template)
    agent_executor = AgentExecutor(
        agent=agent, tools=agent_tools, verbose=str_to_bool(os.getenv("AGENT_VERBOSE", "True")),
        handle_parsing_errors="Lütfen JSON formatında geçerli bir yanıt ver.",
        max_iterations=8 # Haber analizi için bir iterasyon daha eklendi
    )
except Exception as e:
    logging.critical(f"LLM veya Agent başlatılırken hata oluştu: {e}")
    exit()

# GÜNCELLENDİ: Prompt artık haber verilerini de alıyor ve işliyor
def create_mta_analysis_prompt(symbol: str, price: float, entry_timeframe: str, entry_indicators: dict, trend_timeframe: str, trend_indicators: dict, market_sentiment: dict, news_data: str) -> str:
    entry_indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in entry_indicators.items()])
    trend_indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in trend_indicators.items()])
    sentiment_text = "\n".join([f"- {key}: {value}" for key, value in market_sentiment.items()])

    # GÜNCELLENDİ: Haber analizi kapalıysa prompt'ta ilgili bölümü gösterme
    news_section = f"""
    ### Temel Analiz (Son Haberler)
    {news_data}
    """ if config.USE_NEWS_ANALYSIS else ""

    return f"""
    Sen, teknik, temel (haber) ve duyarlılık analizini birleştiren, piyasanın usta analistisin.
    Görevin, sana sunulan tüm verileri sentezleyerek kapsamlı bir analiz yapmak ve net bir ticaret kararı ('AL', 'SAT' veya 'BEKLE') vermektir.

    ## ANALİZ KURALLARI (ÖNCELİK SIRASINA GÖRE):
    1.  **Haberleri Kontrol Et (En Yüksek Öncelik):** Eğer haber verisi sunulduysa, ilk olarak haber başlıklarına bak. Piyasayı olumsuz etkileyebilecek (FUD, hack, regülasyon vb.) net bir haber varsa, diğer tüm göstergeler olumlu olsa bile kararını 'BEKLE' olarak ver.
    2.  **Piyasa Duyarlılığını Değerlendir:** Fonlama Oranı ve Emir Defteri verilerine bakarak genel piyasa duyarlılığını anla.
    3.  **Ana Trendi Belirle:** '{trend_timeframe}' zaman aralığındaki verilere bakarak ana trendin yönünü belirle.
    4.  **Sinyali Teyit Et:** '{entry_timeframe}' zaman aralığındaki giriş sinyalini, önceki adımlardaki tüm verilerle teyit et. Veriler arasında çelişki varsa 'BEKLE'.
    5.  **Gerekçeni Açıkla:** Kararının arkasındaki mantığı, tüm veri setlerinden bahsederek kısaca açıkla.

    ## SAĞLANAN VERİLER:
    - Sembol: {symbol}
    - Anlık Fiyat: {price}
    {news_section}
    ### Piyasa Duyarlılığı Verileri
    {sentiment_text}
    ### Ana Trend Verileri ({trend_timeframe})
    {trend_indicator_text}
    ### Giriş Sinyali Verileri ({entry_timeframe})
    {entry_indicator_text}

    ## İSTENEN JSON ÇIKTI FORMATI:
    ```json
    {{
      "symbol": "{symbol}",
      "timeframe": "{entry_timeframe}",
      "recommendation": "KARARIN (AL, SAT, veya BEKLE)",
      "reason": "Tüm analizlere dayalı kısa ve net gerekçen.",
      "analysis_type": "MTA_Sentiment_News",
      "trend_timeframe": "{trend_timeframe}",
      "data": {{
        "price": {price}
      }}
    }}
    ```
    """

# GÜNCELLENDİ: Bu prompt da artık haber verilerini işliyor
def create_final_analysis_prompt(symbol: str, timeframe: str, price: float, indicators: dict, market_sentiment: dict, news_data: str) -> str:
    indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in indicators.items()])
    sentiment_text = "\n".join([f"- {key}: {value}" for key, value in market_sentiment.items()])

    return f"""
    Sen, uzman bir trading analistisin. Analiz yaparken teknik göstergelerle birlikte temel (haber) ve piyasa duyarlılığı verilerini de dikkate al.
    Aşağıda sana '{symbol}' adlı kripto para için '{timeframe}' zaman aralığında toplanmış veriler sunulmuştur.
    
    GÖREVİN: Önce haberleri kontrol et. Olumsuz bir haber varsa, diğer veriler ne olursa olsun 'BEKLE' de. Haberler nötr veya olumluysa, diğer verileri analiz ederek 'AL', 'SAT' veya 'BEKLE' şeklinde net bir tavsiye kararı ver.
    Kararını ve gerekçeni, aşağıda formatı verilen JSON çıktısı olarak sun. Başka hiçbir açıklama yapma.
    
    SAĞLANAN VERİLER:
    - Anlık Fiyat: {price}

    Temel Analiz (Son Haberler):
    {news_data}
    
    Piyasa Duyarlılığı:
    {sentiment_text}
    
    Teknik Göstergeler:
    {indicator_text}
    
    İSTENEN JSON ÇIKTI FORMATI:
    ```json
    {{
      "symbol": "{symbol}",
      "timeframe": "{timeframe}",
      "recommendation": "KARARIN (AL, SAT, veya BEKLE)",
      "reason": "Kararının kısa ve net gerekçesi (haberleri ve piyasa duyarlılığını da dikkate alarak).",
      "analysis_type": "Single_Sentiment_News",
      "data": {{
        "price": {price}
      }}
    }}
    ```
    """

# GÜNCELLENDİ: Bu prompt da artık ajanı haberleri kontrol etmeye yönlendiriyor
def create_reanalysis_prompt(position: dict) -> str:
    symbol = position.get("symbol")
    timeframe = position.get("timeframe")
    side = position.get("side", "").upper()
    entry_price = position.get("entry_price")
    
    return f"""
    Sen, tecrübeli bir pozisyon yöneticisisin.
    ## Mevcut Pozisyon Bilgileri:
    - Sembol: {symbol}
    - Yön: {side}
    - Giriş Fiyatı: {entry_price}
    - Analiz Zaman Aralığı: {timeframe}

    ## Görevin:
    Bu pozisyonun mevcut durumunu, en son haberleri, piyasa duyarlılığını ve teknik göstergeleri kullanarak yeniden değerlendir. Ardından, pozisyon için 'TUT' (Hold) veya 'KAPAT' (Close) şeklinde net bir tavsiye ver.
    Unutma, olumsuz bir haber varsa pozisyonu kapatmak genellikle en güvenli yoldur.

    ## Nihai Rapor Formatı:
    Kararını ve gerekçeni içeren bir JSON nesnesi döndür.
    Örnek: {{"recommendation": "KAPAT", "reason": "Fiyat giriş seviyesinin üzerine çıktı ve RSI aşırı alım sinyali veriyor, ancak olumsuz bir regülasyon haberi çıktı. Riski ortadan kaldırmak için pozisyon kapatılmalı."}}
    """

def parse_agent_response(response: str) -> dict | None:
    if not response or not isinstance(response, str):
        return None
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())
    except (json.JSONDecodeError, IndexError):
        logging.error(f"JSON ayrıştırma hatası. Gelen Yanıt: {response}")
        return None

def check_and_manage_positions():
    """
    Tüm açık pozisyonları tek bir API çağrısıyla çeker ve yönetir.
    Bu yöntem, her pozisyon için ayrı fiyat sorgusu yapmaktan daha verimli ve güvenilirdir.
    """
    exchange_positions_raw = get_open_positions_from_exchange.invoke({})
    if not isinstance(exchange_positions_raw, list):
        logging.error(f"Borsadan pozisyonlar alınamadı, dönen veri: {exchange_positions_raw}")
        return
        
    exchange_positions_map = {_get_unified_symbol(p.get('symbol')): p for p in exchange_positions_raw}
    
    db_positions = database.get_all_positions()
    db_positions_map = {p['symbol']: p for p in db_positions}

    for symbol, db_pos in list(db_positions_map.items()):
        exchange_pos = exchange_positions_map.get(symbol)

        if not exchange_pos:
            logging.warning(f"Pozisyon '{symbol}' veritabanında var ama borsada yok. Veritabanından siliniyor.")
            database.remove_position(symbol)
            continue

        try:
            current_price_str = exchange_pos.get('markPrice')
            if not current_price_str:
                logging.warning(f"'{symbol}' için pozisyon verisinden 'markPrice' alınamadı, atlanıyor.")
                continue
            
            current_price = float(current_price_str)
            
            side = db_pos.get("side")
            sl_price = db_pos.get("stop_loss", 0.0)
            tp_price = db_pos.get("take_profit", 0.0)
            
            close_reason = None
            if sl_price > 0 and ( (side == "buy" and current_price <= sl_price) or (side == "sell" and current_price >= sl_price) ):
                close_reason = "SL"
            elif tp_price > 0 and ( (side == "buy" and current_price >= tp_price) or (side == "sell" and current_price <= tp_price) ):
                close_reason = "TP"
            
            if close_reason:
                logging.info(f"\n[AUTO] POZİSYON HEDEFE ULAŞTI ({close_reason}): {symbol} @ {current_price}")
                db_pos['close_price'] = current_price
                handle_manual_close(db_pos, from_auto=True, close_reason=close_reason)
                continue

            if config.USE_PARTIAL_TP and not db_pos.get('partial_tp_executed'):
                initial_sl = db_pos.get('initial_stop_loss')
                entry_price = db_pos.get('entry_price')
                
                if initial_sl and entry_price:
                    risk_distance = abs(entry_price - initial_sl)
                    partial_tp_price = entry_price + (risk_distance * config.PARTIAL_TP_TARGET_RR) if side == 'buy' else entry_price - (risk_distance * config.PARTIAL_TP_TARGET_RR)
                    
                    if (side == 'buy' and current_price >= partial_tp_price) or (side == 'sell' and current_price <= partial_tp_price):
                        logging.info(f"\n[PARTIAL-TP] {symbol} için kısmi kâr alma hedefi {partial_tp_price:.4f} ulaşıldı.")
                        
                        initial_amount = db_pos.get('initial_amount') or db_pos.get('amount')
                        amount_to_close = initial_amount * (config.PARTIAL_TP_CLOSE_PERCENT / 100)
                        remaining_amount = db_pos['amount'] - amount_to_close
                        
                        if remaining_amount > 0:
                            close_side = 'sell' if side == 'buy' else 'buy'
                            result_str = execute_trade_order.invoke({"symbol": symbol, "side": close_side, "amount": amount_to_close})
                            
                            if "başarı" in result_str.lower() or "simülasyon" in result_str.lower():
                                logging.info(f"Kısmi kâr alma başarılı: {amount_to_close:.4f} {symbol} kapatıldı.")
                                new_sl_price = entry_price
                                sl_update_result = update_stop_loss_order.invoke({"symbol": symbol, "side": side, "amount": remaining_amount, "new_stop_price": new_sl_price})
                                logging.info(f"Kalan pozisyon için SL girişe çekildi: {sl_update_result}")
                                database.update_position_after_partial_tp(symbol, remaining_amount, new_sl_price)
                                message = format_partial_tp_message(symbol, amount_to_close, remaining_amount, entry_price)
                                send_telegram_message(message)
                                continue
                            else:
                                logging.error(f"Kısmi kâr alma sırasında pozisyon kapatılamadı: {result_str}")

            if config.USE_TRAILING_STOP_LOSS:
                entry_price = db_pos.get("entry_price", 0.0)
                initial_sl = db_pos.get('initial_stop_loss')
                if not initial_sl: continue
                
                profit_perc = ((current_price - entry_price) / entry_price) * 100 * (1 if side == 'buy' else -1)
                
                if profit_perc > config.TRAILING_STOP_ACTIVATION_PERCENT:
                    original_sl_distance = abs(entry_price - initial_sl)
                    new_sl = 0.0
                    if side == 'buy' and (new_sl_candidate := current_price - original_sl_distance) > sl_price:
                        new_sl = new_sl_candidate
                    elif side == 'sell' and (new_sl_candidate := current_price + original_sl_distance) < sl_price:
                        new_sl = new_sl_candidate

                    if new_sl > 0:
                        logging.info(f"[TRAIL-SL] {symbol} için yeni SL tetiklendi: {sl_price:.4f} -> {new_sl:.4f}")
                        result = update_stop_loss_order.invoke({"symbol": symbol, "side": side, "amount": db_pos['amount'], "new_stop_price": new_sl})
                        if "Başarılı" in result or "Simülasyon" in result:
                            database.update_position_sl(symbol, new_sl)
        except Exception as e:
            logging.error(f"Pozisyon kontrolü sırasında hata: {e} - Pozisyon: {db_pos}", exc_info=True)


def background_position_checker():
    logging.info("--- Arka plan pozisyon kontrolcüsü başlatıldı. ---")
    while True:
        try:
            check_and_manage_positions()
        except Exception as e:
            logging.critical(f"Arka plan kontrolcüsünde KRİTİK HATA: {e}", exc_info=True)
        time.sleep(config.POSITION_CHECK_INTERVAL_SECONDS)

def handle_trade_confirmation(recommendation, trade_symbol, current_price, timeframe, auto_confirm=False):
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        logging.error("Geçersiz fiyat bilgisi, işlem iptal edildi.")
        return

    prompt_message = f">>> [FIRSAT] {trade_symbol} @ {current_price:.4f} için '{recommendation}' tavsiyesi verildi. İşlem açılsın mı? (e/h): "
    user_onay = "e" if auto_confirm else input(prompt_message).lower()
    
    if user_onay == "e":
        if auto_confirm: logging.info(f"İşlem otomatik olarak onaylandı: {trade_symbol}")
        try:
            active_positions = database.get_all_positions()
            if len(active_positions) >= config.MAX_CONCURRENT_TRADES:
                print("\n### UYARI: Maksimum pozisyon limitine ulaşıldı. ###"); return

            trade_side = "buy" if "AL" in recommendation else "sell"
            
            atr_result = get_atr_value.invoke({"symbol_and_timeframe": f"{trade_symbol},{timeframe}"})
            if atr_result.get("status") != "success":
                print(f"### HATA: ATR değeri alınamadı: {atr_result.get('message')} ###"); return
            
            atr_value = atr_result['value']
            sl_distance = atr_value * config.ATR_MULTIPLIER_SL
            stop_loss_price = current_price - sl_distance if trade_side == "buy" else current_price + sl_distance

            balance_result = get_wallet_balance.invoke({})
            if balance_result.get("status") != "success":
                print(f"### HATA: Cüzdan bakiyesi alınamadı: {balance_result.get('message')} ###"); return
            wallet_balance = balance_result.get('balance', 0.0)

            risk_amount_usd = wallet_balance * (config.RISK_PER_TRADE_PERCENT / 100)
            sl_price_diff = abs(current_price - stop_loss_price)
            if sl_price_diff <= 0:
                print(f"HATA: Stop-loss mesafesi geçersiz ({sl_price_diff}), pozisyon açılamıyor."); return
            
            trade_amount = risk_amount_usd / sl_price_diff
            notional_value = trade_amount * current_price
            required_margin = notional_value / config.LEVERAGE

            logging.info(f"Dinamik Pozisyon Hesabı: Bakiye={wallet_balance:.2f} USDT, Risk={risk_amount_usd:.2f} USDT, Pozisyon Büyüklüğü={notional_value:.2f} USDT, Gerekli Marjin={required_margin:.2f} USDT")

            if required_margin > wallet_balance:
                print(f"### UYARI: Gerekli marjin ({required_margin:.2f} USDT) mevcut bakiyeden ({wallet_balance:.2f} USDT) fazla. İşlem iptal edildi."); return

            tp_distance = sl_distance * config.RISK_REWARD_RATIO_TP
            take_profit_price = current_price + tp_distance if trade_side == "buy" else current_price - tp_distance
            
            position_to_open = {
                "symbol": trade_symbol, "side": trade_side, "amount": trade_amount, 
                "stop_loss": stop_loss_price, "take_profit": take_profit_price, "leverage": config.LEVERAGE,
                "price": current_price if config.DEFAULT_ORDER_TYPE == 'LIMIT' else None
            }
            
            result_str = execute_trade_order.invoke(position_to_open)
            print(f"İşlem Sonucu: {result_str}")

            if "başarı" in result_str.lower() or "simülasyon" in result_str.lower():
                final_entry_price = position_to_open.get('price') or current_price
                managed_position_details = {
                    "symbol": trade_symbol, "side": trade_side, "amount": trade_amount, 
                    "entry_price": final_entry_price, "timeframe": timeframe, "leverage": config.LEVERAGE,
                    "stop_loss": stop_loss_price, "take_profit": take_profit_price
                }
                database.add_position(managed_position_details)
                print("\n+++ YENİ POZİSYON AÇILDI VE VERİTABANINA KAYDEDİLDİ +++")
                print(json.dumps(managed_position_details, indent=2))
                message = format_open_position_message(managed_position_details)
                send_telegram_message(message)
            else:
                print(f"\n--- İŞLEM BAŞARISIZ OLDU. Dönen Mesaj: {result_str} ---")
        except Exception as e:
            logging.error(f"İşlem hazırlığı sırasında bir hata oluştu: {e}", exc_info=True)

def sync_and_display_positions():
    """Borsa ile veritabanını senkronize eder ve pozisyonları listeler."""
    print("\n--- Pozisyonlar Görüntüleniyor... ---")
    
    if not config.LIVE_TRADING:
        active_positions_db = database.get_all_positions()
        print("--- SİMÜLASYON MODU AKTİF ---")
        if not active_positions_db:
            print("Bot tarafından yönetilen simüle edilmiş pozisyon bulunmuyor.")
        else:
            print(f"--- Bot Veritabanındaki Simüle Pozisyonlar: {len(active_positions_db)} ---")
            for pos in active_positions_db:
                pnl_info = "| PNL Hesaplanamadı"
                current_price = _fetch_price_natively(pos['symbol'])
                if current_price is not None:
                    entry_price = pos.get('entry_price', 0); amount = pos.get('amount', 0); side = pos.get('side', 'buy')
                    pnl = calculate_pnl(side, entry_price, current_price, amount)
                    margin = (entry_price * amount) / pos.get('leverage', 1) if pos.get('leverage', 1) > 0 else 0
                    pnl_percentage = (pnl / margin) * 100 if margin > 0 else 0
                    pnl_status = "⬆️ KAR" if pnl >= 0 else "⬇️ ZARAR"
                    pnl_info = f"| PNL (Tahmini): {pnl:+.2f} USDT ({pnl_percentage:+.2f}%) {pnl_status}"
                print(f"  - {pos['symbol']} ({pos['side'].upper()}) | Giriş: {pos.get('entry_price', 0):.4f} | Miktar: {pos.get('amount', 0):.4f} {pnl_info}")
        print("--- Simülasyon gösterimi tamamlandı. ---")
        return

    print("--- CANLI MOD: Borsa ile Senkronize Ediliyor... ---")
    try:
        active_positions_db = database.get_all_positions()
        managed_positions_map = {p['symbol']: p for p in active_positions_db}

        exchange_positions_raw = get_open_positions_from_exchange.invoke({})
        if not isinstance(exchange_positions_raw, list):
            logging.error(f"Borsadan pozisyonlar alınamadı, dönen veri: {exchange_positions_raw}"); return
        exchange_positions_map = {_get_unified_symbol(p.get('symbol')): p for p in exchange_positions_raw}

        for symbol, ex_pos in exchange_positions_map.items():
            if symbol not in managed_positions_map:
                print(f"  - {symbol} borsada açık ama bot tarafından yönetilmiyor.")
                add_to_bot = input(f"      >>> Yönetime eklensin mi? (evet/hayır): ").lower()
                if add_to_bot == 'evet':
                    timeframe = input(f"      >>> Orijinal zaman aralığını girin (örn: 1h, 15m): ").lower().strip() or "1h"
                    leverage = float(ex_pos.get('leverage') or config.LEVERAGE)
                    entry_price = float(ex_pos.get('entryPrice', 0.0) or 0.0)
                    sl_input = input(f"      >>> Stop-Loss fiyatını girin (boş bırakmak için enter): ")
                    tp_input = input(f"      >>> Take-Profit fiyatını girin (boş bırakmak için enter): ")
                    new_pos = { "symbol": symbol, "side": 'buy' if ex_pos.get('side') == 'long' else 'sell', "amount": float(ex_pos.get('contracts', 0.0)), "entry_price": entry_price, "timeframe": timeframe, "leverage": leverage, "stop_loss": float(sl_input) if sl_input else 0.0, "take_profit": float(tp_input) if tp_input else 0.0 }
                    database.add_position(new_pos)
                    print(f"      +++ {symbol} pozisyonu bot yönetimine eklendi.")

        for symbol in list(managed_positions_map.keys()):
            if symbol not in exchange_positions_map:
                logging.warning(f"Pozisyon '{symbol}' veritabanında var ama borsada yok. Veritabanından siliniyor.")
                database.remove_position(symbol)
        
        final_managed_positions = database.get_all_positions()
        final_managed_symbols = {p['symbol'] for p in final_managed_positions}

        if not exchange_positions_map:
             print("Borsada açık pozisyon bulunmuyor.")
        else:
             print(f"--- Borsada Bulunan Açık Pozisyonlar: {len(exchange_positions_map)} ---")
             for symbol, pos_data in exchange_positions_map.items():
                side = 'buy' if pos_data.get('side', 'long') == 'long' else 'sell'
                notional = float(pos_data.get('notional', 0.0) or 0.0)
                pnl = float(pos_data.get('unrealizedPnl', 0.0) or 0.0)
                margin = float(pos_data.get('initialMargin', 0.0) or 0.0)
                pnl_percentage = (pnl / margin) * 100 if margin > 0 else 0
                pnl_status = "⬆️ KAR" if pnl >= 0 else "⬇️ ZARAR"
                is_managed = "✅ Yönetiliyor" if symbol in final_managed_symbols else "❌ Yönetilmiyor"
                print(f"  - {symbol} ({side.upper()}) | Büyüklük: {notional:.2f} USDT | PNL: {pnl:+.2f} USDT ({pnl_percentage:+.2f}%) [{pnl_status}] | {is_managed}")

        print("--- Senkronizasyon tamamlandı. ---")
    except Exception as e:
        logging.error(f"Senkronizasyon sırasında hata oluştu: {e}", exc_info=True)


# GÜNCELLENDİ: Fonksiyon artık haberleri de çekiyor ve prompt'a gönderiyor
def _perform_analysis(symbol: str, entry_tf: str, use_mta: bool, trend_tf: str = None) -> dict | None:
    unified_symbol = _get_unified_symbol(symbol)
    logging.info(f"Analiz başlatılıyor: {unified_symbol} ({'MTA' if use_mta else 'Single'})")
    
    try:
        current_price = _fetch_price_natively(unified_symbol)
        if not current_price:
            logging.error(f"Fiyat alınamadı: {unified_symbol}")
            return None

        # Teknik Veriler
        entry_indicators_result = get_technical_indicators.invoke({"symbol_and_timeframe": f"{unified_symbol},{entry_tf}"})
        if entry_indicators_result.get("status") != "success":
            logging.error(f"{unified_symbol} ({entry_tf}) için teknik veri alınamadı: {entry_indicators_result.get('message')}")
            return None
        entry_indicators_data = entry_indicators_result["data"]
        
        # Duyarlılık Verileri
        market_sentiment_data = {}
        if config.DEFAULT_MARKET_TYPE == 'future':
            funding_rate_str = get_funding_rate.invoke(unified_symbol)
            order_book_str = get_order_book_depth.invoke(unified_symbol)
            market_sentiment_data = {
                "Fonlama Bilgisi": funding_rate_str,
                "Emir Defteri Bilgisi": order_book_str
            }

        # YENİ: Haber verileri sadece ayar aktif ise çekiliyor
        news_data_str = "Haber analizi kapalı."
        if config.USE_NEWS_ANALYSIS:
            logging.info(f"{unified_symbol} için son haberler çekiliyor...")
            news_data_str = get_latest_news.invoke(unified_symbol)
        
        final_prompt = ""
        if use_mta and trend_tf:
            trend_indicators_result = get_technical_indicators.invoke({"symbol_and_timeframe": f"{unified_symbol},{trend_tf}"})
            if trend_indicators_result.get("status") != "success":
                logging.error(f"{unified_symbol} ({trend_tf}) için trend verisi alınamadı: {trend_indicators_result.get('message')}")
                return None
            trend_indicators_data = trend_indicators_result["data"]
            # Not: create_mta_analysis_prompt'un yeni 'news_data_str' argümanını alması gerekiyor
            final_prompt = create_mta_analysis_prompt(unified_symbol, current_price, entry_tf, entry_indicators_data, trend_tf, trend_indicators_data, market_sentiment_data, news_data_str)
        else:
            # Not: create_final_analysis_prompt'un da güncellenmesi gerekir
            # Şimdilik MTA odaklı devam ediyoruz
            final_prompt = create_final_analysis_prompt(unified_symbol, entry_tf, current_price, entry_indicators_data, market_sentiment_data, news_data_str)

        logging.info(f"Yapay zeka analizi için {unified_symbol} gönderiliyor...")
        result = llm.invoke(final_prompt)
        parsed_data = parse_agent_response(result.content)

        if not parsed_data:
            logging.error(f"Yapay zekadan {unified_symbol} için geçerli yanıt alınamadı. Yanıt: {result.content}")
            return None
        
        parsed_data['current_price'] = current_price
        return parsed_data

    except Exception as e:
        logging.critical(f"Analiz sırasında kritik hata ({unified_symbol}): {e}", exc_info=True)
        return None

def create_final_analysis_prompt(symbol: str, timeframe: str, price: float, indicators: dict, market_sentiment: dict, news_data: str) -> str:
    indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in indicators.items()])
    sentiment_text = "\n".join([f"- {key}: {value}" for key, value in market_sentiment.items()])
    news_section = f"""
    Temel Analiz (Son Haberler):
    {news_data}
    """ if config.USE_NEWS_ANALYSIS else ""

    return f"""
    Sen, uzman bir trading analistisin. Analiz yaparken teknik göstergelerle birlikte temel (haber) ve piyasa duyarlılığı verilerini de dikkate al.
    Aşağıda sana '{symbol}' adlı kripto para için '{timeframe}' zaman aralığında toplanmış veriler sunulmuştur.
    
    GÖREVİN: Önce haberleri kontrol et (eğer sunulduysa). Olumsuz bir haber varsa, diğer veriler ne olursa olsun 'BEKLE' de. Haberler nötr veya olumluysa, diğer verileri analiz ederek 'AL', 'SAT' veya 'BEKLE' şeklinde net bir tavsiye kararı ver.
    Kararını ve gerekçeni, aşağıda formatı verilen JSON çıktısı olarak sun. Başka hiçbir açıklama yapma.
    
    SAĞLANAN VERİLER:
    - Anlık Fiyat: {price}
    {news_section}
    Piyasa Duyarlılığı:
    {sentiment_text}
    
    Teknik Göstergeler:
    {indicator_text}
    
    İSTENEN JSON ÇIKTI FORMATI:
    ```json
    {{
      "symbol": "{symbol}",
      "timeframe": "{timeframe}",
      "recommendation": "KARARIN (AL, SAT, veya BEKLE)",
      "reason": "Kararının kısa ve net gerekçesi (haberleri ve piyasa duyarlılığını da dikkate alarak).",
      "analysis_type": "Single_Sentiment_News",
      "data": {{
        "price": {price}
      }}
    }}
    ```
    """

def _execute_single_scan_cycle():
    logging.info("--- 🚀 Yeni Proaktif Tarama Döngüsü Başlatılıyor 🚀 ---")
    active_positions = database.get_all_positions()
    if len(active_positions) >= config.MAX_CONCURRENT_TRADES:
        logging.warning(f"Maksimum pozisyon limitine ({config.MAX_CONCURRENT_TRADES}) ulaşıldı. Tarama atlanıyor.")
        return
    open_symbols = {p['symbol'] for p in active_positions}

    now = time.time()
    for symbol, expiry in list(BLACKLISTED_SYMBOLS.items()):
        if now > expiry:
            del BLACKLISTED_SYMBOLS[symbol]
            logging.info(f"{symbol} dinamik kara listeden çıkarıldı.")

    symbols_to_scan = []
    whitelist_symbols = [_get_unified_symbol(s) for s in config.PROACTIVE_SCAN_WHITELIST]
    symbols_to_scan.extend(whitelist_symbols)
    logging.info(f"Beyaz listeden eklendi: {', '.join(whitelist_symbols) or 'Yok'}")

    if config.PROACTIVE_SCAN_USE_GAINERS_LOSERS:
        try:
            logging.info("En çok yükselen/düşenler listesi çekiliyor...")
            gainer_loser_list = get_top_gainers_losers(config.PROACTIVE_SCAN_TOP_N, config.PROACTIVE_SCAN_MIN_VOLUME_USDT)
            gainer_loser_symbols = [item['symbol'] for item in gainer_loser_list]
            symbols_to_scan.extend(gainer_loser_symbols)
            logging.info(f"Yükselen/Düşenler listesinden eklendi ({len(gainer_loser_symbols)} adet)")
        except Exception as e:
            logging.error(f"Yükselen/Düşenler listesi alınamadı: {e}")

    final_scan_list = []
    seen = set()
    static_blacklist = {_get_unified_symbol(s) for s in config.PROACTIVE_SCAN_BLACKLIST}

    for symbol in symbols_to_scan:
        if (symbol not in seen and 
            symbol not in open_symbols and
            symbol not in static_blacklist and
            symbol not in BLACKLISTED_SYMBOLS):
            final_scan_list.append(symbol)
            seen.add(symbol)
    
    if not final_scan_list:
        logging.info("Analiz edilecek yeni ve uygun sembol bulunamadı.")
        return

    logging.info(f"Filtrelenmiş Nihai Tarama Listesi ({len(final_scan_list)} sembol): {', '.join(final_scan_list)}")

    for symbol in final_scan_list:
        if len(database.get_all_positions()) >= config.MAX_CONCURRENT_TRADES:
            logging.warning("Tarama sırasında maksimum pozisyon limitine ulaşıldı. Döngü sonlandırılıyor.")
            break
        
        print("-" * 50)
        logging.info(f"🔍 Analiz ediliyor: {symbol}")
        
        analysis_result = _perform_analysis(
            symbol=symbol,
            entry_tf=config.PROACTIVE_SCAN_ENTRY_TIMEFRAME,
            use_mta=config.PROACTIVE_SCAN_MTA_ENABLED,
            trend_tf=config.PROACTIVE_SCAN_TREND_TIMEFRAME
        )

        if not analysis_result:
            logging.warning(f"{symbol} için analiz tamamlanamadı, bir sonraki sembole geçiliyor.")
            continue
        
        print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
        
        recommendation = analysis_result.get("recommendation")
        if recommendation in ["AL", "SAT"]:
            handle_trade_confirmation(
                recommendation,
                analysis_result.get('symbol'),
                analysis_result.get('current_price'),
                config.PROACTIVE_SCAN_ENTRY_TIMEFRAME,
                auto_confirm=config.PROACTIVE_SCAN_AUTO_CONFIRM
            )
        else:
            logging.info(f"{symbol} için net bir al/sat sinyali bulunamadı ('{recommendation}').")
        
        time.sleep(5)

    logging.info("--- ✅ Proaktif Tarama Döngüsü Tamamlandı ✅ ---")

def run_proactive_scanner():
    logging.info("🚀 PROAKTİF TARAMA MODU BAŞLATILDI 🚀")
    if config.PROACTIVE_SCAN_IN_LOOP:
        while True:
            _execute_single_scan_cycle()
            logging.info(f"Döngüsel tarama aktif. Sonraki tarama için {config.PROACTIVE_SCAN_INTERVAL_SECONDS} saniye bekleniyor...")
            time.sleep(config.PROACTIVE_SCAN_INTERVAL_SECONDS)
    else:
        _execute_single_scan_cycle()
        print("Tek seferlik tarama tamamlandı. Ana menüye dönülüyor.")

def handle_new_analysis():
    active_positions = database.get_all_positions()
    if len(active_positions) >= config.MAX_CONCURRENT_TRADES:
        print("\n### UYARI: Maksimum pozisyon limitine ulaşıldı. ###"); return

    entry_timeframe = input(f"Giriş için zaman aralığı seçin (örn: 15m, 1h) [varsayılan: 15m]: ").lower().strip() or "15m"
    user_input = input(f"Analiz edilecek kripto parayı girin (örn: BTC): ")
    if not user_input: return
    
    analysis_result = _perform_analysis(
        symbol=user_input,
        entry_tf=entry_timeframe,
        use_mta=config.USE_MTA_ANALYSIS,
        trend_tf=config.MTA_TREND_TIMEFRAME
    )

    if not analysis_result:
        print("\n--- HATA: Analiz gerçekleştirilemedi. Detaylar için logları kontrol edin. ---")
        return

    print("\n--- Analiz Raporu ---")
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))

    recommendation = analysis_result.get("recommendation")
    if recommendation in ["AL", "SAT"]:
        handle_trade_confirmation(
            recommendation, 
            analysis_result.get('symbol'), 
            analysis_result.get('current_price'), 
            entry_timeframe
        )
    else:
        print("\n--- Bir işlem tavsiyesi ('AL' veya 'SAT') bulunamadı. ---")

def handle_manage_position():
    active_positions = database.get_all_positions()
    if not active_positions:
        print("Yönetilecek açık pozisyon bulunmuyor."); return
    print("\n--- Yönetilen Açık Pozisyonlar ---")
    for i, pos in enumerate(active_positions):
        print(f"  [{i+1}] {pos['symbol']} ({pos['side'].upper()}) | Giriş: {pos.get('entry_price', 'N/A')}")
    try:
        choice_str = input("Yönetmek istediğiniz pozisyonun numarasını girin (çıkmak için 'q'): ")
        if choice_str.lower() == 'q': return
        pos_index = int(choice_str) - 1
        if not 0 <= pos_index < len(active_positions):
            print("Geçersiz numara."); return
        
        position_to_manage = active_positions[pos_index]
        while True:
            print(f"\n--- {position_to_manage['symbol']} Pozisyonu Yönetiliyor ---")
            print("1. Manuel Kapat")
            print("2. Pozisyonu Yeniden Analiz Et")
            print("3. Ana Menüye Dön")
            action_choice = input("Seçiminiz: ")
            if action_choice == '1':
                handle_manual_close(position_to_manage); break 
            elif action_choice == '2':
                handle_reanalyze_position(position_to_manage); break
            elif action_choice == '3': break
            else: print("Geçersiz seçim.")
    except (ValueError, IndexError):
        print("Geçersiz giriş.")

def handle_manual_close(position, from_auto=False, close_reason="MANUAL"):
    """Bir pozisyonu manuel veya otomatik olarak kapatır ve ilişkili emirleri temizler."""
    if not from_auto:
        print(f"UYARI: {position['symbol']} pozisyonunu manuel olarak kapatacaksınız.")
        onay = input("Emin misiniz? (evet/hayır): ").lower()
        if onay != 'evet':
            print("İşlem iptal edildi."); return
    
    logging.info(f"Kapatılacak pozisyon ({position['symbol']}) için mevcut emirler iptal ediliyor...")
    cancel_all_open_orders.invoke(position['symbol'])
    time.sleep(1) 

    close_side = 'sell' if position['side'] == 'buy' else 'buy'
    result = execute_trade_order.invoke({
        "symbol": position['symbol'], "side": close_side, "amount": position['amount']
    })
    print(f"Kapatma Sonucu: {result}")
    
    if "başarı" in result.lower() or "simülasyon" in result.lower():
        closed_pos = database.remove_position(position['symbol'])
        if closed_pos:
            current_price = position.get('close_price') or _fetch_price_natively(closed_pos['symbol']) or closed_pos['entry_price']
            
            pnl = calculate_pnl(side=closed_pos.get('side'), entry_price=closed_pos.get('entry_price'), close_price=current_price, amount=closed_pos.get('amount'))

            database.log_trade_to_history(closed_pos, current_price, close_reason)
            message = format_close_position_message(closed_pos, pnl, close_reason)
            send_telegram_message(message)
        print(f"+++ POZİSYON BAŞARIYLA KAPATILDI: {position['symbol']} +++")
    else:
        logging.error(f"Pozisyon kapatılamadı: {position['symbol']}. Sonuç: {result}")

def handle_reanalyze_position(position):
    print(f"\n--- {position['symbol']} Pozisyonu Yeniden Analiz Ediliyor... ---")
    reanalysis_prompt = create_reanalysis_prompt(position)
    
    try:
        result = agent_executor.invoke({"input": reanalysis_prompt})
        parsed_data = parse_agent_response(result.get("output", ""))

        if not parsed_data or "recommendation" not in parsed_data:
            print("\n--- HATA: Yeniden analiz sırasında Agent'tan geçerli bir tavsiye alınamadı. ---")
            print(f"Gelen yanıt: {result.get('output', '')}")
            return
        
        print("\n--- Yeniden Analiz Raporu ---")
        print(f"Tavsiye: {parsed_data.get('recommendation')}")
        print(f"Gerekçe: {parsed_data.get('reason')}")

        if parsed_data.get('recommendation') == 'KAPAT':
            print("\nAJAN 'KAPAT' TAVSİYESİ VERDİ. POZİSYON KAPATILIYOR...")
            position['close_price'] = _fetch_price_natively(position['symbol'])
            handle_manual_close(position, close_reason="AGENT_CLOSE") 
        else:
            print("\nAJAN 'TUT' TAVSİYESİ VERDİ. POZİSYON AÇIK KALIYOR.")
            
    except Exception as e:
        print(f"\n--- KRİTİK HATA: Yeniden analiz sırasında bir sorun oluştu. ---")
        logging.error(f"handle_reanalyze_position hatası: {e}", exc_info=True)

def launch_dashboard():
    """Web arayüzü sunucusunu ayrı bir işlem olarak başlatır."""
    dashboard_script = os.path.join('dashboard', 'app.py')
    if not os.path.exists(dashboard_script):
        print("HATA: 'dashboard/app.py' dosyası bulunamadı. Lütfen proje yapısını kontrol edin.")
        return

    print("\n--- 📈 Web Arayüzü Başlatılıyor... ---")
    try:
        subprocess.Popen([sys.executable, dashboard_script])
        print("✅ Sunucu başlatıldı. http://127.0.0.1:5001 adresini tarayıcıda açın.")
    except Exception as e:
        print(f"❌ Web arayüzü başlatılamadı: {e}")

def main():
    database.init_db()
    initialize_exchange(config.DEFAULT_MARKET_TYPE)
    
    print("\n" + "="*50)
    print(f"           GEMINI TRADING AGENT BAŞLATILDI")
    print(f"                 Versiyon: {config.APP_VERSION}")
    print("="*50)
    print(f"UYARI: CANLI İŞLEM MODU {'✅ AKTİF ✅' if config.LIVE_TRADING else '❌ KAPALI (Simülasyon Modu) ❌'}.")
    if config.LIVE_TRADING:
        print("DİKKAT: Bot, Binance hesabınızda gerçek para ile işlem yapacaktır!")
    print(f"BİLDİRİMLER: Telegram {'✅ AKTİF ✅' if config.TELEGRAM_ENABLED else '❌ KAPALI ❌'}.")
    print("="*50 + "\n")
    
    checker_thread = threading.Thread(target=background_position_checker, daemon=True)
    checker_thread.start()
    
    menu_options = {
        "1": ("Pozisyonları Göster ve Senkronize Et", sync_and_display_positions),
        "2": ("Yeni Analiz Yap ve Pozisyon Aç", handle_new_analysis),
        "3": ("Açık Pozisyonu Yönet", handle_manage_position),
        "p": ("PROAKTİF TARAMAYI BAŞLAT (Fırsat Avcısı)", run_proactive_scanner),
        "d": ("WEB ARAYÜZÜNÜ BAŞLAT (Dashboard)", launch_dashboard),
        "4": ("Çıkış", lambda: print("Bot kapatılıyor..."))
    }
    
    while True:
        print("\n" + "="*50 + "\n           GEMINI TRADING AGENT MENU\n" + "="*50)
        
        for key, (text, func) in menu_options.items():
            if key == 'p' and not config.PROACTIVE_SCAN_ENABLED:
                continue
            print(f"{key}. {text}")

        choice = input("Seçiminiz: ").lower().strip()
        
        if choice == "4":
            menu_options[choice][1]()
            break

        action = menu_options.get(choice)
        if action:
            if choice == 'p' and not config.PROACTIVE_SCAN_ENABLED:
                 print("Geçersiz seçim. Lütfen menüden bir seçenek girin.")
            else:
                action[1]()
        else:
            print("Geçersiz seçim. Lütfen menüden bir seçenek girin.")

if __name__ == "__main__":
    main()