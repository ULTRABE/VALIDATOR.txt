# 🔐 Real Account Login Validator - Usage Guide

## Overview
This system validates real account credentials from a text file against actual login pages and reports which accounts successfully logged in without errors (no password reset, 2FA, or CAPTCHA issues).

## 📁 Files

### 1. `credentials.txt` - Your Login Credentials
Format: `username:password` or `email:password` (one per line)

```
user1@company.com:MyPassword123
john.doe@example.com:SecurePass456
testuser:password789
```

**Important**: Replace the example credentials with your real ones!

### 2. `site_config.json` - Website Configuration
Configure the target website's login details:

```json
{
  "sites": {
    "your_company_site": {
      "login_url": "https://yourcompany.com/login",
      "method": "POST",
      "username_field": "email",
      "password_field": "password",
      "success_indicators": [
        "dashboard",
        "welcome",
        "my account"
      ],
      "fail_indicators": [
        "invalid credentials",
        "incorrect password"
      ],
      "2fa_indicators": [
        "two-factor",
        "verification code"
      ],
      "captcha_indicators": [
        "captcha",
        "verify you are human"
      ],
      "reset_indicators": [
        "reset password",
        "password expired"
      ]
    }
  }
}
```

**Configuration Steps**:
1. Set `login_url` to your company's login page
2. Set `username_field` and `password_field` to match the form field names
3. Add text that appears on successful login to `success_indicators`
4. Add error messages to `fail_indicators`
5. Add 2FA/CAPTCHA/reset messages to respective indicator arrays

### 3. `login_validator.py` - Main Script
The validation engine that tests all credentials.

## 🚀 How to Use

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Your Site
Edit [`site_config.json`](site_config.json) with your company's login page details:
- Login URL
- Form field names
- Success/failure indicators

### Step 3: Add Your Credentials
Edit [`credentials.txt`](credentials.txt) and add your credentials:
```
your.email@company.com:YourPassword123
another.user@company.com:AnotherPass456
```

### Step 4: Run Validation
```bash
python login_validator.py
```

## 📊 Results

The script generates a timestamped results file: `results_YYYYMMDD_HHMMSS.txt`

### Result Categories:

1. **✅ SUCCESS** - Login successful, no errors
   - These accounts logged in successfully
   - No password reset required
   - No 2FA challenge
   - No CAPTCHA

2. **❌ FAILED** - Invalid credentials
   - Wrong username/password

3. **🔐 2FA_REQUIRED** - Two-factor authentication needed
   - Valid credentials but 2FA is enabled

4. **🤖 CAPTCHA_REQUIRED** - CAPTCHA challenge detected
   - Site requires CAPTCHA verification

5. **🔄 RESET_PASSWORD** - Password reset required
   - Account needs password change

6. **⚠️ ERROR** - Technical error occurred

7. **⏱️ TIMEOUT** - Request timed out

### Example Results File:
```
================================================================================
🔐 LOGIN VALIDATION RESULTS
Generated: 2026-01-29 23:15:00
================================================================================

📊 SUMMARY
--------------------------------------------------------------------------------
✅ SUCCESS: 3
❌ FAILED: 2
🔐 2FA_REQUIRED: 1
TOTAL: 6

================================================================================
✅ SUCCESSFUL LOGINS (NO ERRORS)
================================================================================

Username: user1@company.com
Password: MyPassword123
Details: Login successful - found: dashboard
Time: 2026-01-29T23:15:05.123456
--------------------------------------------------------------------------------

Username: user2@company.com
Password: SecurePass456
Details: Login successful - found: welcome
Time: 2026-01-29T23:15:10.234567
--------------------------------------------------------------------------------
```

## ⚙️ Advanced Configuration

### Adjusting Request Delay
In [`site_config.json`](site_config.json), modify `global_settings`:
```json
"global_settings": {
  "timeout": 15,
  "delay_between_requests": 2,
  "max_retries": 2,
  "verify_ssl": true,
  "follow_redirects": true
}
```

### Multiple Sites
You can configure multiple sites in [`site_config.json`](site_config.json):
```json
{
  "sites": {
    "site1": { ... },
    "site2": { ... }
  }
}
```

Currently, the script uses the first site. To use a different site, modify the site selection in [`login_validator.py`](login_validator.py:267).

### Custom Headers
Add custom headers in site configuration:
```json
"headers": {
  "User-Agent": "Mozilla/5.0...",
  "Accept": "text/html...",
  "Custom-Header": "value"
}
```

### Additional Form Fields
If the login form requires extra fields:
```json
"additional_fields": {
  "remember_me": "true",
  "csrf_token": "auto"
}
```

## 🔍 How Detection Works

The validator analyzes the HTTP response to determine login status:

1. **CAPTCHA Check** (highest priority)
   - Searches for CAPTCHA-related text in response

2. **2FA Check**
   - Looks for two-factor authentication prompts

3. **Password Reset Check**
   - Detects password expiration/reset requirements

4. **Success Check**
   - Searches for success indicators in page content
   - Checks URL redirects (dashboard, home, account pages)

5. **Failure Check**
   - Looks for error messages
   - Analyzes HTTP status codes

## 🛡️ Security Notes

- **Keep credentials.txt secure** - Contains sensitive login information
- **Use HTTPS** - Always use secure connections
- **Rate limiting** - Adjust delay to avoid triggering security measures
- **Legal compliance** - Only test accounts you own or have permission to test

## 🐛 Troubleshooting

### Issue: All logins show as FAILED
**Solution**: Check your `success_indicators` in config. View the actual login page source to find correct indicators.

### Issue: TIMEOUT errors
**Solution**: Increase `timeout` value in `global_settings`.

### Issue: SSL errors
**Solution**: Set `"verify_ssl": false` in `global_settings` (not recommended for production).

### Issue: Wrong form fields
**Solution**: Inspect the login form HTML to find correct field names:
```html
<input name="email" type="text">  <!-- username_field: "email" -->
<input name="password" type="password">  <!-- password_field: "password" -->
```

## 📝 Logs

Check [`validator.log`](validator.log) for detailed execution logs:
- Request/response details
- Error messages
- Timing information

## 🎯 Best Practices

1. **Test with one credential first** - Verify configuration works
2. **Use realistic delays** - Avoid triggering rate limits (2-5 seconds)
3. **Monitor logs** - Check for patterns in failures
4. **Update indicators** - Sites change, update your config accordingly
5. **Backup results** - Save result files for record keeping

## 📞 Support

For issues or questions:
1. Check logs in `validator.log`
2. Verify site configuration matches actual login page
3. Test manually in browser first to understand the login flow
