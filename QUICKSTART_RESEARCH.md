# Token Research Feature - Quick Start

## 5-Minute Setup

### 1. Install Dependencies (1 min)
```bash
cd backend
pip install anthropic redis
```

### 2. Get API Keys (2 min)

**Anthropic Claude API:**
1. Go to https://console.anthropic.com/
2. Sign up (free $5 credit)
3. Create API key
4. Copy key (starts with `sk-ant-`)

**Optional - Redis (Local):**
```bash
# Windows (via Chocolatey):
choco install redis-64

# Mac (via Homebrew):
brew install redis
brew services start redis

# Or skip Redis entirely - code works without it
```

### 3. Configure Environment (30 sec)
Edit `backend/.env`:
```bash
# Add this line:
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional (skip if no Redis):
REDIS_URL=redis://localhost:6379
```

### 4. Run Migration (30 sec)
```bash
cd backend
python database/migrate_research.py
```

Expected output:
```
Running research tables migration...
Migration complete! New tables created:
  - token_analysis_requests
  - token_analysis_reports
  - wallet_reputations
  - rate_limits
```

### 5. Test It! (1 min)
```bash
# Start server
python main.py

# In another terminal, test analysis:
curl -X POST http://localhost:8000/api/research/analyze \
  -H "Content-Type: application/json" \
  -d "{\"token_address\": \"CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump\"}"

# You should see:
# {"request_id": 1, "status": "pending", ...}
```

Check status:
```bash
curl http://localhost:8000/api/research/status/1

# Wait for "status": "completed"
```

Get report:
```bash
curl http://localhost:8000/api/research/report/1

# You'll see the full fraud analysis!
```

## What You Just Built

✅ AI-powered token fraud detection
✅ Holder concentration analysis
✅ Risk scoring (0-100)
✅ Natural language summaries
✅ Red flag detection
✅ 24-hour caching
✅ Background processing

**All integrated with your existing P/L tracker!**

## Next: Add Frontend

Create `frontend/app/research/page.tsx`:

```typescript
'use client';

import { useState } from 'react';

export default function ResearchPage() {
  const [address, setAddress] = useState('');
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    setLoading(true);

    // Submit request
    const res = await fetch('http://localhost:8000/api/research/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token_address: address }),
    });

    const { request_id } = await res.json();

    // Poll for completion
    const poll = async () => {
      const statusRes = await fetch(`http://localhost:8000/api/research/status/${request_id}`);
      const status = await statusRes.json();

      if (status.status === 'completed') {
        const reportRes = await fetch(`http://localhost:8000/api/research/report/${status.report_id}`);
        setReport(await reportRes.json());
        setLoading(false);
      } else if (status.status === 'failed') {
        alert('Analysis failed');
        setLoading(false);
      } else {
        setTimeout(poll, 2000);
      }
    };

    poll();
  };

  return (
    <div className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">Token Research</h1>

      <div className="mb-8">
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Enter token address..."
          className="w-full p-3 border rounded-lg"
        />
        <button
          onClick={analyze}
          disabled={loading || !address}
          className="mt-4 bg-blue-600 text-white px-6 py-3 rounded-lg disabled:opacity-50"
        >
          {loading ? 'Analyzing...' : 'Analyze Token'}
        </button>
      </div>

      {report && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="mb-4">
            <span className={`text-4xl font-bold ${
              report.risk_level === 'critical' ? 'text-red-600' :
              report.risk_level === 'high' ? 'text-orange-600' :
              report.risk_level === 'medium' ? 'text-yellow-600' :
              'text-green-600'
            }`}>
              {report.risk_score}/100
            </span>
            <span className="ml-4 text-xl text-gray-600">
              Risk: {report.risk_level.toUpperCase()}
            </span>
          </div>

          <p className="mb-6 text-gray-700">{report.summary}</p>

          <div className="grid grid-cols-3 gap-4 mb-6">
            <div>
              <div className="text-sm text-gray-500">Total Holders</div>
              <div className="text-2xl font-bold">{report.total_holders}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Top 10 Hold</div>
              <div className="text-2xl font-bold">{report.top_10_holder_percentage.toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Whales</div>
              <div className="text-2xl font-bold">{report.whale_count}</div>
            </div>
          </div>

          <h3 className="text-xl font-bold mb-3">Red Flags</h3>
          <div className="space-y-3">
            {report.red_flags.map((flag: any, i: number) => (
              <div
                key={i}
                className={`p-4 rounded-lg ${
                  flag.severity === 'critical' ? 'bg-red-50 border-l-4 border-red-600' :
                  flag.severity === 'high' ? 'bg-orange-50 border-l-4 border-orange-600' :
                  'bg-yellow-50 border-l-4 border-yellow-600'
                }`}
              >
                <div className="font-bold mb-1">{flag.title}</div>
                <div className="text-sm text-gray-700">{flag.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

Add to your nav in `layout.tsx`:
```typescript
<nav>
  <Link href="/dashboard">Portfolio</Link>
  <Link href="/research">Research</Link>
</nav>
```

## Test With Real Tokens

### High Risk (Should score 70+):
- Oxedium: `CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump`
- Most Pump.fun tokens with <1000 holders

### Low Risk (Should score <30):
- Established tokens with broad distribution
- Tokens with verified teams and long history

## Costs

- **First analysis**: Free (Anthropic $5 credit)
- **Per analysis**: ~$0.001 (0.1 cents)
- **1000 analyses**: ~$1
- **Monthly (moderate use)**: $5-10

## Troubleshooting

### "No Helius API key"
Make sure `.env` has:
```bash
HELIUS_API_KEY=your_key_here
```

### "Anthropic API error"
Check your API key:
```bash
echo $ANTHROPIC_API_KEY  # Should print your key
```

### "Migration failed"
Make sure database is running:
```bash
# Check DATABASE_URL in .env
DATABASE_URL=sqlite:///./solpnl.db  # For local
# OR
DATABASE_URL=postgresql://...  # For Railway
```

### "Analysis stuck on 'processing'"
Check backend logs - error will be shown there.
Background task might have failed.

## Success!

You now have:
✅ Automated fraud detection
✅ Same analysis we did manually for Oxedium
✅ <$0.01 per analysis cost
✅ Full integration with P/L tracking

**Time to build the frontend and ship it!** 🚀

See `RESEARCH_FEATURE.md` for full documentation.
See `IMPLEMENTATION_SUMMARY.md` for architecture details.
