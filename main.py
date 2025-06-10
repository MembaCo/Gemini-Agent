# main.py
# @author: Memba Co.

import os
import json
import time
import threading
import logging
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from distutils.util import strtobool

from tools import (
    get_market_price, get_technical_indicators, execute_trade_order,
    initialize_exchange, get_open_positions_from_exchange, get_atr_value,
    _get_unified_symbol, get_top_gainers_losers
)
import config

# ... (Dosyanın üst kısmı aynı, değişiklik yok) ...
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "Gemini Trading Agent")

POSITIONS_FILE = "managed_positions.json"
open_positions_managed_by_bot = []
positions_lock = threading.RLock()

try:
    llm = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, temperature=0.1)
    agent_tools = [get_market_price, get_technical_indicators, get_open_positions_from_exchange, execute_trade_order, get_atr_value]
    prompt_template = hub.pull("hwchase17/react")
    agent = create_react_agent(llm=llm, tools=agent_tools, prompt=prompt_template)
    agent_executor = AgentExecutor(
        agent=agent, tools=agent_tools, verbose=strtobool(os.getenv("AGENT_VERBOSE", "True")),
        handle_parsing_errors="Lütfen JSON formatında geçerli bir yanıt ver.",
        max_iterations=7
    )
except Exception as e:
    logging.critical(f"Agent başlatılırken hata oluştu: {e}")
    exit()

def save_positions_to_file():
    with positions_lock:
        try:
            with open(POSITIONS_FILE, 'w') as f:
                json.dump(open_positions_managed_by_bot, f, indent=4)
        except IOError as e:
            logging.error(f"HATA: Pozisyonlar dosyaya kaydedilemedi: {e}")

def load_positions_from_file():
    global open_positions_managed_by_bot
    if os.path.exists(POSITIONS_FILE):
        with positions_lock:
            try:
                with open(POSITIONS_FILE, 'r') as f:
                    content = f.read()
                    if not content:
                        open_positions_managed_by_bot = []
                        return
                    open_positions_managed_by_bot = json.loads(content)
                logging.info(f"--- {len(open_positions_managed_by_bot)} adet yönetilen pozisyon dosyadan yüklendi. ---")
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"HATA: Pozisyon dosyası ({POSITIONS_FILE}) okunamadı: {e}")
                open_positions_managed_by_bot = []

def create_analysis_prompt(user_query: str, market_type: str, timeframe: str) -> str:
    symbol = _get_unified_symbol(user_query)
    return f"""
    Sen, uzman bir trading analistisin.
    Hedefin: '{symbol}' için '{timeframe}' zaman aralığında piyasayı analiz etmek ve tek bir JSON çıktısı üretmek.
    İŞ AKIŞI:
    1. `get_market_price` ve `get_technical_indicators` ile veri topla.
    2. Verileri analiz ederek 'AL', 'SAT' veya 'BEKLE' kararı ver.
    3. Nihai JSON raporunu oluştur.
    """

def create_reanalysis_prompt(position: dict) -> str:
    symbol = position.get("symbol")
    timeframe = position.get("timeframe")
    side = position.get("side", "").upper()
    entry_price = position.get("entry_price")
    return f"""
    Sen, tecrübeli bir pozisyon yöneticisisin.
    Mevcut Durum: '{symbol}' sembolünde, {entry_price} fiyatından açılmış bir {side} pozisyonum var.
    Görevin: '{timeframe}' zaman aralığını kullanarak bu pozisyonun mevcut durumunu yeniden değerlendir ve 'TUT' veya 'KAPAT' kararı ver.
    Nihai Rapor: Kararını, anahtarları 'recommendation' ve 'reason' olan bir JSON formatında üret.
    """

