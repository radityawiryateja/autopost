# -*- coding: utf-8 -*-
import json
import logging
import re
import os
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from supabase import create_client

# 1. PENGAMBILAN ENVIRONMENT VARIABLES (CHOREO)
# Pastikan Key ini sudah Anda masukkan di menu Configs & Secrets di Choreo
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
GROUP_ID_DISKUSI = int(os.getenv('GROUP_ID_DISKUSI', 0))
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID', 0))
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0))
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Logging Konfigurasi
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot_active = True

# 2. INISIALISASI SUPABASE
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

def save_required_channels(channels):
    try:
        supabase.table('required_channels').delete().neq("channel_username", "").execute()
        for channel in channels:
            supabase.table('required_channels').insert({"channel_username": channel}).execute()
    except Exception as e:
        logger.error(f"Gagal menyimpan required channels: {e}")

async def check_subscription(user_id, context: CallbackContext):
    if not required_channels: return True
    for channel in required_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except Exception: return False
    return True

async def save_user(user_id, username):
    try:
        supabase.table("users").upsert({"user_id": user_id, "username": username}, on_conflict=["user_id"]).execute()
    except Exception: pass

# --- HANDLERS ---
async def start(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private": return
    user_id = update.effective_user.id
    await save_user(user_id, update.effective_user.username)

    if await check_subscription(user_id, context):
        await update.message.reply_text(
            "Halo, selamat datang di *Bazarfess*! ☕️\n\n"
            "Ketuk /menu untuk menampilkan navigasi", parse_mode="Markdown"
        )
    else:
        keyboard = [[InlineKeyboardButton("Join Channels", url=f"https://t.me/{c[1:]}")] for c in required_channels]
        await update.message.reply_text("Sebelum lanjut, silakan join channel berikut dulu ya!", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def handle_pesan(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.type != "private": return
    if not bot_active: return await update.message.reply_text("Bot sedang dipause oleh admin.")

    user_id = update.effective_user.id

    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
        match = re.search(r"#ID:(\d+)", replied_text)
        if match:
            try:
                comment_msg_id = int(match.group(1))
                if update.message.text:
                    await context.bot.send_message(chat_id=GROUP_ID_DISKUSI, text=f"🗣️ *Balasan Sender:*\n\n{update.message.text}", reply_to_message_id=comment_msg_id, parse_mode="Markdown")
                else:
                    caption = f"🗣️ *Balasan Sender:*\n\n{update.message.caption or ''}"
                    await context.bot.copy_message(chat_id=GROUP_ID_DISKUSI, from_chat_id=user_id, message_id=update.message.message_id, reply_to_message_id=comment_msg_id, caption=caption, parse_mode="Markdown")
                await update.message.reply_text("✅ Balasan anonim berhasil dikirim!")
                return
            except Exception:
                await update.message.reply_text("❌ Gagal mengirim balasan anonim.")
                return

    if not await check_subscription(user_id, context):
        keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{c[1:]}")] for c in required_channels]
        return await update.message.reply_text("Silakan join channel dulu ya!", reply_markup=InlineKeyboardMarkup(keyboard))

    text_content = (update.message.text or update.message.caption or "").strip().lower()
    is_direct_forward = any(ht.lower() in text_content for ht in CACHE_HASHTAGS)

    target_chat_id = CHANNEL_ID if is_direct_forward else ADMIN_GROUP_ID
    try:
        if update.message.text:
            text_msg = update.message.text if is_direct_forward else f"📩 Pesan dari: {update.effective_user.first_name}\n🆔 ID: {user_id}\n\n💬 Pesan:\n{update.message.text}"
            message_sent = await context.bot.send_message(chat_id=target_chat_id, text=text_msg)
        else:
            cap = update.message.caption if is_direct_forward else f"📩 Pesan dari: {update.effective_user.first_name}\n🆔 ID: {user_id}\n\n💬 Pesan:\n{update.message.caption or ''}"
            message_sent = await context.bot.copy_message(chat_id=target_chat_id, from_chat_id=user_id, message_id=update.message.message_id, caption=cap)
        
        if is_direct_forward:
            await update.message.reply_text("Pesan kamu telah terkirim ke channel!")
            supabase.table("menfess_map").insert({"post_id": message_sent.message_id, "sender_user_id": user_id}).execute()
        else:
            await update.message.reply_text("Pesan terkirim ke admin.")
    except Exception as e:
        logger.error(f"Error: {e}")

async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID or not update.message.reply_to_message: return
    match = re.search(r"ID(?:\s*Pengguna)?:?\s*(\d+)", update.message.reply_to_message.text or update.message.reply_to_message.caption or "")
    if not match: return
    user_id = int(match.group(1))
    try:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=ADMIN_GROUP_ID, message_id=update.message.message_id)
        await update.message.reply_text("✅ Terkirim.")
    except Exception: await update.message.reply_text("❌ Gagal.")

async def handle_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg: return
    if msg.is_automatic_forward and msg.forward_origin and msg.forward_origin.type == "channel":
        if msg.forward_origin.chat.username and ("@" + msg.forward_origin.chat.username.lower() == CHANNEL_ID.lower()):
            try: supabase.table("menfess_map").update({"discussion_message_id": msg.message_id}).eq("post_id", msg.forward_origin.message_id).execute()
            except: pass
        return
    if msg.reply_to_message:
        try:
            res = supabase.table("menfess_map").select("sender_user_id").eq("discussion_message_id", msg.reply_to_message.message_id).execute()
            if res.data:
                await context.bot.send_message(chat_id=res.data[0]["sender_user_id"], text=f"📬 Komentar baru di menfess kamu!\n\n`#ID:{msg.message_id}`", parse_mode="Markdown")
        except: pass

async def menu(update: Update, context: CallbackContext):
    await update.message.reply_text("📜 *Menu Bazarfess*", parse_mode="Markdown")

async def open_bot(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.id == ADMIN_GROUP_ID:
        bot_active = True
        await update.message.reply_text("✅ Bot ON.")

async def close_bot(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.id == ADMIN_GROUP_ID:
        bot_active = False
        await update.message.reply_text("⏸️ Bot OFF.")

# --- MAIN ---
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN Kosong!")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', menu))
    application.add_handler(CommandHandler('open', open_bot))
    application.add_handler(CommandHandler('close', close_bot))
    
    application.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_GROUP_ID), handle_admin_reply))
    application.add_handler(MessageHandler(filters.Chat(GROUP_ID_DISKUSI), handle_discussion))
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_pesan))

    logger.info("🚀 Bot Running via Polling di Choreo...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
