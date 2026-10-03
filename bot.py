#!/usr/bin/env python3
import os
import time
import shutil
import zipfile
import logging
import subprocess
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ========== CONFIG ==========
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8883436602:AAEUuxDl9qEprq5dBGHdaf4_R6nhC7G_kDg"
ADMIN_ID = int(os.getenv("ADMIN_ID") or "5510702228")
DEV_NAME = "@VICKYGAMING0"
BOT_NAME = "VTX PATCHER"

# ★ APNI .so KA NAAM YAHAN
TARGET_SO = "libEliteMods.so"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_FILE = 1


# ========== TOOLS ==========
def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    for c in [
        f"/usr/bin/{name}",
        f"/usr/local/bin/{name}",
    ]:
        if os.path.exists(c):
            return c
    return None


# ========== PATCH .SO CORE ==========
def patch_so_file(so_path):
    """Exact 'show' → 'hide'"""
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

            before_ok = True
            if idx > 0:
                b = data[idx - 1]
                before_ok = not (chr(b).isalnum() or b == ord('_'))

            after_idx = idx + 4
            after_ok = True
            if after_idx < len(data):
                a = data[after_idx]
                after_ok = not (chr(a).isalnum() or a == ord('_'))

            if before_ok and after_ok:
                data[idx:idx + 4] = new
                replaced += 1

            i = idx + 4

        if replaced > 0:
            with open(so_path, 'wb') as f:
                f.write(data)

        return replaced
    except Exception as e:
        logger.error(f"patch_so error: {e}")
        return 0


# ========== SIGN APK ==========
def sign_apk(apk_path):
    """Uber APK Signer (zipalign + sign)"""
    uber = os.getenv("UBER_PATH") or "/tmp/tools/uber-apk-signer.jar"
    if not os.path.exists(uber):
        return "❌ uber-apk-signer not found"

    r = subprocess.run(
        f'java -jar "{uber}" --apks "{apk_path}" --allowResign --overwrite',
        shell=True, capture_output=True, text=True, timeout=600
    )

    logger.info(f"Uber stdout: {r.stdout[-300:]}")
    logger.info(f"Uber stderr: {r.stderr[-300:]}")

    # Cleanup extra files
    folder = os.path.dirname(apk_path)
    base = os.path.basename(apk_path)[:-4]
    for f in os.listdir(folder):
        if f.startswith(base) and f != os.path.basename(apk_path):
            try:
                os.remove(os.path.join(folder, f))
            except: pass

    if r.returncode == 0:
        return "✅ Signed V1+V2+V3"
    return f"❌ {r.stderr[:150]}"


# ========== MODE 1: PATCH .SO ONLY ==========
async def patch_so_only(update, context, msg, so_path):
    try:
        await msg.edit_text("🔧 Patching .so...")
        fname = os.path.basename(so_path)
        out_path = so_path + ".patched"
        shutil.copy2(so_path, out_path)

        count = patch_so_file(out_path)

        if count == 0:
            await update.message.reply_document(
                document=open(so_path, 'rb'),
                filename=f"VTX_{fname}",
                caption=f"⚠️ Exact 'show' nahi mila\n⚡ {BOT_NAME} | {DEV_NAME}"
            )
        else:
            size_kb = os.path.getsize(out_path) / 1024
            await update.message.reply_document(
                document=open(out_path, 'rb'),
                filename=f"VTX_{fname}",
                caption=(
                    f"✅ SO PATCHED\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📦 {fname}\n"
                    f"🔧 Replaced: {count} 'show'\n"
                    f"📊 {size_kb:.2f} KB\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"⚡ {BOT_NAME} | {DEV_NAME}"
                )
            )
            try: os.remove(out_path)
            except: pass
    except Exception as e:
        logger.exception("patch_so_only")
        await msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        try: os.remove(so_path)
        except: pass


