import os, requests, aiohttp, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = os.getenv("RAPID_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ **Universal Social Downloader** ✨\n\nSend a link from YouTube, Instagram, or TikTok to begin!")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    status = await update.message.reply_text("🔎 **Processing link...**")

    # headers for the /dl endpoint
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "social-download-all-in-one.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    try:
        # Switching to the robust 'dl' endpoint
        api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/dl"
        response = requests.post(api_url, json={"url": url}, headers=headers, timeout=30)
        res = response.json()

        # Log the response to Render for debugging
        print(f"DEBUG API RESPONSE: {res}")

        media_url = None
        # Check 'medias' array which is the standard for this endpoint
        if res.get('status') == 'success' and res.get('medias'):
            # Grab the first available video link
            media_url = res['medias'][0].get('url')
        
        if not media_url:
            error_msg = res.get('message', 'Media not found or private.')
            return await status.edit_text(f"❌ **Error:** {error_msg}")

        await status.edit_text("📥 **Downloading to Server...**")
        filename = f"video_{update.effective_user.id}.mp4"

        async with aiohttp.ClientSession() as session:
            async with session.get(media_url, timeout=300) as resp:
                if resp.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await resp.read())
                else:
                    return await status.edit_text("❌ Failed to fetch video file from source.")
        
        await status.edit_text("📤 **Uploading to Telegram...**")
        with open(filename, 'rb') as f:
            # Uploading to your archive channel first for better reliability
            log = await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
            # Send to user using the file_id
            await update.message.reply_video(video=log.video.file_id, caption="✅ **Downloaded Successfully!**")
        
        if os.path.exists(filename): os.remove(filename)
        await status.delete()

    except Exception as e:
        print(f"SYSTEM ERROR: {e}")
        await status.edit_text(f"❌ **System Error:** Check Render logs for details.")

def main():
    keep_alive()
    # drop_pending_updates=True prevents the bot from crashing if it was offline
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    print("Bot is successfully polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
