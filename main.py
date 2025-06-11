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
    _get_unified_symbol, get_top_gainers_losers, _fetch_price_natively
)
import config
from config import APP_VERSION

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
        max_iterations=5
    )
except Exception as e:
    logging.critical(f"LLM veya Agent başlatılırken hata oluştu: {e}")
    exit()

# <<< HATA DÜZELTME: Eksik fonksiyonlar buraya eklendi >>>
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

def create_mta_analysis_prompt(symbol: str, price: float, entry_timeframe: str, entry_indicators: dict, trend_timeframe: str, trend_indicators: dict) -> str:
    """
    Çoklu Zaman Aralığı (MTA) analizi için Gemini'ye özel bir prompt oluşturur.
    """
    entry_indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in entry_indicators.items()])
    trend_indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in trend_indicators.items()])

    return f"""
    Sen, Çoklu Zaman Aralığı (MTA) konusunda uzmanlaşmış profesyonel bir trading analistisin.
    Görevin, sana sunulan iki farklı zaman aralığına ait veriyi birleştirerek kapsamlı bir analiz yapmak ve net bir ticaret kararı ('AL', 'SAT' veya 'BEKLE') vermektir.

    ## ANALİZ KURALLARI:
    1.  **Önce Trendi Belirle:** İlk olarak '{trend_timeframe}' zaman aralığındaki verilere bakarak ana trendin yönünü (Yükseliş, Düşüş, Yönsüz) belirle. ADX > 25 ise trendin güçlü olduğunu unutma.
    2.  **Sinyali Trend ile Teyit Et:** Ardından '{entry_timeframe}' zaman aralığındaki giriş sinyalini analiz et.
        - Eğer ana trend Yükseliş ise ve giriş sinyali 'AL' ise, bu güçlü bir teyittir. Kararın 'AL' olabilir.
        - Eğer ana trend Düşüş ise ve giriş sinyali 'SAT' ise, bu güçlü bir teyittir. Kararın 'SAT' olabilir.
        - **Eğer trend ile sinyal arasında bir uyumsuzluk varsa (örn: Trend yükselirken giriş sinyali 'SAT' ise) VEYA ana trend 'Yönsüz' ise, kararını 'BEKLE' olarak ver.**
    3.  **Gerekçeni Açıkla:** Kararının arkasındaki mantığı, her iki zaman aralığından da bahsederek kısaca açıkla.

    ## SAĞLANAN VERİLER:
    - Sembol: {symbol}
    - Anlık Fiyat: {price}

    ### Ana Trend Verileri ({trend_timeframe})
    {trend_indicator_text}

    ### Giriş Sinyali Verileri ({entry_timeframe})
    {entry_indicator_text}

    ## İSTENEN JSON ÇIKTI FORMATI:
    Kararını ve gerekçeni, aşağıda formatı verilen JSON çıktısı olarak sun. Başka hiçbir açıklama yapma.
    ```json
    {{
      "symbol": "{symbol}",
      "timeframe": "{entry_timeframe}",
      "recommendation": "KARARIN (AL, SAT, veya BEKLE)",
      "reason": "MTA analizine dayalı kısa ve net gerekçen. (Örn: '4h trendi yükselişteyken, 15m'de RSI ve MACD AL sinyali üretti.')",
      "analysis_type": "MTA",
      "trend_timeframe": "{trend_timeframe}",
      "data": {{
        "price": {price}
      }}
    }}
    ```
    """

def create_final_analysis_prompt(symbol: str, timeframe: str, price: float, indicators: dict) -> str:
    """Tekli zaman aralığı analizi için standart prompt'u oluşturur."""
    indicator_text = "\n".join([f"- {key}: {value:.4f}" for key, value in indicators.items()])
    return f"""
    Sen, uzman bir trading analistisin.
    Aşağıda sana '{symbol}' adlı kripto para için '{timeframe}' zaman aralığında toplanmış veriler sunulmuştur.

    GÖREVİN: Bu verileri analiz ederek 'AL', 'SAT' veya 'BEKLE' şeklinde net bir tavsiye kararı ver.
    Kararını ve gerekçeni, aşağıda formatı verilen JSON çıktısı olarak sun. Başka hiçbir açıklama yapma.

    SAĞLANAN VERİLER:
    - Anlık Fiyat: {price}
    Teknik Göstergeler:
    {indicator_text}

    İSTENEN JSON ÇIKTI FORMATI:
    ```json
    {{
      "symbol": "{symbol}",
      "timeframe": "{timeframe}",
      "recommendation": "KARARIN (AL, SAT, veya BEKLE)",
      "reason": "Kararının kısa ve net gerekçesi.",
      "analysis_type": "Single",
      "data": {{
        "price": {price}
      }}
    }}
    ```
    """

