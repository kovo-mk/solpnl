"""Test script to fetch and examine raw Helius API response."""
import requests
import json

# Use Helius public demo key for testing (limited rate)
# Or we can call our own production API to proxy the request
wallet = "56YahmTzWix9nAYaeRKDMHZhyHZe6diU1tcgkBXA5iVt"

# Option: Call production API's sync endpoint and examine logs
# For now, let's use the public Solscan API to see a sample transaction

# Get a sample VXM transaction from Solscan (public, no key needed for basic data)
tx_sig = "5VazcsgRgCKQ2FbZURGhs2yTwAbKTLGjQazHoS16hcHLeigHfZ5bmPTx9T88KEpSjqjbnTijtTd32D82cf6WoBxE"

# Call Solscan public API
url = f"https://public-api.solscan.io/transaction/{tx_sig}"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    print("=== SOLSCAN TRANSACTION DATA ===")
    print(json.dumps(data, indent=2))

    # Save to file
    with open("solscan_transaction_sample.json", "w") as f:
        json.dumps(data, f, indent=2)
else:
    print(f"Error: {response.status_code}")
    print(response.text)
