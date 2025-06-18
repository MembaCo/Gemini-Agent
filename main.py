# main.py
# @author: Memba Co.

import os
import json
import time
import threading
import logging
import subprocess
import sys
from dotenv import load_dotenv

import core
import tools
import config
import database
import telegram_bot

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

def sync_and_display_positions():
    """Borsa ile veritabanını senkronize eder ve pozisyonları listeler."""
    print("\n--- Pozisyonlar Görüntüleniyor... ---")
    
    if not config.LIVE_TRADING:
        print("--- SİMÜLASYON MODU AKTİF ---")
        positions = database.get_all_positions()
        if not positions:
            print("Yönetilen simüle pozisyon bulunmuyor.")
            return
        for pos in positions:
            print(f"  - {pos['symbol']} ({pos['side'].upper()}) | Giriş: {pos['entry_price']:.4f}")
        return

    print("--- CANLI MOD: Borsa ile Senkronize Ediliyor... ---")
    try:
        active_positions_db = database.get_all_positions()
        managed_symbols = {p['symbol'] for p in active_positions_db}

        exchange_positions_raw = tools.get_open_positions_from_exchange.invoke({})
        if not isinstance(exchange_positions_raw, list):
            logging.error(f"Borsadan pozisyonlar alınamadı: {exchange_positions_raw}"); return
        
        if not exchange_positions_raw:
             print("Borsada açık pozisyon bulunmuyor.")
        else:
             print(f"--- Borsada Bulunan Açık Pozisyonlar: {len(exchange_positions_raw)} ---")
             for pos_data in exchange_positions_raw:
                symbol = tools._get_unified_symbol(pos_data.get('symbol'))
                side = 'buy' if pos_data.get('side', 'long') == 'long' else 'sell'
                notional = float(pos_data.get('notional', 0.0) or 0.0)
                pnl = float(pos_data.get('unrealizedPnl', 0.0) or 0.0)
                is_managed = "✅ Yönetiliyor" if symbol in managed_symbols else "❌ Yönetilmiyor"
                print(f"  - {symbol} ({side.upper()}) | Büyüklük: {notional:.2f} USDT | PNL: {pnl:+.2f} USDT | {is_managed}")

        print("--- Senkronizasyon tamamlandı. ---")
    except Exception as e:
        logging.error(f"Senkronizasyon sırasında hata oluştu: {e}", exc_info=True)

def handle_new_analysis_cli():
    """Terminal üzerinden yeni analiz yapar."""
    symbol = input("Analiz edilecek sembol (örn: BTC): ").upper()
    timeframe = input("Zaman aralığı (örn: 15m): ") or "15m"
    if not symbol: return
    
    print(f"\n{symbol} için analiz başlatılıyor...")
    result = core.perform_analysis(symbol, timeframe)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result.get('status') == 'success' and result.get('recommendation') in ['AL', 'SAT']:
        onay = input(">>> Pozisyon açılsın mı? (e/h): ").lower()
        if onay == 'e':
            pos_result = core.open_new_position(
                result['recommendation'],
                result['symbol'],
                result['current_price'],
                result['timeframe']
            )
            print(pos_result.get('message'))
    else:
        print("Bir işlem tavsiyesi bulunamadı veya analiz başarısız oldu.")

def handle_manage_position_cli():
    """Terminalden açık bir pozisyonu yönetir."""
    positions = database.get_all_positions()
    if not positions:
        print("Yönetilecek pozisyon bulunmuyor.")
        return
    
    for i, pos in enumerate(positions):
        print(f"  [{i+1}] {pos['symbol']} ({pos['side'].upper()})")
    
    try:
        choice_str = input("İşlem yapılacak pozisyonun numarasını girin (çıkmak için 'q'): ")
        if choice_str.lower() == 'q': return
        choice_idx = int(choice_str) - 1
        position = positions[choice_idx]
        
        action = input(f"Ne yapmak istersiniz? (1: Kapat, 2: Yeniden Analiz Et): ")
        if action == '1':
            onay = input(f">>> {position['symbol']} pozisyonunu kapatmak istediğinizden emin misiniz? (e/h): ").lower()
            if onay == 'e':
                result = core.close_position_by_symbol(position['symbol'])
                print(result['message'])
            else:
                print("İşlem iptal edildi.")
        elif action == '2':
            print("Yeniden analiz ediliyor...")
            analysis_result = core.reanalyze_position(position)
            
            if analysis_result.get('status') == 'success':
                data = analysis_result['data']
                print(f"\n--- Yeniden Analiz Raporu [{position['symbol']}] ---")
                print(f"Tavsiye: {data.get('recommendation')}")
                print(f"Gerekçe: {data.get('reason')}")

                if data.get('recommendation') == 'KAPAT':
                    if config.AGENT_CLOSE_AUTO_CONFIRM:
                        print("Otomatik onay aktif. Pozisyon kapatılıyor...")
                        close_result = core.close_position_by_symbol(position['symbol'], "AGENT_CLOSE")
                        print(close_result.get('message'))
                    else:
                        onay = input(">>> Ajan pozisyonu kapatmayı tavsiye ediyor. Onaylıyor musunuz? (e/h): ").lower()
                        if onay == 'e':
                            close_result = core.close_position_by_symbol(position['symbol'], "AGENT_CLOSE")
                            print(close_result.get('message'))
                        else:
                            print("Kapatma işlemi iptal edildi.")
            else:
                print(f"Analiz başarısız oldu: {analysis_result.get('message')}")
    except (ValueError, IndexError):
        print("Geçersiz seçim.")