def handle_new_analysis():
    with positions_lock:
        if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
            print("\n### UYARI: Maksimum pozisyon limitine ulaşıldı. ###")
            return

    entry_timeframe = input(f"Giriş için zaman aralığı seçin (örn: 15m, 1h) [varsayılan: 15m]: ").lower().strip() or "15m"
    user_input = input(f"Analiz edilecek kripto parayı girin (örn: BTC): ")
    if not user_input: return
    
    unified_symbol = _get_unified_symbol(user_input)
    
    use_mta = config.USE_MTA_ANALYSIS
    trend_timeframe = config.MTA_TREND_TIMEFRAME if use_mta else None
    
    if use_mta:
        print(f"\nÇoklu Zaman Aralığı (MTA) Analizi başlatılıyor ({unified_symbol})...")
        print(f"Trend Zaman Aralığı: {trend_timeframe}, Giriş Zaman Aralığı: {entry_timeframe}")
    else:
        print(f"\nStandart analiz başlatılıyor ({unified_symbol}, {entry_timeframe})...")
    
    print("Veriler toplanıyor...")
    
    try:
        current_price = _fetch_price_natively(unified_symbol)
        if current_price is None:
            print(f"HATA: Fiyat bilgisi alınamadı: {unified_symbol}")
            return
        
        entry_indicators_result = get_technical_indicators.invoke({"symbol_and_timeframe": f"{unified_symbol},{entry_timeframe}"})
        if entry_indicators_result.get("status") != "success":
            print(f"HATA: Giriş ({entry_timeframe}) için teknik göstergeler alınamadı: {entry_indicators_result.get('message')}")
            return
        entry_indicators_data = entry_indicators_result["data"]
        
        final_prompt = ""
        if use_mta:
            trend_indicators_result = get_technical_indicators.invoke({"symbol_and_timeframe": f"{unified_symbol},{trend_timeframe}"})
            if trend_indicators_result.get("status") != "success":
                print(f"HATA: Trend ({trend_timeframe}) için teknik göstergeler alınamadı: {trend_indicators_result.get('message')}")
                return
            trend_indicators_data = trend_indicators_result["data"]
            
            final_prompt = create_mta_analysis_prompt(
                symbol=unified_symbol,
                price=current_price,
                entry_timeframe=entry_timeframe,
                entry_indicators=entry_indicators_data,
                trend_timeframe=trend_timeframe,
                trend_indicators=trend_indicators_data
            )
        else:
            final_prompt = create_final_analysis_prompt(unified_symbol, entry_timeframe, current_price, entry_indicators_data)

        print("Yapay zeka analizi yapılıyor...")
        result = llm.invoke(final_prompt)
        parsed_data = parse_agent_response(result.content)

        if not parsed_data:
            print("\n--- HATA: Yapay zekadan geçerli bir JSON yanıtı alınamadı. Yanıt: ---")
            print(result.content)
            return

        print("\n--- Analiz Raporu ---")
        print(json.dumps(parsed_data, indent=2, ensure_ascii=False))

        recommendation = parsed_data.get("recommendation")
        if recommendation in ["AL", "SAT"]:
            price_from_report = parsed_data.get('data', {}).get('price', current_price)
            handle_trade_confirmation(
                recommendation=recommendation,
                trade_symbol=parsed_data.get('symbol'),
                current_price=price_from_report,
                timeframe=entry_timeframe, 
                parsed_data=parsed_data
            )
        else:
            print("\n--- Bir işlem tavsiyesi ('AL' veya 'SAT') bulunamadı. ---")

    except Exception as e:
        print(f"\n--- KRİTİK HATA: Analiz sırasında bir sorun oluştu. ---")
        logging.error(f"handle_new_analysis hatası: {e}", exc_info=True)

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
            current_price = _fetch_price_natively(position["symbol"])
            if current_price is None:
                continue

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
        execute_trade_order.invoke({
            "symbol": pos_to_close['symbol'], 
            "side": close_side, 
            "amount": pos_to_close['amount']
        })
        with positions_lock:
            if index < len(open_positions_managed_by_bot) and open_positions_managed_by_bot[index] == pos_to_close:
                open_positions_managed_by_bot.pop(index)
                save_positions_to_file()
                logging.info(f"Bot hafızasından silindi: {pos_to_close['symbol']}")


