# notifications.py
# @author: Memba Co.

import requests
import logging
import os
from dotenv import load_dotenv
import config

load_dotenv()

def send_telegram_message(message: str):
    """Telegram API'sini kullanarak belirli bir chat'e mesaj gönderir."""
    if not config.TELEGRAM_ENABLED: return
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logging.warning("Telegram token veya chat ID bulunamadı. Bildirim gönderilemedi.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logging.error(f"Telegram'a bildirim gönderilemedi: {response.json()}")
    except requests.RequestException as e:
        logging.error(f"Telegram API'sine bağlanırken bir hata oluştu: {e}")

def format_open_position_message(pos_details: dict) -> str:
    """Yeni açılan bir pozisyon için Telegram mesajını formatlar."""
    symbol = pos_details.get('symbol', 'N/A').replace('/', r'\/')
    side_emoji = "📈" if pos_details.get('side') == 'buy' else "📉"
    
    # DÜZELTME: Fiyat formatlayıcıları .8f olarak güncellendi.
    message = (
        f"*{side_emoji} YENİ POZİSYON AÇILDI *`{symbol}`\n\n"
        f"➡️ *Yön:* `{pos_details.get('side', 'N/A').upper()}`\n"
        f"💰 *Giriş Fiyatı:* `{pos_details.get('entry_price', 0):.8f}`\n"
        f"📦 *Miktar:* `{pos_details.get('amount', 0):.4f}`\n"
        f"⚙️ *Kaldıraç:* `{pos_details.get('leverage', 1):.0f}x`\n\n"
        f"🛑 *Stop-Loss:* `{pos_details.get('stop_loss', 0):.8f}`\n"
        f"🎯 *Take-Profit:* `{pos_details.get('take_profit', 0):.8f}`"
    )
    return message

def format_close_position_message(closed_pos: dict, pnl: float, status: str) -> str:
    """Kapanan bir pozisyon için Telegram mesajı formatlar."""
    symbol = closed_pos.get('symbol', 'N/A').replace('/', r'\/')
    pnl_emoji = "✅" if pnl >= 0 else "❌"

    # DÜZELTME: Fiyat formatlayıcıları .8f olarak güncellendi.
    message = (
        f"*{pnl_emoji} POZİSYON KAPANDI *`{symbol}`\n\n"
        f"▪️ *Kapanış Nedeni:* `{status}`\n"
        f"💵 *P&L:* `{pnl:+.2f} USDT`\n\n"
        f"Giriş Fiyatı: `{closed_pos.get('entry_price', 0):.8f}`\n"
        f"Kapanış Fiyatı: `{closed_pos.get('close_price', 0):.8f}`"
    )
    return message

def format_partial_tp_message(symbol: str, close_amount: float, remaining_amount: float, entry_price: float) -> str:
    """Kısmi kâr alındığında Telegram mesajı formatlar."""
    symbol_md = symbol.replace('/', r'\/')
    # DÜZELTME: Fiyat formatlayıcısı .8f olarak güncellendi.
    message = (
        f"✅ *KISMİ KÂR ALINDI* `{symbol_md}`\n\n"
        f"Pozisyonun bir kısmı kapatılarak kâr realize edildi ve kalan pozisyonun riski sıfırlandı.\n\n"
        f"▪️ *Kapatılan Miktar:* `{close_amount:.4f}`\n"
        f"▪️ *Kalan Miktar:* `{remaining_amount:.4f}`\n"
        f"▪️ *Yeni Stop-Loss:* `{entry_price:.8f}` (Giriş Seviyesi)"
    )
    return message