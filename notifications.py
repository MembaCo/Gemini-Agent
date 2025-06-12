# notifications.py
# @author: Memba Co.

import requests
import logging
import os
from dotenv import load_dotenv
import config

# .env dosyasındaki değişkenleri yükle
load_dotenv()

def send_telegram_message(message: str):
    """
    Telegram API'sini kullanarak belirli bir chat'e mesaj gönderir.
    Bu fonksiyonun çalışması için .env dosyasında TELEGRAM_BOT_TOKEN ve
    TELEGRAM_CHAT_ID değişkenlerinin tanımlanmış olması gerekir.
    """
    # Bildirimler config dosyasında aktif edilmemişse fonksiyonu terk et
    if not config.TELEGRAM_ENABLED:
        return

    # Gerekli çevre değişkenlerini al
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # Token veya chat_id eksikse uyarı ver ve fonksiyonu sonlandır
    if not token or not chat_id:
        logging.warning("Telegram token veya chat ID bulunamadı. Bildirim gönderilemedi.")
        return

    # Telegram API'sine gönderilecek URL'yi ve payload'u hazırla
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"  # Mesaj formatını Markdown olarak ayarla
    }

    try:
        # Mesajı göndermek için POST isteği yap
        response = requests.post(url, json=payload, timeout=10)
        # İstek başarısız olursa JSON yanıtından hata mesajını logla
        if response.status_code != 200:
            logging.error(f"Telegram'a bildirim gönderilemedi. Hata Kodu: {response.status_code}, Yanıt: {response.json()}")
    except requests.RequestException as e:
        # Ağ hatası veya başka bir istek hatası olursa logla
        logging.error(f"Telegram API'sine bağlanırken bir hata oluştu: {e}")

def format_open_position_message(pos_details: dict) -> str:
    """Yeni açılan bir pozisyon için Telegram mesajı formatlar."""
    symbol = pos_details.get('symbol', 'N/A').replace('/', r'\/')
    side_emoji = "📈" if pos_details.get('side') == 'buy' else "📉"
    
    message = (
        f"*{side_emoji} YENİ POZİSYON AÇILDI *`{symbol}`\n\n"
        f"➡️ *Yön:* `{pos_details.get('side', 'N/A').upper()}`\n"
        f"💰 *Giriş Fiyatı:* `{pos_details.get('entry_price', 0):.4f}`\n"
        f"📦 *Miktar:* `{pos_details.get('amount', 0):.4f}`\n"
        f"⚙️ *Kaldıraç:* `{pos_details.get('leverage', 1)}x`\n\n"
        f"🛑 *Stop-Loss:* `{pos_details.get('stop_loss', 0):.4f}`\n"
        f"🎯 *Take-Profit:* `{pos_details.get('take_profit', 0):.4f}`"
    )
    return message

def format_close_position_message(closed_pos: dict, pnl: float, status: str) -> str:
    """Kapanan bir pozisyon için Telegram mesajı formatlar."""
    symbol = closed_pos.get('symbol', 'N/A').replace('/', r'\/')
    pnl_emoji = "✅" if pnl >= 0 else "❌"
    
    message = (
        f"*{pnl_emoji} POZİSYON KAPANDI *`{symbol}`\n\n"
        f"▪️ *Kapanış Nedeni:* `{status}`\n"
        f"💵 *P&L:* `{pnl:+.2f} USDT`\n\n"
        f"Giriş Fiyatı: `{closed_pos.get('entry_price', 0):.4f}`\n"
        f"Kapanış Fiyatı: `{closed_pos.get('close_price', 0):.4f}`"
    )
    return message
