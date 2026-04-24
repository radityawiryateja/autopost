# -*- coding: utf-8 -*-
import json
import logging
import re
import os
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from supabase import create_client

# Pengambilan Environment Variables (Bukan lagi dari Colab Secrets)
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
GROUP_ID_DISKUSI = int(os.getenv('GROUP_ID_DISKUSI', 0))
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID', 0))
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0))
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot_active = True

# Inisialisasi Supabase
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"Gagal koneksi ke Supabase: {e}")

CACHE_HASHTAGS = []
required_channels = []

# --- FUNGSI HELPER & CACHE ---
async def update_hashtags_cache():
    global CACHE_HASHTAGS
    try:
        response = supabase.table("triggered_hashtags").select("hashtag").eq("active", True).execute()
        CACHE_HASHTAGS = [row["hashtag"] for row in response.data] if hasattr(response, 'data') and response.data else []
    except Exception as e:
        logger.error(f"Gagal memuat cache hashtag: {e}")

async def update_required_channels_cache():
    global required_channels
    try:
        response = supabase.table('required_channels').select("channel_username").execute()
        required_channels = [row["channel_username"] for row in response.data] if hasattr(response, 'data') and response.data else []
    except Exception as e:
        logger.error(f"Gagal memuat required channels: {e}")

async def on_startup(application: Application):
    try:
        me = await application.bot.get_me()
        logger.info(f"✅ Bot siap: @{me.username} (id={me.id})")
        await update_hashtags_cache()
        await update_required_channels_cache()
    except Exception as e:
        logger.error(f"⚠️ Gagal startup: {e}")

# ... (Fungsi save_required_channels, check_subscription, add_hashtag, dll tetap sama seperti kode asli) ...
# Salin semua fungsi handler (start, handle_pesan, handle_admin_reply, handle_discussion, broadcast, dll) dari kode Colab Anda ke sini.
# Pastikan tidak ada perubahan logika, cukup pindahkan fungsinya di bawah ini.

# --- BAGIAN MAIN UNTUK DEPLOYMENT ---
def main():
    # Pastikan Token ada
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN tidak ditemukan di Environment Variables!")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', menu))
    application.add_handler(CommandHandler('open', open_bot))
    application.add_handler(CommandHandler('close', close_bot))
    application.add_handler(CommandHandler('grupid', get_group_id))
    application.add_handler(CommandHandler('setrequired', set_required_channels))
    application.add_handler(CommandHandler("addhashtag", add_hashtag))
    application.add_handler(CommandHandler("removehashtag", remove_hashtag))
    application.add_handler(CommandHandler("enablehashtag", enable_hashtag))
    application.add_handler(CommandHandler("disablehashtag", disable_hashtag))
    application.add_handler(CommandHandler('broadcastfw', broadcast_forward))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler("addcommand", add_command))
    application.add_handler(CommandHandler("deletecommand", delete_command))
    application.add_handler(CommandHandler("settings", settings))

    application.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_GROUP_ID), handle_admin_reply))
    application.add_handler(MessageHandler(filters.Chat(GROUP_ID_DISKUSI), handle_discussion))
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_pesan))

    logger.info("🚀 Bot running via Polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
