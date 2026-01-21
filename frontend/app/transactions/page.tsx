'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  RefreshCw,
  ExternalLink,
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
  Send,
  Download,
  History,
  BarChart3,
  Sun,
  Moon,
  WalletIcon,
  LineChart,
} from 'lucide-react';
import { api, type Wallet, type WalletTransactionHistory, type TokenTransactionGroup, type TokenTransaction } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';

const shortenAddress = (address: string) => `${address.slice(0, 4)}...${address.slice(-4)}`;

export default function TransactionsPage() {
  const { theme, toggleTheme } = useTheme();
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [selectedWallet, setSelectedWallet] = useState<string | null>(null);
  const [history, setHistory] = useState<WalletTransactionHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedToken, setExpandedToken] = useState<string | null>(null);

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

  // Fetch transaction history
  const fetchHistory = useCallback(async () => {
    if (!selectedWallet) {
      setHistory(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const data = await api.getWalletTransactionsDetailed(selectedWallet);
      setHistory(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      setHistory(null);
    } finally {
      setLoading(false);
    }
  }, [selectedWallet]);

  useEffect(() => {
    fetchWallets();
  }, [fetchWallets]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const formatAmount = (amount: number) => {
    if (amount >= 1000000) return (amount / 1000000).toFixed(2) + 'M';
    if (amount >= 1000) return (amount / 1000).toFixed(2) + 'K';
    if (amount >= 1) return amount.toFixed(2);
    if (amount >= 0.0001) return amount.toFixed(4);
    return amount > 0 ? amount.toExponential(2) : '0.00';
  };

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const TransactionRow = ({ tx, type }: { tx: TokenTransaction; type: 'buy' | 'sell' | 'transfer_out' | 'transfer_in' }) => {
    const icon = type === 'buy' ? (
      <ArrowDownRight className="w-4 h-4 text-green-500" />
    ) : type === 'sell' ? (
      <ArrowUpRight className="w-4 h-4 text-red-500" />
    ) : type === 'transfer_out' ? (
      <Send className="w-4 h-4 text-orange-500" />
    ) : (
      <Download className="w-4 h-4 text-blue-500" />
    );

    const typeLabel = type === 'buy' ? 'Buy' : type === 'sell' ? 'Sell' : type === 'transfer_out' ? 'Sent' : 'Received';
    const typeColor = type === 'buy' ? 'text-green-600 dark:text-green-400' : type === 'sell' ? 'text-red-600 dark:text-red-400' : type === 'transfer_out' ? 'text-orange-600 dark:text-orange-400' : 'text-blue-600 dark:text-blue-400';

    return (
      <div className="flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-lg transition-colors">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="flex-shrink-0">{icon}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={cn('font-medium text-sm', typeColor)}>{typeLabel}</span>
              <a
                href={`https://solscan.io/tx/${tx.signature}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                title="View on Solscan"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">{formatTimestamp(tx.timestamp)}</p>
            {(type === 'transfer_out' || type === 'transfer_in') && (
              <p className="text-xs text-gray-400 dark:text-gray-500 truncate" title={type === 'transfer_out' ? tx.to : tx.from}>
                {type === 'transfer_out' ? 'To: ' : 'From: '}
                {shortenAddress(type === 'transfer_out' ? tx.to : tx.from)}
              </p>
            )}
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="font-medium text-sm text-gray-900 dark:text-white">{formatAmount(tx.amount)}</p>
          <p className="text-xs text-gray-500">{tx.type}</p>
        </div>
      </div>
    );
  };

  const TokenCard = ({ token }: { token: TokenTransactionGroup }) => {
    const isExpanded = expandedToken === token.mint;
    const totalActivity = token.buy_count + token.sell_count + token.transfer_out_count + token.transfer_in_count;

    return (
      <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden transition-colors">
        <button
          onClick={() => setExpandedToken(isExpanded ? null : token.mint)}
          className="w-full p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors text-left"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                <span className="text-xs font-bold text-gray-600 dark:text-gray-400">
                  {token.symbol.slice(0, 2)}
                </span>
              </div>
              <div>
                <h3 className="font-bold text-gray-900 dark:text-white">{token.symbol}</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">{totalActivity} transactions</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right hidden sm:block">
                <div className="flex gap-3 text-sm">
                  {token.buy_count > 0 && (
                    <span className="text-green-600 dark:text-green-400">{token.buy_count} buys</span>
                  )}
                  {token.sell_count > 0 && (
                    <span className="text-red-600 dark:text-red-400">{token.sell_count} sells</span>
                  )}
                  {token.transfer_out_count > 0 && (
                    <span className="text-orange-600 dark:text-orange-400">{token.transfer_out_count} sent</span>
                  )}
                  {token.transfer_in_count > 0 && (
                    <span className="text-blue-600 dark:text-blue-400">{token.transfer_in_count} received</span>
                  )}
                </div>
              </div>
              <History className={cn('w-5 h-5 text-gray-400 transition-transform', isExpanded && 'rotate-180')} />
            </div>
          </div>
        </button>

        {isExpanded && (
          <div className="border-t border-gray-200 dark:border-gray-700 p-4 space-y-2 bg-gray-50/50 dark:bg-gray-900/30">
            {token.buys.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Buys ({token.buy_count})</h4>
                {token.buys.map((tx) => (
                  <TransactionRow key={tx.signature} tx={tx} type="buy" />
                ))}
              </div>
            )}
            {token.sells.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Sells ({token.sell_count})</h4>
                {token.sells.map((tx) => (
                  <TransactionRow key={tx.signature} tx={tx} type="sell" />
                ))}
              </div>
            )}
            {token.transfers_out.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Sent ({token.transfer_out_count})</h4>
                {token.transfers_out.map((tx) => (
                  <TransactionRow key={tx.signature} tx={tx} type="transfer_out" />
                ))}
              </div>
            )}
            {token.transfers_in.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Received ({token.transfer_in_count})</h4>
                {token.transfers_in.map((tx) => (
                  <TransactionRow key={tx.signature} tx={tx} type="transfer_in" />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gradient-to-b dark:from-gray-900 dark:to-black pb-20 md:pb-0 transition-colors">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm sticky top-0 z-40 transition-colors">
        <div className="max-w-7xl mx-auto px-3 py-2.5 md:px-4 md:py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link href="/" className="flex items-center gap-2">
                <div className="p-1.5 bg-gradient-to-br from-sol-purple to-sol-green rounded-lg">
                  <BarChart3 className="w-5 h-5 text-white" />
                </div>
                <span className="text-lg font-bold text-gray-900 dark:text-white">SolPnL</span>
              </Link>

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
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <LineChart className="w-4 h-4" />
                  P&L
                </Link>
                <Link
                  href="/transactions"
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800"
                >
                  <History className="w-4 h-4" />
                  Transactions
                </Link>
              </nav>
            </div>

            <div className="flex items-center gap-2">
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

              {wallets.length > 0 && (
                <select
                  value={selectedWallet || ''}
                  onChange={(e) => setSelectedWallet(e.target.value)}
                  className="px-2 md:px-3 py-1.5 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs md:text-sm max-w-[100px] sm:max-w-[140px] md:max-w-[180px] text-gray-900 dark:text-white"
                >
                  {wallets.map((wallet) => (
                    <option key={wallet.address} value={wallet.address}>
                      {wallet.label ? `${wallet.label.slice(0, 12)}${wallet.label.length > 12 ? '...' : ''}` : shortenAddress(wallet.address)}
                    </option>
                  ))}
                </select>
              )}

              <button
                type="button"
                onClick={fetchHistory}
                disabled={loading || !selectedWallet}
                className="hidden md:flex items-center gap-1.5 px-3 py-1.5 bg-sol-purple hover:bg-sol-purple/80 rounded-lg font-medium transition-colors disabled:opacity-50 text-sm text-white"
              >
                <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-3 py-4 md:px-4 md:py-6">
        {/* Summary Stats */}
        {history && !loading && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Transactions</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{history.total_transactions.toLocaleString()}</p>
            </div>
            <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Unique Tokens</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{history.unique_tokens}</p>
            </div>
            <div className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Cached</p>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {history.cached_at ? new Date(history.cached_at).toLocaleDateString() : 'N/A'}
              </p>
            </div>
          </div>
        )}

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
            <p className="text-sm mt-2">
              Make sure to fetch transaction history first using the wallet-complete-history endpoint.
            </p>
          </div>
        )}

        {/* Token List */}
        {history && !loading && (
          <div className="space-y-3">
            {history.tokens.map((token) => (
              <TokenCard key={token.mint} token={token} />
            ))}

            {history.tokens.length === 0 && (
              <div className="text-center py-20 text-gray-500">
                No transaction history found. Sync your wallet first.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