def create_batch_analysis_prompt(market_data_batch: list) -> str:
    prompt_header = """Sen, aynı anda birden fazla kripto parayı analiz edebilen uzman bir trading analistisin.
Aşağıda sana bir dizi kripto para için toplanmış teknik veriler sunulmuştur.
Görevin: Her bir sembolü aşağıdaki kapsamlı kurallara göre değerlendir ve her biri için 'AL', 'SAT' veya 'BEKLE' tavsiyesi içeren bir JSON listesi döndür.
Sağlanan veriler dışında başka bir araç KULLANMA. Sadece bu verileri analiz et.
## ANALİZ KURALLARI:
1.  **Trend Filtresi (ADX):** Önce ADX değerine bak.
    - Eğer ADX < 25 ise, kararını 'BEKLE' olarak ver ve gerekçeni "ADX zayıf, piyasa yönsüz." olarak belirt.
    - Eğer ADX >= 25 ise, 2. adıma geç.
2.  **Sinyal Teyidi (ADX >= 25 iken):**
    - **AL Koşulu (Long Sinyal):** Aşağıdaki koşullardan **en az ikisi** aynı anda sağlanıyorsa 'AL' kararı ver:
        - RSI < 45, Stokastik %K > %D, Fiyat Bollinger Alt bandına yakın, MACD > Sinyal.
    - **SAT Koşulu (Short Sinyal):** Aşağıdaki koşullardan **en az ikisi** aynı anda sağlanıyorsa 'SAT' kararı ver:
        - RSI > 55, Stokastik %K < %D, Fiyat Bollinger Üst bandına yakın, MACD < Sinyal.
3.  **BEKLE Koşulu:** Yukarıdaki AL veya SAT koşulları net bir şekilde karşılanmıyorsa 'BEKLE'.

## SAĞLANAN VERİLER:
"""
    data_section = ""
    for data in market_data_batch:
        indicator_str = "\n".join([f"{key.replace('_', ' ').title()}: {value:.4f}" for key, value in data["indicators"].items()])
        data_section += f"""---
Sembol: {data['symbol']}
Anlık Fiyat: {data['price']}
{indicator_str}
"""
    prompt_footer = f"""---
## GÖREV:
Yukarıdaki {len(market_data_batch)} sembolün her birini yeni ve kapsamlı kurallara göre analiz et ve `Final Answer:` anahtar kelimesini kullanarak aşağıdaki formatta TEK BİR JSON LİSTESİ döndür. Her sembol için bir gerekçe (reason) ekle.

```json
[
  {{"symbol": "İNCELENEN_SEMBOL_1/USDT", "recommendation": "AL", "reason": "ADX>25, RSI<45 ve Stokastik yukarı kesişim sağladı."}},
  {{"symbol": "İNCELENEN_SEMBOL_2/USDT", "recommendation": "BEKLE", "reason": "ADX zayıf, piyasa yönsüz."}}
]
```"""
    return prompt_header + data_section + prompt_footer


def check_and_manage_positions_thread_safe():
    global open_positions_managed_by_bot
    positions_to_close = []
    with positions_lock:
        positions_to_iterate = open_positions_managed_by_bot[:]
    for i, position in enumerate(positions_to_iterate):
        try:
            price_str_result = get_market_price.invoke({"symbol": position["symbol"]})
            if "HATA" in price_str_result: continue
            current_price = float(re.search(r'[\d\.]+$', price_str_result).group())
            side, sl_price, tp_price = position.get("side"), position.get("stop_loss"), position.get("take_profit")
            if not all([side, sl_price, tp_price]) or sl_price == 0 or tp_price == 0: continue
            if (side == "buy" and (current_price <= sl_price or current_price >= tp_price)) or \
               (side == "sell" and (current_price >= sl_price or current_price <= tp_price)):
                reason = "Zarar Durdur (SL)" if (current_price <= sl_price if side == 'buy' else current_price >= sl_price) else "Kar Al (TP)"
                logging.info(f"\n[AUTO] POZİSYON HEDEFE ULAŞTI ({reason}): {position['symbol']} @ {current_price}")
                positions_to_close.append((i, position))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            logging.error(f"[AUTO-HATA] Pozisyon kontrolü sırasında hata: {e} - Pozisyon: {position}")
    for index, pos_to_close in sorted(positions_to_close, reverse=True):
        close_side = 'sell' if pos_to_close['side'] == 'buy' else 'buy'
        execute_trade_order.invoke({"symbol": pos_to_close['symbol'], "side": close_side, "amount": pos_to_close['amount']})
        with positions_lock:
            if index < len(open_positions_managed_by_bot) and open_positions_managed_by_bot[index] == pos_to_close:
                open_positions_managed_by_bot.pop(index)
                save_positions_to_file()
                logging.info(f"Bot hafızasından silindi: {pos_to_close['symbol']}")


