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

# RAM Cache for <1s delivery
cache_memory = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✨ **Social Media Downloader** ✨\n\nSend Any Platform Content Link To Download👋"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
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
    
    # 1. Instant Cache Check
    if url in cache_memory:
        data = cache_memory[url]
        kb = [[InlineKeyboardButton("Download More🫥", callback_data="start_again")]]
        await update.message.reply_video(video=data['id'], caption=data['cap'], reply_markup=InlineKeyboardMarkup(kb), supports_streaming=True)
        return

    status = await update.message.reply_text("🔎 **Searching for video...**")

    # 2. Universal API Request
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autodownload"
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "social-download-all-in-one.p.rapidapi.com"
    }
    
    try:
        response = requests.post(api_url, json={"url": url}, headers=headers, timeout=30)
        res = response.json()

        # Robust Media Extraction
        media_url = None
        # Check standard fields
        if res.get('url'): media_url = res['url']
        # Check list of links (common for YouTube/Instagram)
        elif res.get('links') and len(res['links']) > 0:
            media_url = res['links'][0].get('url')
        # Check 'medias' array (from your HTML sample)
        elif res.get('medias') and len(res['medias']) > 0:
            media_url = res['medias'][0].get('url')

        if not media_url:
            return await status.edit_text("❌ **Link Not Supported.**\nPlease ensure the post is public.")

        await status.edit_text("📥 **Uploading to Telegram...**")
        filename = f"vid_{update.effective_user.id}.mp4"
        
        if await download_file(media_url, filename):
            title = res.get('title', 'Social Media Video')
            caption = f"🎬 **{title[:50]}**\n\n🕒 **Auto-deleting in 20 min.**"
            kb = [[InlineKeyboardButton("Download More🫥", callback_data="start_again")]]
            
            with open(filename, 'rb') as f:
                # Log to Archive for caching
                log = await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
                file_id = log.video.file_id
                cache_memory[url] = {'id': file_id, 'cap': caption}
                
                f.seek(0)
                sent = await update.message.reply_video(
                    video=f, 
                    caption=caption, 
                    reply_markup=InlineKeyboardMarkup(kb), 
                    supports_streaming=True
                )

            if os.path.exists(filename): os.remove(filename)
            await status.delete()
            asyncio.create_task(delete_msg(context, update.effective_chat.id, sent.message_id))
        else:
            await status.edit_text("❌ **Download Failed.** (The video file was too large or unreachable)")

    except Exception as e:
        print(f"API Error: {e}")
        await status.edit_text(f"❌ **API Error.** Please check your RapidAPI subscription.")

async def delete_msg(context, chat_id, msg_id):
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
    
    # Conflict fix: Clear old updates before starting
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
