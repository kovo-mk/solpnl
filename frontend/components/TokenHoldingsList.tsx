'use client';

import { useState } from 'react';
import { Search, ExternalLink, ChevronDown, ChevronUp, ShieldCheck, ShieldOff, EyeOff, Eye } from 'lucide-react';
import { type TokenBalance, type Transaction, api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface TokenHoldingsListProps {
  tokens: TokenBalance[];
  walletAddress: string;
  onTokenVerificationChange?: () => void;
}

type TabType = 'all' | 'verified' | 'hidden';

export default function TokenHoldingsList({ tokens, walletAddress, onTokenVerificationChange }: TokenHoldingsListProps) {
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<TabType>('all');
  const [expandedToken, setExpandedToken] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<Record<string, Transaction[]>>({});
  const [loadingTx, setLoadingTx] = useState<string | null>(null);
  const [togglingVerification, setTogglingVerification] = useState<string | null>(null);
  const [togglingHidden, setTogglingHidden] = useState<string | null>(null);
  const [localVerification, setLocalVerification] = useState<Record<string, boolean>>({});
  const [localHidden, setLocalHidden] = useState<Record<string, boolean>>({});

  // Get verification/hidden status (local state takes precedence)
  const isTokenVerified = (token: TokenBalance) => {
    if (localVerification[token.mint] !== undefined) {
      return localVerification[token.mint];
    }
    return token.is_verified;
  };

  const isTokenHidden = (token: TokenBalance) => {
    if (localHidden[token.mint] !== undefined) {
      return localHidden[token.mint];
    }
    return token.is_hidden;
  };

  // Filter tokens by search and tab
  const filteredTokens = tokens.filter((token) => {
    const query = search.toLowerCase();
    const matchesSearch =
      token.symbol.toLowerCase().includes(query) ||
      token.name.toLowerCase().includes(query) ||
      token.mint.toLowerCase().includes(query);

    if (!matchesSearch) return false;

    const hidden = isTokenHidden(token);
    const verified = isTokenVerified(token);

    switch (activeTab) {
      case 'verified':
        return verified && !hidden;
      case 'hidden':
        return hidden;
      case 'all':
      default:
        return !hidden;
    }
  });

  // Sort tokens: verified first, then by value
  const sortedTokens = [...filteredTokens].sort((a, b) => {
    // SOL always first
    if (a.mint === 'So11111111111111111111111111111111111111112') return -1;
    if (b.mint === 'So11111111111111111111111111111111111111112') return 1;

    const aVerified = isTokenVerified(a);
    const bVerified = isTokenVerified(b);

    // Verified tokens first
    if (aVerified && !bVerified) return -1;
    if (!aVerified && bVerified) return 1;

    // Then by value
    const aValue = a.value_usd || 0;
    const bValue = b.value_usd || 0;
    return bValue - aValue;
  });

  // Count tokens by category
  const verifiedCount = tokens.filter(t => isTokenVerified(t) && !isTokenHidden(t)).length;
  const hiddenCount = tokens.filter(t => isTokenHidden(t)).length;
  const allCount = tokens.filter(t => !isTokenHidden(t)).length;

  // Open DexScreener
  const openDexScreener = (mint: string) => {
    window.open(`https://dexscreener.com/solana/${mint}`, '_blank');
  };

  // Toggle token verification
  const handleToggleVerification = async (mint: string, e: React.MouseEvent) => {
    e.stopPropagation();
    // Don't allow toggling SOL
    if (mint === 'So11111111111111111111111111111111111111112') return;

    setTogglingVerification(mint);
    try {
      const result = await api.toggleTokenVerification(mint);
      setLocalVerification((prev) => ({ ...prev, [mint]: result.is_verified }));
      // Refresh balances to update wallet value
      if (onTokenVerificationChange) {
        onTokenVerificationChange();
      }
    } catch (err) {
      console.error('Failed to toggle verification:', err);
    } finally {
      setTogglingVerification(null);
    }
  };

  // Toggle token hidden
  const handleToggleHidden = async (mint: string, e: React.MouseEvent) => {
    e.stopPropagation();
    // Don't allow hiding SOL
    if (mint === 'So11111111111111111111111111111111111111112') return;

    setTogglingHidden(mint);
    try {
      const result = await api.toggleTokenHidden(mint);
      setLocalHidden((prev) => ({ ...prev, [mint]: result.is_hidden }));
      setLocalVerification((prev) => ({ ...prev, [mint]: result.is_verified }));
      // Refresh balances to update wallet value
      if (onTokenVerificationChange) {
        onTokenVerificationChange();
      }
    } catch (err) {
      console.error('Failed to toggle hidden:', err);
    } finally {
      setTogglingHidden(null);
    }
  };

  // Fetch transactions for a token
  const fetchTransactions = async (mint: string) => {
    if (transactions[mint]) {
      // Already loaded
      setExpandedToken(expandedToken === mint ? null : mint);
      return;
    }

    setLoadingTx(mint);
    try {
      const txs = await api.getWalletTransactions(walletAddress, mint, 50);
      setTransactions((prev) => ({ ...prev, [mint]: txs }));
      setExpandedToken(mint);
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
    } finally {
      setLoadingTx(null);
    }
  };

  const formatBalance = (balance: number) => {
    if (balance >= 1000000) return (balance / 1000000).toFixed(2) + 'M';
    if (balance >= 1000) return (balance / 1000).toFixed(2) + 'K';
    if (balance >= 1) return balance.toFixed(2);
    if (balance >= 0.0001) return balance.toFixed(4);
    return balance.toExponential(2);
  };

  const formatUSD = (value: number | null) => {
    if (value === null) return '-';
    return '$' + value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden">
      {/* Header with tabs and search */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">Current Holdings</h3>
          <span className="text-sm text-gray-400">{sortedTokens.length} tokens</span>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => setActiveTab('all')}
            className={cn(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'all'
                ? 'bg-sol-purple text-white'
                : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700'
            )}
          >
            All ({allCount})
          </button>
          <button
            onClick={() => setActiveTab('verified')}
            className={cn(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1',
              activeTab === 'verified'
                ? 'bg-green-500/30 text-green-400'
                : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700'
            )}
          >
            <ShieldCheck className="w-3 h-3" />
            Verified ({verifiedCount})
          </button>
          <button
            onClick={() => setActiveTab('hidden')}
            className={cn(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1',
              activeTab === 'hidden'
                ? 'bg-red-500/30 text-red-400'
                : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700'
            )}
          >
            <EyeOff className="w-3 h-3" />
            Hidden ({hiddenCount})
          </button>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search by name, symbol, or address..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-sm placeholder-gray-500 focus:outline-none focus:border-sol-purple"
          />
        </div>
      </div>

      {/* Token list */}
      <div className="max-h-[500px] overflow-y-auto">
        {sortedTokens.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {search ? 'No tokens match your search' : activeTab === 'hidden' ? 'No hidden tokens' : activeTab === 'verified' ? 'No verified tokens' : 'No tokens found'}
          </div>
        ) : (
          <div className="divide-y divide-gray-700/50">
            {sortedTokens.map((token) => (
              <div key={token.mint} className="hover:bg-gray-700/30 transition-colors">
                {/* Token row */}
                <div className="p-4 flex items-center gap-4">
                  {/* Logo */}
                  <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                    {token.logo_url ? (
                      <img src={token.logo_url} alt={token.symbol} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-xs font-bold text-gray-400">
                        {token.symbol.slice(0, 2)}
                      </span>
                    )}
                  </div>

                  {/* Token info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{token.symbol}</span>
                      <button
                        type="button"
                        onClick={() => openDexScreener(token.mint)}
                        className="p-1 hover:bg-gray-600 rounded transition-colors"
                        title="View on DexScreener"
                      >
                        <ExternalLink className="w-3 h-3 text-gray-400" />
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 truncate">{token.name}</p>
                  </div>

                  {/* Balance */}
                  <div className="text-right">
                    <p className="font-medium">{formatBalance(token.balance)}</p>
                    <p className={cn(
                      'text-sm',
                      token.value_usd ? 'text-gray-300' : 'text-gray-500'
                    )}>
                      {formatUSD(token.value_usd)}
                    </p>
                  </div>

                  {/* Verification toggle */}
                  <button
                    type="button"
                    onClick={(e) => handleToggleVerification(token.mint, e)}
                    disabled={togglingVerification === token.mint || token.mint === 'So11111111111111111111111111111111111111112'}
                    className={cn(
                      'p-2 rounded-lg transition-colors',
                      isTokenVerified(token)
                        ? 'bg-green-500/20 hover:bg-green-500/30 text-green-400'
                        : 'bg-gray-700/50 hover:bg-gray-700 text-gray-500',
                      token.mint === 'So11111111111111111111111111111111111111112' && 'cursor-default',
                      togglingVerification === token.mint && 'opacity-50'
                    )}
                    title={isTokenVerified(token) ? 'Verified (counts towards wallet value)' : 'Not verified (click to verify)'}
                  >
                    {togglingVerification === token.mint ? (
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : isTokenVerified(token) ? (
                      <ShieldCheck className="w-4 h-4" />
                    ) : (
                      <ShieldOff className="w-4 h-4" />
                    )}
                  </button>

                  {/* Hide toggle */}
                  <button
                    type="button"
                    onClick={(e) => handleToggleHidden(token.mint, e)}
                    disabled={togglingHidden === token.mint || token.mint === 'So11111111111111111111111111111111111111112'}
                    className={cn(
                      'p-2 rounded-lg transition-colors',
                      isTokenHidden(token)
                        ? 'bg-red-500/20 hover:bg-red-500/30 text-red-400'
                        : 'bg-gray-700/50 hover:bg-gray-700 text-gray-500',
                      token.mint === 'So11111111111111111111111111111111111111112' && 'cursor-default',
                      togglingHidden === token.mint && 'opacity-50'
                    )}
                    title={isTokenHidden(token) ? 'Hidden (click to unhide)' : 'Click to hide (scam airdrop)'}
                  >
                    {togglingHidden === token.mint ? (
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : isTokenHidden(token) ? (
                      <Eye className="w-4 h-4" />
                    ) : (
                      <EyeOff className="w-4 h-4" />
                    )}
                  </button>

                  {/* Expand button for transactions */}
                  <button
                    type="button"
                    onClick={() => fetchTransactions(token.mint)}
                    className="p-2 hover:bg-gray-600 rounded-lg transition-colors"
                    title="View transactions"
                  >
                    {loadingTx === token.mint ? (
                      <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                    ) : expandedToken === token.mint ? (
                      <ChevronUp className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    )}
                  </button>
                </div>

                {/* Transactions dropdown */}
                {expandedToken === token.mint && transactions[token.mint] && (
                  <div className="px-4 pb-4">
                    <div className="bg-gray-900/50 rounded-lg overflow-hidden">
                      <div className="p-3 border-b border-gray-700 flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-300">
                          Transaction History
                        </span>
                        <button
                          onClick={() => openDexScreener(token.mint)}
                          className="text-xs text-sol-purple hover:underline flex items-center gap-1"
                        >
                          View on DexScreener <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>

                      {transactions[token.mint].length === 0 ? (
                        <div className="p-4 text-center text-sm text-gray-500">
                          No swap transactions found for this token
                        </div>
                      ) : (
                        <div className="divide-y divide-gray-800">
                          {transactions[token.mint].map((tx) => (
                            <div key={tx.signature} className="p-3 flex items-center gap-3 text-sm">
                              <span className={cn(
                                'px-2 py-0.5 rounded text-xs font-medium',
                                tx.tx_type === 'buy'
                                  ? 'bg-green-500/20 text-green-400'
                                  : 'bg-red-500/20 text-red-400'
                              )}>
                                {tx.tx_type.toUpperCase()}
                              </span>
                              <div className="flex-1">
                                <span className="text-gray-300">
                                  {formatBalance(tx.amount_token)} {token.symbol}
                                </span>
                                <span className="text-gray-500 mx-2">for</span>
                                <span className="text-gray-300">
                                  {tx.amount_sol.toFixed(4)} SOL
                                </span>
                              </div>
                              <div className="text-right text-gray-500">
                                <p>{formatDate(tx.block_time)}</p>
                                <a
                                  href={`https://solscan.io/tx/${tx.signature}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-sol-purple hover:underline"
                                >
                                  View tx
                                </a>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