def sync_and_display_positions():
    """Borsadaki pozisyonlarla botun hafızasını senkronize eder ve PNL'i doğru hesaplayarak gösterir."""
    global open_positions_managed_by_bot
    print("\n--- Borsadaki Açık Pozisyonlar Senkronize Ediliyor... ---")
    try:
        exchange_positions = get_open_positions_from_exchange.invoke({})
        if not isinstance(exchange_positions, list):
            logging.error(f"Borsadan pozisyonlar alınamadı, dönen veri: {exchange_positions}")
            return
        
        updated_managed_list = []
        if not exchange_positions:
            print("Borsada açık pozisyon bulunmuyor.")
        else:
            print(f"--- Borsada Bulunan Açık Pozisyonlar: {len(exchange_positions)} ---")
            with positions_lock:
                old_managed_positions_map = {p['symbol']: p for p in open_positions_managed_by_bot}
            
            for pos_data in exchange_positions:
                unified_symbol = pos_data.get('symbol')
                side = 'buy' if pos_data.get('side', 'long') == 'long' else 'sell'
                amount = float(pos_data.get('contracts', 0.0) or 0.0)
                entry_price = float(pos_data.get('entryPrice', 0.0) or 0.0)
                pnl = float(pos_data.get('unrealizedPnl', 0.0) or 0.0)
                margin = float(pos_data.get('initialMargin', 0.0) or pos_data.get('margin', 0.0) or 0.0)
                
                pnl_percentage = (pnl / margin) * 100 if margin > 0 else 0
                pnl_status = "⬆️ KAR" if pnl >= 0 else "⬇️ ZARAR"
                notional_value = float(pos_data.get('notional', 0.0) or 0.0)

                print(f"  - {unified_symbol} ({side.upper()}) | Büyüklük: {notional_value:.2f} USDT | PNL: {pnl:.2f} USDT ({pnl_percentage:.2f}%) [{pnl_status}]")
                
                if unified_symbol in old_managed_positions_map:
                    old_pos = old_managed_positions_map[unified_symbol]
                    old_pos['amount'] = amount
                    updated_managed_list.append(old_pos)
                else:
                    add_to_bot = input(f"      >>> Bu pozisyon bot tarafından yönetilmiyor. Yönetime eklensin mi? (evet/hayır): ").lower()
                    if add_to_bot == 'evet':
                        timeframe = input(f"      >>> Orijinal zaman aralığını girin (örn: 1h, 15m): ").lower().strip() or "1h"
                        
                        # === DEĞİŞİKLİK BURADA ===
                        # `get` ile gelen `None` değerini `or` ile yakalayıp varsayılan değeri atıyoruz.
                        leverage = float(pos_data.get('leverage') or config.LEVERAGE)
                        
                        managed_position = {
                            "symbol": unified_symbol, "side": side, "amount": amount,
                            "entry_price": entry_price, "timeframe": timeframe, "leverage": leverage
                        }
                        updated_managed_list.append(managed_position)
                        print(f"      +++ {unified_symbol} pozisyonu bot yönetimine eklendi.")
        
        with positions_lock:
            open_positions_managed_by_bot = updated_managed_list
            save_positions_to_file()
        print("--- Senkronizasyon tamamlandı. ---")
    except Exception as e:
        logging.error(f"Senkronizasyon sırasında hata oluştu: {e}")
        import traceback
        traceback.print_exc() # Hatanın tam traceback'ini görmek için


