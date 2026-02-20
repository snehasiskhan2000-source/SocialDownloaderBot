import os
import requests
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# 1. Configuration (Set these in Render Env Vars)
TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = os.getenv("RAPID_API_KEY") # 96e8e0eec2msh6b9604051262d3ep117f79jsn7d8408147ffd
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✨ **Social Media Downloader** ✨\n\nSend a link from TikTok, Instagram, or YouTube to download!"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_url = update.message.text
    
    # CLEANING: Remove tracking parameters (e.g., ?is_from_webapp=1)
    # This ensures the API gets a clean, recognizable URL
    clean_url = raw_url.split('?')[0]
    
    status_msg = await update.message.reply_text("🔎 **Processing Link...**")

    # API Configuration matching your verified CURL request
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"
    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Host": "social-download-all-in-one.p.rapidapi.com",
        "X-RapidAPI-Key": RAPID_API_KEY
    }
    
    try:
        # Step 1: Request data from RapidAPI
        response = requests.post(api_url, json={"url": clean_url}, headers=headers, timeout=30)
        res_data = response.json()
        
        # LOGGING: Check your Render logs to see this output
        print(f"API DEBUG: {res_data}")

        # Step 2: Extract Media URL based on the API response structure
        # Standard structure: { "medias": [ { "url": "..." } ] }
        media_url = None
        if res_data.get('medias') and len(res_data['medias']) > 0:
            media_url = res_data['medias'][0].get('url')
        elif res_data.get('url'):
            media_url = res_data.get('url')

        if not media_url:
            error_msg = res_data.get('message', 'Media not found or private.')
            return await status_msg.edit_text(f"❌ **Error:** {error_msg}")

        await status_msg.edit_text("📥 **Downloading to Server...**")
        
        # Step 3: Download the file
        filename = f"dl_{update.effective_user.id}.mp4"
        async with aiohttp.ClientSession() as session:
            async with session.get(media_url, timeout=300) as resp:
                if resp.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await resp.read())
                else:
                    return await status_msg.edit_text("❌ Failed to reach media source.")

        # Step 4: Upload to Telegram
        await status_msg.edit_text("📤 **Uploading to you...**")
        kb = [[InlineKeyboardButton("Download More 📥", callback_data="start_again")]]
        
        with open(filename, 'rb') as f:
            # Backup to channel first
            log = await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
            # Send to user using the fast file_id
            await update.message.reply_video(
                video=log.video.file_id, 
                caption=f"✅ **Success!**\n🎬 {res_data.get('title', 'Video')[:50]}",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        # Cleanup
        if os.path.exists(filename): os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        print(f"SYSTEM ERROR: {e}")
        await status_msg.edit_text("❌ **System Error.** Please try again with a different link.")

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
    
    print("Bot is successfully polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
