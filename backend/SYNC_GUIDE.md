# Wallet Sync Guide

This guide explains the wallet syncing system, including manual sync, incremental sync, and auto-sync features.

---

## Sync Types

### 1. **Incremental Sync** (Default)
Only fetches transactions newer than the last synced transaction.

**Benefits:**
- Fast (typically 1-5 seconds vs 20-30 seconds for full sync)
- Saves API calls to Helius
- Recommended for regular updates

**How it works:**
1. Checks database for most recent transaction
2. Only fetches Helius data newer than that timestamp
3. Skips already-processed transactions

**API Usage:**
```bash
# Default behavior (incremental)
POST /api/wallets/{address}/sync

# Explicit incremental sync
POST /api/wallets/{address}/sync?force_full=false
```

---

### 2. **Full Resync**
Re-fetches ALL transactions from Helius (up to 1000 max).

**When to use:**
- After updating the transaction parser (e.g., fixing USDC cost basis bug)
- When you suspect data inconsistencies
- First time syncing a wallet

**API Usage:**
```bash
POST /api/wallets/{address}/sync?force_full=true
```

---

### 3. **Auto-Sync** (Scheduled)
Automatically syncs all wallets at a configured interval.

**Benefits:**
- Hands-off operation
- Keep portfolio updated without manual intervention
- Uses incremental sync for efficiency

**Configuration:**

```bash
# Enable auto-sync (every 24 hours)
POST /api/sync/auto/configure?enabled=true&interval_hours=24

# Enable auto-sync (every 6 hours)
POST /api/sync/auto/configure?enabled=true&interval_hours=6

# Disable auto-sync
POST /api/sync/auto/configure?enabled=false

# Check auto-sync status
GET /api/sync/auto/status

# Manually trigger auto-sync now (for all wallets)
POST /api/sync/auto/trigger
```

**Example Response:**
```json
{
  "auto_sync_enabled": true,
  "interval_hours": 24,
  "message": "Auto-sync enabled"
}
```

---

## Speed Improvements

### Before (Old Parser)
- Full sync: 20-30 seconds
- No incremental option
- Re-processed ALL transactions every time

### After (New System)
- **Incremental sync: 1-5 seconds** (only new transactions)
- **Full resync: 15-25 seconds** (filtered duplicates)
- Smart filtering reduces database writes

### Example Timeline
```
First sync:        ~25 seconds (fetching 67 transactions)
Second sync:       ~2 seconds  (fetching 3 new transactions)
Third sync:        ~1 second   (no new transactions)
```

---

## Frontend Integration

### Current Sync Button
Update your frontend sync button to support force resync:

```typescript
// Default: incremental sync
const handleSync = async () => {
  const response = await fetch(
    `${API_BASE}/wallets/${address}/sync`,
    { method: 'POST' }
  );
  const data = await response.json();
  console.log(data.message); // "Incremental sync started"
};

// Force full resync
const handleFullResync = async () => {
  const response = await fetch(
    `${API_BASE}/wallets/${address}/sync?force_full=true`,
    { method: 'POST' }
  );
  const data = await response.json();
  console.log(data.message); // "Full resync started"
};
```

### Auto-Sync Settings Page (Optional)
Add a settings page to configure auto-sync:

```typescript
const AutoSyncSettings = () => {
  const [enabled, setEnabled] = useState(false);
  const [intervalHours, setIntervalHours] = useState(24);

  const saveSettings = async () => {
    await fetch(
      `${API_BASE}/sync/auto/configure?enabled=${enabled}&interval_hours=${intervalHours}`,
      { method: 'POST' }
    );
  };

  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Enable Auto-Sync
      </label>
      <select value={intervalHours} onChange={(e) => setIntervalHours(+e.target.value)}>
        <option value={6}>Every 6 hours</option>
        <option value={12}>Every 12 hours</option>
        <option value={24}>Every 24 hours</option>
      </select>
      <button onClick={saveSettings}>Save</button>
    </div>
  );
};
```

---

## Railway Deployment

The auto-sync scheduler runs as a background task within the same Railway service (no separate cron needed).

**Environment Variables:**
No additional config required! The scheduler is built into the backend.

**To enable auto-sync in production:**
```bash
# Using curl or your frontend settings page
curl -X POST "https://your-backend.railway.app/api/sync/auto/configure?enabled=true&interval_hours=24"
```

**Monitoring:**
```bash
# Check if auto-sync is running
curl "https://your-backend.railway.app/api/sync/auto/status"

# Response:
{
  "enabled": true,
  "interval_hours": 24,
  "is_running": true
}
```

---

## Troubleshooting

### Sync seems slow
- Use **incremental sync** (default) instead of full resync
- Incremental only fetches new transactions (1-5 seconds)
- Full resync re-processes everything (20-30 seconds)

### USDC shows wrong cost basis
- Run **full resync** with `force_full=true` to recalculate with the new parser
- This re-processes all transactions with the comprehensive parser
- USDC cost basis should be correct after resync

### Auto-sync not working
1. Check status: `GET /api/sync/auto/status`
2. Ensure `enabled: true` and `is_running: true`
3. Check Railway logs for sync scheduler messages
4. Manually trigger: `POST /api/sync/auto/trigger`

### Want to see sync progress
- Poll the sync status endpoint: `GET /api/wallets/{address}/sync/status`
- Response shows:
  - `status`: "syncing", "completed", "error"
  - `transactions_fetched`: Total fetched from Helius
  - `swaps_found`: Relevant transactions parsed
  - `message`: Current operation

---

## Summary

**For regular updates:** Use default incremental sync (fast)

**For fixing data issues:** Use full resync with `force_full=true`

**For automation:** Enable auto-sync with your preferred interval

**Speed comparison:**
- Incremental: 1-5 seconds
- Full resync: 15-25 seconds
- Auto-sync: Incremental (every N hours)