def _execute_single_scan_cycle():
    logging.info("--- Yeni Tarama Döngüsü Başlatılıyor ---")
    try:
        with positions_lock:
            if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
                logging.warning(f"Maksimum pozisyon limitine ({config.MAX_CONCURRENT_TRADES}) ulaşıldı.")
                return

        symbols_to_process = get_top_gainers_losers(config.PROACTIVE_SCAN_TOP_N) if config.PROACTIVE_SCAN_USE_GAINERS_LOSERS else [{'symbol': s} for s in config.PROACTIVE_SCAN_COIN_LIST]

        if not symbols_to_process:
            logging.warning("Taranacak sembol bulunamadı.")
            return

        with positions_lock:
            open_symbols = {p['symbol'] for p in open_positions_managed_by_bot}
        
        symbols_to_process = [s for s in symbols_to_process if s.get('symbol') and s['symbol'] not in open_symbols]
        
        if not symbols_to_process:
            logging.info("Tüm potansiyel semboller için zaten açık pozisyon var.")
            return

        logging.info(f"Analiz edilecek {len(symbols_to_process)} sembol: {', '.join([s['symbol'] for s in symbols_to_process])}")

        market_data_batch = []
        timeframe = config.PROACTIVE_SCAN_TIMEFRAME
        for item in symbols_to_process:
            symbol = item['symbol']
            price = item.get('price')
            if price is None:
                logging.warning(f"{symbol} için fiyat bilgisi Gainer/Loser listesinden alınamadı, atlanıyor.")
                continue

            logging.info(f"...Teknik veri toplanıyor: {symbol}")
            
            tech_data_result = get_technical_indicators.invoke({"symbol_and_timeframe": f"{symbol},{timeframe}"})

            if tech_data_result.get("status") != "success":
                logging.warning(f"{symbol} için veri alınamadı: {tech_data_result.get('message')}")
                time.sleep(1)
                continue
            
            market_data_batch.append({
                "symbol": symbol,
                "price": price,
                "indicators": tech_data_result["data"]
            })
            time.sleep(1)

        if not market_data_batch:
            logging.info("Analiz edilecek geçerli veri bulunamadı.")
            return

        logging.info(f"Toplam {len(market_data_batch)} sembol için toplu analiz isteği gönderiliyor...")
        batch_prompt = create_batch_analysis_prompt(market_data_batch)
        result = agent_executor.invoke({"input": batch_prompt})
        recommendations = parse_agent_response(result.get("output", ""))

        if not recommendations or not isinstance(recommendations, list):
            logging.error(f"Toplu analizden geçerli bir yanıt alınamadı: {recommendations}")
            return
        
        print("\n--- PROAKTİF TARAMA SONUÇLARI ---")
        actionable_opportunities = []
        for rec in recommendations:
            print(f"  - {rec.get('symbol')}: {rec.get('recommendation')} ({rec.get('reason')})")
            if rec.get("recommendation") in ["AL", "SAT"]:
                price_info = next((d['price'] for d in market_data_batch if d['symbol'] == rec.get('symbol')), None)
                if price_info:
                    rec['price'] = price_info
                    rec['timeframe'] = timeframe
                    actionable_opportunities.append(rec)
        
        if actionable_opportunities:
            print("\n--- İŞLEM ONAYI GEREKEN FIRSATLAR ---")
            for opportunity in actionable_opportunities:
                 with positions_lock:
                    if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
                        logging.warning("Fırsat bulundu ancak maksimum pozisyon limitine ulaşıldı.")
                        break
                
                 handle_trade_confirmation(
                    recommendation=opportunity.get('recommendation'),
                    trade_symbol=opportunity.get('symbol'),
                    current_price=opportunity.get('price'),
                    timeframe=opportunity.get('timeframe'),
                    auto_confirm=config.PROACTIVE_SCAN_AUTO_CONFIRM
                )
        else:
            print("--- Bu tarama döngüsünde yeni bir işlem fırsatı bulunamadı. ---")

    except Exception as e:
        logging.critical(f"Proaktif tarama döngüsünde KRİTİK HATA: {e}", exc_info=True)
    
    logging.info("--- Tarama Döngüsü Tamamlandı. ---")


