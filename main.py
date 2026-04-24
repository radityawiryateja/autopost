# -*- coding: utf-8 -*-
import json
import logging
import re
import markdown
import os
import asyncio

# nest_asyncio.apply() dihapus karena hanya dibutuhkan di dalam Colab
# from google.colab import userdata dihapus karena Choreo menggunakan Environment Variables (OS)

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from supabase import create_client

# Tarik data dari Environment Variables / Secrets Choreo
try:
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    CHANNEL_ID = os.environ.get('CHANNEL_ID')
    GROUP_ID_DISKUSI = int(os.environ.get('GROUP_ID_DISKUSI'))
    ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID'))
    LOG_GROUP_ID = int(os.environ.get('LOG_GROUP_ID'))
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
except Exception as e:
    print(f"⚠️ Error mengambil Secrets: {e}")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot_active = True

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"Gagal koneksi ke Supabase: {e}")

CACHE_HASHTAGS = []
required_channels = []

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
        logger.error(f"⚠️ Gagal get_me saat startup: {e}")

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

async def add_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    if not context.args: return await update.message.reply_text("Gunakan format: /addhashtag <hashtag>")
    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").upsert({"hashtag": hashtag}).execute()
    await update_hashtags_cache()
    await update.message.reply_text(f"✅ Hashtag `{hashtag}` berhasil ditambahkan!", parse_mode="Markdown")

async def remove_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    if not context.args: return await update.message.reply_text("Gunakan format: /removehashtag <hashtag>")
    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").delete().eq("hashtag", hashtag).execute()
    await update_hashtags_cache()
    await update.message.reply_text(f"❌ Hashtag `{hashtag}` berhasil dihapus!", parse_mode="Markdown")

async def enable_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    if not context.args: return await update.message.reply_text("Gunakan format: /enablehashtag <hashtag>")
    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").update({"active": True}).eq("hashtag", hashtag).execute()
    await update_hashtags_cache()
    await update.message.reply_text(f"✅ Hashtag `{hashtag}` diaktifkan!", parse_mode="Markdown")

