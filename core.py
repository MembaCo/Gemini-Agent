# core.py
# @author: Memba Co.

import logging
import json
import time
import sys
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from dotenv import load_dotenv

import config
import database
import tools
from notifications import send_telegram_message, format_open_position_message, format_close_position_message, format_partial_tp_message

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_agent_response(response: str) -> dict | None:
    if not response or not isinstance(response, str): return None
    try:
        if "```json" in response: response = response.split("```json")[1].split("```")[0]
        elif "```" in response: response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())
    except (json.JSONDecodeError, IndexError) as e:
        logging.error(f"JSON ayrıştırma hatası: {response}. Hata: {e}")
        return None

def create_mta_analysis_prompt(symbol: str, price: float, entry_timeframe: str, entry_indicators: dict, trend_timeframe: str, trend_indicators: dict, market_sentiment: dict, news_data: str) -> str:
    def format_indicator(value):
        if value is None:
            return "N/A"
        return f"{value:.4f}"

    entry_indicator_text = "\n".join([f"- {key}: {format_indicator(value)}" for key, value in entry_indicators.items()])
    trend_indicator_text = "\n".join([f"- {key}: {format_indicator(value)}" for key, value in trend_indicators.items()])
    
    funding_rate_text = f"{market_sentiment.get('funding_rate', 'N/A'):.4f}" if isinstance(market_sentiment.get('funding_rate'), (int, float)) else str(market_sentiment.get('funding_rate', 'N/A'))
    bid_ask_ratio_text = f"{market_sentiment.get('bid_ask_ratio', 'N/A'):.2f}" if isinstance(market_sentiment.get('bid_ask_ratio'), (int, float)) else str(market_sentiment.get('bid_ask_ratio', 'N/A'))
    
    sentiment_text = f"- Fonlama Oranı: {funding_rate_text}\n- Alış/Satış Oranı: {bid_ask_ratio_text}"
    news_section = f"### Temel Analiz (Son Haberler)\n{news_data}" if config.USE_NEWS_ANALYSIS else ""
    return f"""
Sen, teknik, temel ve duyarlılık analizini birleştiren bir piyasa analistisin. Görevin, sunulan verileri analiz ederek net bir ticaret kararı ('AL', 'SAT' veya 'BEKLE') vermektir.
## ANALİZ KURALLARI:
1.  **Eksik Veri:** Eğer bir gösterge değeri "N/A" (Mevcut Değil) ise, bu göstergeyi yorum yapmadan analizine devam et. Kararını mevcut olan diğer verilere dayandır.
2.  **Haberler:** Olumsuz bir haber (FUD, hack) varsa, diğer tüm sinyaller olumlu olsa bile 'BEKLE'.
3.  **Piyasa Duyarlılığı:** Fonlama oranı ve alış/satış oranını yorumla.
4.  **Ana Trend ({trend_timeframe}):** Ana trend yönünü belirle.
5.  **Giriş Sinyali ({entry_timeframe}):** Ana trend ile uyumlu bir giriş sinyali ara.
6.  **Sentez:** Tüm verileri birleştirerek kararını ve gerekçeni açıkla.
## SAĞLANAN VERİLER:
{news_section}
### Piyasa Duyarlılığı
{sentiment_text}
### Ana Trend Verileri ({trend_timeframe})
{trend_indicator_text}
### Giriş Sinyali Verileri ({entry_timeframe})
{entry_indicator_text}
## İSTENEN JSON ÇIKTI FORMATI:
```json
{{
  "recommendation": "KARARIN (AL, SAT, veya BEKLE)",
  "reason": "Tüm analizlere dayalı kısa ve net gerekçen."
}}
```"""

