#!/usr/bin/env python3
import os
import re
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ========== CONFIG ==========
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8883436602:AAEUuxDl9qEprq5dBGHdaf4_R6nhC7G_kDg"
ADMIN_ID = int(os.getenv("ADMIN_ID") or "5510702228")
DEV_NAME = "@VICKYGAMING0"
BOT_NAME = "VTX SO PATCHER"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_SO = 1


# ========== PATCH FUNCTION ==========
def patch_so(so_path, out_path):
    """
    Sirf exact 'show' string ko 'hide' se replace karo.
    'showDialog', 'showToast' jaisa kuch nahi.
    """
    try:
        with open(so_path, 'rb') as f:
            data = bytearray(f.read())

        old = b"show"
        new = b"hide"

        replaced = 0
        i = 0

        while True:
            idx = data.find(old, i)
            if idx == -1:
                break

            # Aage check
            if idx == 0:
                before_ok = True
            else:
                b = data[idx - 1]
                before_ok = not (chr(b).isalnum() or b == ord('_'))

            # Peeche check
            after_idx = idx + 4
            if after_idx >= len(data):
                after_ok = True
            else:
                a = data[after_idx]
                after_ok = not (chr(a).isalnum() or a == ord('_'))

            if before_ok and after_ok:
                data[idx:idx + 4] = new
                replaced += 1
                logger.info(f"Replaced at offset 0x{idx:x}")

            i = idx + 4

        if replaced == 0:
            return False, "❌ Exact 'show' string nahi mili", 0

        with open(out_path, 'wb') as f:
            f.write(data)

        return True, f"✅ Replaced {replaced} exact 'show'", replaced

    except Exception as e:
        logger.exception("Patch error")
        return False, f"❌ Error: {str(e)}", 0


# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔧 {BOT_NAME}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📌 Commands:\n"
        f"/patch  - .so file upload karo\n"
        f"/help   - Help\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⚡ {DEV_NAME}"
    )


async def patch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔧 SO PATCHER\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Koi bhi `.so` file upload kar.\n\n"
        "Bot:\n"
        "  1. File scan karega\n"
        "  2. Sirf exact string dhundhega\n"
        "  3. replace karega\n"
        "  4. Patched file return karega\n\n"
        "⚠️ 'Dialog', 'showToast' jaise strings\n"
        "   touch nahi honge."
    )
    context.user_data['action'] = 'patch'
    return WAITING_SO


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 HELP\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"/patch → `.so` upload kar\n"
        f"Bot sirf exact 'show' → 'hide' karega.\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⚡ {DEV_NAME}"
    )


# ========== DOC HANDLER ==========
async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    action = context.user_data.get('action', '')
    if action != 'patch':
        return

    msg = await update.message.reply_text("📥 Downloading...")

    fname = doc.file_name or "input.so"
    path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{fname}")
    out_path = os.path.join(TEMP_DIR, f"VTX_{fname}")

    try:
        f = await context.bot.get_file(doc.file_id)
        await f.download_to_drive(path)
    except Exception as e:
        await msg.edit_text(f"❌ Download fail: {e}")
        context.user_data['action'] = ''
        return

    await msg.edit_text("🔧 Scanning for exact 'show'...")

    success, result, count = patch_so(path, out_path)

    if success:
        size_kb = os.path.getsize(out_path) / 1024
        await update.message.reply_document(
            document=open(out_path, 'rb'),
            filename=f"VTX_{fname}",
            caption=(
                f"✅ SO PATCHED\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📦 File: {fname}\n"
                f"🔧 Replaced: {count} exact 'F@CK'\n"
                f"📊 Size: {size_kb:.2f} KB\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"⚡ {BOT_NAME} | {DEV_NAME}"
            )
        )
    else:
        await msg.edit_text(result)

    try: os.remove(path)
    except: pass
    try: os.remove(out_path)
    except: pass

    context.user_data['action'] = ''


# ========== MAIN ==========
def main():
    import asyncio
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("patch", patch_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    print(f"✅ {BOT_NAME} ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
