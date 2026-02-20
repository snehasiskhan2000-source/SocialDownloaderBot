import os
import requests
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("XAPIVERSE_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# RAM Cache for <1s delivery on repeated links
cache_memory = {}

TERABOX_DOMAINS = ["terabox.com", "nephobox.com", "4shared.com", "mirrobox.com", "momerybox.com", "teraboxapp.com", "1024tera.com", "terasharelink.com"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clean welcome message without any buttons
    text = "✨ **TeraBox Video Downloader** ✨\n\nSend A Terabox Video Link To Download😎"
    
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")

async def download_media(url, filename):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=300) as response:
                if response.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await response.read())
                    return True
        except Exception as e:
            print(f"Download error: {e}")
    return False

async def auto_delete_msg(context, chat_id, message_id):
    await asyncio.sleep(1200) # 20 minutes
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

def cleanup_files(*filenames):
    """Confirming Render deletes videos immediately after sending"""
    for filename in filenames:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"Successfully deleted: {filename}")
            except Exception as e:
                print(f"Cleanup error: {e}")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not any(domain in url for domain in TERABOX_DOMAINS):
        return await update.message.reply_text("❌ Please send a valid Terabox link!")

    # 1. INSTANT DELIVERY (Cached logic)
    if url in cache_memory:
        data = cache_memory[url]
        keyboard = [[InlineKeyboardButton("Download More👋", callback_data="start_again")]]
        caption = f"🎬 **{data['name']}**\n\n📦 **Size:** {data['size']}\n\n🕒 **Auto-deleting in 20 min.**"
        
        sent_msg = await update.message.reply_video(
            video=data['file_id'],
            thumbnail=data['thumb_id'],
            duration=data['duration'],
            caption=caption,
            supports_streaming=True,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        asyncio.create_task(auto_delete_msg(context, update.effective_chat.id, sent_msg.message_id))
        return

    # 2. STANDARD UPLOAD LOGIC
    status_msg = await update.message.reply_text("🔎 **Fetching details...**", parse_mode="Markdown")
    api_url = "https://xapiverse.com/api/terabox-pro"
    headers = {"Content-Type": "application/json", "xAPIverse-Key": API_KEY}

    try:
        response = requests.post(api_url, json={"url": url}, headers=headers, timeout=60)
        data = response.json()

        if data.get("status") == "success" and data.get("list"):
            info = data["list"][0]
            dl_link = info.get("download_link")
            thumb_url = info.get("thumbnail")
            duration_str = info.get("duration", "00:00")
            filename = info.get("name", "video.mp4")
            size_fmt = info.get("size_formatted", "Unknown")

            dur_seconds = sum(int(x) * 60**i for i, x in enumerate(reversed(duration_str.split(":"))))
            thumb_name = f"thumb_{update.effective_user.id}.jpg"

            await status_msg.edit_text("📥 **Downloading...**")
            video_success = await download_media(dl_link, filename)
            thumb_success = await download_media(thumb_url, thumb_name) if thumb_url else False
            
            if video_success:
                await status_msg.edit_text("📤 **Uploading...**")
                
                with open(filename, 'rb') as video_file:
                    thumb_file = open(thumb_name, 'rb') if thumb_success else None
                    
                    # Log to channel for File ID generation
                    log_msg = await context.bot.send_video(
                        chat_id=CHANNEL_ID,
                        video=video_file,
                        thumbnail=thumb_file,
                        duration=dur_seconds,
                        supports_streaming=True
                    )
                    
                    # Update Cache
                    cache_memory[url] = {
                        'file_id': log_msg.video.file_id,
                        'thumb_id': log_msg.video.thumbnail.file_id if thumb_success else None,
                        'duration': dur_seconds,
                        'name': filename,
                        'size': size_fmt
                    }

                    # Reset file pointers
                    video_file.seek(0)
                    if thumb_file: thumb_file.seek(0)
                    
                    # Send to User with Clean Caption & Button
                    caption = f"🎬 **{filename}**\n\n📦 **Size:** {size_fmt}\n\n🕒 **Auto-deleting in 20 min.**"
                    sent_msg = await update.message.reply_video(
                        video=video_file,
                        caption=caption,
                        thumbnail=thumb_file,
                        duration=dur_seconds,
                        supports_streaming=True,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Download More👋", callback_data="start_again")]]),
                        parse_mode="Markdown"
                    )
                    if thumb_file: thumb_file.close()

                # IMMEDIATE CLEANUP FROM RENDER DISK
                cleanup_files(filename, thumb_name)
                
                await status_msg.delete()
                asyncio.create_task(auto_delete_msg(context, update.effective_chat.id, sent_msg.message_id))
            else:
                await status_msg.edit_text("❌ Download failed.")
        else:
            await status_msg.edit_text("❌ API Error: File not found.")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "start_again":
        await start(update, context)

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
