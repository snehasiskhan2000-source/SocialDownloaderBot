import os, requests, aiohttp, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# Configuration from Render Env Vars
TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = "96e8e0eec2msh6b9604051262d3ep117f79jsn7d8408147ffd" # Using your verified key
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✨ **Universal Social Downloader** ✨\n\nSend a link from TikTok, Instagram, or YouTube to begin!"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    status_msg = await update.message.reply_text("🔎 **Searching for media...**")

    # The exact endpoint and headers you verified
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "social-download-all-in-one.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    try:
        # Step 1: API Request with proper JSON payload
        response = requests.post(api_url, json={"url": url}, headers=headers, timeout=30)
        res = response.json()
        
        # Log for debugging in Render
        print(f"API Response: {res}")

        # Step 2: Extract Media URL
        media_url = None
        if res.get('medias') and len(res['medias']) > 0:
            media_url = res['medias'][0].get('url')
        
        if not media_url:
            return await status_msg.edit_text("❌ **Media not found.**\nThis usually happens with private or restricted posts.")

        await status_msg.edit_text("📥 **Downloading content...**")
        
        # Step 3: Download file to local storage
        filename = f"dl_{update.effective_user.id}.mp4"
        async with aiohttp.ClientSession() as session:
            async with session.get(media_url, timeout=300) as resp:
                if resp.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await resp.read())
                else:
                    return await status_msg.edit_text("❌ Failed to reach media source.")

        # Step 4: Upload to Telegram
        kb = [[InlineKeyboardButton("Download More 📥", callback_data="start_again")]]
        with open(filename, 'rb') as f:
            # Backup to channel
            log = await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
            # Send to user
            f.seek(0)
            await update.message.reply_video(
                video=f, 
                caption="✅ **Successfully Downloaded!**",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        if os.path.exists(filename): os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        print(f"ERROR: {e}")
        await status_msg.edit_text("❌ **An error occurred.** Please check your link or try later.")

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
    # Prevents conflict errors by dropping old messages on restart
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
