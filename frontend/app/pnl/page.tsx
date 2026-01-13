'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import {
  RefreshCw,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Loader2,
  Search,
  Settings,
  Wallet as WalletIcon,
  LineChart,
  Plus,
  BarChart3,
  Sun,
  Moon,
} from 'lucide-react';
import { api, type Portfolio, type TokenPnL, type Wallet } from '@/lib/api';
import { cn } from '@/lib/utils';
import AddWalletModal from '@/components/AddWalletModal';
import { useTheme } from '@/contexts/ThemeContext';

type SortField = 'last_trade' | 'unrealized' | 'realized' | 'total_pnl' | 'balance' | 'bought' | 'sold' | 'position';
type SortDirection = 'asc' | 'desc';
type TabType = 'recently_traded' | 'live_positions' | 'most_profitable';
type TimePeriod = 'all' | '24h' | '7d' | '30d';

// Helper to shorten wallet addresses
const shortenAddress = (address: string) => `${address.slice(0, 4)}...${address.slice(-4)}`;

export default function PnLDashboard() {
  const { theme, toggleTheme } = useTheme();
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [selectedWallet, setSelectedWallet] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('recently_traded');
  const [sortField, setSortField] = useState<SortField>('last_trade');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [timePeriod, setTimePeriod] = useState<TimePeriod>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showWalletManager, setShowWalletManager] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingWallet, setEditingWallet] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState('');

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

  // Fetch portfolio
  const fetchPortfolio = useCallback(async () => {
    if (!selectedWallet) {
      setPortfolio(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const data = await api.getWalletPortfolio(selectedWallet);
      setPortfolio(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      setPortfolio(null);
    } finally {
      setLoading(false);
    }
  }, [selectedWallet]);

  // Sync wallet
  const handleSync = async () => {
    if (!selectedWallet) return;
    setSyncing(true);
    try {
      await api.syncWallet(selectedWallet);
      // Poll for completion
      let attempts = 0;
      const pollStatus = async () => {
        const status = await api.getSyncStatus(selectedWallet);
        if (status.status === 'completed' || status.status === 'error') {
          setSyncing(false);
          fetchPortfolio();
        } else if (attempts < 60) {
          attempts++;
          setTimeout(pollStatus, 2000);
        } else {
          setSyncing(false);
        }
      };
      pollStatus();
    } catch (err: any) {
      setError(err.message);
      setSyncing(false);
    }
  };

  // Update wallet label
  const handleUpdateWalletLabel = async (address: string, newLabel: string) => {
    try {
      await api.updateWallet(address, { label: newLabel || undefined });
      fetchWallets();
      setEditingWallet(null);
      setEditLabel('');
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchWallets();
  }, []);

  useEffect(() => {
    fetchPortfolio();
  }, [selectedWallet, fetchPortfolio]);

  // Filter tokens by time period
  const filteredByTime = useMemo(() => {
    if (!portfolio) return [];
    if (timePeriod === 'all') return portfolio.tokens;

    const now = new Date();
    const cutoff = new Date();

    switch (timePeriod) {
      case '24h':
        cutoff.setHours(now.getHours() - 24);
        break;
      case '7d':
        cutoff.setDate(now.getDate() - 7);
        break;
      case '30d':
        cutoff.setDate(now.getDate() - 30);
        break;
    }

    return portfolio.tokens.filter(t => {
      if (!t.last_trade) return false;
      return new Date(t.last_trade) >= cutoff;
    });
  }, [portfolio, timePeriod]);

  // Calculate stats based on filtered tokens
  const stats = portfolio ? calculateStats(portfolio, filteredByTime) : null;

  // Filter by search query
  const searchFiltered = useMemo(() => {
    if (!searchQuery.trim()) return filteredByTime;
    const query = searchQuery.toLowerCase();
    return filteredByTime.filter(t =>
      t.token_symbol.toLowerCase().includes(query) ||
      t.token_name.toLowerCase().includes(query) ||
      t.token_address.toLowerCase().includes(query)
    );
  }, [filteredByTime, searchQuery]);

  // Sort and filter tokens
  const sortedTokens = getSortedTokens(searchFiltered, activeTab, sortField, sortDirection);

  // Format helpers
  const formatUSD = (value: number | null, showSign = false) => {
    if (value === null) return '-';
    const sign = showSign && value > 0 ? '+' : '';
    return sign + '$' + Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatPercent = (value: number | null, showSign = false) => {
    if (value === null) return '';
    const sign = showSign && value > 0 ? '+' : '';
    return sign + value.toFixed(2) + '%';
  };

  const formatBalance = (balance: number) => {
    if (balance >= 1000000) return (balance / 1000000).toFixed(2) + 'M';
    if (balance >= 1000) return (balance / 1000).toFixed(2) + 'K';
    if (balance >= 1) return balance.toFixed(2);
    if (balance >= 0.0001) return balance.toFixed(4);
    return balance > 0 ? balance.toExponential(2) : '0.00';
  };

  const formatSOL = (value: number) => {
    if (value >= 1000) return (value / 1000).toFixed(2) + 'K';
    return value.toFixed(4);
  };

  const formatPrice = (price: number | null) => {
    if (price === null) return '-';
    if (price >= 1) return '$' + price.toFixed(2);
    if (price >= 0.01) return '$' + price.toFixed(4);
    if (price >= 0.0001) return '$' + price.toFixed(6);
    return '$' + price.toExponential(2);
  };

  const timeAgo = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    return `${diffDays}d`;
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-b dark:from-gray-900 dark:to-black pb-20 md:pb-0 transition-colors">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm sticky top-0 z-40 transition-colors">
        <div className="max-w-7xl mx-auto px-3 py-2.5 md:px-4 md:py-3">
          <div className="flex items-center justify-between">
            {/* Left: Logo + Desktop Nav */}
            <div className="flex items-center gap-6">
              {/* Logo */}
              <Link href="/" className="flex items-center gap-2">
                <div className="p-1.5 bg-gradient-to-br from-sol-purple to-sol-green rounded-lg">
                  <BarChart3 className="w-5 h-5 text-white" />
                </div>
                <span className="text-lg font-bold text-gray-900 dark:text-white">SolPnL</span>
              </Link>

              {/* Desktop Nav Tabs */}
              <nav className="hidden md:flex items-center gap-1">
                <Link
                  href="/"
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <WalletIcon className="w-4 h-4" />
                  Portfolio
                </Link>
                <Link
                  href="/pnl"
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800"
                >
                  <LineChart className="w-4 h-4" />
                  P&L
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
                  <Moon className="w-4 h-4 text-gray-600" />
                )}
              </button>

              {/* Wallet selector */}
              {wallets.length > 0 && (
                <select
                  value={selectedWallet || ''}
                  onChange={(e) => setSelectedWallet(e.target.value)}
                  className="px-2 md:px-3 py-1.5 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs md:text-sm max-w-[100px] sm:max-w-[140px] md:max-w-[180px] text-gray-900 dark:text-white"
                  title="Select wallet"
                  aria-label="Select wallet"
                >
                  {wallets.map((wallet) => (
                    <option key={wallet.address} value={wallet.address}>
                      {wallet.label ? `${wallet.label.slice(0, 12)}${wallet.label.length > 12 ? '...' : ''}` : shortenAddress(wallet.address)}
                    </option>
                  ))}
                </select>
              )}

              {/* Desktop: Settings + Sync */}
              <div className="hidden md:flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowWalletManager(true)}
                  className="p-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  title="Manage Wallets"
                >
                  <Settings className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                </button>
                <button
                  type="button"
                  onClick={handleSync}
                  disabled={syncing || !selectedWallet}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-sol-purple hover:bg-sol-purple/80 rounded-lg font-medium transition-colors disabled:opacity-50 text-sm text-white"
                >
                  <RefreshCw className={cn('w-4 h-4', syncing && 'animate-spin')} />
                  {syncing ? 'Syncing...' : 'Sync'}
                </button>
              </div>

              {/* Mobile: Just sync button */}
              <button
                type="button"
                onClick={handleSync}
                disabled={syncing || !selectedWallet}
                className="md:hidden p-2 bg-sol-purple hover:bg-sol-purple/80 rounded-lg transition-colors disabled:opacity-50"
                title="Sync wallet"
              >
                <RefreshCw className={cn('w-4 h-4 text-white', syncing && 'animate-spin')} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm border-t border-gray-200 dark:border-gray-800 z-50 transition-colors">
        <div className="flex items-center justify-around py-2 px-2">
          <Link
            href="/"
            className="flex flex-col items-center gap-0.5 px-3 py-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            <WalletIcon className="w-5 h-5" />
            <span className="text-[10px] font-medium">Portfolio</span>
          </Link>
          <Link
            href="/pnl"
            className="flex flex-col items-center gap-0.5 px-3 py-1.5 text-sol-purple"
          >
            <LineChart className="w-5 h-5" />
            <span className="text-[10px] font-medium">P&L</span>
          </Link>
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="flex flex-col items-center gap-0.5 px-3 py-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            <Plus className="w-5 h-5" />
            <span className="text-[10px] font-medium">Add</span>
          </button>
          <button
            type="button"
            onClick={() => setShowWalletManager(true)}
            className="flex flex-col items-center gap-0.5 px-3 py-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            <Settings className="w-5 h-5" />
            <span className="text-[10px] font-medium">Settings</span>
          </button>
        </div>
      </nav>

      {/* Wallet Manager Modal */}
      {showWalletManager && (
        <div className="fixed inset-0 bg-black/30 dark:bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl max-w-lg w-full max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">Manage Wallets</h2>
              <button
                type="button"
                onClick={() => {
                  setShowWalletManager(false);
                  setEditingWallet(null);
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400"
              >
                ✕
              </button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto max-h-[60vh]">
              {wallets.map((wallet) => (
                <div key={wallet.address} className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                  {editingWallet === wallet.address ? (
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={editLabel}
                        onChange={(e) => setEditLabel(e.target.value)}
                        placeholder="Wallet label (optional)"
                        className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleUpdateWalletLabel(wallet.address, editLabel)}
                          className="px-3 py-1 bg-sol-purple hover:bg-sol-purple/80 rounded text-sm text-white"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingWallet(null);
                            setEditLabel('');
                          }}
                          className="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded text-sm text-gray-700 dark:text-gray-300"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{wallet.label || 'Unnamed Wallet'}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">{shortenAddress(wallet.address)}</p>
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Full: {wallet.address}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingWallet(wallet.address);
                          setEditLabel(wallet.label || '');
                        }}
                        className="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded text-sm text-gray-700 dark:text-gray-300"
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-3 py-4 md:px-4 md:py-6">
        {/* Time Period Selector - Mobile optimized */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 md:mb-6">
          <div className="flex items-center gap-2">
            <span className="text-xs md:text-sm text-gray-500 dark:text-gray-400 hidden sm:inline">Time Period:</span>
            <div className="flex gap-0.5 md:gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 md:p-1 flex-1 sm:flex-initial">
              {(['all', '24h', '7d', '30d'] as TimePeriod[]).map((period) => (
                <button
                  key={period}
                  type="button"
                  onClick={() => setTimePeriod(period)}
                  className={cn(
                    'px-2 md:px-3 py-1.5 md:py-1 text-xs md:text-sm rounded-md transition-colors flex-1 sm:flex-initial',
                    timePeriod === period
                      ? 'bg-sol-purple text-white'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-gray-700'
                  )}
                >
                  {period === 'all' ? 'All' : period.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          {selectedWallet && (
            <p className="text-xs md:text-sm text-gray-500 hidden sm:block">
              Viewing: <span className="font-mono text-gray-600 dark:text-gray-400">{shortenAddress(selectedWallet)}</span>
            </p>
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-sol-purple" />
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-100 dark:bg-red-500/10 border border-red-300 dark:border-red-500/30 rounded-xl text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Dashboard Content */}
        {portfolio && stats && !loading && (
          <div className="space-y-4 md:space-y-6">
            {/* Mobile Summary - Horizontal scroll stats */}
            <div className="md:hidden bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-3 transition-colors">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-medium">Summary</h3>
                <span className="text-cyan-600 dark:text-cyan-400 text-sm font-bold">{stats.winRate.toFixed(0)}% Win</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-gray-500 text-[10px]">Holdings</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">{formatUSD(stats.totalHoldings)}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-[10px]">Unrealised</p>
                  <p className={cn(
                    'text-sm font-semibold',
                    stats.unrealizedPnL >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                  )}>
                    {formatUSD(stats.unrealizedPnL, true)}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500 text-[10px]">Total PnL</p>
                  <p className={cn(
                    'text-sm font-semibold',
                    stats.totalPnL >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                  )}>
                    {formatUSD(stats.totalPnL, true)}
                  </p>
                </div>
              </div>
              {/* Mini distribution bar */}
              <div className="mt-3 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex">
                {stats.distribution.map((tier, idx) => (
                  <div
                    key={idx}
                    className={cn(tier.barColor)}
                    style={{ width: `${tier.percent}%` }}
                  />
                ))}
              </div>
            </div>

            {/* Desktop Summary Cards Row */}
            <div className="hidden md:grid md:grid-cols-3 gap-4">
              {/* Summary Card */}
              <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-5 transition-colors">
                <h3 className="text-gray-500 dark:text-gray-400 text-sm font-medium mb-4">Summary</h3>

                <div className="space-y-3">
                  <div>
                    <p className="text-gray-500 text-xs">Holdings</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatUSD(stats.totalHoldings)}</p>
                  </div>

                  <div>
                    <p className="text-gray-500 text-xs">Unrealised PnL</p>
                    <p className={cn(
                      'text-lg font-semibold',
                      stats.unrealizedPnL >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    )}>
                      {formatUSD(stats.unrealizedPnL, true)}
                      <span className="text-sm ml-1">
                        {formatPercent(stats.unrealizedPnLPercent, true)}
                      </span>
                    </p>
                  </div>

                  <div>
                    <p className="text-gray-500 text-xs">Total PnL</p>
                    <p className={cn(
                      'text-lg font-semibold',
                      stats.totalPnL >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    )}>
                      {formatUSD(stats.totalPnL, true)}
                      <span className="text-sm ml-1">
                        {formatPercent(stats.totalPnLPercent, true)}
                      </span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Analysis Card */}
              <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-5 transition-colors">
                <h3 className="text-gray-500 dark:text-gray-400 text-sm font-medium mb-4">Analysis</h3>

                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Win Rate</span>
                    <span className="text-cyan-600 dark:text-cyan-400 text-xl font-bold">{stats.winRate.toFixed(2)}%</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Realised PnL</span>
                    <span className={cn(
                      'font-semibold',
                      stats.realizedPnL >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    )}>
                      {formatUSD(stats.realizedPnL, true)}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Txns</span>
                    <span>
                      <span className="text-gray-900 dark:text-white font-semibold">{stats.totalTxns.toLocaleString()}</span>
                      <span className="text-green-600 dark:text-green-400 ml-1">{stats.buyTxns}</span>
                      <span className="text-gray-500"> / </span>
                      <span className="text-red-600 dark:text-red-400">{stats.sellTxns}</span>
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Avg PnL per Asset</span>
                    <span className={cn(
                      'font-semibold',
                      stats.avgPnLPerAsset >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    )}>
                      {formatUSD(stats.avgPnLPerAsset, true)}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Avg Buy Value</span>
                    <span className="text-gray-900 dark:text-white font-semibold">{formatUSD(stats.avgBuyValue)}</span>
                  </div>
                </div>
              </div>

              {/* Distribution Card */}
              <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-5 transition-colors">
                <h3 className="text-gray-500 dark:text-gray-400 text-sm font-medium mb-4">Distribution</h3>

                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-gray-500 mb-2">
                    <span>PnL %</span>
                    <span>Count (Rate)</span>
                  </div>

                  {stats.distribution.map((tier, idx) => (
                    <div key={idx} className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <div className={cn('w-2 h-2 rounded-full', tier.color)} />
                        <span className="text-sm text-gray-700 dark:text-gray-300">{tier.label}</span>
                      </div>
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {tier.count} ({tier.percent.toFixed(2)}%)
                      </span>
                    </div>
                  ))}
                </div>

                {/* Distribution bar */}
                <div className="mt-4 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex">
                  {stats.distribution.map((tier, idx) => (
                    <div
                      key={idx}
                      className={cn(tier.barColor)}
                      style={{ width: `${tier.percent}%` }}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Tabs and Table */}
            <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden transition-colors">
              {/* Tabs and Search - Mobile optimized */}
              <div className="border-b border-gray-200 dark:border-gray-700 px-3 md:px-4 py-2 md:py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 md:gap-3">
                <div className="flex gap-2 md:gap-4 overflow-x-auto pb-1 sm:pb-0 -mx-1 px-1">
                  <button
                    type="button"
                    onClick={() => setActiveTab('recently_traded')}
                    className={cn(
                      'text-xs md:text-sm font-medium transition-colors whitespace-nowrap',
                      activeTab === 'recently_traded' ? 'text-gray-900 dark:text-white' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                    )}
                  >
                    Recent
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('live_positions')}
                    className={cn(
                      'text-xs md:text-sm font-medium transition-colors whitespace-nowrap',
                      activeTab === 'live_positions' ? 'text-gray-900 dark:text-white' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                    )}
                  >
                    Live
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('most_profitable')}
                    className={cn(
                      'text-xs md:text-sm font-medium transition-colors whitespace-nowrap',
                      activeTab === 'most_profitable' ? 'text-gray-900 dark:text-white' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                    )}
                  >
                    Top Gains
                  </button>
                </div>

                {/* Search Input */}
                <div className="relative">
                  <Search className="absolute left-2.5 md:left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 md:w-4 md:h-4 text-gray-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search..."
                    className="pl-8 md:pl-9 pr-3 md:pr-4 py-1.5 md:py-2 bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-xs md:text-sm w-full sm:w-36 md:w-48 focus:outline-none focus:border-sol-purple text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              {/* Mobile Token Cards */}
              <div className="md:hidden divide-y divide-gray-200 dark:divide-gray-700/30">
                {sortedTokens.map((token) => {
                  const totalPnL = (token.unrealized_pnl_usd || 0) + token.realized_pnl_usd;
                  const totalPnLPercent = token.total_buy_sol > 0
                    ? ((token.total_sell_sol + (token.current_balance * token.avg_buy_price_sol) - token.total_buy_sol) / token.total_buy_sol) * 100
                    : 0;
                  const positionPercent = token.total_bought > 0
                    ? (token.current_balance / token.total_bought) * 100
                    : 0;

                  return (
                    <div key={token.token_address} className="p-3 hover:bg-gray-50 dark:hover:bg-gray-700/20">
                      {/* Token header row */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-7 h-7 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                            {token.token_logo ? (
                              <img src={token.token_logo} alt={token.token_symbol} className="w-full h-full object-cover" />
                            ) : (
                              <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400">
                                {token.token_symbol.slice(0, 2)}
                              </span>
                            )}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <span className="font-medium text-sm truncate text-gray-900 dark:text-white">{token.token_symbol}</span>
                              <a
                                href={`https://dexscreener.com/solana/${token.token_address}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 flex-shrink-0"
                                title="View on DexScreener"
                              >
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            </div>
                            <p className="text-[10px] text-gray-500">{timeAgo(token.last_trade)}</p>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className={cn(
                            'text-sm font-semibold',
                            totalPnL >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                          )}>
                            {formatUSD(totalPnL, true)}
                          </p>
                          <p className={cn(
                            'text-[10px]',
                            totalPnLPercent >= 0 ? 'text-green-600/70 dark:text-green-400/70' : 'text-red-600/70 dark:text-red-400/70'
                          )}>
                            {formatPercent(totalPnLPercent, true)}
                          </p>
                        </div>
                      </div>

                      {/* Stats row */}
                      <div className="grid grid-cols-4 gap-2 text-center">
                        <div>
                          <p className="text-[10px] text-gray-500">Balance</p>
                          <p className="text-xs font-medium">{formatUSD(token.current_value_usd)}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">Unrealised</p>
                          <p className={cn(
                            'text-xs font-medium',
                            (token.unrealized_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                          )}>
                            {formatUSD(token.unrealized_pnl_usd, true)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">Realised</p>
                          {token.current_balance > 0 && token.total_sold === 0 ? (
                            <p className="text-xs font-medium text-cyan-400">Hold</p>
                          ) : (
                            <p className={cn(
                              'text-xs font-medium',
                              token.realized_pnl_usd >= 0 ? 'text-green-400' : 'text-red-400'
                            )}>
                              {formatUSD(token.realized_pnl_usd, true)}
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">Position</p>
                          <p className="text-xs font-medium">{positionPercent.toFixed(0)}%</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b border-gray-700/50">
                      <th className="text-left px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('last_trade')} className="flex items-center gap-1 hover:text-gray-300">
                          Last Traded {sortField === 'last_trade' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('unrealized')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Unrealised {sortField === 'unrealized' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('realized')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Realised {sortField === 'realized' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('total_pnl')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Total PnL {sortField === 'total_pnl' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('balance')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Balance {sortField === 'balance' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('bought')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Bought / Avg {sortField === 'bought' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('sold')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Sold / Avg {sortField === 'sold' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button type="button" onClick={() => handleSort('position')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Position % {sortField === 'position' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700/30">
                    {sortedTokens.map((token) => {
                      const totalPnL = (token.unrealized_pnl_usd || 0) + token.realized_pnl_usd;
                      const totalPnLPercent = token.total_buy_sol > 0
                        ? ((token.total_sell_sol + (token.current_balance * token.avg_buy_price_sol) - token.total_buy_sol) / token.total_buy_sol) * 100
                        : 0;
                      const positionPercent = token.total_bought > 0
                        ? (token.current_balance / token.total_bought) * 100
                        : 0;
                      const avgBuyPrice = token.total_bought > 0 ? token.total_buy_sol / token.total_bought : 0;
                      const avgSellPrice = token.total_sold > 0 ? token.total_sell_sol / token.total_sold : 0;

                      return (
                        <tr key={token.token_address} className="hover:bg-gray-700/20">
                          {/* Token Name */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                                {token.token_logo ? (
                                  <img src={token.token_logo} alt={token.token_symbol} className="w-full h-full object-cover" />
                                ) : (
                                  <span className="text-xs font-bold text-gray-400">
                                    {token.token_symbol.slice(0, 2)}
                                  </span>
                                )}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-medium">{token.token_symbol}</span>
                                  <a
                                    href={`https://dexscreener.com/solana/${token.token_address}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-gray-500 hover:text-gray-300"
                                    title="View on DexScreener"
                                  >
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                  <a
                                    href={`https://solscan.io/token/${token.token_address}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-sol-purple hover:text-sol-purple/80"
                                    title="View on Solscan"
                                  >
                                    Solscan
                                  </a>
                                </div>
                                <p className="text-xs text-gray-500">{timeAgo(token.last_trade)}</p>
                              </div>
                            </div>
                          </td>

                          {/* Unrealized */}
                          <td className="px-4 py-3 text-right">
                            {token.current_balance > 0 ? (
                              <div>
                                <p className={cn(
                                  'font-medium',
                                  (token.unrealized_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                                )}>
                                  {formatUSD(token.unrealized_pnl_usd, true)}
                                </p>
                                <p className={cn(
                                  'text-xs',
                                  (token.unrealized_pnl_percent || 0) >= 0 ? 'text-green-400/70' : 'text-red-400/70'
                                )}>
                                  {formatPercent(token.unrealized_pnl_percent, true)}
                                </p>
                              </div>
                            ) : (
                              <div>
                                <p className="text-gray-500">$0.00</p>
                                <p className="text-xs text-gray-500">0%</p>
                              </div>
                            )}
                          </td>

                          {/* Realized */}
                          <td className="px-4 py-3 text-right">
                            {token.current_balance > 0 && token.total_sold === 0 ? (
                              <p className="text-cyan-400 font-medium">Holding</p>
                            ) : (
                              <div>
                                <p className={cn(
                                  'font-medium',
                                  token.realized_pnl_usd >= 0 ? 'text-green-400' : 'text-red-400'
                                )}>
                                  {formatUSD(token.realized_pnl_usd, true)}
                                </p>
                                <p className={cn(
                                  'text-xs',
                                  token.realized_pnl_usd >= 0 ? 'text-green-400/70' : 'text-red-400/70'
                                )}>
                                  {token.total_buy_sol > 0 ? formatPercent((token.realized_pnl_sol / token.total_buy_sol) * 100, true) : ''}
                                </p>
                              </div>
                            )}
                          </td>

                          {/* Total PnL */}
                          <td className="px-4 py-3 text-right">
                            <div>
                              <p className={cn(
                                'font-medium',
                                totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
                              )}>
                                {formatUSD(totalPnL, true)}
                              </p>
                              <p className={cn(
                                'text-xs',
                                totalPnLPercent >= 0 ? 'text-green-400/70' : 'text-red-400/70'
                              )}>
                                {formatPercent(totalPnLPercent, true)}
                              </p>
                            </div>
                          </td>

                          {/* Balance */}
                          <td className="px-4 py-3 text-right">
                            <div>
                              <p className="font-medium">{formatUSD(token.current_value_usd)}</p>
                              <p className="text-xs text-gray-500">{formatBalance(token.current_balance)}</p>
                            </div>
                          </td>

                          {/* Bought / Avg */}
                          <td className="px-4 py-3 text-right">
                            <div>
                              <p className="font-medium">{formatUSD(token.total_buy_sol * (portfolio?.total_value_usd || 0) / (portfolio?.total_cost_sol || 1))}</p>
                              <p className="text-xs text-gray-500">{formatSOL(avgBuyPrice)}</p>
                            </div>
                          </td>

                          {/* Sold / Avg */}
                          <td className="px-4 py-3 text-right">
                            {token.total_sold > 0 ? (
                              <div>
                                <p className="font-medium">{formatUSD(token.total_sell_sol * (portfolio?.total_value_usd || 0) / (portfolio?.total_cost_sol || 1))}</p>
                                <p className="text-xs text-gray-500">{formatSOL(avgSellPrice)}</p>
                              </div>
                            ) : (
                              <p className="text-gray-500">-</p>
                            )}
                          </td>

                          {/* Position % */}
                          <td className="px-4 py-3 text-right">
                            <p className="font-medium">{positionPercent.toFixed(1)}%</p>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {sortedTokens.length === 0 && (
                <div className="p-6 md:p-8 text-center text-gray-500 text-sm">
                  No tokens found. Sync your wallet to see your trading history.
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

// Helper function to calculate stats (uses filtered tokens for time period)
function calculateStats(portfolio: Portfolio, filteredTokens: TokenPnL[]) {
  const tokens = filteredTokens;

  // Holdings (current value of all positions)
  const totalHoldings = tokens.reduce((sum, t) => sum + (t.current_value_usd || 0), 0);

  // Unrealized P&L (based on filtered tokens)
  const unrealizedPnL = tokens.reduce((sum, t) => sum + (t.unrealized_pnl_usd || 0), 0);
  const totalCostUsd = tokens.reduce((sum, t) => sum + (t.current_balance > 0 ? t.total_cost_sol * 200 : 0), 0); // Rough estimate
  const unrealizedPnLPercent = totalCostUsd > 0 ? (unrealizedPnL / totalCostUsd) * 100 : 0;

  // Realized P&L (based on filtered tokens)
  const realizedPnL = tokens.reduce((sum, t) => sum + t.realized_pnl_usd, 0);

  // Total P&L
  const totalPnL = unrealizedPnL + realizedPnL;
  const totalInvested = tokens.reduce((sum, t) => sum + t.total_buy_sol, 0) * 200; // Rough estimate
  const totalPnLPercent = totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0;

  // Win rate (tokens with positive total P&L)
  const profitableTokens = tokens.filter(t => (t.unrealized_pnl_usd || 0) + t.realized_pnl_usd > 0).length;
  const winRate = tokens.length > 0 ? (profitableTokens / tokens.length) * 100 : 0;

  // Transaction counts
  const totalTxns = tokens.reduce((sum, t) => sum + t.trade_count, 0);
  const buyTxns = tokens.reduce((sum, t) => sum + Math.ceil(t.trade_count / 2), 0); // Estimate
  const sellTxns = totalTxns - buyTxns;

  // Avg PnL per asset
  const avgPnLPerAsset = tokens.length > 0 ? totalPnL / tokens.length : 0;

  // Avg buy value
  const avgBuyValue = tokens.length > 0
    ? tokens.reduce((sum, t) => sum + t.total_buy_sol, 0) * 200 / tokens.length
    : 0;

  // Distribution tiers
  const distribution = calculateDistribution(tokens);

  return {
    totalHoldings,
    unrealizedPnL,
    unrealizedPnLPercent,
    realizedPnL,
    totalPnL,
    totalPnLPercent,
    winRate,
    totalTxns,
    buyTxns,
    sellTxns,
    avgPnLPerAsset,
    avgBuyValue,
    distribution,
  };
}

function calculateDistribution(tokens: TokenPnL[]) {
  const tiers = [
    { label: '> 500%', min: 500, color: 'bg-green-400', barColor: 'bg-green-400', count: 0, percent: 0 },
    { label: '200% - 500%', min: 200, max: 500, color: 'bg-green-500', barColor: 'bg-green-500', count: 0, percent: 0 },
    { label: '50% - 200%', min: 50, max: 200, color: 'bg-green-600', barColor: 'bg-green-600', count: 0, percent: 0 },
    { label: '0% - 50%', min: 0, max: 50, color: 'bg-yellow-500', barColor: 'bg-yellow-500', count: 0, percent: 0 },
    { label: '< -50%', max: -50, color: 'bg-red-500', barColor: 'bg-red-500', count: 0, percent: 0 },
  ];

  tokens.forEach(token => {
    const totalPnL = (token.unrealized_pnl_usd || 0) + token.realized_pnl_usd;
    const totalCost = token.total_buy_sol * 200; // Rough estimate
    const pnlPercent = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

    for (const tier of tiers) {
      if (tier.min !== undefined && tier.max !== undefined) {
        if (pnlPercent >= tier.min && pnlPercent < tier.max) {
          tier.count++;
          break;
        }
      } else if (tier.min !== undefined) {
        if (pnlPercent >= tier.min) {
          tier.count++;
          break;
        }
      } else if (tier.max !== undefined) {
        if (pnlPercent < tier.max) {
          tier.count++;
          break;
        }
      }
    }
  });

  const total = tokens.length;
  tiers.forEach(tier => {
    tier.percent = total > 0 ? (tier.count / total) * 100 : 0;
  });

  return tiers;
}

function getSortedTokens(tokens: TokenPnL[], tab: TabType, sortField: SortField, sortDirection: SortDirection): TokenPnL[] {
  let filtered = [...tokens];

  // Filter by tab
  if (tab === 'live_positions') {
    filtered = tokens.filter(t => t.current_balance > 0);
  } else if (tab === 'most_profitable') {
    filtered = [...tokens].sort((a, b) => {
      const aPnL = (a.unrealized_pnl_usd || 0) + a.realized_pnl_usd;
      const bPnL = (b.unrealized_pnl_usd || 0) + b.realized_pnl_usd;
      return bPnL - aPnL;
    });
  }

  // Sort
  filtered.sort((a, b) => {
    let aVal = 0, bVal = 0;

    switch (sortField) {
      case 'last_trade':
        aVal = a.last_trade ? new Date(a.last_trade).getTime() : 0;
        bVal = b.last_trade ? new Date(b.last_trade).getTime() : 0;
        break;
      case 'unrealized':
        aVal = a.unrealized_pnl_usd || 0;
        bVal = b.unrealized_pnl_usd || 0;
        break;
      case 'realized':
        aVal = a.realized_pnl_usd;
        bVal = b.realized_pnl_usd;
        break;
      case 'total_pnl':
        aVal = (a.unrealized_pnl_usd || 0) + a.realized_pnl_usd;
        bVal = (b.unrealized_pnl_usd || 0) + b.realized_pnl_usd;
        break;
      case 'balance':
        aVal = a.current_value_usd || 0;
        bVal = b.current_value_usd || 0;
        break;
      case 'bought':
        aVal = a.total_buy_sol;
        bVal = b.total_buy_sol;
        break;
      case 'sold':
        aVal = a.total_sell_sol;
        bVal = b.total_sell_sol;
        break;
      case 'position':
        aVal = a.total_bought > 0 ? (a.current_balance / a.total_bought) * 100 : 0;
        bVal = b.total_bought > 0 ? (b.current_balance / b.total_bought) * 100 : 0;
        break;
    }

    return sortDirection === 'desc' ? bVal - aVal : aVal - bVal;
  });

  return filtered;
}
