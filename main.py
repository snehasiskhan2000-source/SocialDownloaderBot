import os
import requests
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# Config
TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = os.getenv("RAPID_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# RAM Cache for <1s delivery on repeated links
cache_memory = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clean welcome message - no buttons attached
    text = "✨ **Social Media Downloader** ✨\n\nSend Any Platform Content Link To Download👋"
    
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        # Triggered by "Download More" - sends fresh start message
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")

async def download_file(url, filename):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=300) as res:
                if res.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await res.read())
                    return True
        except Exception as e:
            print(f"Download error: {e}")
    return False

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # 1. INSTANT CACHE CHECK (<1s Speed)
    if url in cache_memory:
        data = cache_memory[url]
        keyboard = [[InlineKeyboardButton("Download More🫥", callback_data="start_again")]]
        
        if data['type'] == 'video':
            await update.message.reply_video(video=data['id'], caption=data['cap'], reply_markup=InlineKeyboardMarkup(keyboard), supports_streaming=True)
        else:
            await update.message.reply_photo(photo=data['id'], caption=data['cap'], reply_markup=InlineKeyboardMarkup(keyboard))
        return

    status = await update.message.reply_text("🔎 **Processing Link...**")

    # 2. RapidAPI Fetch
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autodownload"
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "social-download-all-in-one.p.rapidapi.com"
    }
    
    try:
        res = requests.post(api_url, json={"url": url}, headers=headers, timeout=30).json()
        
        # Extract media (Handles different API response styles)
        media_url = res.get('url') or (res.get('medias', [{}])[0].get('url') if res.get('medias') else None)
        title = res.get('title', 'Social Content')
        is_video = ".mp4" in str(media_url).lower() or res.get('type') == 'video'

        if not media_url:
            return await status.edit_text("❌ Unsupported link or private content.")

        await status.edit_text("📥 **Streaming to Telegram...**")
        filename = f"file_{update.effective_user.id}.mp4" if is_video else f"img_{update.effective_user.id}.jpg"
        
        if await download_file(media_url, filename):
            caption = f"🎬 **{title[:60]}**\n\n🕒 **Auto-deleting in 20 min.**"
            kb = [[InlineKeyboardButton("Download More🫥", callback_data="start_again")]]
            
            with open(filename, 'rb') as f:
                # Store in Archive for File IDs
                if is_video:
                    log = await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
                    file_id = log.video.file_id
                else:
                    log = await context.bot.send_photo(chat_id=CHANNEL_ID, photo=f)
                    file_id = log.photo[-1].file_id

                # Cache it
                cache_memory[url] = {'id': file_id, 'type': 'video' if is_video else 'photo', 'cap': caption}
                
                # Send to user
                f.seek(0)
                if is_video:
                    sent = await update.message.reply_video(video=f, caption=caption, reply_markup=InlineKeyboardMarkup(kb), supports_streaming=True)
                else:
                    sent = await update.message.reply_photo(photo=f, caption=caption, reply_markup=InlineKeyboardMarkup(kb))

            # Render Cleanup
            if os.path.exists(filename): os.remove(filename)
            await status.delete()
            
            # Auto-delete from user chat
            asyncio.create_task(delete_msg(context, update.effective_chat.id, sent.message_id))
        else:
            await status.edit_text("❌ Download failed.")
    except Exception as e:
        await status.edit_text(f"❌ Error: `{str(e)}`")

async def delete_msg(context, chat_id, msg_id):
    await asyncio.sleep(1200)
    try: await context.bot.delete_message(chat_id, msg_id)
    except: pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "start_again":
        await start(update, context) # Hiddenly triggers start

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