# ========== MODE 2: CRACK APK (REPLACE, NOT REBUILD) ==========
async def crack_apk(update, context, msg, apk_path):
    user_id = update.effective_user.id
    ts = int(time.time())
    temp_so = os.path.join(TEMP_DIR, f"target_{user_id}_{ts}.so")
    temp_so_patched = temp_so + ".patched"
    out_apk = os.path.join(TEMP_DIR, f"VTX_{user_id}_{ts}.apk")

    apk_path = os.path.abspath(apk_path)
    out_apk = os.path.abspath(out_apk)

    try:
        # ===== STEP 1: ZIP view — .so dhundo =====
        await msg.edit_text(f"🔍 Step 1/5: Viewing APK for '{TARGET_SO}'...")

        with zipfile.ZipFile(apk_path, 'r') as zin:
            # .so file dhundo
            so_entry = None
            for name in zin.namelist():
                if name.endswith("/" + TARGET_SO) or name == TARGET_SO:
                    so_entry = name
                    break

            if not so_entry:
                await msg.edit_text(
                    f"❌ '{TARGET_SO}' APK mein nahi mili.\n\n"
                    f"APK mein ye .so files hain:\n"
                    + "\n".join(
                        f"   • {n}" for n in zin.namelist()
                        if n.endswith(".so")
                    )[:600]
                )
                return

            # .so file extract
            await msg.edit_text(f"🔧 Step 2/5: Extracting '{TARGET_SO}'...")
            with zin.open(so_entry) as src, open(temp_so, 'wb') as dst:
                shutil.copyfileobj(src, dst)

        # ===== STEP 2: Patch .so =====
        await msg.edit_text(f"🔧 Step 3/5: Patching .so...")
        shutil.copy2(temp_so, temp_so_patched)
        count = patch_so_file(temp_so_patched)

        if count == 0:
            await msg.edit_text("⚠️ Exact 'show' nahi mila .so mein.")
            return

        # ===== STEP 3: APK copy + .so REPLACE =====
        await msg.edit_text("🔧 Step 4/5: Replacing .so in APK...")
        shutil.copy2(apk_path, out_apk)

        # APK ko update karo — sirf ek entry replace karo
        # zipfile se update nahi hota, isliye temp APK banao
        temp_apk = out_apk + ".tmp"

        with zipfile.ZipFile(apk_path, 'r') as zin:
            with zipfile.ZipFile(temp_apk, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == so_entry:
                        # Patched .so daalo
                        zout.write(temp_so_patched, item.filename)
                    else:
                        # Baaki sab copy — bilkul same
                        data = zin.read(item.filename)
                        zout.writestr(item, data)

        os.replace(temp_apk, out_apk)

        # ===== STEP 4: Sign =====
        await msg.edit_text("🔧 Step 5/5: Signing...")
        sign = sign_apk(out_apk)

        size_mb = os.path.getsize(out_apk) / (1024 * 1024)
        await update.message.reply_document(
            document=open(out_apk, 'rb'),
            filename=f"VTX_{os.path.basename(apk_path)}",
            caption=(
                f"✅ APK PATCHED\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🎯 Target: {TARGET_SO}\n"
                f"🔧 Replaced: {count} 'show'\n"
                f"📦 {sign}\n"
                f"📊 Size: {size_mb:.2f} MB\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"⚡ {BOT_NAME} | {DEV_NAME}"
            )
        )

    except Exception as e:
        logger.exception("crack_apk")
        await msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        for p in [apk_path, out_apk, temp_so, temp_so_patched]:
            try: os.remove(p)
            except: pass


# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔧 {BOT_NAME}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"/patch  - .so patch\n"
        f"/crack  - APK patch ({TARGET_SO})\n"
        f"/help   - Help\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚡ {DEV_NAME}"
    )


async def patch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔧 .SO PATCHER\n.so file upload kar.")
    context.user_data['action'] = 'patch'
    return WAITING_FILE


async def crack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔧 APK CRACKER\nTarget: {TARGET_SO}\n\nAPK upload kar."
    )
    context.user_data['action'] = 'crack'
    return WAITING_FILE


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 /patch → .so upload\n"
        f"📖 /crack → APK upload\n"
        f"⚡ {DEV_NAME}"
    )


# ========== HANDLER ==========
async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    action = context.user_data.get('action', '')
    if action not in ['patch', 'crack']:
        return

    msg = await update.message.reply_text("📥 Downloading...")
    fname = doc.file_name or "input"
    path = os.path.join(TEMP_DIR, f"{update.effective_user.id}_{fname}")

    try:
        f = await context.bot.get_file(doc.file_id)
        await f.download_to_drive(path)
    except Exception as e:
        await msg.edit_text(f"❌ Download fail: {e}")
        context.user_data['action'] = ''
        return

    context.user_data['action'] = ''

    if action == 'patch':
        if not fname.lower().endswith(".so"):
            await msg.edit_text("❌ Sirf .so file bhej.")
            try: os.remove(path)
            except: pass
            return
        await patch_so_only(update, context, msg, path)

    elif action == 'crack':
        apk_path = path

        if path.lower().endswith(".zip"):
            await msg.edit_text("📦 Zip extract...")
            ext = path + "_x"
            os.makedirs(ext, exist_ok=True)
            with zipfile.ZipFile(path, 'r') as z:
                z.extractall(ext)
            found = None
            for root, _, files in os.walk(ext):
                for f2 in files:
                    if f2.lower().endswith(".apk"):
                        found = os.path.join(root, f2)
                        break
                if found:
                    break
            if not found:
                await msg.edit_text("❌ Zip mein APK nahi mili.")
                return
            apk_path = found
        elif not fname.lower().endswith(".apk"):
            await msg.edit_text("❌ Sirf APK ya ZIP bhej.")
            return

        await crack_apk(update, context, msg, apk_path)


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
    app.add_handler(CommandHandler("crack", crack_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    print(f"✅ {BOT_NAME} ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
