# 🔐 Real Account Login Validator

A Python-based system that validates real account credentials against actual login pages and reports which accounts successfully logged in **without any errors** (no password reset, 2FA, or CAPTCHA issues).

## ✨ Features

- ✅ **Real Login Testing** - Tests actual credentials against real websites
- 🔍 **Smart Detection** - Identifies successful logins vs errors
- 🚫 **Error Filtering** - Detects and reports:
  - ❌ Invalid credentials
  - 🔐 2FA requirements
  - 🤖 CAPTCHA challenges
  - 🔄 Password reset requirements
- 📊 **Detailed Reports** - Generates comprehensive results files
- ⚙️ **Configurable** - Easy JSON configuration for any website
- 🔒 **Secure** - Local execution, no data sent to third parties

## 📋 What You Get

### Successfully Logged In Accounts
The system will identify and report accounts that:
- ✅ Logged in successfully
- ✅ No password reset required
- ✅ No 2FA challenge
- ✅ No CAPTCHA verification
- ✅ Ready to use immediately

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

Or use the quick start script:
```bash
./quick_start.sh
```

### 2. Configure Your Site
Edit [`site_config.json`](site_config.json):

```json
{
  "sites": {
    "your_company": {
      "login_url": "https://yourcompany.com/login",
      "username_field": "email",
      "password_field": "password",
      "success_indicators": ["dashboard", "welcome"],
      "fail_indicators": ["invalid credentials"],
      "2fa_indicators": ["verification code"],
      "captcha_indicators": ["captcha"],
      "reset_indicators": ["reset password"]
    }
  }
}
```

### 3. Add Your Credentials
Edit [`credentials.txt`](credentials.txt):

```
user1@company.com:Password123
user2@company.com:SecurePass456
testuser:mypassword789
```

### 4. Run Validation
```bash
python3 login_validator.py
```

## 📊 Results

The validator generates a timestamped results file with:

### Summary Section
```
📊 SUMMARY
✅ SUCCESS: 5
❌ FAILED: 3
🔐 2FA_REQUIRED: 2
🤖 CAPTCHA_REQUIRED: 1
🔄 RESET_PASSWORD: 1
TOTAL: 12
```

### Successful Logins (Most Important)
```
✅ SUCCESSFUL LOGINS (NO ERRORS)
================================================================================

Username: user1@company.com
Password: Password123
Details: Login successful - found: dashboard
Time: 2026-01-29T23:15:05.123456
--------------------------------------------------------------------------------
```

These are the accounts you can use immediately without any issues!

## 🔧 Configuration Guide

### Finding Form Field Names

Inspect your login page HTML to find the correct field names:

```html
<form action="/login" method="POST">
  <input name="email" type="text">        <!-- username_field: "email" -->
  <input name="password" type="password"> <!-- password_field: "password" -->
  <button type="submit">Login</button>
</form>
```

### Setting Success Indicators

Look at the page you see after successful login:
- URL contains "dashboard"? Add `"dashboard"` to `success_indicators`
- Page shows "Welcome back"? Add `"welcome back"` to `success_indicators`
- Page title is "My Account"? Add `"my account"` to `success_indicators`

### Setting Error Indicators

Try logging in with wrong credentials and note the error message:
- "Invalid credentials" → Add to `fail_indicators`
- "Incorrect password" → Add to `fail_indicators`

### Detecting 2FA/CAPTCHA/Reset

If you encounter these, note the text shown:
- "Enter verification code" → Add to `2fa_indicators`
- "Complete the CAPTCHA" → Add to `captcha_indicators`
- "Your password has expired" → Add to `reset_indicators`

## 📁 File Structure

```
.
├── login_validator.py      # Main validation script
├── credentials.txt          # Your login credentials (email:password)
├── site_config.json         # Website configuration
├── requirements.txt         # Python dependencies
├── quick_start.sh          # Quick start script
├── USAGE_GUIDE.md          # Detailed usage guide
├── results_*.txt           # Generated results (timestamped)
└── validator.log           # Execution logs
```

## 🎯 Use Cases

### 1. Account Verification
Verify which accounts in your list are still valid and accessible.

### 2. Migration Testing
Test credentials after a system migration to ensure they still work.

