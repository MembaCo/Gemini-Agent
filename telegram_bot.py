# telegram_bot.py
# @author: Memba Co.
# v2.2 - Nihai asyncio ve threading uyumluluk düzeltmeleri.

import logging
import os
import asyncio
from dotenv import load_dotenv

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Projemizin diğer modüllerini doğrudan import ediyoruz.
import database
import config
import core 

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Komut Handler'ları ---

async def set_commands(application: Application):
    """Bot için komut listesini ayarlar."""
    commands = [
        BotCommand("start", "Botu başlatır ve yardım mesajı gösterir."),
        BotCommand("pozisyonlar", "Yönetilen pozisyonları ve işlem seçeneklerini gösterir."),
        BotCommand("analiz", "Yeni bir sembol analizi yapar. Örn: /analiz BTC 15m"),
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komutu gönderildiğinde çalışır."""
    user = update.effective_user
    help_text = (
        f"Merhaba {user.first_name}! Gemini Trading Agent kontrol paneline hoş geldiniz.\n\n"
        "Kullanabileceğiniz komutlar:\n"
        "▪️ /pozisyonlar - Bot tarafından yönetilen pozisyonları gösterir ve işlem yapmanızı sağlar.\n"
        "▪️ /analiz <SEMBOl> [zaman_aralığı] - Yeni bir analiz yapar. Örn: `/analiz ETH 1h`"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def list_managed_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Yönetilen pozisyonları butonlarla listeler."""
    await update.message.reply_text("Yönetilen pozisyonlar veritabanından alınıyor...")
    # DÜZELTME: Senkron veritabanı çağrısını to_thread ile asenkron yap.
    positions = await asyncio.to_thread(database.get_all_positions)
    if not positions:
        await update.message.reply_text("Bot tarafından yönetilen aktif pozisyon bulunmuyor.")
        return

    keyboard = []
    for pos in positions:
        symbol = pos['symbol']
        keyboard.append([
            InlineKeyboardButton("🔄 Yeniden Analiz", callback_data=f"reanalyze:{symbol}"),
            InlineKeyboardButton("❌ Kapat", callback_data=f"close_confirm:{symbol}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('İşlem yapmak istediğiniz pozisyonu seçin:', reply_markup=reply_markup)

async def analyze_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/analiz komutunu işler."""
    if not context.args:
        await update.message.reply_text("Lütfen bir sembol belirtin. Örnek: /analiz BTC 15m")
        return

    symbol = context.args[0]
    timeframe = context.args[1] if len(context.args) > 1 else config.PROACTIVE_SCAN_ENTRY_TIMEFRAME
    
    await update.message.reply_text(f"⏳ `{symbol}` için `{timeframe}` zaman aralığında analiz başlatılıyor...", parse_mode=ParseMode.MARKDOWN)

    # DÜZELTME: Senkron ve uzun sürebilen core.perform_analysis'i to_thread ile çağır.
    analysis_result = await asyncio.to_thread(core.perform_analysis, symbol, timeframe)
    
    if not analysis_result or analysis_result.get('status') != 'success':
        error_message = analysis_result.get('message', 'Bilinmeyen bir hata oluştu.')
        await update.message.reply_text(f"❌ Analiz gerçekleştirilemedi: {error_message}")
        return

    rec, reason, sym = analysis_result.get('recommendation'), analysis_result.get('reason'), analysis_result.get('symbol')
    report = (
        f"<b>🔎 Analiz Raporu [{sym}]</b>\n\n"
        f"<b>Tavsiye:</b> {rec}\n"
        f"<b>Gerekçe:</b> {reason}"
    )
    await update.message.reply_html(report)

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Butonlardan gelen geri aramaları yönetir."""
    query = update.callback_query
    await query.answer()
    action, symbol = query.data.split(':', 1)

    if action == "reanalyze":
        await query.edit_message_text(text=f"🔄 `{symbol}` için yeniden analiz yapılıyor...", parse_mode=ParseMode.MARKDOWN)
        position = await asyncio.to_thread(lambda: next((p for p in database.get_all_positions() if p['symbol'] == symbol), None))
        if position:
            result = await asyncio.to_thread(core.reanalyze_position, position)
            if result.get('status') == 'success':
                data = result['data']
                report_text = f"<b>🔄 Yeniden Analiz [{symbol}]</b>\n\n<b>Tavsiye:</b> {data.get('recommendation')}\n<b>Gerekçe:</b> {data.get('reason')}"
                await query.edit_message_text(text=report_text, parse_mode=ParseMode.HTML)
            else:
                await query.edit_message_text(text=f"❌ Analiz başarısız: {result.get('message')}")
        else:
            await query.edit_message_text(text=f"❌ Hata: `{symbol}` pozisyonu bulunamadı.", parse_mode=ParseMode.MARKDOWN)
    
    elif action == "close_confirm":
        keyboard = [[InlineKeyboardButton("EVET, KAPAT", callback_data=f"close_execute:{symbol}"), InlineKeyboardButton("HAYIR, İPTAL", callback_data=f"close_cancel:{symbol}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"⚠️ `{symbol}` pozisyonunu kapatmak istediğinizden emin misiniz?", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    elif action == "close_execute":
        await query.edit_message_text(text=f"⏳ `{symbol}` pozisyonu kapatılıyor...", parse_mode=ParseMode.MARKDOWN)
        result = await asyncio.to_thread(core.close_position_by_symbol, symbol, "TELEGRAM_MANUAL")
        await query.edit_message_text(text=result.get('message', 'İşlem sonucu bilinmiyor.'), parse_mode=ParseMode.MARKDOWN)

    elif action == "close_cancel":
        await query.edit_message_text(text="İşlem iptal edildi.")

def run_telegram_bot():
    """Telegram botunu başlatır ve asenkron olay döngüsünü doğru bir şekilde kurar."""
    if not TELEGRAM_BOT_TOKEN:
        logging.error("Telegram bot token bulunamadı. Telegram kontrolü başlatılamıyor.")
        return

    # DÜZELTME: Bu fonksiyon, yeni bir thread içinde çalıştırıldığında kendi asyncio
    # olay döngüsünü kurar ve yönetir.
    async def main():
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(set_commands).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("pozisyonlar", list_managed_positions))
        application.add_handler(CommandHandler("analiz", analyze_symbol))
        # Proaktif tarama komutunu, uzun süren bir işlem olduğu için ve
        # geri bildirimi karmaşıklaştıracağı için şimdilik CLI/Web arayüzüne bırakmak daha sağlıklı.
        # application.add_handler(CommandHandler("tara", run_proactive_scan))
        application.add_handler(CallbackQueryHandler(button_callback_handler))

        # DÜZELTME: run_polling() yerine, kütüphanenin temel asenkron fonksiyonlarını kullanıyoruz.
        # Bu, olay döngüsü üzerinde tam kontrol sağlar ve çatışmaları önler.
        try:
            logging.info("--- Telegram Botu başlatılıyor (asenkron mod)... ---")
            await application.initialize()
            await application.start()
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logging.info("--- Telegram Botu komutları dinlemeye başladı ---")
            # Botun sonsuza kadar çalışmasını sağlar
            await asyncio.Event().wait()
        except Exception as e:
            logging.critical(f"Telegram botu asenkron döngüsünde kritik hata: {e}", exc_info=True)
        finally:
            logging.warning("--- Telegram Botu durduruluyor... ---")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Telegram botu manuel olarak durduruldu.")
    except Exception as e:
        logging.critical(f"Telegram botu başlatılamadı: {e}", exc_info=True)