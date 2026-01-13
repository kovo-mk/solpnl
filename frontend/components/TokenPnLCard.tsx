'use client';

import { useState } from 'react';
import { TokenPnL, api } from '@/lib/api';
import {
  formatUSD,
  formatSOL,
  formatTokenAmount,
  formatPercent,
  formatPnL,
  timeAgo,
  cn,
} from '@/lib/utils';
import { TrendingUp, TrendingDown, ExternalLink, ShieldCheck, ShieldOff, EyeOff, Eye } from 'lucide-react';

interface TokenPnLCardProps {
  token: TokenPnL;
  onTokenChange?: (mint: string, isVerified: boolean, valueUsd: number | null) => void;
}

export default function TokenPnLCard({ token, onTokenChange }: TokenPnLCardProps) {
  const [isVerified, setIsVerified] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const [togglingVerification, setTogglingVerification] = useState(false);
  const [togglingHidden, setTogglingHidden] = useState(false);

  const hasHoldings = token.current_balance > 0;
  const totalPnL = (token.unrealized_pnl_usd || 0) + token.realized_pnl_usd;
  const isProfit = totalPnL >= 0;

  const handleToggleVerification = async () => {
    const newVerified = !isVerified;

    // Optimistic update
    setIsVerified(newVerified);
    if (onTokenChange) {
      onTokenChange(token.token_address, newVerified, token.current_value_usd);
    }

    setTogglingVerification(true);
    try {
      await api.toggleTokenVerification(token.token_address);
    } catch (err) {
      console.error('Failed to toggle verification:', err);
      // Revert on error
      setIsVerified(!newVerified);
      if (onTokenChange) {
        onTokenChange(token.token_address, !newVerified, token.current_value_usd);
      }
    } finally {
      setTogglingVerification(false);
    }
  };

  const handleToggleHidden = async () => {
    const newHidden = !isHidden;
    const wasVerified = isVerified;

    // Optimistic update
    setIsHidden(newHidden);
    if (newHidden) setIsVerified(false);

    // If was verified and now hidden, update parent
    if (onTokenChange && wasVerified && newHidden) {
      onTokenChange(token.token_address, false, token.current_value_usd);
    }

    setTogglingHidden(true);
    try {
      await api.toggleTokenHidden(token.token_address);
    } catch (err) {
      console.error('Failed to toggle hidden:', err);
      // Revert on error
      setIsHidden(!newHidden);
      setIsVerified(wasVerified);
      if (onTokenChange && wasVerified && newHidden) {
        onTokenChange(token.token_address, wasVerified, token.current_value_usd);
      }
    } finally {
      setTogglingHidden(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:border-gray-300 dark:hover:border-gray-600 transition-colors shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {token.token_logo ? (
            <img
              src={token.token_logo}
              alt={token.token_symbol}
              className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700"
              onError={(e) => {
                (e.target as HTMLImageElement).src = '/token-placeholder.png';
              }}
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 dark:from-sol-purple dark:to-sol-green flex items-center justify-center font-bold text-white">
              {token.token_symbol?.charAt(0) || '?'}
            </div>
          )}
          <div>
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white">{token.token_symbol}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 truncate max-w-[150px]">
              {token.token_name}
            </p>
          </div>
        </div>

        {/* Total P/L Badge */}
        <div
          className={cn(
            'px-3 py-1.5 rounded-lg flex items-center gap-1.5',
            isProfit
              ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400'
              : 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
          )}
        >
          {isProfit ? (
            <TrendingUp className="w-4 h-4" />
          ) : (
            <TrendingDown className="w-4 h-4" />
          )}
          <span className="font-semibold">{formatPnL(totalPnL)}</span>
        </div>
      </div>

      {/* Current Holdings */}
      {hasHoldings && (
        <div className="bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-transparent rounded-lg p-3 mb-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-gray-500 dark:text-gray-400 text-sm">Holdings</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {formatTokenAmount(token.current_balance)} {token.token_symbol}
            </span>
          </div>
          <div className="flex justify-between items-center mb-2">
            <span className="text-gray-500 dark:text-gray-400 text-sm">Current Value</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {formatUSD(token.current_value_usd)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-500 dark:text-gray-400 text-sm">Avg Buy Price</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {formatSOL(token.avg_buy_price_sol)}
            </span>
          </div>
        </div>
      )}

      {/* P/L Breakdown */}
      <div className="grid grid-cols-2 gap-3">
        {/* Unrealized */}
        <div className="bg-gray-50 dark:bg-gray-900/30 border border-gray-100 dark:border-transparent rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Unrealized P/L</p>
          <p
            className={cn(
              'font-semibold',
              (token.unrealized_pnl_usd || 0) >= 0
                ? 'text-green-600 dark:text-green-400'
                : 'text-red-600 dark:text-red-400'
            )}
          >
            {formatPnL(token.unrealized_pnl_usd)}
          </p>
          {token.unrealized_pnl_percent !== null && (
            <p
              className={cn(
                'text-xs',
                token.unrealized_pnl_percent >= 0
                  ? 'text-green-600/70 dark:text-green-400/70'
                  : 'text-red-600/70 dark:text-red-400/70'
              )}
            >
              {formatPercent(token.unrealized_pnl_percent)}
            </p>
          )}
        </div>

        {/* Realized */}
        <div className="bg-gray-50 dark:bg-gray-900/30 border border-gray-100 dark:border-transparent rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Realized P/L</p>
          <p
            className={cn(
              'font-semibold',
              token.realized_pnl_usd >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
            )}
          >
            {formatPnL(token.realized_pnl_usd)}
          </p>
          <p className="text-xs text-gray-500">
            {formatSOL(token.realized_pnl_sol)}
          </p>
        </div>
      </div>

      {/* Trade Stats */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700/50">
        <div className="flex justify-between text-sm">
          <div>
            <span className="text-gray-500">Bought: </span>
            <span className="text-green-600 dark:text-green-400">
              {formatTokenAmount(token.total_bought)}
            </span>
            <span className="text-gray-400 dark:text-gray-600 mx-1">|</span>
            <span className="text-gray-500 dark:text-gray-400">{formatSOL(token.total_buy_sol)}</span>
          </div>
          <div>
            <span className="text-gray-500">Sold: </span>
            <span className="text-red-600 dark:text-red-400">
              {formatTokenAmount(token.total_sold)}
            </span>
            <span className="text-gray-400 dark:text-gray-600 mx-1">|</span>
            <span className="text-gray-500 dark:text-gray-400">{formatSOL(token.total_sell_sol)}</span>
          </div>
        </div>

        {token.last_trade && (
          <p className="text-xs text-gray-500 mt-2">
            Last trade: {timeAgo(token.last_trade)}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="mt-3 flex gap-2">
        <a
          href={`https://solscan.io/token/${token.token_address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 px-3 py-2 bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm text-center transition-colors flex items-center justify-center gap-1 text-gray-700 dark:text-gray-300"
        >
          <ExternalLink className="w-3 h-3" />
          Solscan
        </a>
        <a
          href={`https://dexscreener.com/solana/${token.token_address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 px-3 py-2 bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm text-center transition-colors flex items-center justify-center gap-1 text-gray-700 dark:text-gray-300"
        >
          <ExternalLink className="w-3 h-3" />
          Chart
        </a>
      </div>

      {/* Verify/Hide buttons */}
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={handleToggleVerification}
          disabled={togglingVerification}
          className={cn(
            'flex-1 px-3 py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-1',
            isVerified
              ? 'bg-green-100 dark:bg-green-500/20 hover:bg-green-200 dark:hover:bg-green-500/30 text-green-600 dark:text-green-400'
              : 'bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400'
          )}
        >
          {togglingVerification ? (
            <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : isVerified ? (
            <ShieldCheck className="w-3 h-3" />
          ) : (
            <ShieldOff className="w-3 h-3" />
          )}
          {isVerified ? 'Verified' : 'Verify'}
        </button>
        <button
          type="button"
          onClick={handleToggleHidden}
          disabled={togglingHidden}
          className={cn(
            'flex-1 px-3 py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-1',
            isHidden
              ? 'bg-red-100 dark:bg-red-500/20 hover:bg-red-200 dark:hover:bg-red-500/30 text-red-600 dark:text-red-400'
              : 'bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400'
          )}
        >
          {togglingHidden ? (
            <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : isHidden ? (
            <Eye className="w-3 h-3" />
          ) : (
            <EyeOff className="w-3 h-3" />
          )}
          {isHidden ? 'Unhide' : 'Hide'}
        </button>
      </div>
    </div>
  );
}