# ... (Dosyanın geri kalanı aynı, değişiklik yok) ...
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

def parse_agent_response(response: str) -> dict:
    if not response or not isinstance(response, str):
        return None
    try:
        if "Final Answer:" in response:
            response = response.split("Final Answer:")[1]
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        return json.loads(response.strip())
    except (json.JSONDecodeError, IndexError):
        logging.error(f"JSON ayrıştırma hatası. Gelen Yanıt: {response}")
        return None

def handle_trade_confirmation(recommendation, trade_symbol, current_price, timeframe, auto_confirm=False, parsed_data=None):
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        logging.error(f"Geçersiz fiyat bilgisi ({current_price}), işlem iptal edildi.")
        return

    prompt_message = f">>> [FIRSAT] {trade_symbol} @ {current_price} için '{recommendation}' tavsiyesi verildi. İşlem açılsın mı? (evet/hayır): "
    user_onay = "evet" if auto_confirm else input(prompt_message).lower()
    
    if user_onay == "evet":
        if auto_confirm:
            logging.info(f"İşlem otomatik olarak onaylandı: {trade_symbol}")
        try:
            with positions_lock:
                if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
                    print("\n### UYARI: Maksimum pozisyon limitine ulaşıldı. ###")
                    return

            trade_side = "buy" if "AL" in recommendation else "sell"
            leverage = config.LEVERAGE
            margin_usdt = config.TRADE_MARGIN_USDT
            position_value_usdt = margin_usdt * leverage
            trade_amount = position_value_usdt / current_price
            
            stop_loss_price, take_profit_price = 0, 0
            
            if config.USE_ATR_FOR_SLTP:
                atr_result = get_atr_value.invoke({"symbol_and_timeframe": f"{trade_symbol},{timeframe}"})
                if atr_result.get("status") != "success":
                    print(f"### HATA: ATR değeri alınamadı: {atr_result.get('message')} ###")
                    return
                
                atr_value = atr_result['value']
                stop_loss_distance = atr_value * config.ATR_MULTIPLIER_SL
                take_profit_distance = stop_loss_distance * config.RISK_REWARD_RATIO_TP
                
                if trade_side == "buy":
                    stop_loss_price = current_price - stop_loss_distance
                    take_profit_price = current_price + take_profit_distance
                else:
                    stop_loss_price = current_price + stop_loss_distance
                    take_profit_price = current_price - take_profit_distance
            
            position_to_open = {
                "symbol": trade_symbol, "side": trade_side, "amount": trade_amount, 
                "stop_loss": stop_loss_price, "take_profit": take_profit_price, "leverage": leverage
            }
            
            limit_price = None
            if config.DEFAULT_ORDER_TYPE == 'LIMIT':
                limit_price = current_price
                position_to_open['price'] = limit_price

            result_str = execute_trade_order.invoke(position_to_open)
            print(f"İşlem Sonucu: {result_str}")

            if "başarılı" in result_str.lower() or "simülasyon" in result_str.lower():
                final_entry_price = limit_price if limit_price else current_price
                managed_position_details = {
                    "symbol": trade_symbol, "side": trade_side, "amount": trade_amount, 
                    "entry_price": final_entry_price, "timeframe": timeframe, "leverage": leverage,
                    "stop_loss": stop_loss_price, "take_profit": take_profit_price
                }
                with positions_lock:
                    open_positions_managed_by_bot.append(managed_position_details)
                    save_positions_to_file()
                print("\n+++ YENİ POZİSYON AÇILDI VE BOT HAFIZASINA KAYDEDİLDİ +++")
                print(json.dumps(managed_position_details, indent=2))
            else:
                print(f"\n--- İŞLEM BAŞARISIZ OLDU. Dönen Mesaj: {result_str} ---")

        except Exception as e:
            logging.error(f"İşlem hazırlığı sırasında bir hata oluştu: {e}", exc_info=True)