### 3. Bulk Account Validation
Validate multiple accounts at once instead of manual testing.

### 4. Security Auditing
Identify accounts that require password resets or have 2FA enabled.

## ⚙️ Advanced Options

### Adjust Request Timing
In [`site_config.json`](site_config.json):
```json
"global_settings": {
  "delay_between_requests": 2,  // Seconds between each test
  "timeout": 15                  // Request timeout in seconds
}
```

### Custom Headers
Add custom HTTP headers:
```json
"headers": {
  "User-Agent": "Mozilla/5.0...",
  "Accept-Language": "en-US",
  "Custom-Header": "value"
}
```

### Additional Form Fields
If login requires extra fields:
```json
"additional_fields": {
  "remember_me": "true",
  "redirect": "/dashboard"
}
```

## 🛡️ Security & Privacy

- ✅ **Local execution** - All processing happens on your machine
- ✅ **No external services** - No data sent to third parties
- ✅ **Secure storage** - Keep `credentials.txt` secure
- ✅ **HTTPS support** - Supports secure connections
- ⚠️ **Sensitive data** - Treat result files as confidential

## 🐛 Troubleshooting

### All Results Show as FAILED
**Problem**: Success indicators don't match the actual page content.

**Solution**: 
1. Log in manually to your site
2. View page source after successful login
3. Find unique text that appears only after login
4. Add that text to `success_indicators`

### Getting TIMEOUT Errors
**Problem**: Requests are timing out.

**Solution**: Increase timeout in `global_settings`:
```json
"timeout": 30
```

### SSL Certificate Errors
**Problem**: SSL verification failing.

**Solution**: Disable SSL verification (not recommended for production):
```json
"verify_ssl": false
```

### Rate Limiting / Blocked
**Problem**: Too many requests triggering security measures.

**Solution**: Increase delay between requests:
```json
"delay_between_requests": 5
```

## 📝 Example Workflow

1. **Prepare credentials file**
   ```
   john@company.com:Pass123
   jane@company.com:Secure456
   ```

2. **Configure site settings**
   - Set login URL
   - Set form field names
   - Add success indicators

3. **Run validator**
   ```bash
   python3 login_validator.py
   ```

4. **Review results**
   - Check `results_*.txt` for successful logins
   - Use accounts marked as ✅ SUCCESS
   - Handle accounts with errors appropriately

## 📚 Documentation

- [`USAGE_GUIDE.md`](USAGE_GUIDE.md) - Comprehensive usage guide
- [`site_config.json`](site_config.json) - Configuration reference
- [`validator.log`](validator.log) - Execution logs

## 🔍 How It Works

1. **Load Configuration** - Reads site settings and indicators
2. **Load Credentials** - Parses credentials from text file
3. **Test Each Credential** - Makes HTTP POST request to login URL
4. **Analyze Response** - Checks response for indicators:
   - CAPTCHA detection (highest priority)
   - 2FA detection
   - Password reset detection
   - Success indicators
   - Failure indicators
5. **Generate Report** - Creates detailed results file

## ⚡ Performance

- **Speed**: ~2-5 seconds per credential (configurable)
- **Capacity**: Tested with 100+ credentials
- **Reliability**: Automatic retry on network errors
- **Efficiency**: Async HTTP requests for better performance

## 🎓 Best Practices

1. ✅ **Test with 1-2 credentials first** - Verify configuration
2. ✅ **Use realistic delays** - Avoid triggering rate limits
3. ✅ **Keep credentials secure** - Use file permissions
4. ✅ **Monitor logs** - Check `validator.log` for issues
5. ✅ **Update indicators** - Sites change, keep config current
6. ✅ **Backup results** - Save result files for records

## 📞 Support

For issues:
1. Check [`validator.log`](validator.log) for detailed errors
2. Review [`USAGE_GUIDE.md`](USAGE_GUIDE.md) for solutions
3. Verify configuration matches actual login page
4. Test manually in browser first

## 📄 License

This tool is for legitimate account validation purposes only. Only test accounts you own or have explicit permission to test.

---

**Ready to validate your accounts?** Edit [`credentials.txt`](credentials.txt) and [`site_config.json`](site_config.json), then run:

```bash
python3 login_validator.py
```
