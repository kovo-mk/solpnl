# Token Research & Fraud Detection Feature

## Overview

The research feature adds comprehensive token fraud detection to SolPnL, powered by Claude AI. Users can analyze any Solana token for scam patterns, holder concentration, and risk factors.

## Features

### Automated Analysis
- **Holder Concentration**: Detects whale dominance and Sybil attacks
- **Contract Analysis**: Checks for freeze/mint authorities, Pump.fun tokens
- **Pattern Detection**: Identifies suspicious wallet clustering, rushed development
- **AI-Powered**: Claude analyzes all data and provides natural language summary
- **Risk Scoring**: 0-100 risk score with severity levels (low/medium/high/critical)

### Integration with P/L Tracking
- Users can research tokens before buying
- Research results cached for 24 hours
- Same Helius API used for both features
- Unified database and authentication

## API Endpoints

### POST /api/research/analyze
Request fraud analysis for a token.

**Request:**
```json
{
  "token_address": "CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump",
  "force_refresh": false
}
```

**Response:**
```json
{
  "request_id": 123,
  "status": "pending",
  "created_at": "2026-01-16T10:00:00Z",
  "report_id": null
}
```

### GET /api/research/status/{request_id}
Check analysis progress.

**Response:**
```json
{
  "request_id": 123,
  "status": "completed",
  "created_at": "2026-01-16T10:00:00Z",
  "report_id": 456
}
```

### GET /api/research/report/{report_id}
Get full analysis report.

**Response:**
```json
{
  "token_address": "CYtqp57...",
  "risk_score": 75,
  "risk_level": "high",
  "verdict": "likely_scam",
  "summary": "This token shows extreme holder concentration (41.8% in top 10)...",
  "total_holders": 620,
  "top_10_holder_percentage": 41.85,
  "whale_count": 3,
  "is_pump_fun": true,
  "has_freeze_authority": false,
  "has_mint_authority": false,
  "red_flags": [
    {
      "severity": "high",
      "title": "Extreme Holder Concentration",
      "description": "Top 10 holders control 41.8% of supply..."
    }
  ],
  "suspicious_patterns": [
    "extreme_holder_concentration",
    "solo_developer",
    "rushed_development"
  ],
  "created_at": "2026-01-16T10:00:30Z",
  "updated_at": "2026-01-16T10:00:30Z"
}
```

### GET /api/research/token/{token_address}
Get latest report by token address (shortcut).

## Database Schema

### token_analysis_requests
Tracks user analysis requests.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| token_address | String | Token mint address |
| user_id | Integer | Optional user who requested |
| status | String | pending/processing/completed/failed |
| report_id | Integer | Link to completed report |
| error_message | Text | Error details if failed |
| created_at | DateTime | Request timestamp |
| completed_at | DateTime | Completion timestamp |

### token_analysis_reports
Stores comprehensive fraud analysis results.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| token_address | String | Token mint address |
| risk_score | Integer | 0-100 risk score |
| risk_level | String | low/medium/high/critical |
| holder_concentration | Text (JSON) | Top holder percentages |
| suspicious_patterns | Text (JSON) | Detected pattern array |
| red_flags | Text (JSON) | Red flag objects |
| total_holders | Integer | Total holder count |
| top_10_holder_percentage | Float | % held by top 10 |
| whale_count | Integer | Holders with >5% |
| is_pump_fun | Boolean | Pump.fun token flag |
| has_freeze_authority | Boolean | Freeze authority present |
| has_mint_authority | Boolean | Mint authority present |
| github_repo_url | String | Optional GitHub link |
| twitter_handle | String | Optional Twitter handle |
| telegram_group | String | Optional Telegram link |
| github_commit_count | Integer | Commit count |
| github_developer_count | Integer | Dev count |
| twitter_followers | Integer | Follower count |
| telegram_members | Integer | Member count |
| claude_summary | Text | AI natural language summary |
| claude_verdict | String | safe/suspicious/likely_scam/confirmed_scam |
| is_stale | Boolean | Mark for re-analysis |
| cached_until | DateTime | Cache expiry |
| created_at | DateTime | Report creation time |
| updated_at | DateTime | Last update time |

### wallet_reputations
Tracks individual wallet reputations for Sybil detection.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| wallet_address | String | Wallet public key |
| reputation_score | Integer | 0-100, 50=neutral |
| first_seen_at | DateTime | First transaction |
| total_tokens_held | Integer | Token count |
| total_transactions | Integer | TX count |
| is_sybil_cluster | Boolean | Coordinated wallet flag |
| wash_trading_score | Float | 0-1 suspicion level |
| rapid_dump_count | Integer | Tokens dumped <24h after buy |
| cluster_id | String | Group ID for related wallets |
| cluster_confidence | Float | 0-1 clustering confidence |
| analyzed_in_report_id | Integer | Link to analysis report |

## Setup Instructions

### 1. Install Dependencies
```bash
cd backend
pip install anthropic redis
```

### 2. Add Environment Variables
Add to `.env`:
```bash
# Get your API key at https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: Redis for caching (or use Railway Redis add-on)
REDIS_URL=redis://localhost:6379
```

### 3. Run Database Migration
```bash
cd backend
python database/migrate_research.py
```

This creates the new tables without affecting existing P/L data.

### 4. Start the Server
```bash
python main.py
```

API docs available at http://localhost:8000/docs

## Frontend Integration

Add a new page/tab to your Next.js frontend:

```
frontend/
├── app/
│   ├── dashboard/          # Existing P/L tracking
│   └── research/           # NEW: Token research
│       ├── page.tsx        # Research form + results
│       └── [report]/       # Individual report view
│           └── page.tsx
```

