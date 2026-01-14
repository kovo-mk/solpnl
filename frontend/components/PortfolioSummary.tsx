'use client';

import { Portfolio } from '@/lib/api';
import { formatUSD, formatPnL, cn, shortenAddress, timeAgo } from '@/lib/utils';
import { Wallet, TrendingUp, TrendingDown, RefreshCw, Loader2, Info } from 'lucide-react';

interface PortfolioSummaryProps {
  portfolio: Portfolio;
  onSync?: () => void;
  syncing?: boolean;
}

export default function PortfolioSummary({
  portfolio,
  onSync,
  syncing,
}: PortfolioSummaryProps) {
  const totalPnL =
    portfolio.total_unrealized_pnl_usd + portfolio.total_realized_pnl_usd;
  const isProfit = totalPnL >= 0;

  return (
    <div className="bg-white dark:bg-gradient-to-br dark:from-gray-800/80 dark:to-gray-900/80 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-100 dark:bg-sol-purple/20 rounded-xl">
            <Wallet className="w-6 h-6 text-blue-600 dark:text-sol-purple" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {portfolio.wallet_label || shortenAddress(portfolio.wallet_address)}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {portfolio.wallet_label
                ? shortenAddress(portfolio.wallet_address)
                : 'Tracking ' + portfolio.token_count + ' tokens'}
            </p>
          </div>
        </div>

        {onSync && (
          <button
            onClick={onSync}
            disabled={syncing}
            className="p-2 bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50 text-gray-600 dark:text-white"
            title="Sync transactions"
          >
            {syncing ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <RefreshCw className="w-5 h-5" />
            )}
          </button>
        )}
      </div>

      {/* Main Stats */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Portfolio Value */}
        <div className="bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-transparent rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm text-gray-500 dark:text-gray-400">Portfolio Value</p>
            <div className="group relative">
              <Info className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500 cursor-help" />
              <div className="absolute left-0 top-5 bg-gray-900 dark:bg-gray-800 text-white text-xs rounded-lg p-3 w-64 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-10 shadow-lg">
                Trading performance calculated from transaction history (swaps, transfers, airdrops, etc.) - includes realized & unrealized P/L
              </div>
            </div>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {formatUSD(portfolio.total_value_usd)}
          </p>
        </div>

        {/* Total P/L */}
        <div
          className={cn(
            'rounded-xl p-4 border',
            isProfit
              ? 'bg-green-50 dark:bg-green-500/10 border-green-100 dark:border-transparent'
              : 'bg-red-50 dark:bg-red-500/10 border-red-100 dark:border-transparent'
          )}
        >
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total P/L</p>
          <div className="flex items-center gap-2">
            {isProfit ? (
              <TrendingUp className="w-5 h-5 text-green-600 dark:text-green-400" />
            ) : (
              <TrendingDown className="w-5 h-5 text-red-600 dark:text-red-400" />
            )}
            <p
              className={cn(
                'text-2xl font-bold',
                isProfit ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              )}
            >
              {formatPnL(totalPnL)}
            </p>
          </div>
        </div>
      </div>

      {/* P/L Breakdown */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-50 dark:bg-gray-900/30 border border-gray-100 dark:border-transparent rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Unrealized P/L</p>
          <p
            className={cn(
              'text-lg font-semibold',
              portfolio.total_unrealized_pnl_usd >= 0
                ? 'text-green-600 dark:text-green-400'
                : 'text-red-600 dark:text-red-400'
            )}
          >
            {formatPnL(portfolio.total_unrealized_pnl_usd)}
          </p>
          <p className="text-xs text-gray-500">On current holdings</p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-900/30 border border-gray-100 dark:border-transparent rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Realized P/L</p>
          <p
            className={cn(
              'text-lg font-semibold',
              portfolio.total_realized_pnl_usd >= 0
                ? 'text-green-600 dark:text-green-400'
                : 'text-red-600 dark:text-red-400'
            )}
          >
            {formatPnL(portfolio.total_realized_pnl_usd)}
          </p>
          <p className="text-xs text-gray-500">From completed trades</p>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700/50 flex items-center justify-between text-sm text-gray-500">
        <span>{portfolio.token_count} tokens tracked</span>
        <span>Synced: {timeAgo(portfolio.last_synced)}</span>
      </div>
    </div>
  );
}