async def disable_hashtag(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    if not context.args: return await update.message.reply_text("Gunakan format: /disablehashtag <hashtag>")
    hashtag = context.args[0].strip()
    supabase.table("triggered_hashtags").update({"active": False}).eq("hashtag", hashtag).execute()
    await update_hashtags_cache()
    await update.message.reply_text(f"⚠️ Hashtag `{hashtag}` dinonaktifkan!", parse_mode="Markdown")

async def set_required_channels(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    if not context.args: return await update.message.reply_text("Gunakan format: /setrequired @channel1 @channel2")
    global required_channels
    required_channels = context.args
    save_required_channels(required_channels)
    await update.message.reply_text(f"Daftar channel wajib diikuti telah diperbarui: {', '.join(required_channels)}")

async def save_user(user_id, username):
    try:
        supabase.table("users").upsert({"user_id": user_id, "username": username}, on_conflict=["user_id"]).execute()
    except Exception: pass

async def start(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private": return
    user_id = update.effective_user.id
    await save_user(user_id, update.effective_user.username)

    if await check_subscription(user_id, context):
        await update.message.reply_text(
            "Halo, selamat datang di *Bazarfess*! ☕️\n\n"
            "𔐼 *Bazarfess:* [@bazarfess](https://t.me/bazarfess)\n"
            "𔐼 *LPM Bazar:* [@lpmbazar](https://t.me/lpmbazar)\n"
            "𔐼 *Info Base:* [@rekapbazar](https://t.me/rekapbazar)\n\n"
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

    # === FITUR BARU: CEK BALASAN ANONIM VIA TEKS TERSEMBUNYI (STATELESS) ===
    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""

        # Cari angka di sebelah format #ID:
        match = re.search(r"#ID:(\d+)", replied_text)
        if match:
            try:
                comment_msg_id = int(match.group(1))

                # Kirim balasan sender ke grup diskusi dengan mereply komentar asli
                if update.message.text:
                    await context.bot.send_message(
                        chat_id=GROUP_ID_DISKUSI,
                        text=f"🗣️ *Balasan Sender:*\n\n{update.message.text}",
                        reply_to_message_id=comment_msg_id,
                        parse_mode="Markdown"
                    )
                else:
                    caption = f"🗣️ *Balasan Sender:*\n\n{update.message.caption or ''}"
                    await context.bot.copy_message(
                        chat_id=GROUP_ID_DISKUSI,
                        from_chat_id=user_id,
                        message_id=update.message.message_id,
                        reply_to_message_id=comment_msg_id,
                        caption=caption,
                        parse_mode="Markdown"
                    )
                await update.message.reply_text("✅ Balasan anonim berhasil dikirim ke pengomentar!")
                return # Stop eksekusi agar tidak dianggap menfess baru
            except Exception as e:
                logger.error(f"Gagal memproses balasan anonim (stateless): {e}")
                await update.message.reply_text("❌ Gagal mengirim balasan anonim, mungkin komentar aslinya sudah dihapus.")
                return
    # ======================================================================

    username = update.effective_user.username
    first_name = update.effective_user.first_name
    display_name = f"@{username}" if username else first_name

    if not await check_subscription(user_id, context):
        keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{c[1:]}")] for c in required_channels]
        return await update.message.reply_text("Sebelum lanjut, silakan join channel berikut dulu ya!", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

    text_content = (update.message.text or update.message.caption or "").strip().lower()
    is_direct_forward = any(ht.lower() in text_content for ht in CACHE_HASHTAGS)

    text_without_hashtag = text_content
    for ht in CACHE_HASHTAGS:
        text_without_hashtag = re.sub(re.escape(ht), "", text_without_hashtag, flags=re.IGNORECASE)

    if is_direct_forward and not text_without_hashtag.strip() and not (update.message.photo or update.message.video or update.message.document or update.message.audio or update.message.voice or update.message.sticker):
        return await update.message.reply_text("⚠️ Harap isi pesan terlebih dahulu sebelum mengirim!")

    target_chat_id = CHANNEL_ID if is_direct_forward else ADMIN_GROUP_ID
    message_sent = None

    try:
        if update.message.text:
            text_msg = update.message.text if is_direct_forward else f"📩 Pesan dari: {first_name}\n👤 Username: {display_name}\n🆔 ID: {user_id}\n\n💬 Pesan:\n{update.message.text}"
            message_sent = await context.bot.send_message(chat_id=target_chat_id, text=text_msg)
        else:
            if is_direct_forward:
                message_sent = await context.bot.copy_message(chat_id=target_chat_id, from_chat_id=user_id, message_id=update.message.message_id)
            else:
                cap = f"📩 Pesan dari: {first_name}\n👤 Username: {display_name}\n🆔 ID: {user_id}\n\n💬 Pesan:\n{update.message.caption or ''}"
                message_sent = await context.bot.copy_message(chat_id=target_chat_id, from_chat_id=user_id, message_id=update.message.message_id, caption=cap)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        return await update.message.reply_text("Tipe pesan tidak didukung atau terjadi kesalahan.")

    if is_direct_forward and message_sent:
        keyboard = [[InlineKeyboardButton("Lihat Pesan Kamu", url=f"https://t.me/{CHANNEL_ID[1:]}/{message_sent.message_id}")]]
        await update.message.reply_text(
            "Pesan kamu telah dikirim ke channel! 🪶\n\n"
            "𔐼 *Bazarfess:* [@bazarfess](https://t.me/bazarfess)\n"
            "𔐼 *LPM Bazar:* [@lpmbazar](https://t.me/lpmbazar)\n"
            "𔐼 *Info Base:* [@rekapbazar](https://t.me/rekapbazar)\n\n"
            "Jangan lupa kepoin channel diatas ya!",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        try:
            supabase.table("menfess_map").insert({"post_id": message_sent.message_id, "sender_user_id": user_id}).execute()
        except Exception: pass

        log_msg = f"📌 Log Menfess:\n🕰️ Waktu: {update.message.date}\n👤 Pengirim: {display_name}\n🆔 ID: {user_id}\n💬 Pesan: {update.message.text or 'Media'}"
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Lihat Pesan", url=f"https://t.me/{CHANNEL_ID[1:]}/{message_sent.message_id}")]]))
    else:
        await update.message.reply_text("Pesan kamu telah dikirim ke admin, mohon tunggu beberapa saat.")

async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID or not update.message.reply_to_message: return

    match = re.search(r"ID(?:\s*Pengguna)?:?\s*(\d+)", update.message.reply_to_message.text or update.message.reply_to_message.caption or "")
    if not match: return

    user_id = int(match.group(1))
    reply_text = update.message.text or update.message.caption

    if reply_text and reply_text.startswith("/"):
        try:
            response = supabase.table("commands").select("content").eq("name", reply_text.split()[0]).execute()
            if hasattr(response, 'data') and response.data:
                await context.bot.send_message(chat_id=user_id, text=response.data[0]["content"], parse_mode="Markdown")
                notif = await update.message.reply_text(f"✅ Command dikirim ke user {user_id}")
                await asyncio.sleep(5)
                try: await notif.delete()
                except: pass
        except Exception: pass
        return

    try:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=ADMIN_GROUP_ID, message_id=update.message.message_id)
        notif = await update.message.reply_text("✅ Balasan telah dikirim ke user.")
        await asyncio.sleep(5)
        try: await notif.delete()
        except: pass
    except Exception: await update.message.reply_text("❌ Gagal mengirim balasan.")

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def handle_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg: return

    if msg.is_automatic_forward and msg.forward_origin and msg.forward_origin.type == "channel":
        origin_chat = msg.forward_origin.chat
        if origin_chat.username and ("@" + origin_chat.username.lower() == CHANNEL_ID.lower()):
            try:
                supabase.table("menfess_map").update({"discussion_message_id": msg.message_id}).eq("post_id", msg.forward_origin.message_id).execute()
            except Exception: pass
        return

    if msg.reply_to_message:
        try:
            replied_msg_id = msg.reply_to_message.message_id
            response = supabase.table("menfess_map").select("sender_user_id, post_id").eq("discussion_message_id", replied_msg_id).execute()
            if hasattr(response, 'data') and response.data:
                sender_user_id = response.data[0]["sender_user_id"]
                post_id = response.data[0]["post_id"]

                commenter = f"{msg.from_user.first_name} (@{msg.from_user.username})" if msg.from_user.username else msg.from_user.first_name
                link = f"https://t.me/{CHANNEL_ID.lstrip('@')}/{post_id}?comment={msg.message_id}"

                # Format notifikasi dengan menyisipkan #ID pesan diskusi
                notif_text = (
                    f"📬 {commenter} berkomentar di menfess kamu!\n\n"
                    f"*(balas/reply pesan ini jika kamu ingin membalas komentarnya secara anonim)*\n\n"
                    f"`#ID:{msg.message_id}`"
                )

                await context.bot.send_message(
                    chat_id=sender_user_id,
                    text=notif_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Lihat Balasan", url=link)]]),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"❌ Gagal proses balasan diskusi: {e}")

async def open_bot(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.id == ADMIN_GROUP_ID:
        bot_active = True
        await update.message.reply_text("✅ Bot telah diaktifkan kembali.")

async def close_bot(update: Update, context: CallbackContext):
    global bot_active
    if update.effective_chat.id == ADMIN_GROUP_ID:
        bot_active = False
        await update.message.reply_text("⏸️ Bot telah dipause.")

async def get_group_id(update: Update, context: CallbackContext):
    await update.message.reply_text(f"🆔 ID: `{update.effective_chat.id}`\n🏷️ Nama: {update.effective_chat.title or 'Private'}", parse_mode="Markdown")

async def get_all_user_ids():
    try:
        response = supabase.table("users").select("user_id").execute()
        return [row["user_id"] for row in response.data] if hasattr(response, "data") and response.data else []
    except Exception: return []

async def menu(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private": return
    menu_text = "𔐼 *Bazarfess:* [@bazarfess](https://t.me/bazarfess)\n𔐼 *LPM Bazar:* [@lpmbazar](https://t.me/lpmbazar)\n𔐼 *Info Base:* [@rekapbazar](https://t.me/rekapbazar)\n\n"
    await update.message.reply_text(menu_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📜 Info Bazar", url="https://t.me/rekapbazar")]]))

async def broadcast_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID or not context.args:
        return await update.message.reply_text("Format: /broadcastfw <link>")

    link = context.args[0]

    # Menggunakan re.search agar bisa membaca "t.me/..." meskipun tanpa "https://"
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)", link)

    if not match:
        return await update.message.reply_text("❌ Link tidak valid! Pastikan formatnya t.me/username_channel/angka")

    channel_username, message_id = match.groups()

    if channel_username == "c":
        return await update.message.reply_text("❌ Tidak bisa forward menggunakan link dari channel private!")

    user_list = await get_all_user_ids()
    sc, fc = 0, 0

    for user_id in user_list:
        try:
            await context.bot.forward_message(
                chat_id=user_id,
                from_chat_id=f"@{channel_username}",
                message_id=int(message_id)
            )
            sc += 1
        except Exception as e:
            print(f"⚠️ Gagal forward ke {user_id}: {e}")
            fc += 1

        await asyncio.sleep(0.05)

    await update.message.reply_text(f"✅ Selesai! Berhasil: {sc}, Gagal: {fc}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID or not context.args: return await update.message.reply_text("Format: /broadcast <teks>")
    message_text = " ".join(context.args)
    user_list = await get_all_user_ids()
    sc, fc = 0, 0
    for user_id in user_list:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sc += 1
        except Exception: fc += 1
        await asyncio.sleep(0.05)
    await update.message.reply_text(f"✅ Selesai! Berhasil: {sc}, Gagal: {fc}")

async def add_command(update: Update, context: CallbackContext) -> None:
    if update.message.reply_to_message:
        command_name = context.args[0] if context.args else None
        command_content = update.message.reply_to_message.text
    else:
        if len(context.args) < 2: return await update.message.reply_text("Format: /addcommand <nama> <isi>")
        command_name, command_content = context.args[0], " ".join(context.args[1:])
    command_name = command_name if command_name.startswith("/") else "/" + command_name
    try:
        supabase.table("commands").upsert({"name": command_name, "content": command_content}).execute()
        await update.message.reply_text(f"✅ `{command_name}` disimpan!", parse_mode='Markdown')
    except Exception: await update.message.reply_text("❌ Gagal.")

async def delete_command(update: Update, context: CallbackContext) -> None:
    if not context.args: return await update.message.reply_text("Format: /deletecommand <nama>")
    command_name = context.args[0] if context.args[0].startswith("/") else "/" + context.args[0]
    try:
        supabase.table("commands").delete().eq("name", command_name).execute()
        await update.message.reply_text(f"✅ `{command_name}` dihapus!", parse_mode='Markdown')
    except Exception: await update.message.reply_text("❌ Gagal.")

async def settings(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    channels_text = "\n".join([f"𔐼 {c}" for c in required_channels]) if required_channels else "–"
    hashtags_text = "\n".join([f"𔐼 `{h}`" for h in CACHE_HASHTAGS]) if CACHE_HASHTAGS else "–"
    try:
        response = supabase.table("commands").select("name, content").execute()
        commands_text = "\n\n".join([f"*{c['name']}*\n{c['content']}" for c in response.data]) if hasattr(response, 'data') and response.data else "–"
    except Exception: commands_text = "– Error –"
    await update.message.reply_text(f"⚙️ *Settings*\n\n📌 *Channels:*\n{channels_text}\n\n🏷️ *Hashtags:*\n{hashtags_text}\n\n💻 *Commands:*\n{commands_text}", parse_mode="Markdown")

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

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
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    application.add_handler(MessageHandler(filters.Chat(GROUP_ID_DISKUSI), handle_discussion))
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_pesan))

    logger.info("✅ Membangun bot selesai. Menjalankan polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == '__main__':
    main()
