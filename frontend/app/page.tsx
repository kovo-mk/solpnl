'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Wallet,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Loader2,
  BarChart3,
} from 'lucide-react';
import { api, type Portfolio, type Wallet as WalletType, type SyncStatus, type WalletBalances } from '@/lib/api';
import { formatUSD, formatPnL, cn, shortenAddress, timeAgo } from '@/lib/utils';
import AddWalletModal from '@/components/AddWalletModal';
import TokenPnLCard from '@/components/TokenPnLCard';
import PortfolioSummary from '@/components/PortfolioSummary';
import TokenHoldingsList from '@/components/TokenHoldingsList';

export default function Home() {
  const [wallets, setWallets] = useState<WalletType[]>([]);
  const [selectedWallet, setSelectedWallet] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [balances, setBalances] = useState<WalletBalances | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<Record<string, boolean>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch wallets
  const fetchWallets = useCallback(async () => {
    try {
      const data = await api.getWallets();
      setWallets(data);
      if (data.length > 0 && !selectedWallet) {
        setSelectedWallet(data[0].address);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }, [selectedWallet]);

  // Fetch portfolio and balances for selected wallet
  const fetchPortfolio = useCallback(async () => {
    if (!selectedWallet) {
      setPortfolio(null);
      setBalances(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      // Fetch both portfolio (P/L data) and actual on-chain balances in parallel
      const [portfolioData, balanceData] = await Promise.all([
        api.getWalletPortfolio(selectedWallet),
        api.getWalletBalances(selectedWallet)
      ]);
      setPortfolio(portfolioData);
      setBalances(balanceData);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      setPortfolio(null);
      setBalances(null);
    } finally {
      setLoading(false);
    }
  }, [selectedWallet]);

  // Sync wallet
  const handleSync = async (address: string) => {
    setSyncing((prev) => ({ ...prev, [address]: true }));
    try {
      await api.syncWallet(address);

      // Poll for completion
      let attempts = 0;
      const pollStatus = async () => {
        const status = await api.getSyncStatus(address);
        if (status.status === 'completed' || status.status === 'error') {
          setSyncing((prev) => ({ ...prev, [address]: false }));
          fetchPortfolio();
        } else if (attempts < 60) {
          attempts++;
          setTimeout(pollStatus, 2000);
        } else {
          setSyncing((prev) => ({ ...prev, [address]: false }));
        }
      };
      pollStatus();
    } catch (err: any) {
      setError(err.message);
      setSyncing((prev) => ({ ...prev, [address]: false }));
    }
  };

  // Initial load
  useEffect(() => {
    fetchWallets();
  }, []);

  // Fetch portfolio when wallet changes
  useEffect(() => {
    fetchPortfolio();
  }, [selectedWallet, fetchPortfolio]);

  // Calculate total P/L
  const totalPnL = portfolio
    ? portfolio.total_unrealized_pnl_usd + portfolio.total_realized_pnl_usd
    : 0;
  const isProfit = totalPnL >= 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-sol-purple to-sol-green rounded-xl">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold">SolPnL</h1>
                <p className="text-xs text-gray-400">
                  Track your Solana P/L per token
                </p>
              </div>
            </div>

            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-sol-purple hover:bg-sol-purple/80 rounded-lg font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Wallet
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Wallet Selector */}
        {wallets.length > 0 && (
          <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
            {wallets.map((wallet) => (
              <button
                key={wallet.address}
                onClick={() => setSelectedWallet(wallet.address)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors',
                  selectedWallet === wallet.address
                    ? 'bg-sol-purple text-white'
                    : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                )}
              >
                <Wallet className="w-4 h-4" />
                {wallet.label || shortenAddress(wallet.address)}
              </button>
            ))}
          </div>
        )}

        {/* Empty State */}
        {wallets.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="p-6 bg-gray-800/50 rounded-full mb-6">
              <Wallet className="w-16 h-16 text-gray-600" />
            </div>
            <h2 className="text-2xl font-bold mb-2">No wallets tracked</h2>
            <p className="text-gray-400 mb-6 text-center max-w-md">
              Add your Solana wallet to start tracking your P/L across all tokens
              you&apos;ve traded.
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-6 py-3 bg-sol-purple hover:bg-sol-purple/80 rounded-lg font-medium transition-colors"
            >
              <Plus className="w-5 h-5" />
              Add Your First Wallet
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading && selectedWallet && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-sol-purple" />
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
            {error}
          </div>
        )}

        {/* Portfolio Content */}
        {portfolio && !loading && (
          <div className="space-y-6">
            {/* Actual Wallet Value (like Phantom) */}
            {balances && (
              <div className="bg-gradient-to-br from-sol-purple/20 to-sol-green/20 border border-sol-purple/30 rounded-2xl p-6 mb-4">
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
            )}

            {/* Token Holdings List with Search */}
            {balances && balances.tokens.length > 0 && (
              <TokenHoldingsList
                tokens={balances.tokens}
                walletAddress={portfolio.wallet_address}
                onTokenVerificationChange={fetchPortfolio}
              />
            )}

            {/* P/L Summary Card */}
            <PortfolioSummary
              portfolio={portfolio}
              onSync={() => handleSync(portfolio.wallet_address)}
              syncing={syncing[portfolio.wallet_address]}
            />

            {/* Token P/L Grid */}
            <div>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>Token P/L Breakdown</span>
                <span className="text-sm font-normal text-gray-400">
                  ({portfolio.tokens.length} tokens)
                </span>
              </h3>

              {portfolio.tokens.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p>No token trades found yet.</p>
                  <p className="text-sm mt-1">
                    Sync your wallet to fetch transaction history.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {portfolio.tokens.map((token) => (
                    <TokenPnLCard key={token.token_address} token={token} onTokenChange={fetchPortfolio} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Add Wallet Modal */}
      <AddWalletModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onWalletAdded={() => {
          fetchWallets();
          setShowAddModal(false);
        }}
      />
    </div>
  );
}