def launch_dashboard():
    """Web arayüzü sunucusunu ayrı bir işlem olarak başlatır."""
    dashboard_script = os.path.join('dashboard', 'app.py')
    if not os.path.exists(dashboard_script):
        print("HATA: 'dashboard/app.py' dosyası bulunamadı.")
        return

    print("\n--- 📈 Web Arayüzü Başlatılıyor... ---")
    try:
        subprocess.Popen([sys.executable, dashboard_script])
        print(f"✅ Sunucu başlatıldı. http://localhost:5001 adresini tarayıcıda açın.")
    except Exception as e:
        print(f"❌ Web arayüzü başlatılamadı: {e}")

def cli_proactive_scanner():
    """CLI için proaktif tarayıcıyı çalıştırır."""
    print("\n--- PROAKTİF TARAMA (CLI MODU) ---")
    
    def opportunity_handler(data):
        print("\n" + "="*20)
        print(f"🚨 FIRSAT BİLDİRİMİ (CLI) 🚨")
        print(f"Sembol: {data['symbol']}")
        print(f"Tavsiye: {data['recommendation']}")
        print(f"Fiyat: {data['current_price']}")
        print(f"Gerekçe: {data['reason']}")
        print("="*20 + "\n")
        onay = input(">>> Bu pozisyon açılsın mı? (e/h): ").lower()
        if onay == 'e':
            result = core.open_new_position(
                data['recommendation'], data['symbol'], data['current_price'], data['timeframe']
            )
            print(f"CLI: Pozisyon açma sonucu: {result.get('message')}")

    def status_handler(message):
        print(f"CLI TARAMA DURUMU: {message}")

    core.run_proactive_scanner(
        opportunity_callback=opportunity_handler,
        status_callback=status_handler
    )

def main():
    try:
        database.init_db()
        tools.initialize_exchange(config.DEFAULT_MARKET_TYPE)
    except Exception as e:
        logging.critical(f"Uygulama başlatılırken kritik bir hata oluştu: {e}")
        sys.exit(1)

    print("\n" + "="*50)
    print(f"           GEMINI TRADING AGENT BAŞLATILDI")
    print(f"                 Versiyon: {config.APP_VERSION}")
    print("="*50)

    checker_thread = threading.Thread(target=core.background_position_checker, daemon=True)
    checker_thread.start()

    if config.TELEGRAM_ENABLED:
        logging.info("--- Telegram Botu başlatılıyor... ---")
        telegram_thread = threading.Thread(target=telegram_bot.run_telegram_bot, daemon=True)
        telegram_thread.start()

    launch_dashboard()

    menu_options = {
        "1": ("Pozisyonları Göster", sync_and_display_positions),
        "2": ("Yeni Analiz Yap (CLI)", handle_new_analysis_cli),
        "3": ("Açık Pozisyonu Yönet (CLI)", handle_manage_position_cli),
        "p": ("PROAKTİF TARAMAYI BAŞLAT (CLI)", cli_proactive_scanner),
        "q": ("Çıkış", lambda: print("Bot kapatılıyor..."))
    }
    
    while True:
        print("\n" + "="*50 + "\n           TERMINAL MENU\n" + "="*50)
        for key, (text, _) in menu_options.items():
            print(f"{key}. {text}")

        choice = input("Seçiminiz: ").lower().strip()
        
        if choice == "q":
            menu_options[choice][1]()
            sys.exit(0)

        action = menu_options.get(choice)
        if action:
            action[1]()
        else:
            print("Geçersiz seçim.")

if __name__ == "__main__":
    main()