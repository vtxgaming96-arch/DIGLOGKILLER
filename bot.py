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
TOKEN = os.getenv("TELEGRAM_TOKEN") or "your_token_here"
ADMIN_ID = int(os.getenv("ADMIN_ID") or "5510702228")
DEV_NAME = "@VICKYGAMING0"
BOT_NAME = "VTX PATCHER"

# ★ APNI .so KA NAAM YAHAN DAAL
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


# ========== FIND TOOL ==========
def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    for c in [
        f"/usr/bin/{name}",
        f"/usr/local/bin/{name}",
        "/usr/lib/android-sdk/build-tools/debian/" + name,
        "/opt/android-sdk/build-tools/debian/" + name,
    ]:
        if os.path.exists(c):
            return c
    # Build tools folder
    for base in ["/usr/lib/android-sdk/build-tools",
                 "/opt/android-sdk/build-tools"]:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d, name)
                if os.path.exists(p):
                    return p
    return None


# ========== SIGN APK ==========
def sign_apk(apk_path):
    """Uber APK Signer se sign karo"""
    uber = "/tmp/uber-apk-signer.jar"

    if os.path.exists(uber):
        r = subprocess.run(
            f'java -jar "{uber}" --apks "{apk_path}" --allowResign',
            shell=True, capture_output=True, text=True, timeout=300
        )

        # Output file
        base = apk_path[:-4]
        signed_candidates = [
            f"{base}-aligned-signed.apk",
            f"{base}-signed.apk",
        ]
        for s in signed_candidates:
            if os.path.exists(s):
                os.replace(s, apk_path)
                return "✅ Signed (uber V1+V2+V3)"

        # Cleanup extra files
        for f in os.listdir(os.path.dirname(apk_path)):
            if f.endswith("-aligned.apk") or f.endswith("-signed.apk"):
                try:
                    os.remove(os.path.join(os.path.dirname(apk_path), f))
                except: pass

        return f"⚠️ uber output missing"

    # Fallback: apksigner
    apksigner = find_tool("apksigner")
    if apksigner:
        ks = "/tmp/vtx.keystore"
        if not os.path.exists(ks):
            subprocess.run(
                f'keytool -genkeypair -v -keystore {ks} -alias vtx '
                f'-keyalg RSA -keysize 2048 -validity 10000 '
                f'-storepass vtxpass -keypass vtxpass '
                f'-dname "CN=VTX, O=VTX, C=IN"',
                shell=True, capture_output=True
            )

        r = subprocess.run(
            f'{apksigner} sign --ks {ks} --ks-key-alias vtx '
            f'--ks-pass pass:vtxpass --key-pass pass:vtxpass '
            f'--v1-signing-enabled true --v2-signing-enabled true '
            f'--v3-signing-enabled true "{apk_path}"',
            shell=True, capture_output=True, text=True, timeout=300
        )
        return "✅ Signed (apksigner)" if r.returncode == 0 else f"❌ {r.stderr[:150]}"

    return "❌ No signer available"


# ========== ZIPALIGN ==========
def zipalign_apk(apk_path):
    z = find_tool("zipalign")
    if not z:
        return "⚠️ zipalign not found"
    out = apk_path.replace(".apk", "_aligned.apk")
    r = subprocess.run(
        f'{z} -p -f 4 "{apk_path}" "{out}"',
        shell=True, capture_output=True, text=True, timeout=300
    )
    if r.returncode == 0 and os.path.exists(out):
        os.replace(out, apk_path)
        return "✅ Aligned"
    return f"⚠️ align failed"


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
        logger.error(f"patch error: {e}")
        return 0


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


# ========== MODE 2: CRACK APK ==========
async def crack_apk(update, context, msg, apk_path):
    user_id = update.effective_user.id
    ts = int(time.time())
    out_dir = os.path.join(TEMP_DIR, f"crack_{user_id}_{ts}")
    out_apk = os.path.join(TEMP_DIR, f"VTX_{user_id}_{ts}.apk")

    apk_path = os.path.abspath(apk_path)
    out_dir = os.path.abspath(out_dir)
    out_apk = os.path.abspath(out_apk)

    try:
        await msg.edit_text("🔍 Step 1/6: Extracting APK...")
        os.makedirs(out_dir, exist_ok=True)
        with zipfile.ZipFile(apk_path, 'r') as z:
            z.extractall(out_dir)

        await msg.edit_text(f"🔍 Step 2/6: Looking for '{TARGET_SO}'...")

        found_path = None
        for root, _, files in os.walk(out_dir):
            for f in files:
                if f == TARGET_SO:
                    found_path = os.path.join(root, f)
                    break
            if found_path:
                break

        if not found_path:
            await msg.edit_text(
                f"❌ '{TARGET_SO}' nahi mili.\n\n"
                f"Available .so files:\n"
                + "\n".join(
                    f"   • {f}" for root, _, files in os.walk(out_dir)
                    for f in files if f.endswith(".so")
                )[:600]
            )
            return

        await msg.edit_text(f"🔧 Step 3/6: Patching '{TARGET_SO}'...")
        count = patch_so_file(found_path)

        if count == 0:
            await msg.edit_text(f"⚠️ '{TARGET_SO}' mein exact 'show' nahi mila.")
            return

        await msg.edit_text("🔧 Step 4/6: Rebuilding APK...")
        with zipfile.ZipFile(out_apk, 'w', zipfile.ZIP_DEFLATED) as zf:
            manifest = os.path.join(out_dir, "AndroidManifest.xml")
            if os.path.exists(manifest):
                zf.write(manifest, "AndroidManifest.xml")

            for root, _, files in os.walk(out_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, out_dir).replace("\\", "/")
                    if rel == "AndroidManifest.xml":
                        continue
                    zf.write(full, rel)

        await msg.edit_text("🔧 Step 5/6: Zipalign...")
        align = zipalign_apk(out_apk)

        await msg.edit_text("🔧 Step 6/6: Signing...")
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
                f"📦 {align}\n"
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
        shutil.rmtree(out_dir, ignore_errors=True)
        try: os.remove(apk_path)
        except: pass
        try: os.remove(out_apk)
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