def sync_and_display_positions():
    """
    Pozisyonları görüntüler. CANLI modda borsa ile senkronize olur.
    SİMÜLASYON modunda ise sadece botun kendi hafızasındaki pozisyonları listeler.
    """
    global open_positions_managed_by_bot
    print("\n--- Pozisyonlar Görüntüleniyor... ---")

    if not config.LIVE_TRADING:
        print("--- SİMÜLASYON MODU AKTİF ---")
        with positions_lock:
            load_positions_from_file()
            if not open_positions_managed_by_bot:
                print("Bot tarafından yönetilen simüle edilmiş pozisyon bulunmuyor.")
            else:
                print(f"--- Bot Hafızasındaki Simüle Pozisyonlar: {len(open_positions_managed_by_bot)} ---")
                for pos in open_positions_managed_by_bot:
                    pnl_info = "| PNL Hesaplanamadı"
                    current_price = _fetch_price_natively(pos['symbol'])
                    
                    if current_price is not None:
                        entry_price = pos.get('entry_price', 0)
                        amount = pos.get('amount', 0)
                        leverage = pos.get('leverage', 1)
                        side = pos.get('side', 'buy')
                        
                        pnl = (current_price - entry_price) * amount
                        if side == 'sell':
                            pnl = -pnl
                        
                        margin = (entry_price * amount) / leverage if leverage > 0 else (entry_price * amount)
                        pnl_percentage = (pnl / margin) * 100 if margin > 0 else 0
                        pnl_status = "⬆️ KAR" if pnl >= 0 else "⬇️ ZARAR"
                        
                        pnl_info = f"| PNL (Tahmini): {pnl:+.2f} USDT ({pnl_percentage:+.2f}%) {pnl_status}"
                    
                    print(f"  - {pos['symbol']} ({pos['side'].upper()}) | Giriş: {pos.get('entry_price', 0):.4f} | Miktar: {pos.get('amount', 0):.4f} {pnl_info}")
        
        print("--- Simülasyon gösterimi tamamlandı. ---")
        return

    print("--- CANLI MOD: Borsa ile Senkronize Ediliyor... ---")
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
        logging.error(f"Senkronizasyon sırasında hata oluştu: {e}", exc_info=True)


