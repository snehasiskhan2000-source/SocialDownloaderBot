import os
import requests
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = os.getenv("RAPID_API_KEY") # Get from RapidAPI Dashboard
CHANNEL_ID = os.getenv("CHANNEL_ID")

# RAM Cache for Instant Re-delivery
cache_memory = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clean welcome message - no buttons attached here as requested
    text = "✨ **Social Media Downloader** ✨\n\nSend Any Platform Content Link To Download👋"
    
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

def cleanup_files(*filenames):
    for filename in filenames:
        if filename and os.path.exists(filename):
            try: os.remove(filename)
            except: pass

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # 1. Instant Cache Check
    if url in cache_memory:
        data = cache_memory[url]
        keyboard = [[InlineKeyboardButton("Download More🫥", callback_data="start_again")]]
        
        if data['type'] == 'video':
            await update.message.reply_video(video=data['file_id'], caption=data['caption'], reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_photo(photo=data['file_id'], caption=data['caption'], reply_markup=InlineKeyboardMarkup(keyboard))
        return

    status_msg = await update.message.reply_text("🔎 **Processing Link...**", parse_mode="Markdown")

    # 2. RapidAPI Integration
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autodownload"
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "social-download-all-in-one.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(api_url, json={"url": url}, headers=headers, timeout=30)
        res_data = response.json()
        
        # Adjusting to the common response structure of All-In-One APIs
        media_url = res_data.get('url') or res_data.get('links', [{}])[0].get('url')
        title = res_data.get('title', 'Social Media Content')
        
        if not media_url:
            return await status_msg.edit_text("❌ Unsupported link or private content.")

        await status_msg.edit_text("📥 **Streaming to Telegram...**")
        
        filename = f"dl_{update.effective_user.id}.mp4"
        success = await download_media(media_url, filename)

        if success:
            keyboard = [[InlineKeyboardButton("Download More🫥", callback_data="start_again")]]
            caption = f"🎬 **{title[:50]}**\n\n🕒 **Auto-deleting in 20 min.**"
            
            with open(filename, 'rb') as f:
                # Send to archive for caching
                log_msg = await context.bot.send_video(chat_id=CHANNEL_ID, video=f, supports_streaming=True)
                
                # Cache the File ID
                cache_memory[url] = {
                    'file_id': log_msg.video.file_id,
                    'type': 'video',
                    'name': title,
                    'caption': caption
                }
                
                f.seek(0)
                sent_msg = await update.message.reply_video(
                    video=f,
                    caption=caption,
                    supports_streaming=True,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )

            cleanup_files(filename)
            await status_msg.delete()
            # Auto-delete from chat
            asyncio.create_task(delete_after(context, update.effective_chat.id, sent_msg.message_id))
        else:
            await status_msg.edit_text("❌ Download failed.")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown")

async def delete_after(context, chat_id, msg_id):
    await asyncio.sleep(1200)
    try: await context.bot.delete_message(chat_id, msg_id)
    except: pass

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
