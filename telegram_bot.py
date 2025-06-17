# telegram_bot.py
# @author: Memba Co.

import logging
import os
import json
import asyncio
from dotenv import load_dotenv

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Projemizin diğer modüllerini import ediyoruz
import database
import config
from tools import _get_unified_symbol

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# Temel loglama ayarı
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def set_commands(application: Application):
    """Bot için komut listesini ayarlar."""
    commands = [
        BotCommand("start", "Botu başlatır ve yardım mesajı gösterir."),
        BotCommand("status", "Borsadaki açık pozisyonların durumunu gösterir."),
        BotCommand("pozisyonlar", "Yönetilen pozisyonları ve işlem seçeneklerini gösterir."),
        BotCommand("analiz", "Yeni bir sembol analizi yapar. Örn: /analiz BTC 15m"),
        BotCommand("tara", "Proaktif tarama modunu bir kereliğine çalıştırır."),
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komutu gönderildiğinde çalışır."""
    user = update.effective_user
    help_text = (
        f"Merhaba {user.first_name}! Gemini Trading Agent kontrol paneline hoş geldiniz.\n\n"
        "Kullanabileceğiniz komutlar:\n"
        "▪️ /status - Borsadaki tüm açık pozisyonları listeler.\n"
        "▪️ /pozisyonlar - Bot tarafından yönetilen pozisyonları gösterir ve işlem yapmanızı sağlar.\n"
        "▪️ /analiz <SEMBOl> [zaman_aralığı] - Yeni bir analiz yapar. Örn: `/analiz ETH 1h`\n"
        "▪️ /tara - Fırsat avcısını manuel olarak tetikler."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status komutu için anlık pozisyon durumunu gönderir."""
    await update.message.reply_text("Pozisyon durumu kontrol ediliyor, lütfen bekleyin...")
    get_status_func = context.bot_data.get('get_status')
    if get_status_func:
        status_message = await asyncio.to_thread(get_status_func)
        await update.message.reply_html(status_message)
    else:
        await update.message.reply_text("❌ Hata: Durum sorgulama fonksiyonu bulunamadı.")

async def list_managed_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Yönetilen pozisyonları butonlarla listeler."""
    positions = await asyncio.to_thread(database.get_all_positions)
    if not positions:
        await update.message.reply_text("Bot tarafından yönetilen aktif pozisyon bulunmuyor.")
        return

    keyboard = []
    for pos in positions:
        symbol = pos['symbol']
        button_text = f"{symbol} ({pos['side'].upper()})"
        keyboard.append([
            InlineKeyboardButton("🔄 Yeniden Analiz", callback_data=f"reanalyze:{symbol}"),
            InlineKeyboardButton("❌ Kapat", callback_data=f"close_confirm:{symbol}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('İşlem yapmak istediğiniz pozisyonu seçin:', reply_markup=reply_markup)

async def analyze_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/analiz komutunu işler."""
    _perform_analysis = context.bot_data.get('analyze')
    if not _perform_analysis:
        await update.message.reply_text("❌ Hata: Analiz fonksiyonu başlatılamadı.")
        return

    if not context.args:
        await update.message.reply_text("Lütfen bir sembol belirtin. Örnek: /analiz BTC 15m")
        return

    symbol = context.args[0]
    timeframe = context.args[1] if len(context.args) > 1 else config.PROACTIVE_SCAN_ENTRY_TIMEFRAME
    
    await update.message.reply_text(f"⏳ {symbol} için {timeframe} zaman aralığında analiz başlatılıyor...")

    analysis_result = await asyncio.to_thread(
        _perform_analysis,
        symbol=symbol,
        entry_tf=timeframe,
        use_mta=config.USE_MTA_ANALYSIS,
        trend_tf=config.MTA_TREND_TIMEFRAME
    )
    
    if not analysis_result:
        await update.message.reply_text("❌ Analiz gerçekleştirilemedi. Detaylar için logları kontrol edin.")
        return

    report = f"<b>🔎 Analiz Raporu [{analysis_result.get('symbol')}]</b>\n\n"
    report += f"<b>Tavsiye:</b> {analysis_result.get('recommendation')}\n"
    report += f"<b>Gerekçe:</b> {analysis_result.get('reason')}"
    
    await update.message.reply_html(report)

async def run_proactive_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Proaktif taramayı tetikler."""
    _execute_single_scan_cycle = context.bot_data.get('scan')
    if not _execute_single_scan_cycle:
        await update.message.reply_text("❌ Hata: Tarama fonksiyonu başlatılamadı.")
        return

    await update.message.reply_text("🚀 Proaktif Tarama (Fırsat Avcısı) manuel olarak başlatılıyor... Sonuçlar için terminal loglarını kontrol edin.")
    
    try:
        await asyncio.to_thread(_execute_single_scan_cycle)
        await update.message.reply_text("✅ Tarama döngüsü tamamlandı.")
    except Exception as e:
        await update.message.reply_text(f"❌ Tarama sırasında bir hata oluştu: {e}")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Butonlardan gelen geri aramaları yönetir."""
    query = update.callback_query
    await query.answer()

    action, symbol = query.data.split(':', 1)
    
    _get_reanalysis_report = context.bot_data.get('reanalyze')
    _handle_manual_close = context.bot_data.get('close')

    if action == "reanalyze":
        await query.edit_message_text(text=f"🔄 `{symbol}` için yeniden analiz yapılıyor...", parse_mode=ParseMode.MARKDOWN)
        
        position = next((p for p in database.get_all_positions() if p['symbol'] == symbol), None)
        if position and _get_reanalysis_report:
            report_json_str = await asyncio.to_thread(_get_reanalysis_report, position)
            report_data = json.loads(report_json_str)
            report_text = report_data.get("report_text", "Rapor alınamadı.")
            await query.edit_message_text(text=report_text, parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(text=f"❌ Hata: `{symbol}` pozisyonu bulunamadı veya analiz fonksiyonu eksik.", parse_mode=ParseMode.MARKDOWN)
    
    elif action == "close_confirm":
        keyboard = [
            [
                InlineKeyboardButton("EVET, KAPAT", callback_data=f"close_execute:{symbol}"),
                InlineKeyboardButton("HAYIR, İPTAL", callback_data=f"close_cancel:{symbol}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"⚠️ `{symbol}` pozisyonunu kapatmak istediğinizden emin misiniz?", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    elif action == "close_execute":
        await query.edit_message_text(text=f"⏳ `{symbol}` pozisyonu kapatılıyor...", parse_mode=ParseMode.MARKDOWN)
        position = next((p for p in database.get_all_positions() if p['symbol'] == symbol), None)
        
        if position and _handle_manual_close:
            result_message = await asyncio.to_thread(
                _handle_manual_close,
                position,
                from_auto=True,
                close_reason="TELEGRAM_MANUAL",
                send_notification=False 
            )
            await query.edit_message_text(text=result_message, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(text=f"❌ Hata: `{symbol}` pozisyonu kapatılamadı. Pozisyon bulunamadı veya kapatma fonksiyonu eksik.", parse_mode=ParseMode.MARKDOWN)

    elif action == "close_cancel":
        await query.edit_message_text(text="İşlem iptal edildi.")

def run_telegram_bot(actions: dict):
    """Telegram botunu başlatır ve komutları dinlemeye başlar."""
    if not TELEGRAM_BOT_TOKEN:
        logging.error("Telegram bot token bulunamadı. Telegram kontrolü başlatılamıyor.")
        return

    # Telegram botu kendi asenkron döngüsünde çalışır
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Application nesnesini oluştur
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(set_commands).build()

    # Ana uygulamadan gelen fonksiyonları (actions) bot_data'ya ekle
    # Bu, handler'ların bu fonksiyonlara context.bot_data üzerinden erişmesini sağlar.
    application.bot_data.update(actions)

    # Komut yöneticileri
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("pozisyonlar", list_managed_positions))
    application.add_handler(CommandHandler("analiz", analyze_symbol))
    application.add_handler(CommandHandler("tara", run_proactive_scan))
    
    # Buton yöneticisi
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    logging.info("--- Telegram Botu komutları dinlemeye başladı ---")
    application.run_polling()