def _execute_single_scan_cycle():
    """Proaktif tarama döngüsünün tek bir adımını çalıştırır."""
    logging.info("--- Yeni Tarama Döngüsü Başlatılıyor ---")
    try:
        with positions_lock:
            if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
                logging.warning(f"Maksimum pozisyon limitine ({config.MAX_CONCURRENT_TRADES}) ulaşıldı. Tarama atlanıyor.")
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
        
        for item in symbols_to_process:
            symbol = item['symbol']
            price = item.get('price')
            if price is None:
                logging.warning(f"{symbol} için fiyat bilgisi Gainer/Loser listesinden alınamadı, atlanıyor.")
                continue

            successful_result = None
            successful_timeframe = None

            for timeframe in config.PROACTIVE_SCAN_TIMEFRAMES:
                logging.info(f"...Teknik veri toplanıyor: {symbol} (Zaman aralığı: {timeframe})")
                
                tech_data_result = get_technical_indicators.invoke({"symbol_and_timeframe": f"{symbol},{timeframe}"})

                if tech_data_result.get("status") == "success":
                    successful_result = tech_data_result
                    successful_timeframe = timeframe
                    logging.info(f"+++ Veri başarıyla toplandı: {symbol} @ {timeframe}")
                    break
                else:
                    logging.warning(f"--- Veri alınamadı ({timeframe}): {tech_data_result.get('message')}. Sonraki zaman aralığı denenecek...")
                    time.sleep(1)

            if successful_result:
                market_data_batch.append({
                    "symbol": symbol,
                    "price": price,
                    "indicators": successful_result["data"],
                    "timeframe": successful_timeframe
                })
            else:
                logging.error(f"Tüm zaman aralıkları denendi, {symbol} için veri alınamadı, bu sembol atlanıyor.")

        if not market_data_batch:
            logging.info("Analiz edilecek geçerli veri bulunamadı.")
            return

        logging.info(f"Toplam {len(market_data_batch)} sembol için toplu analiz isteği gönderiliyor...")
        batch_prompt = create_batch_analysis_prompt(market_data_batch)
        result = llm.invoke(batch_prompt)
        recommendations = parse_agent_response(result.content)

        if not recommendations or not isinstance(recommendations, list):
            logging.error(f"Toplu analizden geçerli bir yanıt alınamadı: {recommendations}")
            return
        
        print("\n--- PROAKTİF TARAMA SONUÇLARI ---")
        actionable_opportunities = []
        for rec in recommendations:
            print(f"  - {rec.get('symbol')}: {rec.get('recommendation')} ({rec.get('reason')})")
            if rec.get("recommendation") in ["AL", "SAT"]:
                source_data = next((d for d in market_data_batch if d['symbol'] == rec.get('symbol')), None)
                if source_data:
                    rec['price'] = source_data['price']
                    rec['timeframe'] = source_data['timeframe']
                    actionable_opportunities.append(rec)
        
        if actionable_opportunities:
            print("\n--- İŞLEM ONAYI GEREKEN FIRSATLAR ---")
            for opportunity in actionable_opportunities:
                with positions_lock:
                    if len(open_positions_managed_by_bot) >= config.MAX_CONCURRENT_TRADES:
                        logging.warning("Fırsat bulundu ancak maksimum pozisyon limitine ulaşıldı. Diğer fırsatlar atlanıyor.")
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
        if response.strip().lower().startswith("json"):
            response = response.strip()[4:]

        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
            
        return json.loads(response.strip())
    except (json.JSONDecodeError, IndexError):
        logging.error(f"JSON ayrıştırma hatası. Gelen Yanıt: {response}")
        return None

def handle_trade_confirmation(recommendation, trade_symbol, current_price, timeframe, auto_confirm=False, parsed_data=None):
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        logging.error(f"Geçersiz fiyat bilgisi ({current_price}), işlem iptal edildi.")
        return

    prompt_message = f">>> [FIRSAT] {trade_symbol} @ {current_price:.4f} için '{recommendation}' tavsiyesi verildi. İşlem açılsın mı? (evet/hayır): "
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

            if "başarı" in result_str.lower() or "simülasyon" in result_str.lower():
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
        if "başarı" in result.lower() or "simülasyon" in result.lower():
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
    print(f"           GEMINI TRADING AGENT BAŞLATILDI")
    print(f"                 Versiyon: {APP_VERSION}")
    print("="*50)
    print(f"UYARI: CANLI İŞLEM MODU {'✅ AKTİF ✅' if config.LIVE_TRADING else '❌ KAPALI (Simülasyon Modu) ❌'}.")
    if config.LIVE_TRADING:
        print("DİKKAT: Bot, Binance hesabınızda gerçek para ile işlem yapacaktır!")
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
        choice = input("Seçiminiz: ").lower().strip()
        
        if choice == "1":
            sync_and_display_positions()
        elif choice == "2":
            handle_new_analysis()
        elif choice == "3":
            handle_manage_position()
        elif choice == "p" and config.PROACTIVE_SCAN_ENABLED:
            run_proactive_scanner()
        elif choice == "4":
            print("Bot kapatılıyor...")
            break
        else:
            print("Geçersiz seçim. Lütfen menüden bir seçenek girin.")
            time.sleep(1)

if __name__ == "__main__":
    main()