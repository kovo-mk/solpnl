'use client';

import { cn } from '@/lib/utils';

interface PnLSummaryCardProps {
  walletValue: number;
  totalPnL: number;
  totalPnLPercentage: number;
  unrealizedPnL: number;
  unrealizedPnLPercentage: number;
  realizedPnL: number;
  realizedPnLPercentage: number;
  solBalance: number;
  solValue: number;
}

export default function PnLSummaryCard({
  walletValue,
  totalPnL,
  totalPnLPercentage,
  unrealizedPnL,
  unrealizedPnLPercentage,
  realizedPnL,
  realizedPnLPercentage,
  solBalance,
  solValue,
}: PnLSummaryCardProps) {
  const formatCurrency = (value: number) => {
    return `$${Math.abs(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const formatPnL = (value: number) => {
    return `${value >= 0 ? '+' : '-'}${formatCurrency(value)}`;
  };

  return (
    <div className="bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700 rounded-2xl p-6">
      {/* Top Row: Balance and Total P/L */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div>
          <p className="text-sm text-gray-400 mb-1">Balance</p>
          <p className="text-3xl font-bold text-white">
            {formatCurrency(walletValue)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {solBalance.toFixed(4)} SOL
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-400 mb-1">Total PnL</p>
          <p className={cn(
            'text-3xl font-bold',
            totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPnL(totalPnL)}
          </p>
          <p className={cn(
            'text-xs mt-1',
            totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPercentage(totalPnLPercentage)}
          </p>
        </div>
      </div>

      {/* Bottom Row: Unrealized and Realized P/L */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-gray-900/50 rounded-lg p-4">
          <p className="text-sm text-gray-400 mb-1">Unrealized PnL</p>
          <p className={cn(
            'text-xl font-bold',
            unrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPnL(unrealizedPnL)}
          </p>
          <p className={cn(
            'text-xs mt-1',
            unrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPercentage(unrealizedPnLPercentage)}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-4">
          <p className="text-sm text-gray-400 mb-1">Realized PnL</p>
          <p className={cn(
            'text-xl font-bold',
            realizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPnL(realizedPnL)}
          </p>
          <p className={cn(
            'text-xs mt-1',
            realizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {formatPercentage(realizedPnLPercentage)}
          </p>
        </div>
      </div>
    </div>
  );
}