def handle_new_analysis():
    with positions_lock:
        if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
            print("\n### UYARI: Maksimum pozisyon limitine ulaşıldı. ###")
            return
    timeframe = input(f"Zaman aralığı seçin (örn: 15m, 1h) [varsayılan: 1h]: ").lower().strip() or "1h"
    user_input = input(f"Analiz edilecek kripto parayı girin (örn: BTC): ")
    if not user_input: return
    
    print("\nYapay zeka analiz yapıyor, lütfen bekleyin...")
    analysis_prompt = create_analysis_prompt(user_input, config.DEFAULT_MARKET_TYPE, timeframe)
    result = agent_executor.invoke({"input": analysis_prompt})
    parsed_data = parse_agent_response(result.get("output", ""))
    
    if not parsed_data:
        print("\n--- HATA: Agent'tan geçerli bir yanıt alınamadı. ---")
        return

    print("\n--- Analiz Raporu ---")
    print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
    
    recommendation = parsed_data.get("recommendation")
    if recommendation in ["AL", "SAT"]:
        try:
            price_str = get_market_price.invoke({"symbol": parsed_data.get('symbol')})
            if "HATA" in price_str:
                raise ValueError("Piyasa fiyatı alınamadı.")
            price = float(re.search(r'[\d\.]+$', price_str).group())
            handle_trade_confirmation(
                recommendation=recommendation, 
                trade_symbol=parsed_data.get('symbol'), 
                current_price=price,
                timeframe=timeframe,
                parsed_data=parsed_data 
            )
        except (TypeError, ValueError) as e:
            print(f"\n--- HATA: Analiz yanıtında veya fiyatta sorun var. {e} ---")
    else:
        print("\n--- Bir işlem tavsiyesi ('AL' veya 'SAT') bulunamadı. ---")


def handle_manage_position():
    global open_positions_managed_by_bot
    with positions_lock:
        if not open_positions_managed_by_bot:
            print("Yönetilecek açık pozisyon bulunmuyor.")
            return
        print("\n--- Yönetilen Açık Pozisyonlar ---")
        for i, pos in enumerate(open_positions_managed_by_bot):
            print(f"  [{i+1}] {pos['symbol']} ({pos['side'].upper()}) | Giriş: {pos.get('entry_price', 'N/A')}")
    try:
        choice_str = input("Yönetmek istediğiniz pozisyonun numarasını girin (çıkmak için 'q'): ")
        if choice_str.lower() == 'q': return
        pos_index = int(choice_str) - 1
        with positions_lock:
            if not 0 <= pos_index < len(open_positions_managed_by_bot):
                print("Geçersiz numara.")
                return
            position_to_manage = open_positions_managed_by_bot[pos_index]
        while True:
            print(f"\n--- {position_to_manage['symbol']} Pozisyonu Yönetiliyor ---")
            print("1. Manuel Kapat")
            print("2. Pozisyonu Yeniden Analiz Et")
            print("3. Ana Menüye Dön")
            action_choice = input("Seçiminiz: ")
            if action_choice == '1':
                handle_manual_close(position_to_manage, pos_index)
                break 
            elif action_choice == '2':
                handle_reanalyze_position(position_to_manage, pos_index)
                break
            elif action_choice == '3':
                break
            else:
                print("Geçersiz seçim.")
    except (ValueError, IndexError):
        print("Geçersiz giriş.")

