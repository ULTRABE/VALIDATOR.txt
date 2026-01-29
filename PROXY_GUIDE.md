# 🔧 Proxy Management Guide

## Overview

The Auth Checker Bot now includes a comprehensive proxy management system with database persistence, automatic testing, and dead proxy detection.

## Features

### 🗄️ Database Persistence
- All proxies are stored in SQLite database
- Proxies persist across bot restarts and redeployments
- Each proxy tracks success/fail counts and average response time

### 🔄 Automatic Proxy Selection
- Bot automatically uses the best performing proxy
- Selection based on success rate and response time
- No manual proxy switching needed

### 🧪 Proxy Testing
- Test proxies before adding them
- Manual testing available via inline buttons
- Real-time response time measurement

### 🔴 Dead Proxy Detection
- Automatic detection of non-responsive proxies
- Proxies with >80% fail rate (after 10 attempts) are auto-disabled
- Prevents wasting time on dead proxies

### 📊 Performance Tracking
- Success/fail count for each proxy
- Average response time tracking
- Health indicators (🟢 Good, 🟡 Warning, 🔴 Poor)

## How to Use

### Adding a Proxy

1. **Via Command**:
   ```
   /proxy
   ```
   Then send your proxy URL

2. **Supported Formats**:
   - `http://ip:port`
   - `http://user:pass@ip:port`
   - `socks5://ip:port`

3. **Automatic Testing**:
   - Bot tests the proxy before adding
   - Shows response time if successful
   - Rejects non-working proxies

### Managing Proxies

Use `/proxy` command to access the management menu:

#### Proxy List Display
```
🔧 Proxy Management

📋 Your Proxies:

1. ✅ 🟢 http://proxy1.com:8080...
   Success: 45 | Fail: 2 | Avg: 1.23s

2. ✅ 🟡 http://proxy2.com:3128...
   Success: 20 | Fail: 15 | Avg: 3.45s

3. ❌ 🔴 http://proxy3.com:1080...
   Success: 5 | Fail: 25 | Avg: 0.00s
```

#### Status Indicators
- ✅ = Active (will be used)
- ❌ = Disabled (won't be used)

#### Health Indicators
- 🟢 = Excellent (fail rate < 33%)
- 🟡 = Warning (fail rate 33-50%)
- 🔴 = Poor (fail rate > 50%)

### Proxy Actions

#### Test Proxy
- Click "Test #N" button
- Bot tests proxy connectivity
- Updates statistics
- Shows response time

#### Enable/Disable Proxy
- Click "Disable #N" or "Enable #N"
- Toggles proxy active status
- Disabled proxies won't be used

#### Delete Proxy
- Click "Delete #N"
- Permanently removes proxy
- Cannot be undone

## Automatic Features

### Auto-Selection
When checking credentials:
1. Bot queries database for active proxies
2. Selects proxy with best success rate
3. Falls back to direct connection if no proxies

### Auto-Disable
During credential checking:
1. Bot tracks each proxy request
2. Updates success/fail counts
3. Calculates fail rate
4. Auto-disables if:
   - At least 10 total attempts
   - Fail rate > 80%

### Performance Tracking
Every credential check:
- Records success/failure
- Measures response time
- Updates average response time
- Updates last tested timestamp

## Database Schema

### Proxies Table
```sql
CREATE TABLE proxies (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    proxy_url TEXT NOT NULL,
    proxy_type TEXT DEFAULT 'http',
    is_active INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_response_time REAL DEFAULT 0.0,
    last_tested TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

## Best Practices

### 1. Test Before Use
Always test proxies before adding them to ensure they work.

### 2. Monitor Performance
Check proxy statistics regularly via `/proxy` command.

### 3. Remove Dead Proxies
Delete proxies that consistently fail (🔴 indicator).

### 4. Use Multiple Proxies
Add multiple proxies for redundancy and load distribution.

### 5. Check Response Times
Prefer proxies with lower average response times.

## Troubleshooting

### Proxy Not Working
1. Check proxy format is correct
2. Verify proxy is online
3. Test proxy manually
4. Check proxy credentials if using auth

### All Proxies Disabled
1. Use `/proxy` to view status
2. Test each proxy individually
3. Re-enable working proxies
4. Add new proxies if needed

### Slow Performance
1. Check average response times
2. Disable slow proxies (>5s)
3. Add faster proxies
4. Consider direct connection

### Proxy Auto-Disabled
This means the proxy had >80% fail rate:
1. Test the proxy manually
2. If it works, re-enable it
3. If it fails, delete it
4. Add a replacement proxy

## Advanced Usage

### Proxy Rotation
The bot automatically uses the best proxy based on:
1. Success rate (higher is better)
2. Response time (lower is better)
3. Active status (only active proxies)

### Statistics Analysis
Monitor these metrics:
- **Success Count**: Higher is better
- **Fail Count**: Lower is better
- **Success Rate**: Should be >50%
- **Avg Response Time**: Should be <3s

### Maintenance
Regularly:
1. Review proxy list
2. Test all proxies
3. Remove dead proxies
4. Add new proxies
5. Monitor performance

## API Functions

### For Developers

```python
# Add proxy
add_proxy(user_id, proxy_url) -> bool

# Get user's proxies
get_user_proxies(user_id) -> list

# Get best active proxy
get_active_proxy(user_id) -> str

# Update proxy stats
update_proxy_stats(proxy_url, success, response_time)

# Test proxy
test_proxy(proxy_url) -> tuple(success, response_time)

# Deactivate proxy
deactivate_proxy(proxy_id) -> bool

# Delete proxy
delete_proxy(proxy_id) -> bool
```

## Security Notes

1. **Proxy Credentials**: Stored in database (consider encryption for production)
2. **Database Access**: Only bot has access to proxy database
3. **Proxy Testing**: Uses HTTPS for security
4. **Data Privacy**: Proxy stats are per-user

## Future Enhancements

Planned features:
- Proxy pool sharing
- Automatic proxy rotation
- Proxy health monitoring
- Email notifications for dead proxies
- Proxy performance graphs
- Bulk proxy import

## Support

For issues or questions:
1. Check this guide first
2. Review bot logs
3. Test proxies manually
4. Contact bot administrator

---

**Note**: Proxy management requires proper configuration. Always test proxies before relying on them for credential checking.
