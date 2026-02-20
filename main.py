import os, requests, aiohttp, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

TOKEN = os.getenv("BOT_TOKEN")
RAPID_API_KEY = os.getenv("RAPID_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    # YT/IG links often have extra junk at the end; splitting helps cleaning
    clean_url = url.split('?')[0] 
    status = await update.message.reply_text("🔎 **Searching YT/IG Servers...**")

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "social-download-all-in-one.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    try:
        api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"
        response = requests.post(api_url, json={"url": clean_url}, headers=headers, timeout=30)
        res = response.json()

        # LOGIC FOR YT & IG: They usually return a list of 'medias'
        media_url = None
        if res.get('medias'):
            # This looks for the first available 'video' type in the list
            for item in res['medias']:
                if item.get('type') == 'video' or 'mp4' in item.get('extension', ''):
                    media_url = item.get('url')
                    break
        
        if not media_url:
            return await status.edit_text("❌ **YT/IG Link Not Supported.**\nEnsure it is a public video/reel.")

        await status.edit_text("📥 **Downloading...**")
        filename = f"vid_{update.effective_user.id}.mp4"

        async with aiohttp.ClientSession() as session:
            async with session.get(media_url) as resp:
                if resp.status == 200:
                    with open(filename, 'wb') as f: f.write(await resp.read())
        
        # Send using the file_id for faster delivery if cached
        with open(filename, 'rb') as f:
            await update.message.reply_video(video=f, caption="✅ YT/IG Download Success!")
        
        if os.path.exists(filename): os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ Error: YT/IG APIs are currently busy.")
        