def handle_manual_close(position, index):
    print(f"UYARI: {position['symbol']} pozisyonunu manuel olarak kapatacaksınız.")
    onay = input("Emin misiniz? (evet/hayır): ").lower()
    if onay == 'evet':
        close_side = 'sell' if position['side'] == 'buy' else 'buy'
        result = execute_trade_order.invoke({
            "symbol": position['symbol'], 
            "side": close_side, 
            "amount": position['amount']
        })
        print(f"Kapatma Sonucu: {result}")
        if "başarılı" in result.lower() or "simülasyon" in result.lower():
            with positions_lock:
                if index < len(open_positions_managed_by_bot) and open_positions_managed_by_bot[index] == position:
                    open_positions_managed_by_bot.pop(index)
                    save_positions_to_file()
                print(f"+++ POZİSYON MANUEL OLARAK KAPATILDI: {position['symbol']} +++")

def handle_reanalyze_position(position, index):
    print(f"\n--- {position['symbol']} Pozisyonu Yeniden Analiz Ediliyor... ---")
    reanalysis_prompt = create_reanalysis_prompt(position)
    result = agent_executor.invoke({"input": reanalysis_prompt})
    parsed_data = parse_agent_response(result.get("output", ""))
    if not parsed_data:
        print("\n--- HATA: Yeniden analiz sırasında Agent'tan geçerli bir yanıt alınamadı. ---")
        return
    print("\n--- Yeniden Analiz Raporu ---")
    print(f"Tavsiye: {parsed_data.get('recommendation')}")
    print(f"Gerekçe: {parsed_data.get('reason')}")
    if parsed_data.get('recommendation') == 'KAPAT':
        handle_manual_close(position, index)

def background_position_checker():
    logging.info("--- Arka plan pozisyon kontrolcüsü başlatıldı. ---")
    while True:
        try:
            check_and_manage_positions_thread_safe()
        except Exception as e:
            logging.critical(f"Arka plan kontrolcüsünde KRİTİK HATA: {e}", exc_info=True)
        time.sleep(config.POSITION_CHECK_INTERVAL_SECONDS)

def main():
    load_positions_from_file()
    initialize_exchange(config.DEFAULT_MARKET_TYPE)
    
    print("\n" + "="*50)
    print("Bot başlatılıyor...")
    print(f"UYARI: CANLI İŞLEM MODU {'AKTİF' if config.LIVE_TRADING else 'KAPALI'}.")
    if config.LIVE_TRADING:
        print("Lütfen tüm ayarlarınızın doğruluğundan emin olun!")
    print("="*50 + "\n")
    
    checker_thread = threading.Thread(target=background_position_checker, daemon=True)
    checker_thread.start()
    
    while True:
        print("\n" + "="*50 + "\n           GEMINI TRADING AGENT MENU\n" + "="*50)
        print("1. Pozisyonları Göster ve Senkronize Et")
        print("2. Yeni Analiz Yap ve Pozisyon Aç")
        print("3. Açık Pozisyonu Yönet")
        if config.PROACTIVE_SCAN_ENABLED:
            print("P. PROAKTİF TARAMAYI BAŞLAT (Fırsat Avcısı)")
        print("4. Çıkış")
        choice = input("Seçiminiz: ").lower()
        
        if choice == "1":
            sync_and_display_positions()
        elif choice == "2":
            handle_new_analysis()
        elif choice == "3":
            handle_manage_position()
        elif choice == "p" and config.PROACTIVE_SCAN_ENABLED:
            run_proactive_scanner()
            if config.PROACTIVE_SCAN_IN_LOOP:
                print("Sürekli tarama modu aktif. Durdurmak için Ctrl+C kullanın.")
                try:
                    while checker_thread.is_alive():
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nSürekli tarama durduruldu. Ana menüye dönülüyor.")
        elif choice == "4":
            print("Bot kapatılıyor...")
            break
        else:
            print("Geçersiz seçim. Lütfen menüden bir seçenek girin.")
            time.sleep(1)

if __name__ == "__main__":
    main()