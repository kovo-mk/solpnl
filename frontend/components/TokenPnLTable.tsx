'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TokenPnL } from '@/lib/api';

interface TokenPnLTableProps {
  tokens: TokenPnL[];
  walletAddress: string;
}

type TabType = 'open' | 'closed' | 'all';

export default function TokenPnLTable({ tokens, walletAddress }: TokenPnLTableProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('open');
  const [expandedToken, setExpandedToken] = useState<string | null>(null);

  // Filter tokens based on active tab
  const filteredTokens = tokens.filter((token) => {
    if (activeTab === 'open') {
      return token.current_balance > 0;
    } else if (activeTab === 'closed') {
      return token.current_balance === 0;
    }
    return true; // 'all' tab
  });

  const openCount = tokens.filter(t => t.current_balance > 0).length;
  const closedCount = tokens.filter(t => t.current_balance === 0).length;

  const formatCurrency = (value: number) => {
    return `$${Math.abs(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  };

  const formatPnL = (value: number) => {
    return `${value >= 0 ? '+' : '-'}${formatCurrency(value)}`;
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const toggleToken = (tokenAddress: string, e: React.MouseEvent) => {
    // Only toggle if clicking on the row itself, not child elements
    if ((e.target as HTMLElement).closest('a, button')) {
      return;
    }
    setExpandedToken(expandedToken === tokenAddress ? null : tokenAddress);
  };

  const navigateToToken = (tokenAddress: string) => {
    router.push(`/view/${walletAddress}/token/${tokenAddress}`);
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-gray-700">
        <button
          onClick={() => setActiveTab('open')}
          className={cn(
            'flex-1 px-6 py-4 text-sm font-medium transition-colors',
            activeTab === 'open'
              ? 'bg-gray-700/50 text-white border-b-2 border-sol-purple'
              : 'text-gray-400 hover:text-gray-200'
          )}
        >
          Open ({openCount})
        </button>
        <button
          onClick={() => setActiveTab('closed')}
          className={cn(
            'flex-1 px-6 py-4 text-sm font-medium transition-colors',
            activeTab === 'closed'
              ? 'bg-gray-700/50 text-white border-b-2 border-sol-purple'
              : 'text-gray-400 hover:text-gray-200'
          )}
        >
          Closed ({closedCount})
        </button>
        <button
          onClick={() => setActiveTab('all')}
          className={cn(
            'flex-1 px-6 py-4 text-sm font-medium transition-colors',
            activeTab === 'all'
              ? 'bg-gray-700/50 text-white border-b-2 border-sol-purple'
              : 'text-gray-400 hover:text-gray-200'
          )}
        >
          All ({tokens.length})
        </button>
      </div>

      {/* Table Header */}
      <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-gray-900/50 text-xs font-medium text-gray-400 border-b border-gray-700">
        <div className="col-span-5">Token</div>
        <div className="col-span-3 text-right">Balance</div>
        <div className="col-span-3 text-right">Total P/L</div>
        <div className="col-span-1"></div>
      </div>

      {/* Table Rows */}
      <div className="divide-y divide-gray-700/50">
        {filteredTokens.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-400">
            No {activeTab} positions
          </div>
        ) : (
          filteredTokens.map((token) => {
            const totalPnL = (token.unrealized_pnl_usd || 0) + (token.realized_pnl_usd || 0);
            const isExpanded = expandedToken === token.token_address;
            const hasBalance = token.current_balance > 0;

            return (
              <div key={token.token_address} className="hover:bg-gray-700/30 transition-colors">
                {/* Main Row */}
                <div
                  onClick={(e) => toggleToken(token.token_address, e)}
                  onDoubleClick={() => navigateToToken(token.token_address)}
                  className="w-full grid grid-cols-12 gap-4 px-6 py-4 cursor-pointer"
                >
                  {/* Token Info */}
                  <div className="col-span-5 flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    )}
                    <div className="flex items-center gap-2 min-w-0">
                      {token.token_logo && (
                        <img
                          src={token.token_logo}
                          alt={token.token_symbol}
                          className="w-8 h-8 rounded-full flex-shrink-0"
                        />
                      )}
                      <div className="min-w-0">
                        <p className="font-semibold text-white truncate">{token.token_symbol}</p>
                        <p className="text-xs text-gray-400 truncate">{token.token_name}</p>
                      </div>
                    </div>
                  </div>

                  {/* Balance */}
                  <div className="col-span-3 text-right">
                    {hasBalance ? (
                      <>
                        <p className="font-semibold text-white">{formatCurrency(token.current_value_usd)}</p>
                        <p className="text-xs text-gray-400">
                          {token.current_balance.toLocaleString(undefined, {
                            minimumFractionDigits: 0,
                            maximumFractionDigits: 2
                          })}
                        </p>
                      </>
                    ) : (
                      <p className="text-gray-500">$0.00</p>
                    )}
                  </div>

                  {/* Total P/L */}
                  <div className="col-span-3 text-right">
                    <p className={cn(
                      'font-bold',
                      totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
                    )}>
                      {formatPnL(totalPnL)}
                    </p>
                    <p className={cn(
                      'text-xs',
                      totalPnL >= 0 ? 'text-green-400/70' : 'text-red-400/70'
                    )}>
                      {token.pnl_percentage !== undefined && formatPercentage(token.pnl_percentage)}
                    </p>
                  </div>

                  {/* Expand Arrow */}
                  <div className="col-span-1"></div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="px-6 pb-4 bg-gray-900/30">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      {/* Unrealized P/L */}
                      <div className="bg-gray-800/50 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-1">Unrealized P/L</p>
                        <p className={cn(
                          'font-semibold',
                          (token.unrealized_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        )}>
                          {formatPnL(token.unrealized_pnl_usd || 0)}
                        </p>
                      </div>

                      {/* Realized P/L */}
                      <div className="bg-gray-800/50 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-1">Realized P/L</p>
                        <p className={cn(
                          'font-semibold',
                          (token.realized_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        )}>
                          {formatPnL(token.realized_pnl_usd || 0)}
                        </p>
                      </div>

                      {/* Avg Buy Price */}
                      <div className="bg-gray-800/50 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-1">Avg Buy Price</p>
                        <p className="font-semibold text-white">
                          {token.avg_buy_price_usd ? `$${token.avg_buy_price_usd.toFixed(6)}` : 'N/A'}
                        </p>
                      </div>

                      {/* Total Bought/Sold */}
                      <div className="bg-gray-800/50 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-1">Bought / Sold</p>
                        <p className="font-semibold text-white">
                          {token.total_bought?.toLocaleString(undefined, { maximumFractionDigits: 0 })} / {token.total_sold?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </p>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                      <a
                        href={`https://solscan.io/token/${token.token_address}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium transition-colors"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-3 h-3" />
                        Solscan
                      </a>
                      <a
                        href={`https://birdeye.so/token/${token.token_address}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium transition-colors"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-3 h-3" />
                        Chart
                      </a>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
