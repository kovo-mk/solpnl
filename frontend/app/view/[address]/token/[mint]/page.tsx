'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Copy,
  Check,
} from 'lucide-react';
import { api, type TokenPnL } from '@/lib/api';
import { cn } from '@/lib/utils';

export default function TokenDetailPage() {
  const params = useParams();
  const address = params.address as string;
  const mint = params.mint as string;

  const [token, setToken] = useState<TokenPnL | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function fetchTokenData() {
      try {
        const portfolio = await api.getWalletPortfolio(address);
        const tokenData = portfolio.tokens.find(t => t.token_address === mint);
        setToken(tokenData || null);
      } catch (error) {
        console.error('Error fetching token data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchTokenData();
  }, [address, mint]);

  const copyAddress = async (addr: string) => {
    await navigator.clipboard.writeText(addr);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-sol-purple"></div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black p-6">
        <div className="max-w-4xl mx-auto">
          <Link
            href={`/view/${address}`}
            className="inline-flex items-center gap-2 text-gray-400 hover:text-white mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to wallet
          </Link>
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-8 text-center">
            <p className="text-gray-400">Token not found</p>
          </div>
        </div>
      </div>
    );
  }

  const totalPnL = (token.unrealized_pnl_usd || 0) + (token.realized_pnl_usd || 0);
  const hasBalance = token.current_balance > 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black">
      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Header */}
        <Link
          href={`/view/${address}`}
          className="inline-flex items-center gap-2 text-gray-400 hover:text-white mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to wallet
        </Link>

        {/* Token Header */}
        <div className="flex items-center gap-4 mb-8">
          {token.token_logo && (
            <img
              src={token.token_logo}
              alt={token.token_symbol}
              className="w-16 h-16 rounded-full"
            />
          )}
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-white">{token.token_symbol}</h1>
            <p className="text-gray-400">{token.token_name}</p>
            <button
              onClick={() => copyAddress(token.token_address)}
              className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 mt-1"
            >
              <span className="font-mono">{token.token_address.slice(0, 8)}...{token.token_address.slice(-8)}</span>
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
          <div className="flex gap-2">
            <a
              href={`https://solscan.io/token/${token.token_address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Solscan
            </a>
            <a
              href={`https://birdeye.so/token/${token.token_address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Chart
            </a>
          </div>
        </div>

        {/* Position PnL Summary */}
        <div className="bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700 rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-400 mb-4">Position PnL</h2>
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div>
              <p className="text-sm text-gray-400 mb-1">Balance</p>
              <p className="text-3xl font-bold text-white">
                {formatCurrency(token.current_value_usd || 0)}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {hasBalance ? token.current_balance.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '0'} {token.token_symbol}
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
                'text-sm mt-1',
                totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
              )}>
                {token.pnl_percentage !== undefined && formatPercentage(token.pnl_percentage)}
              </p>
            </div>
          </div>

          {/* Unrealized and Realized */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-900/50 rounded-lg p-4">
              <p className="text-sm text-gray-400 mb-1">Unrealized PnL</p>
              <p className={cn(
                'text-2xl font-bold',
                (token.unrealized_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
              )}>
                {formatPnL(token.unrealized_pnl_usd || 0)}
              </p>
              <p className={cn(
                'text-xs mt-1',
                (token.unrealized_pnl_usd || 0) >= 0 ? 'text-green-400/70' : 'text-red-400/70'
              )}>
                {formatPercentage(token.unrealized_pnl_percentage || 0)}
              </p>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-4">
              <p className="text-sm text-gray-400 mb-1">Realized PnL</p>
              <p className={cn(
                'text-2xl font-bold',
                (token.realized_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
              )}>
                {formatPnL(token.realized_pnl_usd || 0)}
              </p>
              <p className={cn(
                'text-xs mt-1',
                (token.realized_pnl_usd || 0) >= 0 ? 'text-green-400/70' : 'text-red-400/70'
              )}>
                {formatPercentage(token.realized_pnl_percentage || 0)}
              </p>
            </div>
          </div>
        </div>

        {/* Trade Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
            <p className="text-sm text-gray-400 mb-1">Bought</p>
            <p className="text-xl font-bold text-white">
              {token.total_bought?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {token.total_buy_sol?.toFixed(2)} SOL
            </p>
          </div>
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
            <p className="text-sm text-gray-400 mb-1">Sold</p>
            <p className="text-xl font-bold text-white">
              {token.total_sold?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {token.total_sell_sol?.toFixed(2)} SOL
            </p>
          </div>
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
            <p className="text-sm text-gray-400 mb-1">Avg Buy Price</p>
            <p className="text-xl font-bold text-white">
              {token.avg_buy_price_sol?.toFixed(6)}
            </p>
            <p className="text-xs text-gray-500 mt-1">SOL</p>
          </div>
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
            <p className="text-sm text-gray-400 mb-1">Current Price</p>
            <p className="text-xl font-bold text-white">
              {formatCurrency(token.current_price_usd || 0)}
            </p>
            <p className="text-xs text-gray-500 mt-1">USD</p>
          </div>
        </div>

        {/* Trade Dates */}
        {(token.first_buy_at || token.last_trade_at) && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              {token.first_buy_at && (
                <div>
                  <p className="text-gray-400 mb-1">First Trade</p>
                  <p className="text-white font-medium">
                    {new Date(token.first_buy_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </p>
                </div>
              )}
              {token.last_trade_at && (
                <div>
                  <p className="text-gray-400 mb-1">Last Trade</p>
                  <p className="text-white font-medium">
                    {new Date(token.last_trade_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
