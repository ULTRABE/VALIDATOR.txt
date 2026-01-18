#!/usr/bin/env python3
"""
🤖 Credential Validator Bot - Railway Ready Single File
Telegram bot for validating email:password credentials against login pages
"""

import os
import re
import asyncio
import logging
import zipfile
import json
from io import BytesIO
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urljoin

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    import aiohttp
except ImportError:
    print("❌ Install dependencies: pip install -r requirements.txt")
    exit(1)

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', 10))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 30))

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@dataclass
class Credential:
    email: str
    password: str
    original_line: str

class CredentialValidatorBot:
    def __init__(self, token: str):
        self.token = token
        self.max_concurrent = MAX_CONCURRENT
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_states = {}
        self.working_creds = []

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🚀 /start command"""
        welcome_msg = """
        🤖 **Credential Validator Bot**

**Validates email:password combos against login pages**

**📋 Supported formats:**
user@gmail.com:password
email@site.com:secret

**⚙️ Workflow:**
1. Send login URL
2. Upload TXT file
3. Get working creds instantly
"""
        
🤖 **Credential Validator Bot**

**Validates email:password combos against login pages**

**📋 Supported formats:**
