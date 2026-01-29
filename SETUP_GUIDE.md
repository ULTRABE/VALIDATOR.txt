# 🚀 Setup Guide - Auth Checker Bot

## Quick Setup (5 minutes)

### Step 1: Get Your Bot Token 🤖

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your User ID 👤

1. Open Telegram and search for **@userinfobot**
2. Send `/start` command
3. Copy your user ID (numeric, e.g., `123456789`)

### Step 3: Configure Environment Variables 🔧

#### For Railway/Cloud Deployment:

1. Go to your Railway project settings
2. Add these environment variables:
   ```
   BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ADMIN_ID=123456789
   OWNER_ID=123456789
   ```

#### For Local Development:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` file with your actual values:
   ```env
   BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ADMIN_ID=123456789
   OWNER_ID=123456789
   ```

### Step 4: Deploy/Run 🚀

#### Railway Deployment:
1. Push your code to GitHub
2. Connect Railway to your repository
3. Railway will automatically deploy
4. Check logs to confirm bot is running

#### Local Development:
```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python auth_bot.py
```

## ⚠️ Common Errors & Solutions

### Error: "BOT_TOKEN not configured"
**Solution**: Make sure you've set the `BOT_TOKEN` environment variable with your actual bot token from @BotFather.

### Error: "Invalid token"
**Solution**: 
- Check that your token is in the correct format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- Make sure there are no extra spaces or quotes
- Verify the token is still valid in @BotFather

### Error: "No module named 'telegram'"
**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

### Bot doesn't respond
**Solution**:
- Check that the bot is running (check logs)
- Verify your BOT_TOKEN is correct
- Make sure you've started the bot with `/start` command in Telegram

## 📋 Environment Variables Explained

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `BOT_TOKEN` | ✅ Yes | Your Telegram bot token from @BotFather | `123456789:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `ADMIN_ID` | ✅ Yes | Your Telegram user ID for admin commands | `123456789` |
| `OWNER_ID` | ⚠️ Optional | Owner's ID for startup notifications | `123456789` |

## 🎯 Testing Your Setup

1. **Start the bot**: Run `python auth_bot.py` or deploy to Railway
2. **Check logs**: Look for "✅ Bot fully configured - starting..."
3. **Test in Telegram**: 
   - Open your bot in Telegram
   - Send `/start` command
   - You should receive a welcome message

## 🔒 Security Best Practices

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Keep your BOT_TOKEN secret** - Don't share it publicly
3. **Use environment variables** - Don't hardcode tokens in code
4. **Rotate tokens if exposed** - Use @BotFather to regenerate

## 📊 Features Overview

### Live Progress Bar
- Real-time visual progress during credential checking
- Shows speed, ETA, and valid credentials found

### Startup Notifications
- Bot sends "Bot is started" message to all users on startup
- Owner always receives notification (via OWNER_ID)

### Credit System
- Each user starts with 1000 credits
- 1 credit = 1 credential check
- Admin can manage credits via database

### Proxy Support
- Configure HTTP/SOCKS5 proxies
- Use `/proxy` command to set up

## 🆘 Need Help?

1. Check the logs for error messages
2. Verify all environment variables are set correctly
3. Make sure dependencies are installed
4. Test with a simple `/start` command first

## 🎉 Success!

If you see this in your logs:
```
✅ Bot fully configured - starting...
📢 Startup notifications: X sent, Y failed
```

Your bot is running successfully! 🚀
