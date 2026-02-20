import os, requests, aiohttp, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# Configuration from Render Env Vars
TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = os.getenv("RAPID_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✨ **Social Media Downloader** ✨\n\nSend a link from YouTube, Instagram, or TikTok!"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    status_msg = await update.message.reply_text("🔎 **Searching for media...**")

    # Reverting to the confirmed 'autolink' endpoint
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "social-download-all-in-one.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    try:
        # Step 1: Request data from API
        response = requests.post(api_url, json={"url": url}, headers=headers, timeout=30)
        res = response.json()
        
        # DEBUG: This prints the full API response in your Render logs
        print(f"API Response: {res}")

        # Step 2: Extract the video URL
        media_url = None
        if res.get('medias') and len(res['medias']) > 0:
            media_url = res['medias'][0].get('url')
        elif res.get('url'):
            media_url = res.get('url')

        if not media_url:
            return await status_msg.edit_text("❌ **Media not found.**\nThis link might be private or restricted.")

        await status_msg.edit_text("📥 **Downloading to server...**")
        
        # Step 3: Stream download to avoid RAM issues
        filename = f"vid_{update.effective_user.id}.mp4"
        async with aiohttp.ClientSession() as session:
            async with session.get(media_url, timeout=300) as resp:
                if resp.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await resp.read())
                else:
                    return await status_msg.edit_text("❌ Download failed at source.")

        # Step 4: Upload to Telegram
        await status_msg.edit_text("📤 **Uploading to you...**")
        kb = [[InlineKeyboardButton("Download More 📥", callback_data="start_again")]]
        
        with open(filename, 'rb') as f:
            # Send to Archive Channel first (Cloud Storage)
            log_msg = await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
            # Forward the file_id to the user for instant delivery
            await update.message.reply_video(
                video=log_msg.video.file_id, 
                caption="✅ **Successfully Downloaded!**",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        # Cleanup
        if os.path.exists(filename): os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        print(f"System Error: {e}")
        await status_msg.edit_text("❌ **System Error.** Check your RapidAPI subscription or link.")

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
    # drop_pending_updates=True is vital for preventing the Conflict error on restart
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
