'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

// Disable static generation for this page since it uses searchParams
export const dynamic = 'force-dynamic';

interface Transaction {
  signature: string;
  block_time: string | null;
  tx_type: string;
  category: string | null;
  helius_type: string | null;
  amount_token: number;
  amount_sol: number;
  price_per_token: number | null;
  price_usd: number | null;
  realized_pnl_sol: number | null;
  realized_pnl_usd: number | null;
  transfer_destination: string | null;
  dex_name: string | null;
}

interface HoldingSummary {
  current_balance: number;
  avg_buy_price: number;
  total_cost_sol: number;
  total_bought: number;
  total_sold: number;
  total_buy_sol: number;
  total_sell_sol: number;
  realized_pnl_sol: number;
  realized_pnl_usd: number;
  first_trade: string | null;
  last_trade: string | null;
}

interface DebugData {
  token: {
    address: string;
    symbol: string;
    name: string;
    current_price_usd: number | null;
  };
  holding_summary: HoldingSummary;
  transactions: Transaction[];
  transaction_count: number;
}

export default function USDCDebugPage() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<DebugData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Get wallet from URL params or use default
  const walletAddress = searchParams.get('wallet') || '';

  useEffect(() => {
    if (!walletAddress) {
      setError('No wallet address provided. Add ?wallet=YOUR_ADDRESS to URL');
      setLoading(false);
      return;
    }

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

    fetch(`${API_BASE}/wallets/${walletAddress}/debug/token/USDC`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        return res.json();
      })
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [walletAddress]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
            Loading USDC Debug Data...
          </h1>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-bold mb-4 text-red-600">Error</h1>
          <p className="text-gray-700 dark:text-gray-300">{error}</p>
          <p className="text-sm text-gray-500 mt-4">
            Usage: /debug/usdc?wallet=YOUR_WALLET_ADDRESS
          </p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-gray-900 dark:text-white">
          USDC Transaction Debug
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Analyzing why USDC shows P/L when it's a stablecoin
        </p>

        {/* Token Info */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 mb-6 border border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
            Token Info
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Symbol</p>
              <p className="font-mono text-gray-900 dark:text-white">{data.token.symbol}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Name</p>
              <p className="font-mono text-gray-900 dark:text-white">{data.token.name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Current Price</p>
              <p className="font-mono text-gray-900 dark:text-white">
                ${data.token.current_price_usd?.toFixed(4) || 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Address</p>
              <p className="font-mono text-xs text-gray-900 dark:text-white break-all">
                {data.token.address}
              </p>
            </div>
          </div>
        </div>

        {/* Holding Summary */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 mb-6 border border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
            Holding Summary
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-500">Current Balance</p>
              <p className="font-mono text-lg font-semibold text-gray-900 dark:text-white">
                {data.holding_summary.current_balance.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Avg Buy Price (SOL)</p>
              <p className="font-mono text-lg font-semibold text-gray-900 dark:text-white">
                {data.holding_summary.avg_buy_price.toFixed(6)}
              </p>
              {data.holding_summary.avg_buy_price === 0 && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                  ⚠️ Zero cost basis = 100% profit!
                </p>
              )}
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Cost (SOL)</p>
              <p className="font-mono text-lg font-semibold text-gray-900 dark:text-white">
                {data.holding_summary.total_cost_sol.toFixed(4)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Bought</p>
              <p className="font-mono text-gray-900 dark:text-white">
                {data.holding_summary.total_bought.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Sold</p>
              <p className="font-mono text-gray-900 dark:text-white">
                {data.holding_summary.total_sold.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Realized P/L (USD)</p>
              <p className={`font-mono font-semibold ${
                data.holding_summary.realized_pnl_usd >= 0
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-red-600 dark:text-red-400'
              }`}>
                ${data.holding_summary.realized_pnl_usd.toFixed(2)}
              </p>
            </div>
          </div>
        </div>

        {/* Transaction List */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
            All Transactions ({data.transaction_count})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left p-2 text-gray-600 dark:text-gray-400">Time</th>
                  <th className="text-left p-2 text-gray-600 dark:text-gray-400">Type</th>
                  <th className="text-left p-2 text-gray-600 dark:text-gray-400">Category</th>
                  <th className="text-right p-2 text-gray-600 dark:text-gray-400">Amount</th>
                  <th className="text-right p-2 text-gray-600 dark:text-gray-400">SOL</th>
                  <th className="text-right p-2 text-gray-600 dark:text-gray-400">Price/Token</th>
                  <th className="text-left p-2 text-gray-600 dark:text-gray-400">DEX</th>
                  <th className="text-left p-2 text-gray-600 dark:text-gray-400">Signature</th>
                </tr>
              </thead>
              <tbody>
                {data.transactions.map((tx, idx) => (
                  <tr key={idx} className="border-b border-gray-100 dark:border-gray-700/50">
                    <td className="p-2 text-gray-700 dark:text-gray-300">
                      {tx.block_time ? new Date(tx.block_time).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="p-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        tx.tx_type === 'buy' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        tx.tx_type === 'sell' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        tx.tx_type?.includes('transfer') ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                        'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                      }`}>
                        {tx.tx_type}
                      </span>
                    </td>
                    <td className="p-2 text-gray-700 dark:text-gray-300">
                      {tx.category || '-'}
                    </td>
                    <td className="p-2 text-right font-mono text-gray-900 dark:text-white">
                      {tx.amount_token.toFixed(2)}
                    </td>
                    <td className="p-2 text-right font-mono text-gray-700 dark:text-gray-300">
                      {tx.amount_sol.toFixed(4)}
                    </td>
                    <td className="p-2 text-right font-mono text-gray-700 dark:text-gray-300">
                      {tx.price_per_token ? tx.price_per_token.toFixed(6) : '0.000000'}
                      {tx.price_per_token === 0 && (
                        <span className="text-xs text-red-600 dark:text-red-400 ml-1">
                          ⚠️
                        </span>
                      )}
                    </td>
                    <td className="p-2 text-gray-700 dark:text-gray-300">
                      {tx.dex_name || '-'}
                    </td>
                    <td className="p-2 text-xs font-mono text-gray-500">
                      {tx.signature.slice(0, 8)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Analysis */}
        <div className="mt-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
          <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-2">
            Analysis
          </h3>
          <div className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
            {data.holding_summary.avg_buy_price === 0 ? (
              <>
                <p>
                  ⚠️ <strong>Issue found:</strong> USDC has a $0 cost basis (avg_buy_price = 0.0000 SOL)
                </p>
                <p>
                  This means the system thinks all USDC was received for free, showing as 100% profit.
                </p>
                <p>
                  <strong>Likely causes:</strong>
                </p>
                <ul className="list-disc ml-6 space-y-1">
                  <li>USDC received via transfer_in (from another wallet) - gets $0 cost basis</li>
                  <li>USDC received as airdrop - gets $0 cost basis</li>
                  <li>Transaction parser didn't capture the buy properly</li>
                </ul>
                <p className="mt-4">
                  <strong>Look at the transactions above</strong> to see how you acquired the USDC:
                </p>
                <ul className="list-disc ml-6">
                  <li>If you see <code>transfer_in</code> - you transferred USDC from another wallet</li>
                  <li>If you see <code>buy</code> with price_per_token = 0 - parser missed the price</li>
                  <li>If you see <code>sell</code> of other tokens - you sold something FOR USDC (this is correct)</li>
                </ul>
              </>
            ) : (
              <p>✓ USDC has a valid cost basis of {data.holding_summary.avg_buy_price.toFixed(6)} SOL</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
