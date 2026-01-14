'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  Wallet,
  RefreshCw,
  Loader2,
  BarChart3,
  ExternalLink,
  Copy,
  Check,
} from 'lucide-react';
import { api, type Portfolio, type WalletBalances } from '@/lib/api';
import { cn } from '@/lib/utils';
import TokenHoldingsList from '@/components/TokenHoldingsList';
import PortfolioSummary from '@/components/PortfolioSummary';
import TokenPnLCard from '@/components/TokenPnLCard';
import PnLSummaryCard from '@/components/PnLSummaryCard';
import TokenPnLTable from '@/components/TokenPnLTable';

export default function ViewWallet() {
  const params = useParams();
  const address = params.address as string;

  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [balances, setBalances] = useState<WalletBalances | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const shortenAddress = (addr: string) => `${addr.slice(0, 6)}...${addr.slice(-4)}`;

  const copyAddress = async () => {
    await navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Fetch data for this wallet (read-only, no auth required)
  const fetchData = useCallback(async () => {
    if (!address) return;

    setLoading(true);
    setError(null);

    try {
      // Fetch balances directly from chain (doesn't require the wallet to be tracked)
      const balanceData = await api.getWalletBalances(address);
      setBalances(balanceData);

      // Try to get portfolio data if available (may fail if not tracked)
      try {
        const portfolioData = await api.getWalletPortfolio(address);
        setPortfolio(portfolioData);
      } catch {
        // Portfolio not available (wallet not tracked) - that's OK
        setPortfolio(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load wallet data');
    } finally {
      setLoading(false);
    }
  }, [address]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="p-2 hover:bg-gray-800 rounded-lg transition-colors">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-sol-purple to-sol-green rounded-xl">
                  <Wallet className="w-6 h-6 text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold font-mono">{shortenAddress(address)}</h1>
                    <button
                      onClick={copyAddress}
                      className="p-1 hover:bg-gray-700 rounded transition-colors"
                      title="Copy address"
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4 text-gray-400" />
                      )}
                    </button>
                    <a
                      href={`https://solscan.io/account/${address}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 hover:bg-gray-700 rounded transition-colors"
                      title="View on Solscan"
                    >
                      <ExternalLink className="w-4 h-4 text-gray-400" />
                    </a>
                  </div>
                  <p className="text-xs text-gray-400">Read-only view</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={fetchData}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
                Refresh
              </button>
              <Link
                href="/"
                className="flex items-center gap-2 px-4 py-2 bg-sol-purple hover:bg-sol-purple/80 rounded-lg font-medium transition-colors"
              >
                <BarChart3 className="w-4 h-4" />
                Track This Wallet
              </Link>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-sol-purple" />
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
            {error}
          </div>
        )}

        {/* Wallet Content */}
        {!loading && !error && balances && (
          <div className="space-y-6">
            {/* Wallet Value Card */}
            <div className="bg-gradient-to-br from-sol-purple/20 to-sol-green/20 border border-sol-purple/30 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-200">Wallet Value</h3>
                <span className="text-sm text-gray-400">Verified tokens only</span>
              </div>
              <p className="text-3xl font-bold text-white mb-2">
                ${balances.total_portfolio_value_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              {balances.total_token_value_usd !== balances.verified_token_value_usd && (
                <p className="text-sm text-gray-400 mb-4">
                  (${(balances.total_token_value_usd + balances.sol_value_usd).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} including unverified)
                </p>
              )}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="bg-gray-900/50 rounded-lg p-3">
                  <p className="text-gray-400">SOL Balance</p>
                  <p className="text-lg font-semibold">
                    {balances.sol_balance.toFixed(4)} SOL
                  </p>
                  <p className="text-xs text-gray-500">
                    ${balances.sol_value_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="bg-gray-900/50 rounded-lg p-3">
                  <p className="text-gray-400">Token Holdings</p>
                  <p className="text-lg font-semibold">
                    {balances.tokens.length} tokens
                  </p>
                  <p className="text-xs text-gray-500">
                    {balances.tokens.filter(t => t.is_verified).length} verified
                  </p>
                </div>
              </div>
            </div>

            {/* Token Holdings List */}
            {balances.tokens.length > 0 && (
              <TokenHoldingsList
                tokens={balances.tokens}
                walletAddress={address}
              />
            )}

            {/* P/L Data (if wallet is tracked) */}
            {portfolio && balances && (
              <>
                {/* Jupiter-style P/L Summary Card */}
                <PnLSummaryCard
                  walletValue={balances.total_portfolio_value_usd}
                  totalPnL={portfolio.total_unrealized_pnl_usd + portfolio.total_realized_pnl_usd}
                  totalPnLPercentage={
                    ((portfolio.total_unrealized_pnl_usd + portfolio.total_realized_pnl_usd) /
                      (balances.total_portfolio_value_usd - (portfolio.total_unrealized_pnl_usd + portfolio.total_realized_pnl_usd))) *
                    100
                  }
                  unrealizedPnL={portfolio.total_unrealized_pnl_usd}
                  unrealizedPnLPercentage={
                    (portfolio.total_unrealized_pnl_usd / (balances.total_portfolio_value_usd - portfolio.total_unrealized_pnl_usd)) * 100
                  }
                  realizedPnL={portfolio.total_realized_pnl_usd}
                  realizedPnLPercentage={
                    (portfolio.total_realized_pnl_usd / (balances.total_portfolio_value_usd - portfolio.total_realized_pnl_usd)) * 100
                  }
                  solBalance={balances.sol_balance}
                  solValue={balances.sol_value_usd}
                />

                {/* Jupiter-style Token P/L Table with Tabs */}
                {portfolio.tokens.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4">Position PnL</h3>
                    <TokenPnLTable tokens={portfolio.tokens} walletAddress={address} />
                  </div>
                )}
              </>
            )}

            {/* No P/L data message */}
            {!portfolio && (
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 text-center">
                <p className="text-gray-400 mb-2">P/L tracking not available for this wallet</p>
                <p className="text-sm text-gray-500">
                  This wallet hasn&apos;t been tracked yet. Track it to see full P/L breakdown.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
