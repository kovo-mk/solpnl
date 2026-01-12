'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Loader2,
} from 'lucide-react';
import { api, type Portfolio, type TokenPnL, type Wallet } from '@/lib/api';
import { cn } from '@/lib/utils';

type SortField = 'last_trade' | 'unrealized' | 'realized' | 'total_pnl' | 'balance';
type SortDirection = 'asc' | 'desc';
type TabType = 'recently_traded' | 'live_positions' | 'most_profitable';

export default function PnLDashboard() {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [selectedWallet, setSelectedWallet] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('recently_traded');
  const [sortField, setSortField] = useState<SortField>('last_trade');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

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

  useEffect(() => {
    fetchWallets();
  }, []);

  useEffect(() => {
    fetchPortfolio();
  }, [selectedWallet, fetchPortfolio]);

  // Calculate stats
  const stats = portfolio ? calculateStats(portfolio) : null;

  // Sort and filter tokens
  const sortedTokens = portfolio ? getSortedTokens(portfolio.tokens, activeTab, sortField, sortDirection) : [];

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
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="p-2 hover:bg-gray-800 rounded-lg transition-colors">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold">P&L Dashboard</h1>
                <p className="text-xs text-gray-400">Track your trading performance</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Wallet selector */}
              {wallets.length > 0 && (
                <select
                  value={selectedWallet || ''}
                  onChange={(e) => setSelectedWallet(e.target.value)}
                  className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
                >
                  {wallets.map((wallet) => (
                    <option key={wallet.address} value={wallet.address}>
                      {wallet.label || wallet.address.slice(0, 8) + '...'}
                    </option>
                  ))}
                </select>
              )}

              <button
                onClick={handleSync}
                disabled={syncing || !selectedWallet}
                className="flex items-center gap-2 px-4 py-2 bg-sol-purple hover:bg-sol-purple/80 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <RefreshCw className={cn('w-4 h-4', syncing && 'animate-spin')} />
                {syncing ? 'Syncing...' : 'Sync'}
              </button>
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
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
            {error}
          </div>
        )}

        {/* Dashboard Content */}
        {portfolio && stats && !loading && (
          <div className="space-y-6">
            {/* Summary Cards Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Summary Card */}
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-5">
                <h3 className="text-gray-400 text-sm font-medium mb-4">Summary</h3>

                <div className="space-y-3">
                  <div>
                    <p className="text-gray-500 text-xs">Holdings</p>
                    <p className="text-2xl font-bold">{formatUSD(stats.totalHoldings)}</p>
                  </div>

                  <div>
                    <p className="text-gray-500 text-xs">Unrealised PnL</p>
                    <p className={cn(
                      'text-lg font-semibold',
                      stats.unrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
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
                      stats.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
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
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-5">
                <h3 className="text-gray-400 text-sm font-medium mb-4">Analysis</h3>

                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Win Rate</span>
                    <span className="text-cyan-400 text-xl font-bold">{stats.winRate.toFixed(2)}%</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Realised PnL</span>
                    <span className={cn(
                      'font-semibold',
                      stats.realizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
                    )}>
                      {formatUSD(stats.realizedPnL, true)}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Txns</span>
                    <span>
                      <span className="text-white font-semibold">{stats.totalTxns.toLocaleString()}</span>
                      <span className="text-green-400 ml-1">{stats.buyTxns}</span>
                      <span className="text-gray-500"> / </span>
                      <span className="text-red-400">{stats.sellTxns}</span>
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Avg PnL per Asset</span>
                    <span className={cn(
                      'font-semibold',
                      stats.avgPnLPerAsset >= 0 ? 'text-green-400' : 'text-red-400'
                    )}>
                      {formatUSD(stats.avgPnLPerAsset, true)}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-500 text-sm">Avg Buy Value</span>
                    <span className="text-white font-semibold">{formatUSD(stats.avgBuyValue)}</span>
                  </div>
                </div>
              </div>

              {/* Distribution Card */}
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-5">
                <h3 className="text-gray-400 text-sm font-medium mb-4">Distribution</h3>

                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-gray-500 mb-2">
                    <span>PnL %</span>
                    <span>Count (Rate)</span>
                  </div>

                  {stats.distribution.map((tier, idx) => (
                    <div key={idx} className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <div className={cn('w-2 h-2 rounded-full', tier.color)} />
                        <span className="text-sm text-gray-300">{tier.label}</span>
                      </div>
                      <span className="text-sm text-gray-400">
                        {tier.count} ({tier.percent.toFixed(2)}%)
                      </span>
                    </div>
                  ))}
                </div>

                {/* Distribution bar */}
                <div className="mt-4 h-2 bg-gray-700 rounded-full overflow-hidden flex">
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
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden">
              {/* Tabs */}
              <div className="border-b border-gray-700 px-4 py-3 flex items-center justify-between">
                <div className="flex gap-4">
                  <button
                    onClick={() => setActiveTab('recently_traded')}
                    className={cn(
                      'text-sm font-medium transition-colors',
                      activeTab === 'recently_traded' ? 'text-white' : 'text-gray-500 hover:text-gray-300'
                    )}
                  >
                    Recently Traded
                  </button>
                  <button
                    onClick={() => setActiveTab('live_positions')}
                    className={cn(
                      'text-sm font-medium transition-colors',
                      activeTab === 'live_positions' ? 'text-white' : 'text-gray-500 hover:text-gray-300'
                    )}
                  >
                    Live Positions
                  </button>
                  <button
                    onClick={() => setActiveTab('most_profitable')}
                    className={cn(
                      'text-sm font-medium transition-colors',
                      activeTab === 'most_profitable' ? 'text-white' : 'text-gray-500 hover:text-gray-300'
                    )}
                  >
                    Most Profitable
                  </button>
                </div>
              </div>

              {/* Table Header */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b border-gray-700/50">
                      <th className="text-left px-4 py-3 font-medium">
                        <button onClick={() => handleSort('last_trade')} className="flex items-center gap-1 hover:text-gray-300">
                          Last Traded {sortField === 'last_trade' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button onClick={() => handleSort('unrealized')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Unrealised {sortField === 'unrealized' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button onClick={() => handleSort('realized')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Realised {sortField === 'realized' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button onClick={() => handleSort('total_pnl')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Total PnL {sortField === 'total_pnl' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">
                        <button onClick={() => handleSort('balance')} className="flex items-center gap-1 hover:text-gray-300 ml-auto">
                          Balance {sortField === 'balance' && (sortDirection === 'desc' ? '↓' : '↑')}
                        </button>
                      </th>
                      <th className="text-right px-4 py-3 font-medium">Bought / Avg</th>
                      <th className="text-right px-4 py-3 font-medium">Sold / Avg</th>
                      <th className="text-right px-4 py-3 font-medium">Position %</th>
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
                                  >
                                    <ExternalLink className="w-3 h-3" />
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
                <div className="p-8 text-center text-gray-500">
                  No tokens found. Sync your wallet to see your trading history.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Helper function to calculate stats
function calculateStats(portfolio: Portfolio) {
  const tokens = portfolio.tokens;

  // Holdings (current value of all positions)
  const totalHoldings = tokens.reduce((sum, t) => sum + (t.current_value_usd || 0), 0);

  // Unrealized P&L
  const unrealizedPnL = portfolio.total_unrealized_pnl_usd;
  const totalCostUsd = tokens.reduce((sum, t) => sum + (t.current_balance > 0 ? t.total_cost_sol * 200 : 0), 0); // Rough estimate
  const unrealizedPnLPercent = totalCostUsd > 0 ? (unrealizedPnL / totalCostUsd) * 100 : 0;

  // Realized P&L
  const realizedPnL = portfolio.total_realized_pnl_usd;

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
    }

    return sortDirection === 'desc' ? bVal - aVal : aVal - bVal;
  });

  return filtered;
}
