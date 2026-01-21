# Insider Wallet Analysis Guide

## Suspicious SOLCEX Wallets Identified

Based on analysis of the first 100 transactions (April 15, 2024 23:52-23:59 UTC), these wallets show potential insider trading patterns:

### Top 3 Suspects:

1. **WGQnogYKikMu8LycuLHUSkpVbPCSKb1avE9GqM2S45q**
   - Bought 1.35M tokens in first 10 minutes
   - Multiple strategic buys
   - Pattern: Large early accumulation

2. **9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8**
   - Bought 1.39M tokens via 5+ transactions
   - All within 5 minutes of launch
   - Pattern: Rapid accumulation

3. **9dyPzf34WNT2BRwh1Wo2cz7rDF5ukpoy4gYb7coQYY7X**
   - Bought 734K tokens
   - Perfectly timed entries
   - Pattern: Strategic positioning

### Other Suspicious Wallets:

4. **BQ72nSv9f3PRyRKCBnHLVrerrv37CYTHm5h3s9VSGQDV**
   - Immediately forwarded tokens to other wallets
   - Pattern: Wallet splitting (classic team behavior)

5. **5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1**
   - Main distribution wallet
   - Source of initial supply
   - Potential creator wallet

## API Usage

### Step 1: Run Deep Track (if not already done)
```bash
POST https://your-backend.railway.app/api/research/deep-track/AMjzRn1TBQwQfNAjHFeBb7uGbbqbJB7FzXAnGgdFPk6K
```

### Step 2: Analyze Each Wallet
```bash
# Wallet #1
GET https://your-backend.railway.app/api/research/wallet-trading-history/AMjzRn1TBQwQfNAjHFeBb7uGbbqbJB7FzXAnGgdFPk6K/WGQnogYKikMu8LycuLHUSkpVbPCSKb1avE9GqM2S45q

# Wallet #2
GET https://your-backend.railway.app/api/research/wallet-trading-history/AMjzRn1TBQwQfNAjHFeBb7uGbbqbJB7FzXAnGgdFPk6K/9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8

# Wallet #3
GET https://your-backend.railway.app/api/research/wallet-trading-history/AMjzRn1TBQwQfNAjHFeBb7uGbbqbJB7FzXAnGgdFPk6K/9dyPzf34WNT2BRwh1Wo2cz7rDF5ukpoy4gYb7coQYY7X
```

## Response Format

```json
{
  "token_address": "AMjzRn1T...",
  "wallet_address": "WGQnogYK...",
  "transactions": [...],  // First 100 transactions
  "total_transactions": 156,
  "total_bought": 1350000,
  "total_sold": 1200000,
  "net_position": 150000,  // Still holding 150K tokens
  "first_transaction": {
    "signature": "...",
    "timestamp": 1713225495,
    "type": "BUY",
    "amount": 50000
  },
  "last_transaction": {
    "signature": "...",
    "timestamp": 1713228000,
    "type": "SELL",
    "amount": 500000
  },
  "pattern": "PARTIAL_SELLER",  // or HOLDER, FULL_EXIT, INITIAL_DISTRIBUTOR
  "is_early_buyer": true,
  "time_to_first_buy_seconds": 15,  // Bought 15 seconds after token creation!
  "buy_count": 8,
  "sell_count": 12
}
```

## Pattern Interpretations

### 🚩 RED FLAGS (Insider Behavior):
- **FULL_EXIT** + **is_early_buyer: true** = Classic insider dump
  - Bought early, sold everything, took profit
  - Left retail holding the bag

- **INITIAL_DISTRIBUTOR** = Team wallet
  - Only sells, never buys
  - Distributing initial supply

- **time_to_first_buy_seconds < 60** = Suspicious
  - How did they know to buy within 60 seconds of launch?
  - Likely had advance notice

### ✅ GOOD SIGNS (Legitimate Trader):
- **HOLDER** + **is_early_buyer: true** = Conviction buyer
  - Bought early, still holding
  - Believes in project

- **PARTIAL_SELLER** = Taking profits
  - Normal trading behavior
  - Not necessarily malicious

## Next Steps

1. Run Deep Track on SOLCEX (if not done)
2. Query all 5 suspicious wallets
3. Look for:
   - Wallets that bought <60 seconds after launch
   - Wallets that sold 100% of holdings
   - Coordinated selling patterns (all wallets sell at same time)
   - Wallet clusters (tokens moving between related wallets)

## Future Enhancements

- Add profit/loss calculations (need price data)
- Detect coordinated trading between multiple wallets
- Show transaction timeline visualization
- Alert when wallet starts dumping large amounts