### Example Component Structure

**Research Form** (`app/research/page.tsx`):
```typescript
'use client';

import { useState } from 'react';

export default function ResearchPage() {
  const [tokenAddress, setTokenAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  const analyzeToken = async () => {
    setLoading(true);

    // 1. Submit analysis request
    const response = await fetch('/api/research/analyze', {
      method: 'POST',
      body: JSON.stringify({ token_address: tokenAddress }),
    });

    const { request_id } = await response.json();

    // 2. Poll for completion
    const checkStatus = async () => {
      const statusRes = await fetch(`/api/research/status/${request_id}`);
      const status = await statusRes.json();

      if (status.status === 'completed') {
        // 3. Fetch full report
        const reportRes = await fetch(`/api/research/report/${status.report_id}`);
        const reportData = await reportRes.json();
        setReport(reportData);
        setLoading(false);
      } else if (status.status === 'failed') {
        setLoading(false);
        alert('Analysis failed');
      } else {
        // Still processing, check again in 2 seconds
        setTimeout(checkStatus, 2000);
      }
    };

    checkStatus();
  };

  return (
    <div>
      <h1>Token Research</h1>
      <input
        value={tokenAddress}
        onChange={(e) => setTokenAddress(e.target.value)}
        placeholder="Token address"
      />
      <button onClick={analyzeToken} disabled={loading}>
        {loading ? 'Analyzing...' : 'Analyze Token'}
      </button>

      {report && (
        <div>
          <h2>Risk Score: {report.risk_score}/100</h2>
          <p>Level: {report.risk_level}</p>
          <p>{report.summary}</p>

          <h3>Red Flags:</h3>
          <ul>
            {report.red_flags.map((flag, i) => (
              <li key={i}>
                <strong>{flag.title}</strong>: {flag.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

## Cost Estimates

### Claude API (Haiku model)
- $0.25 per million input tokens
- $1.25 per million output tokens
- Average analysis: ~2,000 input + 500 output tokens
- **Cost per analysis: ~$0.001 (0.1 cents)**
- 1,000 analyses/month: ~$1

### Helius API
- Free tier: 100,000 requests/day
- Token holder data: 1-3 requests per analysis
- **Effectively free for most use cases**

### Redis (Optional)
- Railway Redis: $5/month (512MB)
- Or use free Redis Cloud tier

**Total monthly cost: $5-10 for moderate usage**

## Real-World Example: Oxedium Analysis

Based on our Oxedium investigation, here's what the system would detect:

### Input Data
- Token: CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump
- 620 holders
- Top 10 hold 41.85%
- Pump.fun token
- GitHub: Solo dev, 98 commits in 10 days

### Analysis Output
```json
{
  "risk_score": 78,
  "risk_level": "high",
  "verdict": "likely_scam",
  "summary": "This token exhibits multiple red flags including extreme holder concentration (41.8% in top 10 wallets), solo developer with rushed 10-day development timeline, and low community engagement. Similar patterns observed in confirmed rug pulls.",
  "red_flags": [
    {
      "severity": "high",
      "title": "Extreme Holder Concentration",
      "description": "Top 10 holders control 41.8% of supply. Creates massive dump risk."
    },
    {
      "severity": "high",
      "title": "Rushed Development Timeline",
      "description": "Project went from first commit to mainnet in 10 days. Similar to confirmed scam patterns."
    },
    {
      "severity": "medium",
      "title": "Solo Developer Project",
      "description": "Only one developer in GitHub repo. Single point of failure."
    }
  ],
  "suspicious_patterns": [
    "extreme_holder_concentration",
    "solo_developer",
    "rushed_development",
    "pump_fun_token"
  ]
}
```

## Future Enhancements

### Phase 2 (Weeks 2-3)
- [ ] Twitter scraping for follower/engagement analysis
- [ ] Telegram member count tracking
- [ ] GitHub automated analysis (commit timeline, license checks)
- [ ] Wallet clustering algorithm (detect Sybil attacks)

### Phase 3 (Weeks 4-5)
- [ ] Wash trading detection (circular trading patterns)
- [ ] Historical price manipulation checks
- [ ] Cross-reference with known scam wallet database
- [ ] Telegram-ready report export (like we manually created)

### Phase 4 (Weeks 6+)
- [ ] Browser extension for quick analysis
- [ ] Alerts for tokens in user's portfolio that turn risky
- [ ] Community reporting (users can flag scams)
- [ ] Multi-chain support (Ethereum, Base)

## Testing

### Manual Test
```bash
# 1. Analyze Oxedium token (known risky)
curl -X POST http://localhost:8000/api/research/analyze \
  -H "Content-Type: application/json" \
  -d '{"token_address": "CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump"}'

# Response: {"request_id": 1, "status": "pending", ...}

# 2. Check status
curl http://localhost:8000/api/research/status/1

# 3. Get report
curl http://localhost:8000/api/research/report/1
```

### Test Safe Token
Try with well-known tokens like USDC or SOL to verify low-risk scores.

## Deployment Notes

### Railway (Backend)
1. Add Anthropic API key to environment variables
2. Optional: Add Railway Redis plugin
3. Run migration: `python database/migrate_research.py`
4. Deploy normally

### Vercel (Frontend)
1. Add research page to Next.js app
2. Update navigation to include research tab
3. Deploy as usual

No additional infrastructure needed - leverages existing setup!

## Support

Issues? Check:
1. `ANTHROPIC_API_KEY` set in .env
2. Database migration ran successfully
3. Helius API working (required for holder data)
4. Check logs: `loguru` outputs to console

## License

Same as SolPnL (MIT)