def create_reanalysis_prompt(position: dict) -> str:
    return f"""
Sen, tecrübeli bir pozisyon yöneticisisin. Verilen pozisyonu (`{position['symbol']} {position['side'].upper()}`) mevcut piyasa koşullarına göre yeniden analiz et. Gerekli tüm araçları kullanarak kapsamlı bir değerlendirme yap.
## Nihai Çıktı Formatı (ZORUNLU):
Analizinin sonucunu, aşağıdaki anahtarları içeren bir JSON nesnesi olarak döndür:
- `recommendation`: Pozisyon için tavsiyen. Sadece "TUT" veya "KAPAT" olabilir.
- `reason`: Kararının arkasındaki tüm adımları ve veri noktalarını içeren detaylı gerekçen.
"""

def perform_analysis(symbol: str, entry_tf: str) -> dict:
    unified_symbol = tools._get_unified_symbol(symbol)
    logging.info(f"-> Analiz adımları başlatılıyor: {unified_symbol}")
    try:
        logging.info(f"[{unified_symbol}] Adım 1/5: Fiyat alınıyor...")
        current_price = tools._fetch_price_natively(unified_symbol)
        if not current_price: 
            return {"status": "error", "message": f"[{unified_symbol}] Fiyat alınamadı"}
        
        logging.info(f"[{unified_symbol}] Adım 2/5: Teknik indikatörler alınıyor...")
        entry_params_str = str({"symbol": unified_symbol, "timeframe": entry_tf})
        trend_params_str = str({"symbol": unified_symbol, "timeframe": config.MTA_TREND_TIMEFRAME})
        
        entry_indicators = tools.get_technical_indicators.invoke(entry_params_str)
        if entry_indicators.get("status") != "success": 
            return {"status": "error", "message": f"[{unified_symbol}] Giriş indikatörleri alınamadı: {entry_indicators.get('message')}"}

        trend_indicators = tools.get_technical_indicators.invoke(trend_params_str)
        if trend_indicators.get("status") != "success": 
            return {"status": "error", "message": f"[{unified_symbol}] Trend indikatörleri alınamadı: {trend_indicators.get('message')}"}

        logging.info(f"[{unified_symbol}] Adım 3/5: Piyasa duyarlılığı verileri alınıyor...")
        market_sentiment = {
            'funding_rate': tools.get_funding_rate.invoke(unified_symbol).get('funding_rate', 'N/A'),
            'bid_ask_ratio': tools.get_order_book_depth.invoke(unified_symbol).get('bid_ask_ratio', 'N/A')
        }

        logging.info(f"[{unified_symbol}] Adım 4/5: Haber verileri alınıyor...")
        news_data = tools.get_latest_news.invoke(unified_symbol) if config.USE_NEWS_ANALYSIS else "Haber analizi kapalı."

        final_prompt = create_mta_analysis_prompt(unified_symbol, current_price, entry_tf, entry_indicators["data"], config.MTA_TREND_TIMEFRAME, trend_indicators["data"], market_sentiment, news_data)
        
        logging.info(f"[{unified_symbol}] Adım 5/5: Yapay zeka (LLM) çağrısı yapılıyor...")
        llm = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, temperature=0.1)
        result = llm.invoke(final_prompt)
        parsed_data = parse_agent_response(result.content)
        logging.info(f"<- [{unified_symbol}] Analiz başarıyla tamamlandı.")

        if not parsed_data: 
            raise Exception(f"Yapay zekadan geçersiz yanıt: {result.content}")
        
        parsed_data.update({'current_price': current_price, 'status': 'success', 'symbol': unified_symbol, 'timeframe': entry_tf})
        return parsed_data
        
    except Exception as e:
        logging.critical(f"[{unified_symbol}] Analiz sırasında kritik hata: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def open_new_position(rec: str, symbol: str, price: float, timeframe: str) -> dict:
    try:
        if len(database.get_all_positions()) >= config.MAX_CONCURRENT_TRADES:
            return {"status": "error", "message": "Maksimum pozisyon limiti dolu."}
        
        trade_side = "buy" if "AL" in rec.upper() else "sell"
        
        # get_atr_value tek bir string argüman beklediği için bu çağrı doğru.
        atr_result = tools.get_atr_value.invoke(f"{symbol},{timeframe}")
        if atr_result.get("status") != "success":
            return {"status": "error", "message": f"ATR değeri alınamadı: {atr_result.get('message')}"}
        
        sl_distance = atr_result['value'] * config.ATR_MULTIPLIER_SL
        stop_loss_price = price - sl_distance if trade_side == "buy" else price + sl_distance
        take_profit_price = price + (sl_distance * config.RISK_REWARD_RATIO_TP) if trade_side == "buy" else price - (sl_distance * config.RISK_REWARD_RATIO_TP)

        # get_wallet_balance argüman beklemediği için bu çağrı doğru.
        balance_result = tools.get_wallet_balance.invoke({})
        wallet_balance = balance_result.get('balance', 0.0)
        risk_amount_usd = wallet_balance * (config.RISK_PER_TRADE_PERCENT / 100)
        trade_amount = risk_amount_usd / sl_distance if sl_distance > 0 else 0

        logging.info(f"Dinamik Pozisyon Hesabı: Bakiye={wallet_balance:.2f} USDT, Risk={risk_amount_usd:.2f} USDT, Pozisyon Miktarı={trade_amount:.4f} {symbol.split('/')[0]}")

        trade_params = {
            "symbol": symbol, "side": trade_side, "amount": trade_amount, 
            "stop_loss": stop_loss_price, "take_profit": take_profit_price, "leverage": config.LEVERAGE
        }
        if config.DEFAULT_ORDER_TYPE.lower() == 'limit':
            trade_params["price"] = price

        # DÜZELTME: Parametre sözlüğünü, 'params' anahtarı olan başka bir sözlük içine sardık.
        result_str = tools.execute_trade_order.invoke({"params": trade_params})

        if "başarı" in result_str.lower() or "simülasyon" in result_str.lower():
            pos_details = {
                "symbol": symbol, "side": trade_side, "amount": trade_amount, "entry_price": price, 
                "timeframe": timeframe, "leverage": config.LEVERAGE, "stop_loss": stop_loss_price, "take_profit": take_profit_price
            }
            database.add_position(pos_details)
            message = format_open_position_message(pos_details)
            send_telegram_message(message)
            return {"status": "success", "message": f"{symbol} için pozisyon açıldı."}
        else:
            return {"status": "error", "message": f"İşlem emri başarısız: {result_str}"}

    except Exception as e:
        logging.error(f"Pozisyon açma hatası: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def close_position_by_symbol(symbol: str, reason: str = "MANUAL") -> dict:
    position = next((p for p in database.get_all_positions() if p['symbol'] == symbol), None)
    if not position: return {"status": "error", "message": f"{symbol} için yönetilen pozisyon bulunamadı."}

    logging.info(f"Kapatılacak pozisyon ({symbol}) için mevcut emirler iptal ediliyor...")
    # cancel_all_open_orders tek bir string argüman beklediği için bu çağrı doğru.
    tools.cancel_all_open_orders.invoke(symbol)
    time.sleep(0.5)
    
    close_params = {
        "symbol": symbol,
        "side": 'sell' if position['side'] == 'buy' else 'buy',
        "amount": position['amount']
    }
    
    # DÜZELTME: Parametre sözlüğünü, 'params' anahtarı olan başka bir sözlük içine sardık.
    result = tools.execute_trade_order.invoke({"params": close_params})
    
    if "başarı" in result.lower() or "simülasyon" in result.lower():
        closed_pos = database.remove_position(symbol)
        if closed_pos:
            current_price = tools._fetch_price_natively(closed_pos['symbol']) or closed_pos['entry_price']
            pnl = tools.calculate_pnl(side=closed_pos.get('side'), entry_price=closed_pos.get('entry_price'), close_price=current_price, amount=closed_pos.get('amount'))
            closed_pos['close_price'] = current_price
            database.log_trade_to_history(closed_pos, current_price, reason)
            message = format_close_position_message(closed_pos, pnl, reason)
            send_telegram_message(message)
        return {"status": "success", "message": f"{symbol} pozisyonu başarıyla kapatıldı."}
    else:
        return {"status": "error", "message": f"Pozisyon kapatılamadı: {result}"}
    
def close_position_by_symbol(symbol: str, reason: str = "MANUAL") -> dict:
    position = next((p for p in database.get_all_positions() if p['symbol'] == symbol), None)
    if not position: return {"status": "error", "message": f"{symbol} için yönetilen pozisyon bulunamadı."}

    logging.info(f"Kapatılacak pozisyon ({symbol}) için mevcut emirler iptal ediliyor...")
    tools.cancel_all_open_orders.invoke(symbol)
    time.sleep(0.5)
    
    close_params = {
        "symbol": symbol, "side": 'sell' if position['side'] == 'buy' else 'buy', "amount": position['amount']
    }
    result = tools.execute_trade_order.invoke(close_params)
    
    if "başarı" in result.lower() or "simülasyon" in result.lower():
        closed_pos = database.remove_position(symbol)
        if closed_pos:
            current_price = tools._fetch_price_natively(closed_pos['symbol']) or closed_pos['entry_price']
            pnl = tools.calculate_pnl(side=closed_pos.get('side'), entry_price=closed_pos.get('entry_price'), close_price=current_price, amount=closed_pos.get('amount'))
            closed_pos['close_price'] = current_price
            database.log_trade_to_history(closed_pos, current_price, reason)
            message = format_close_position_message(closed_pos, pnl, reason)
            send_telegram_message(message)
        return {"status": "success", "message": f"{symbol} pozisyonu başarıyla kapatıldı."}
    else:
        return {"status": "error", "message": f"Pozisyon kapatılamadı: {result}"}

def reanalyze_position(position: dict) -> dict:
    llm = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, temperature=0.1)
    agent_tools = [tools.get_market_price, tools.get_technical_indicators, tools.get_funding_rate, tools.get_order_book_depth, tools.get_latest_news]
    prompt_template = hub.pull("hwchase17/react")
    agent = create_react_agent(llm=llm, tools=agent_tools, prompt=prompt_template)
    agent_executor = AgentExecutor(
        agent=agent, tools=agent_tools, verbose=tools.str_to_bool(os.getenv("AGENT_VERBOSE", "True")),
        handle_parsing_errors="Lütfen JSON formatında geçerli bir yanıt ver.", max_iterations=config.AGENT_MAX_ITERATIONS
    )
    prompt = create_reanalysis_prompt(position)
    try:
        result = agent_executor.invoke({"input": prompt})
        parsed_data = parse_agent_response(result.get("output", ""))
        recommendation = parsed_data.get("recommendation") or parsed_data.get("karar")
        if not recommendation: raise Exception("Ajan'dan geçerli tavsiye alınamadı.")
        
        return {"status": "success", "data": {
            "recommendation": recommendation.upper(),
            "reason": parsed_data.get("reason") or parsed_data.get("gerekce", "Gerekçe belirtilmedi.")
        }}
    except Exception as e:
        logging.error(f"Yeniden analiz hatası: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def _update_blacklist(blacklist: dict, status_callback = None) -> None:
    now = time.time()
    for symbol, expiry in list(blacklist.items()):
        if now > expiry:
            del blacklist[symbol]
            message = f"INFO: {symbol} dinamik kara listeden çıkarıldı."
            logging.info(message)
            if status_callback: status_callback(message)

def _get_scan_candidates(open_symbols: set, blacklist: dict, status_callback = None) -> list[str]:
    """Taranacak nihai sembol listesini oluşturur ve detaylı loglama yapar."""
    symbols_to_scan = []
    
    # Adım 1: Whitelist'i ekle
    whitelist_symbols = [tools._get_unified_symbol(s) for s in config.PROACTIVE_SCAN_WHITELIST if s]
    if whitelist_symbols:
        symbols_to_scan.extend(whitelist_symbols)
        message = f"INFO: Beyaz listeden {len(whitelist_symbols)} sembol eklendi."
        if status_callback: status_callback(message)

    # Adım 2: Gainer/Loser listesini ekle
    if config.PROACTIVE_SCAN_USE_GAINERS_LOSERS:
        try:
            if status_callback: status_callback("INFO: En çok yükselen/düşenler listesi çekiliyor...")
            
            # --- DÜZELTME: Araç, .invoke() metodu ile çağrıldı. ---
            # Parametreler, anahtarları fonksiyon argüman isimleriyle eşleşen bir sözlük içinde verilir.
            params = {"top_n": config.PROACTIVE_SCAN_TOP_N, "min_volume_usdt": config.PROACTIVE_SCAN_MIN_VOLUME_USDT}
            gainer_loser_list = tools.get_top_gainers_losers.invoke(params)
            
            # gainer_loser_list'in bir liste olduğunu varsayarak devam ediyoruz.
            if isinstance(gainer_loser_list, list) and gainer_loser_list:
                gainer_loser_symbols = [item['symbol'] for item in gainer_loser_list]
                symbols_to_scan.extend(gainer_loser_symbols)
                message = f"INFO: Yükselen/düşenler listesinden {len(gainer_loser_symbols)} sembol eklendi."
                if status_callback: status_callback(message)
            else:
                # Hata durumunda veya boş liste döndüğünde logla
                log_message = f"UYARI: Yükselen/düşenler listesi boş veya geçersiz bir formatta döndü: {gainer_loser_list}"
                logging.warning(log_message)
                if status_callback: status_callback(log_message)

        except Exception as e:
            message = f"HATA: Yükselen/Düşenler listesi alınamadı: {e}"
            logging.error(message, exc_info=True) # Hatanın detayını görmek için exc_info eklendi.
            if status_callback: status_callback(f"⚠️ {message}")
            
    # Adım 3: Tekilleştir ve filtrele
    initial_count = len(symbols_to_scan)
    unique_symbols = set(symbols_to_scan)
    if status_callback: status_callback(f"INFO: Toplam {initial_count} aday sembol {len(unique_symbols)} tekil sembole düşürüldü.")

    final_scan_list = [s for s in unique_symbols if s not in open_symbols and s not in blacklist and s not in config.PROACTIVE_SCAN_BLACKLIST]
    
    message = f"Filtrelenmiş Nihai Tarama Listesi ({len(final_scan_list)} sembol)"
    logging.info(message)
    if status_callback: status_callback(message)
    
    return final_scan_list

def _process_candidate(symbol: str, blacklist: dict, opportunity_callback, status_callback):
    if len(database.get_all_positions()) >= config.MAX_CONCURRENT_TRADES:
        status_callback("UYARI: Tarama sırasında maksimum pozisyon limitine ulaşıldı. Döngü sonlandırılıyor.")
        return False

    analysis_result = perform_analysis(symbol, config.PROACTIVE_SCAN_ENTRY_TIMEFRAME)

    if not analysis_result or analysis_result.get('status') != 'success':
        message = f"⚠️ {symbol} için analiz tamamlanamadı. Sebep: {analysis_result.get('message', 'Bilinmiyor')}. 1 saatliğine dinamik kara listeye ekleniyor."
        status_callback(message)
        blacklist[symbol] = time.time() + 3600
        return True

    recommendation = analysis_result.get("recommendation")
    if recommendation in ["AL", "SAT"]:
        status_callback(f"✅ FIRSAT BULUNDU: {symbol} için '{recommendation}'")
        opportunity_callback(analysis_result)
    else:
        status_callback(f"⚪️ {symbol} için net bir sinyal bulunamadı ('{recommendation}'). Atlanıyor.")
    
    time.sleep(3)
    return True

def run_proactive_scanner(opportunity_callback, status_callback):
    BLACKLISTED_SYMBOLS = {}
    
    status_callback("--- 🚀 Yeni Proaktif Tarama Döngüsü Başlatılıyor 🚀 ---")
    
    active_positions = database.get_all_positions()
    if len(active_positions) >= config.MAX_CONCURRENT_TRADES:
        status_callback(f"UYARI: Maksimum pozisyon limitine ({config.MAX_CONCURRENT_TRADES}) ulaşıldı. Tarama atlanıyor.")
        status_callback("--- ✅ Proaktif Tarama Döngüsü Tamamlandı ✅ ---")
        return

    open_symbols = {p['symbol'] for p in active_positions}

    _update_blacklist(BLACKLISTED_SYMBOLS, status_callback)
    
    candidates = _get_scan_candidates(open_symbols, BLACKLISTED_SYMBOLS, status_callback)
    
    if not candidates:
        status_callback("BİLGİ: Analiz edilecek yeni ve uygun sembol bulunamadı.")
    else:
        for symbol in candidates:
            should_continue = _process_candidate(symbol, BLACKLISTED_SYMBOLS, opportunity_callback, status_callback)
            if not should_continue:
                break
    
    status_callback("--- ✅ Proaktif Tarama Döngüsü Tamamlandı ✅ ---")

def check_and_manage_positions():
    """
    Açık pozisyonları kontrol eder ve Kısmi Kâr Alma, İz Süren Zarar Durdurma gibi
    gelişmiş risk yönetimi stratejilerini uygular.
    """
    try:
        exchange_positions_raw = tools.get_open_positions_from_exchange.invoke({})
    except Exception as e:
        logging.error(f"POZİSYON KONTROL: Borsadan pozisyonlar alınamadı: {e}")
        return

    if not isinstance(exchange_positions_raw, list):
        logging.warning(f"POZİSYON KONTROL: Borsadan pozisyonlar alınırken geçersiz veri tipi alındı: {type(exchange_positions_raw)}")
        return
        
    exchange_positions_map = {tools._get_unified_symbol(p.get('symbol')): p for p in exchange_positions_raw}
    db_positions = database.get_all_positions()

    for db_pos in db_positions:
        symbol = db_pos['symbol']
        exchange_pos = exchange_positions_map.get(symbol)

        if not exchange_pos:
            logging.warning(f"Pozisyon '{symbol}' veritabanında var ama borsada yok. Veritabanından siliniyor.")
            database.log_trade_to_history(db_pos, db_pos.get('entry_price'), "SYNC_CLOSED") # Geçmişe SYNC olarak kaydet
            database.remove_position(symbol)
            continue

        try:
            current_price = float(exchange_pos.get('markPrice'))
            side = db_pos.get("side")
            entry_price = db_pos.get("entry_price")
            initial_sl = db_pos.get("initial_stop_loss")
            pos_amount = db_pos.get("amount")
            
            # --- 1. KISMİ KÂR ALMA (PARTIAL TAKE-PROFIT) KONTROLÜ ---
            if config.USE_PARTIAL_TP and not db_pos.get('partial_tp_executed'):
                risk_per_unit = abs(entry_price - initial_sl)
                partial_tp_price = entry_price + (risk_per_unit * config.PARTIAL_TP_TARGET_RR) if side == 'buy' else entry_price - (risk_per_unit * config.PARTIAL_TP_TARGET_RR)

                if (side == 'buy' and current_price >= partial_tp_price) or \
                   (side == 'sell' and current_price <= partial_tp_price):
                    
                    logging.info(f"PARTIAL TP TETİKLENDİ: {symbol} için kısmi kâr alma hedefine ulaşıldı.")
                    
                    close_amount = pos_amount * (config.PARTIAL_TP_CLOSE_PERCENT / 100)
                    remaining_amount = pos_amount - close_amount
                    
                    # Kısmi kapatma emrini gönder
                    close_side = 'sell' if side == 'buy' else 'buy'
                    partial_close_params = {"symbol": symbol, "side": close_side, "amount": close_amount}
                    tools.execute_trade_order.invoke({"params": partial_close_params})
                    
                    # Kalan pozisyonun SL'ini başa baş (breakeven) noktasına çek
                    new_sl_price = entry_price
                    update_sl_params = {"symbol": symbol, "side": side, "amount": remaining_amount, "new_stop_price": new_sl_price}
                    tools.update_stop_loss_order.invoke({"params": update_sl_params})
                    
                    # Veritabanını güncelle
                    realized_pnl = abs(current_price - entry_price) * close_amount
                    database.update_position_after_partial_tp(symbol, remaining_amount, new_sl_price, realized_pnl)
                    
                    # Bildirim gönder
                    notif_message = f"PARTIAL TP: {symbol} pozisyonunun %{config.PARTIAL_TP_CLOSE_PERCENT} kadarı kapatıldı. SL giriş fiyatına çekildi."
                    send_telegram_message(notif_message)
                    logging.info(notif_message)
                    continue # Bu döngüyü bu pozisyon için bitir

            # --- 2. İZ SÜREN ZARAR DURDURMA (TRAILING STOP-LOSS) KONTROLÜ ---
            if config.USE_TRAILING_STOP_LOSS:
                sl_price = db_pos.get("stop_loss", 0.0)
                activation_price = entry_price * (1 + (config.TRAILING_STOP_ACTIVATION_PERCENT / 100)) if side == 'buy' else entry_price * (1 - (config.TRAILING_STOP_ACTIVATION_PERCENT / 100))
                
                if (side == 'buy' and current_price > activation_price) or \
                   (side == 'sell' and current_price < activation_price):
                    
                    new_sl_candidate = current_price * (1 - (config.TRAILING_STOP_ACTIVATION_PERCENT / 100)) if side == 'buy' else current_price * (1 + (config.TRAILING_STOP_ACTIVATION_PERCENT / 100))
                    
                    # Sadece SL'i lehimize hareket ettiriyorsak güncelle
                    if (side == 'buy' and new_sl_candidate > sl_price) or \
                       (side == 'sell' and new_sl_candidate < sl_price):
                        
                        logging.info(f"TRAILING SL TETİKLENDİ: {symbol} için yeni SL: {new_sl_candidate:.8f}")
                        update_sl_params = {"symbol": symbol, "side": side, "amount": pos_amount, "new_stop_price": new_sl_candidate}
                        tools.update_stop_loss_order.invoke({"params": update_sl_params})
                        database.update_position_sl(symbol, new_sl_candidate)

            # --- 3. STANDART TP/SL KONTROLÜ ---
            final_sl_price = db_pos.get("stop_loss", 0.0)
            final_tp_price = db_pos.get("take_profit", 0.0)
            
            if (side == "buy" and current_price <= final_sl_price) or (side == "sell" and current_price >= final_sl_price):
                logging.info(f"POZİSYON KAPANDI (SL): {symbol}")
                close_position_by_symbol(symbol, "SL")
                continue
            if (side == "buy" and current_price >= final_tp_price) or (side == "sell" and current_price <= final_tp_price):
                logging.info(f"POZİSYON KAPANDI (TP): {symbol}")
                close_position_by_symbol(symbol, "TP")
                continue
            
        except Exception as e:
            logging.error(f"Pozisyon kontrolü sırasında hata ({symbol}): {e}", exc_info=True)

def background_position_checker():
    logging.info("--- Arka plan pozisyon kontrolcüsü başlatıldı. ---")
    while True:
        try:
            check_and_manage_positions()
        except Exception as e:
            logging.critical(f"Arka plan kontrolcüsünde KRİTİK HATA: {e}", exc_info=True)
        time.sleep(config.POSITION_CHECK_INTERVAL_SECONDS)