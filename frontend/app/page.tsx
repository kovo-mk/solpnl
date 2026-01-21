'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  Plus,
  Wallet,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Loader2,
  BarChart3,
  LineChart,
  Share2,
  Copy,
  Check,
  Settings,
  Trash2,
  X,
  Edit3,
  Sun,
  Moon,
  Info,
  Search,
  ArrowUpDown,
  History,
} from 'lucide-react';
import { api, type Portfolio, type Wallet as WalletType, type SyncStatus, type WalletBalances } from '@/lib/api';
import { formatUSD, formatPnL, cn, shortenAddress, timeAgo } from '@/lib/utils';
import AddWalletModal from '@/components/AddWalletModal';
import TokenPnLCard from '@/components/TokenPnLCard';
import PortfolioSummary from '@/components/PortfolioSummary';
import TokenHoldingsList from '@/components/TokenHoldingsList';
import WalletConnectButton from '@/components/WalletConnectButton';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';

export default function Home() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [wallets, setWallets] = useState<WalletType[]>([]);
  const [selectedWallet, setSelectedWallet] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [balances, setBalances] = useState<WalletBalances | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<Record<string, boolean>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [walletValueAdjustment, setWalletValueAdjustment] = useState(0);
  const [verifiedCountAdjustment, setVerifiedCountAdjustment] = useState(0);
  const [shareMenuOpen, setShareMenuOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showWalletManager, setShowWalletManager] = useState(false);
  const [editingWallet, setEditingWallet] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState('');
  const [deletingWallet, setDeletingWallet] = useState<string | null>(null);
  const [pnlSearchTerm, setPnlSearchTerm] = useState('');
  const [pnlSortBy, setPnlSortBy] = useState<'name' | 'date' | 'pnl' | 'holdings' | 'value'>('pnl');

  // Handle optimistic wallet value updates from token verification changes
  const handleTokenVerificationChange = useCallback((mint: string, isVerified: boolean, valueUsd: number | null) => {
    if (valueUsd === null) return;

    // Update the displayed wallet value instantly without refetching
    setWalletValueAdjustment(prev => isVerified ? prev + valueUsd : prev - valueUsd);
    setVerifiedCountAdjustment(prev => isVerified ? prev + 1 : prev - 1);
  }, []);

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
      // Reset adjustments when we fetch fresh data
      setWalletValueAdjustment(0);
      setVerifiedCountAdjustment(0);
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

  // Initial load and refetch when auth changes
  useEffect(() => {
    if (!authLoading) {
      // Clear current selection when auth changes
      setSelectedWallet(null);
      setWallets([]);
      fetchWallets();
    }
  }, [isAuthenticated, authLoading]);

  // Fetch portfolio when wallet changes
  useEffect(() => {
    fetchPortfolio();
  }, [selectedWallet, fetchPortfolio]);

  // Calculate total P/L
  const totalPnL = portfolio
    ? portfolio.total_unrealized_pnl_usd + portfolio.total_realized_pnl_usd
    : 0;
  const isProfit = totalPnL >= 0;

  // Copy share link to clipboard
  const copyShareLink = async () => {
    if (!selectedWallet) return;
    const shareUrl = `${window.location.origin}/view/${selectedWallet}`;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Delete wallet handler
  const handleDeleteWallet = async (address: string) => {
    try {
      await api.deleteWallet(address);
      setDeletingWallet(null);
      // If we deleted the selected wallet, clear selection
      if (selectedWallet === address) {
        setSelectedWallet(null);
      }
      fetchWallets();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Update wallet label handler
  const handleUpdateWalletLabel = async (address: string) => {
    try {
      await api.updateWallet(address, { label: editLabel || undefined });
      setEditingWallet(null);
      setEditLabel('');
      fetchWallets();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Start editing a wallet label
  const startEditing = (wallet: WalletType) => {
    setEditingWallet(wallet.address);
    setEditLabel(wallet.label || '');
  };

  return (
    <div className="min-h-screen bg-white dark:bg-gradient-to-b dark:from-gray-900 dark:to-black pb-20 md:pb-0 transition-colors">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/95 backdrop-blur-sm sticky top-0 z-40 transition-colors">
        <div className="max-w-7xl mx-auto px-3 py-2.5 md:px-4 md:py-3">
          <div className="flex items-center justify-between">
            {/* Left: Logo + Desktop Nav */}
            <div className="flex items-center gap-6">
              {/* Logo */}
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-gradient-to-br from-sol-purple to-sol-green rounded-lg">
                  <BarChart3 className="w-5 h-5 text-white" />
                </div>
                <span className="text-lg font-bold text-gray-900 dark:text-white">SolPnL</span>
              </div>

              {/* Desktop Nav Tabs */}
              <nav className="hidden md:flex items-center gap-2 ml-8">
                <Link
                  href="/"
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                >
                  <Wallet className="w-4 h-4" />
                  Portfolio
                </Link>
                <Link
                  href="/research"
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all"
                >
                  <Search className="w-4 h-4" />
                  Research
                </Link>
                <Link
                  href="/pnl"
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all"
                >
                  <LineChart className="w-4 h-4" />
                  P&L
                </Link>
                <Link
                  href="/transactions"
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all"
                >
                  <History className="w-4 h-4" />
                  Transactions
                </Link>
              </nav>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              {/* Theme Toggle */}
              <button
                type="button"
                onClick={toggleTheme}
                className="p-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {theme === 'dark' ? (
                  <Sun className="w-4 h-4 text-yellow-500" />
                ) : (
                  <Moon className="w-4 h-4 text-gray-700" />
                )}
              </button>

              {/* Desktop: Add wallet + Settings + Connect */}
              <div className="hidden md:flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 dark:bg-gray-800 hover:bg-blue-700 dark:hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors text-white dark:text-white"
                >
                  <Plus className="w-4 h-4" />
                  Add Wallet
                </button>
                <button
                  type="button"
                  onClick={() => setShowWalletManager(true)}
                  className="p-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  title="Manage Wallets"
                >
                  <Settings className="w-4 h-4 text-gray-700 dark:text-gray-400" />
                </button>
                <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />
                <WalletConnectButton />
              </div>

              {/* Mobile: Just wallet connect */}
              <div className="md:hidden">
                <WalletConnectButton />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-900/98 backdrop-blur-md border-t border-gray-200 dark:border-gray-800 z-50 safe-area-pb transition-colors shadow-lg">
        <div className="flex items-center justify-around py-3 px-4">
          <Link
            href="/"
            className="flex flex-col items-center gap-1 px-4 py-2 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg"
          >
            <Wallet className="w-5 h-5" />
            <span className="text-xs font-medium">Portfolio</span>
          </Link>
          <Link
            href="/research"
            className="flex flex-col items-center gap-1 px-3 py-2 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-all"
          >
            <Search className="w-5 h-5" />
            <span className="text-xs font-medium">Research</span>
          </Link>
          <Link
            href="/pnl"
            className="flex flex-col items-center gap-1 px-3 py-2 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-all"
          >
            <LineChart className="w-5 h-5" />
            <span className="text-xs font-medium">P&L</span>
          </Link>
          <Link
            href="/transactions"
            className="flex flex-col items-center gap-1 px-2 py-2 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-all"
          >
            <History className="w-5 h-5" />
            <span className="text-xs font-medium">Txns</span>
          </Link>
          <button
            type="button"
            onClick={() => setShowWalletManager(true)}
            className="flex flex-col items-center gap-0.5 px-2 py-1.5 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-white"
          >
            <Settings className="w-5 h-5" />
            <span className="text-[10px] font-medium">Manage</span>
          </button>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-3 py-4 md:px-4 md:py-6">
        {/* Wallet Selector - More compact on mobile */}
        {wallets.length > 0 && (
          <div className="flex gap-2 mb-4 md:mb-6 overflow-x-auto pb-2 items-center -mx-3 px-3 md:mx-0 md:px-0">
            {wallets.map((wallet) => (
              <button
                type="button"
                key={wallet.address}
                onClick={() => setSelectedWallet(wallet.address)}
                className={cn(
                  'flex items-center gap-1.5 md:gap-2 px-3 md:px-4 py-1.5 md:py-2 rounded-lg whitespace-nowrap transition-colors text-sm md:text-base',
                  selectedWallet === wallet.address
                    ? 'bg-blue-600 dark:bg-sol-purple text-white'
                    : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
                )}
                title={wallet.address}
              >
                <Wallet className="w-3.5 h-3.5 md:w-4 md:h-4" />
                <span>
                  {wallet.label ? (
                    <>
                      <span className="hidden sm:inline">{wallet.label}</span>
                      <span className="sm:hidden">{wallet.label.slice(0, 8)}{wallet.label.length > 8 ? '...' : ''}</span>
                      <span className="text-[10px] md:text-xs opacity-60 ml-1">({shortenAddress(wallet.address)})</span>
                    </>
                  ) : (
                    shortenAddress(wallet.address)
                  )}
                </span>
              </button>
            ))}
            {/* Wallet Manager Button - Desktop only (mobile uses bottom nav) */}
            <button
              type="button"
              onClick={() => setShowWalletManager(true)}
              className="hidden md:flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800/50 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors ml-2"
              title="Manage Wallets"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Empty State */}
        {wallets.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="p-6 bg-blue-50 dark:bg-gray-800/50 rounded-full mb-6">
              <Wallet className="w-16 h-16 text-blue-400 dark:text-gray-600" />
            </div>
            <h2 className="text-2xl font-bold mb-2 text-gray-900 dark:text-white">No wallets tracked</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-6 text-center max-w-md">
              Add any Solana wallet to start tracking P/L across all tokens.
              {!isAuthenticated && (
                <span className="block mt-2 text-sm">
                  Optionally connect your wallet to save your tracked wallets to your account.
                </span>
              )}
            </p>
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 dark:bg-sol-purple hover:bg-blue-700 dark:hover:bg-sol-purple/80 rounded-lg font-medium transition-colors text-white"
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
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-xl text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Portfolio Content */}
        {portfolio && !loading && (
          <div className="space-y-4 md:space-y-6">
            {/* Actual Wallet Value - Compact on mobile */}
            {balances && (
              <div className="bg-gradient-to-br from-blue-50 to-blue-100/50 dark:from-sol-purple/20 dark:to-sol-green/20 border border-blue-200 dark:border-sol-purple/30 rounded-xl md:rounded-2xl p-4 md:p-6">
                {/* Header row */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm text-gray-600 dark:text-gray-400 font-medium">Current Wallet Value</p>
                      <div className="group relative">
                        <Info className="w-4 h-4 text-gray-400 dark:text-gray-500 cursor-help" />
                        <div className="absolute left-0 top-6 bg-gray-900 dark:bg-gray-800 text-white text-xs rounded-lg p-3 w-64 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-10 shadow-lg">
                          Actual on-chain balance of all verified tokens + SOL in this wallet right now
                        </div>
                      </div>
                    </div>
                    <p className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white">
                      ${(balances.total_portfolio_value_usd + walletValueAdjustment).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                    {balances.total_token_value_usd !== balances.verified_token_value_usd && (
                      <p className="text-xs md:text-sm text-gray-600 dark:text-gray-400">
                        (${(balances.total_token_value_usd + balances.sol_value_usd).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} incl. unverified)
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={copyShareLink}
                    className="flex items-center gap-1 px-2 py-1 bg-white/70 dark:bg-gray-800/50 hover:bg-white dark:hover:bg-gray-700 rounded-lg text-xs text-gray-700 dark:text-gray-300 transition-colors border border-gray-200 dark:border-transparent"
                    title="Copy share link"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3 h-3 text-green-600 dark:text-green-400" />
                        <span className="hidden sm:inline">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Share2 className="w-3 h-3" />
                        <span className="hidden sm:inline">Share</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Stats row - Horizontal on mobile */}
                <div className="flex gap-3 md:grid md:grid-cols-2 md:gap-4 overflow-x-auto -mx-1 px-1 md:mx-0 md:px-0">
                  <div className="bg-white dark:bg-gray-900/50 rounded-lg p-2.5 md:p-3 flex-shrink-0 min-w-[120px] md:min-w-0 border border-gray-200 dark:border-transparent">
                    <p className="text-[10px] md:text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">SOL</p>
                    <p className="text-base md:text-lg font-semibold text-gray-900 dark:text-white">
                      {balances.sol_balance.toFixed(4)}
                    </p>
                    <p className="text-[10px] md:text-xs text-gray-500">
                      ${balances.sol_value_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                  </div>
                  <div className="bg-white dark:bg-gray-900/50 rounded-lg p-2.5 md:p-3 flex-shrink-0 min-w-[120px] md:min-w-0 border border-gray-200 dark:border-transparent">
                    <p className="text-[10px] md:text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Tokens</p>
                    <p className="text-base md:text-lg font-semibold text-gray-900 dark:text-white">
                      {balances.tokens.length}
                    </p>
                    <p className="text-[10px] md:text-xs text-gray-500">
                      {balances.tokens.filter(t => t.is_verified).length + verifiedCountAdjustment} verified
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
                onTokenVerificationChange={handleTokenVerificationChange}
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
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-gray-900 dark:text-white">
                  <span>Token P/L Breakdown</span>
                  <span className="text-sm font-normal text-gray-600 dark:text-gray-400">
                    ({portfolio.tokens.filter(t =>
                      t.token_symbol?.toLowerCase().includes(pnlSearchTerm.toLowerCase()) ||
                      t.token_name?.toLowerCase().includes(pnlSearchTerm.toLowerCase())
                    ).length} tokens)
                  </span>
                </h3>

                {/* Search and Sort Controls */}
                {portfolio.tokens.length > 0 && (
                  <div className="flex gap-2 flex-1 sm:flex-initial sm:max-w-md">
                    {/* Search */}
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search tokens..."
                        value={pnlSearchTerm}
                        onChange={(e) => setPnlSearchTerm(e.target.value)}
                        className="w-full pl-9 pr-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500 dark:focus:border-sol-purple transition-colors text-gray-900 dark:text-white placeholder:text-gray-400"
                      />
                    </div>

                    {/* Sort */}
                    <div className="relative">
                      <select
                        value={pnlSortBy}
                        onChange={(e) => setPnlSortBy(e.target.value as any)}
                        title="Sort tokens"
                        className="appearance-none pl-3 pr-8 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500 dark:focus:border-sol-purple transition-colors text-gray-900 dark:text-white cursor-pointer"
                      >
                        <option value="pnl">Sort by P/L</option>
                        <option value="name">Sort by Name</option>
                        <option value="date">Sort by Date</option>
                        <option value="holdings">Sort by Holdings</option>
                        <option value="value">Sort by Value</option>
                      </select>
                      <ArrowUpDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                    </div>
                  </div>
                )}
              </div>

              {portfolio.tokens.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p>No token trades found yet.</p>
                  <p className="text-sm mt-1">
                    Sync your wallet to fetch transaction history.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {portfolio.tokens
                    .filter(token =>
                      token.token_symbol?.toLowerCase().includes(pnlSearchTerm.toLowerCase()) ||
                      token.token_name?.toLowerCase().includes(pnlSearchTerm.toLowerCase())
                    )
                    .sort((a, b) => {
                      switch (pnlSortBy) {
                        case 'name':
                          return (a.token_symbol || '').localeCompare(b.token_symbol || '');
                        case 'date':
                          return new Date(b.last_trade || 0).getTime() - new Date(a.last_trade || 0).getTime();
                        case 'pnl':
                          const aPnl = (a.unrealized_pnl_usd || 0) + a.realized_pnl_usd;
                          const bPnl = (b.unrealized_pnl_usd || 0) + b.realized_pnl_usd;
                          return bPnl - aPnl;
                        case 'holdings':
                          return b.current_balance - a.current_balance;
                        case 'value':
                          return (b.current_value_usd || 0) - (a.current_value_usd || 0);
                        default:
                          return 0;
                      }
                    })
                    .map((token) => (
                      <TokenPnLCard key={token.token_address} token={token} onTokenChange={fetchPortfolio} />
                    ))
                  }
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

      {/* Wallet Manager Modal */}
      {showWalletManager && (
        <div className="fixed inset-0 bg-black/30 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col shadow-xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Manage Wallets</h2>
              <button
                type="button"
                onClick={() => {
                  setShowWalletManager(false);
                  setEditingWallet(null);
                  setDeletingWallet(null);
                }}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="Close"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            {/* Wallet List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {wallets.length === 0 ? (
                <p className="text-gray-600 dark:text-gray-400 text-center py-8">No wallets tracked yet</p>
              ) : (
                wallets.map((wallet) => (
                  <div
                    key={wallet.address}
                    className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4 space-y-3 border border-gray-200 dark:border-transparent"
                  >
                    {/* Wallet Info */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-100 dark:bg-gray-700 rounded-lg">
                          <Wallet className="w-4 h-4 text-blue-600 dark:text-gray-400" />
                        </div>
                        <div>
                          {editingWallet === wallet.address ? (
                            <input
                              type="text"
                              value={editLabel}
                              onChange={(e) => setEditLabel(e.target.value)}
                              placeholder="Enter label..."
                              className="bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500 dark:focus:border-sol-purple text-gray-900 dark:text-white"
                              autoFocus
                            />
                          ) : (
                            <>
                              <p className="font-medium text-gray-900 dark:text-white">
                                {wallet.label || 'Unnamed Wallet'}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                                {shortenAddress(wallet.address)}
                              </p>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2">
                        {editingWallet === wallet.address ? (
                          <>
                            <button
                              type="button"
                              onClick={() => handleUpdateWalletLabel(wallet.address)}
                              className="px-3 py-1 bg-blue-600 dark:bg-sol-purple hover:bg-blue-700 dark:hover:bg-sol-purple/80 rounded-lg text-sm transition-colors text-white"
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingWallet(null);
                                setEditLabel('');
                              }}
                              className="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg text-sm transition-colors text-gray-700 dark:text-gray-300"
                            >
                              Cancel
                            </button>
                          </>
                        ) : deletingWallet === wallet.address ? (
                          <>
                            <span className="text-sm text-red-600 dark:text-red-400 mr-2">Delete?</span>
                            <button
                              type="button"
                              onClick={() => handleDeleteWallet(wallet.address)}
                              className="px-3 py-1 bg-red-500 hover:bg-red-600 rounded-lg text-sm transition-colors text-white"
                            >
                              Yes
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeletingWallet(null)}
                              className="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg text-sm transition-colors text-gray-700 dark:text-gray-300"
                            >
                              No
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => startEditing(wallet)}
                              className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                              title="Edit label"
                            >
                              <Edit3 className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeletingWallet(wallet.address)}
                              className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                              title="Delete wallet"
                            >
                              <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Full Address (copyable) */}
                    <div className="flex items-center gap-2 bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-transparent rounded-lg px-3 py-2">
                      <code className="text-xs text-gray-600 dark:text-gray-400 flex-1 truncate">
                        {wallet.address}
                      </code>
                      <button
                        type="button"
                        onClick={async () => {
                          await navigator.clipboard.writeText(wallet.address);
                        }}
                        className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                        title="Copy address"
                      >
                        <Copy className="w-3 h-3 text-gray-500" />
                      </button>
                    </div>

                    {/* Last Synced */}
                    {wallet.last_synced && (
                      <p className="text-xs text-gray-500">
                        Last synced: {timeAgo(wallet.last_synced)}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-700">
              <button
                type="button"
                onClick={() => {
                  setShowWalletManager(false);
                  setShowAddModal(true);
                }}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 dark:bg-gray-800 hover:bg-blue-700 dark:hover:bg-gray-700 rounded-lg font-medium transition-colors text-white dark:text-white"
              >
                <Plus className="w-4 h-4" />
                Add New Wallet
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
