'use client';
// Token fraud detection and analysis page
import { useState, useEffect, useRef } from 'react';
import { Search, Twitter, Wallet, FileText, AlertCircle, Sun, Moon, Download } from 'lucide-react';
import { useReactToPrint } from 'react-to-print';

interface RedFlag {
  severity: string;
  title: string;
  description: string;
}

interface RelatedToken {
  token_address: string;
  token_name: string | null;
  token_symbol: string | null;
  token_logo_url: string | null;
  risk_score: number;
  risk_level: string;
  wash_trading_score: number | null;
  shared_wallet_count: number;
  total_suspicious_wallets: number;
  overlap_percentage: number;
  report_id: number;
  analyzed_at: string;
}

interface LiquidityPool {
  dex: string;
  pool_address: string;
  liquidity_usd: number;
  created_at: string;
  volume_24h?: number;
  price_usd?: number;
}

interface WhaleMovement {
  from: string;
  to: string;
  amount: number;
  amount_usd: number;
  timestamp: number;
  tx_signature: string;
}

interface TokenReport {
  token_address: string;
  risk_score: number;
  risk_level: string;
  verdict: string;
  summary: string;
  // Token metadata
  token_name?: string | null;
  token_symbol?: string | null;
  token_logo_url?: string | null;
  pair_created_at?: string | null;
  // Holder stats
  total_holders: number;  // Number analyzed (usually 20)
  total_holder_count?: number | null;  // Total from Solscan
  top_10_holder_percentage: number;
  whale_count: number;
  is_pump_fun: boolean;
  has_freeze_authority: boolean | null;
  has_mint_authority: boolean | null;
  // Wash trading metrics
  wash_trading_score?: number | null;
  wash_trading_likelihood?: string | null;
  unique_traders_24h?: number | null;
  volume_24h_usd?: number | null;
  txns_24h_total?: number | null;
  airdrop_likelihood?: string | null;
  liquidity_usd?: number | null;
  price_change_24h?: number | null;
  // Transaction breakdown
  transaction_breakdown?: {
    swaps: number;
    transfers: number;
    burns: number;
    other: number;
    total: number;
    by_type: Record<string, number>;
  };
  // Time period breakdowns
  time_periods?: {
    "24h"?: {
      total_transactions: number;
      unique_traders: number;
      wash_trading_score: number;
      suspicious_wallet_pairs: number;
      bot_wallets_detected: number;
    };
    "7d"?: {
      total_transactions: number;
      unique_traders: number;
      wash_trading_score: number;
      suspicious_wallet_pairs: number;
      bot_wallets_detected: number;
    };
    "30d"?: {
      total_transactions: number;
      unique_traders: number;
      wash_trading_score: number;
      suspicious_wallet_pairs: number;
      bot_wallets_detected: number;
    };
  };
  // Liquidity and whale tracking
  liquidity_pools?: string | null;  // JSON string
  whale_movements?: string | null;  // JSON string
  // Other
  red_flags: RedFlag[];
  suspicious_patterns: string[];
  pattern_transactions?: Record<string, string[]>;  // pattern_name -> [transaction_signatures]
  suspicious_wallets?: Array<{
    wallet1: string;
    wallet2?: string;
    wallet1_label?: string;
    wallet2_label?: string;
    trade_count: number;
    counterparties?: number;
    pattern: string;
  }>;
  twitter_handle: string | null;
  twitter_followers: number | null;
  telegram_members: number | null;
  github_repo_url: string | null;
  github_commit_count: number | null;
  created_at: string;
  updated_at: string;
}

export default function ResearchPage() {
  const [tokenAddress, setTokenAddress] = useState('');
  const [twitterHandle, setTwitterHandle] = useState('');
  const [walletAddress, setWalletAddress] = useState('');
  const [telegramUrl, setTelegramUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<TokenReport | null>(null);
  const [error, setError] = useState('');
  const [isDark, setIsDark] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);
  const [selectedPattern, setSelectedPattern] = useState<{name: string, transactions: string[]} | null>(null);
  const [relatedTokens, setRelatedTokens] = useState<RelatedToken[]>([]);
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [selectedRelatedToken, setSelectedRelatedToken] = useState<RelatedToken | null>(null);
  const [sharedWallets, setSharedWallets] = useState<any[]>([]);
  const [loadingSharedWallets, setLoadingSharedWallets] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'network' | 'liquidity' | 'whales'>('overview');
  const [liquidityPools, setLiquidityPools] = useState<LiquidityPool[]>([]);
  const [whaleMovements, setWhaleMovements] = useState<WhaleMovement[]>([]);

  // Initialize theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const shouldBeDark = savedTheme === 'dark' || (!savedTheme && prefersDark);
    setIsDark(shouldBeDark);
    if (shouldBeDark) {
      document.documentElement.classList.add('dark');
    }
  }, []);

  // Toggle theme
  const toggleTheme = () => {
    setIsDark(!isDark);
    if (!isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  };

  // Parse liquidity pools and whale movements when report loads
  useEffect(() => {
    if (report) {
      // Parse liquidity pools
      if (report.liquidity_pools) {
        try {
          const pools = JSON.parse(report.liquidity_pools);
          setLiquidityPools(pools);
        } catch (e) {
          console.error('Failed to parse liquidity_pools:', e);
          setLiquidityPools([]);
        }
      } else {
        setLiquidityPools([]);
      }

      // Parse whale movements
      if (report.whale_movements) {
        try {
          const whales = JSON.parse(report.whale_movements);
          setWhaleMovements(whales);
        } catch (e) {
          console.error('Failed to parse whale_movements:', e);
          setWhaleMovements([]);
        }
      } else {
        setWhaleMovements([]);
      }
    }
  }, [report]);

  // PDF Export handler
  const handlePrint = useReactToPrint({
    contentRef: printRef,
    documentTitle: `Token-Analysis-${report?.token_symbol || report?.token_address?.slice(0, 8) || 'Report'}`,
    pageStyle: `
      @page {
        size: A4;
        margin: 20mm;
      }
      @media print {
        body {
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }
        .no-print {
          display: none !important;
        }
      }
    `,
  });

  const analyzeToken = async () => {
    // At least one field must be filled
    if (!tokenAddress.trim() && !twitterHandle.trim() && !walletAddress.trim()) {
      setError('Please enter at least one search parameter (token, Twitter, or wallet)');
      return;
    }

    setLoading(true);
    setError('');
    setReport(null);

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

      // 1. Submit analysis request with all provided fields
      const response = await fetch(`${API_BASE}/research/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_address: tokenAddress.trim() || undefined,
          twitter_handle: twitterHandle.trim() || undefined,
          wallet_address: walletAddress.trim() || undefined,
          telegram_url: telegramUrl.trim() || undefined,
          force_refresh: true,  // Always force fresh analysis (bypass cache)
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit analysis request');
      }

      const { request_id } = await response.json();

      // 2. Poll for completion
      const checkStatus = async (): Promise<void> => {
        const statusRes = await fetch(`${API_BASE}/research/status/${request_id}`);

        if (!statusRes.ok) {
          throw new Error('Failed to check status');
        }

        const status = await statusRes.json();

        if (status.status === 'completed') {
          // 3. Fetch full report
          const reportRes = await fetch(`${API_BASE}/research/report/${status.report_id}`);

          if (!reportRes.ok) {
            throw new Error('Failed to fetch report');
          }

          const reportData = await reportRes.json();
          setReport(reportData);

          // Fetch related tokens in the background
          if (reportData.token_address) {
            fetchRelatedTokens(reportData.token_address);
          }

          setLoading(false);
        } else if (status.status === 'failed') {
          setError('Analysis failed. Please try again.');
          setLoading(false);
        } else {
          // Still processing, check again in 2 seconds
          setTimeout(checkStatus, 2000);
        }
      };

      checkStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setLoading(false);
    }
  };

  const fetchRelatedTokens = async (tokenAddress: string) => {
    setLoadingRelated(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      const response = await fetch(`${API_BASE}/research/related-tokens/${tokenAddress}`);

      if (!response.ok) {
        console.error('Failed to fetch related tokens');
        setRelatedTokens([]);
        return;
      }

      const data = await response.json();
      setRelatedTokens(data.related_tokens || []);
    } catch (err) {
      console.error('Error fetching related tokens:', err);
      setRelatedTokens([]);
    } finally {
      setLoadingRelated(false);
    }
  };

  const fetchSharedWallets = async (token1: string, token2: string) => {
    setLoadingSharedWallets(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      const response = await fetch(`${API_BASE}/research/shared-wallets/${token1}/${token2}`);

      if (!response.ok) {
        console.error('Failed to fetch shared wallets');
        setSharedWallets([]);
        return;
      }

      const data = await response.json();
      setSharedWallets(data.shared_wallets || []);
    } catch (err) {
      console.error('Error fetching shared wallets:', err);
      setSharedWallets([]);
    } finally {
      setLoadingSharedWallets(false);
    }
  };

  const handleRelatedTokenClick = async (relatedToken: RelatedToken) => {
    setSelectedRelatedToken(relatedToken);
    if (report) {
      await fetchSharedWallets(report.token_address, relatedToken.token_address);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'text-red-600 dark:text-red-400';
      case 'high':
        return 'text-orange-600 dark:text-orange-400';
      case 'medium':
        return 'text-yellow-600 dark:text-yellow-400';
      default:
        return 'text-green-600 dark:text-green-400';
    }
  };

  const getRiskBgColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
      case 'high':
        return 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800';
      case 'medium':
        return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800';
      default:
        return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
    }
  };

  const getFlagBgColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-50 dark:bg-red-900/20 border-l-4 border-red-600 dark:border-red-500';
      case 'high':
        return 'bg-orange-50 dark:bg-orange-900/20 border-l-4 border-orange-600 dark:border-orange-500';
      case 'medium':
        return 'bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-600 dark:border-yellow-500';
      default:
        return 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-600 dark:border-blue-500';
    }
  };

  const loadExample = (type: 'oxedium' | 'pumpdotfun') => {
    if (type === 'oxedium') {
      setTokenAddress('CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump');
      setTwitterHandle('');
      setWalletAddress('');
    } else {
      setTokenAddress('');
      setTwitterHandle('@pumpdotfun');
      setWalletAddress('');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-3 text-gray-900 dark:text-white">Token Research v2.1</h1>
            <p className="text-gray-600 dark:text-gray-400 text-sm sm:text-base md:text-lg">
              AI-powered analysis to detect fraud patterns, holder concentration, and risk factors
            </p>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="ml-4 p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shadow-sm no-print"
            aria-label="Toggle theme"
          >
            {isDark ? (
              <Sun className="w-5 h-5 text-yellow-500" />
            ) : (
              <Moon className="w-5 h-5 text-gray-700" />
            )}
          </button>
        </div>

        {/* Search Form */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-8 border border-gray-200 dark:border-gray-700 no-print">
          <div className="space-y-4">
            {/* Token Address Input */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <FileText className="w-4 h-4" />
                Token Address
              </label>
              <input
                type="text"
                value={tokenAddress}
                onChange={(e) => setTokenAddress(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeToken()}
                placeholder="Enter Solana token mint address (e.g., CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump)"
                className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-colors"
                disabled={loading}
              />
            </div>

            {/* Twitter Handle Input */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Twitter className="w-4 h-4" />
                Twitter/X Handle (Optional)
              </label>
              <input
                type="text"
                value={twitterHandle}
                onChange={(e) => setTwitterHandle(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeToken()}
                placeholder="Enter Twitter handle (e.g., @pumpdotfun or pumpdotfun)"
                className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-colors"
                disabled={loading}
              />
            </div>

            {/* Telegram URL Input */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18 1.897-.962 6.502-1.359 8.627-.168.9-.5 1.201-.82 1.23-.697.064-1.226-.461-1.901-.903-1.056-.693-1.653-1.124-2.678-1.8-1.185-.781-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.248-.024c-.106.024-1.793 1.139-5.062 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.241-1.865-.44-.752-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.831-2.529 6.998-3.015 3.332-1.386 4.025-1.627 4.476-1.635.099-.002.321.023.465.141.121.099.155.232.171.326.016.094.037.308.021.475z"/></svg>
                Telegram Channel/Group (Optional)
              </label>
              <input
                type="text"
                value={telegramUrl}
                onChange={(e) => setTelegramUrl(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeToken()}
                placeholder="Enter Telegram URL (e.g., https://t.me/channel_name)"
                className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-colors"
                disabled={loading}
              />
            </div>

            {/* Wallet Address Input */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Wallet className="w-4 h-4" />
                Wallet Address (Optional)
              </label>
              <input
                type="text"
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeToken()}
                placeholder="Enter wallet address to analyze holdings (e.g., 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU)"
                className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-colors"
                disabled={loading}
              />
            </div>

            {/* Analyze Button */}
            <button
              type="button"
              onClick={analyzeToken}
              disabled={loading || (!tokenAddress.trim() && !twitterHandle.trim() && !walletAddress.trim())}
              className="w-full px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-md hover:shadow-lg flex items-center justify-center gap-2 text-lg"
            >
              <Search className="w-5 h-5" />
              {loading ? 'Analyzing...' : 'Analyze Token'}
            </button>
          </div>

          {error && (
            <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Example Buttons */}
          <div className="mt-5 pt-5 border-t border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 font-medium">Try these examples:</p>
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => loadExample('oxedium')}
                className="text-sm px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg transition-colors"
                disabled={loading}
              >
                Oxedium (High Risk Token)
              </button>
              <button
                type="button"
                onClick={() => loadExample('pumpdotfun')}
                className="text-sm px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg transition-colors"
                disabled={loading}
              >
                @pumpdotfun (Twitter)
              </button>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-12 text-center border border-gray-200 dark:border-gray-700 no-print">
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-4 border-gray-200 dark:border-gray-700 border-t-blue-600 mb-4"></div>
            <p className="text-gray-900 dark:text-white font-medium text-lg">Analyzing token...</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">This may take 10-30 seconds</p>
          </div>
        )}

        {/* Report Display */}
        {report && !loading && (
          <div className="space-y-6">
            {/* Export PDF Button */}
            <div className="flex justify-end no-print">
              <button
                type="button"
                onClick={handlePrint}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-lg font-medium shadow-md hover:shadow-lg transition-all"
              >
                <Download className="w-5 h-5" />
                Export PDF
              </button>
            </div>

            {/* Printable Report Content */}
            <div ref={printRef}>
            {/* Pump.fun Warning */}
            {report.is_pump_fun && (
              <div className="rounded-xl shadow-lg p-6 border-2 bg-purple-50 dark:bg-purple-900/20 border-purple-500">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-6 h-6 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-1" />
                  <div>
                    <h3 className="text-lg font-bold text-purple-900 dark:text-purple-100 mb-2">
                      Pump.fun Token Detected
                    </h3>
                    <p className="text-purple-800 dark:text-purple-200">
                      This token was created on pump.fun (address ends with &quot;pump&quot;). These tokens often have:
                    </p>
                    <ul className="list-disc list-inside mt-2 space-y-1 text-purple-800 dark:text-purple-200">
                      <li>High volatility and speculation</li>
                      <li>Anonymous or pseudonymous developers</li>
                      <li>Minimal project infrastructure</li>
                      <li>Higher risk of rug pulls</li>
                    </ul>
                    <p className="mt-3 text-sm text-purple-700 dark:text-purple-300 font-medium">
                      Exercise extreme caution and only invest what you can afford to lose.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Wash Trading Warning */}
            {report.wash_trading_likelihood && ['high', 'critical'].includes(report.wash_trading_likelihood.toLowerCase()) && (
              <div className="rounded-xl shadow-lg p-6 border-2 bg-red-50 dark:bg-red-900/20 border-red-500">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0 mt-1" />
                  <div>
                    <h3 className="text-lg font-bold text-red-900 dark:text-red-100 mb-2">
                      Wash Trading Detected
                    </h3>
                    <p className="text-red-800 dark:text-red-200 mb-2">
                      This token shows strong indicators of wash trading (artificial volume):
                    </p>
                    <div className="grid grid-cols-2 gap-3 my-3 text-sm">
                      <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                        <div className="text-gray-600 dark:text-gray-400">Wash Trading Score</div>
                        <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                          {report.wash_trading_score}/100
                        </div>
                      </div>
                      {report.unique_traders_24h !== null && report.unique_traders_24h !== undefined && report.txns_24h_total && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                          <div className="text-gray-600 dark:text-gray-400">Trader/Txn Ratio</div>
                          <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                            {((report.unique_traders_24h / report.txns_24h_total) * 100).toFixed(1)}%
                          </div>
                        </div>
                      )}
                    </div>
                    <p className="text-sm text-red-700 dark:text-red-300 font-medium">
                      ⚠️ Volume may be artificially inflated by the same wallets trading back and forth. Exercise extreme caution.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Airdrop Scheme Warning */}
            {report.airdrop_likelihood && ['high', 'critical'].includes(report.airdrop_likelihood.toLowerCase()) && (
              <div className="rounded-xl shadow-lg p-6 border-2 bg-orange-50 dark:bg-orange-900/20 border-orange-500">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-6 h-6 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-1" />
                  <div>
                    <h3 className="text-lg font-bold text-orange-900 dark:text-orange-100 mb-2">
                      Airdrop Scheme Detected
                    </h3>
                    <p className="text-orange-800 dark:text-orange-200">
                      This token shows signs of a mass airdrop scheme:
                    </p>
                    <ul className="list-disc list-inside mt-2 space-y-1 text-orange-800 dark:text-orange-200">
                      <li>Many holders received identical token amounts</li>
                      <li>Likely used to create artificial holder count</li>
                      <li>Recipients may dump tokens immediately</li>
                      <li>Could be a Sybil attack (one person, many wallets)</li>
                    </ul>
                    <p className="mt-3 text-sm text-orange-700 dark:text-orange-300 font-medium">
                      High risk of coordinated dump. Holder count may be misleading.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Tab Navigation */}
            <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 mb-6 -mx-6 px-6">
              <div className="flex overflow-x-auto scrollbar-hide scroll-smooth" style={{ scrollSnapType: 'x mandatory' }}>
                {[
                  { id: 'overview', label: 'Overview', icon: '📊' },
                  { id: 'network', label: 'Network', icon: '🕸️' },
                  { id: 'liquidity', label: 'Liquidity', icon: '💧' },
                  { id: 'whales', label: 'Whales', icon: '🐋' }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id as 'overview' | 'network' | 'liquidity' | 'whales')}
                    className={`
                      flex-shrink-0 px-4 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-semibold whitespace-nowrap transition-all duration-200
                      border-b-2 scroll-snap-align-start min-h-[44px] flex items-center
                      ${activeTab === tab.id
                        ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-600'
                      }
                    `}
                    style={{ scrollSnapAlign: 'start' }}
                  >
                    <span className="mr-1 sm:mr-2 text-base sm:text-lg">{tab.icon}</span>
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {/* Token Metadata */}
                {(report.token_name || report.token_symbol || report.token_logo_url || report.pair_created_at) && (
                  <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-xl shadow-md p-6 border border-blue-200 dark:border-blue-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-3">
                  {report.token_logo_url && (
                    <img
                      src={report.token_logo_url}
                      alt={report.token_name || 'Token logo'}
                      className="w-10 h-10 rounded-full border-2 border-white dark:border-gray-700 shadow-md"
                      onError={(e) => { e.currentTarget.style.display = 'none'; }}
                    />
                  )}
                  <span>🪙 Token Information</span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {report.token_name && (
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Token Name</div>
                      <div className="text-xl font-bold text-gray-900 dark:text-white">{report.token_name}</div>
                    </div>
                  )}
                  {report.token_symbol && (
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Symbol</div>
                      <div className="text-xl font-bold text-gray-900 dark:text-white">${report.token_symbol}</div>
                    </div>
                  )}
                  {report.pair_created_at && (
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Pair Created</div>
                      <div className="text-lg font-bold text-gray-900 dark:text-white">
                        {new Date(report.pair_created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric'
                        })}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {Math.floor((Date.now() - new Date(report.pair_created_at).getTime()) / (1000 * 60 * 60 * 24))} days ago
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Risk Score Card */}
            <div className={`rounded-xl shadow-lg p-8 border-2 ${getRiskBgColor(report.risk_level)}`}>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <div className={`text-7xl font-bold ${getRiskColor(report.risk_level)}`}>
                    {report.risk_score}
                    <span className="text-3xl text-gray-500 dark:text-gray-400">/100</span>
                  </div>
                  <div className="text-xl font-medium text-gray-700 dark:text-gray-300 mt-3">
                    Risk Level: <span className={getRiskColor(report.risk_level)}>{report.risk_level.toUpperCase()}</span>
                  </div>
                </div>
                <div className={`px-6 py-3 rounded-full text-sm font-bold shadow-md ${
                  report.verdict === 'safe' ? 'bg-green-200 dark:bg-green-900 text-green-800 dark:text-green-200' :
                  report.verdict === 'suspicious' ? 'bg-yellow-200 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200' :
                  report.verdict === 'likely_scam' ? 'bg-orange-200 dark:bg-orange-900 text-orange-800 dark:text-orange-200' :
                  'bg-red-200 dark:bg-red-900 text-red-800 dark:text-red-200'
                }`}>
                  {report.verdict.replace('_', ' ').toUpperCase()}
                </div>
              </div>
              <p className="text-gray-700 dark:text-gray-300 text-lg leading-relaxed">{report.summary}</p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Total Holders</div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">
                  {report.total_holder_count ? report.total_holder_count.toLocaleString() : 'N/A'}
                </div>
                {report.total_holder_count && (
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Analyzed top {report.total_holders}
                  </div>
                )}
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Top 10 Concentration</div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{report.top_10_holder_percentage.toFixed(1)}%</div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2">
                  Whale Count
                  <span className="group relative cursor-help">
                    <AlertCircle className="w-4 h-4 text-gray-400" />
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-64 p-3 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded-lg shadow-lg z-10">
                      Number of wallets holding more than 5% of total supply. High whale counts indicate concentration risk - these large holders can dump tokens and crash the price.
                      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900 dark:border-t-gray-700"></div>
                    </div>
                  </span>
                </div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{report.whale_count}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Wallets holding &gt;5% supply
                </div>
              </div>
            </div>

            {/* Market Data & Wash Trading Analysis */}
            {(report.volume_24h_usd || report.liquidity_usd || report.wash_trading_score !== null) && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">📊 Market & Trading Analysis</h2>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Volume 24h */}
                  {report.volume_24h_usd !== null && report.volume_24h_usd !== undefined && report.volume_24h_usd > 0 && (
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">24h Volume</div>
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">
                        ${(report.volume_24h_usd || 0).toLocaleString()}
                      </div>
                      {report.price_change_24h !== null && report.price_change_24h !== undefined && (
                        <div className={`text-sm mt-1 ${report.price_change_24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {report.price_change_24h >= 0 ? '↑' : '↓'} {Math.abs(report.price_change_24h).toFixed(2)}%
                        </div>
                      )}
                    </div>
                  )}

                  {/* Liquidity */}
                  {report.liquidity_usd !== null && report.liquidity_usd !== undefined && report.liquidity_usd > 0 && (
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Liquidity</div>
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">
                        ${(report.liquidity_usd || 0).toLocaleString()}
                      </div>
                    </div>
                  )}

                  {/* Unique Traders */}
                  {report.unique_traders_24h !== null && report.unique_traders_24h !== undefined && (
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Unique Traders (24h)</div>
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">
                        {report.unique_traders_24h}
                      </div>
                      {report.txns_24h_total !== null && report.txns_24h_total !== undefined && (
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {report.txns_24h_total} total txns
                        </div>
                      )}
                    </div>
                  )}

                  {/* Wash Trading Score */}
                  {report.wash_trading_score !== null && report.wash_trading_score !== undefined && (
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Wash Trading Risk</div>
                      <div className={`text-2xl font-bold ${
                        report.wash_trading_score >= 75 ? 'text-red-600' :
                        report.wash_trading_score >= 50 ? 'text-orange-600' :
                        report.wash_trading_score >= 25 ? 'text-yellow-600' :
                        'text-green-600'
                      }`}>
                        {report.wash_trading_score}/100
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 capitalize">
                        {report.wash_trading_likelihood || 'low'} likelihood
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Transaction Pattern Analysis */}
            {report.wash_trading_score !== null && report.wash_trading_score !== undefined && report.wash_trading_score > 0 && report.unique_traders_24h && report.txns_24h_total && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🔍 Transaction Pattern Analysis</h2>

                {/* Summary Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Transactions Analyzed</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">{report.txns_24h_total}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">Last 30 days</div>
                  </div>

                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Unique Wallets</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">{report.unique_traders_24h}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">Trading wallets</div>
                  </div>

                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Trader/Txn Ratio</div>
                    <div className={`text-xl font-bold ${
                      (report.unique_traders_24h / report.txns_24h_total) < 0.2 ? 'text-red-600' :
                      (report.unique_traders_24h / report.txns_24h_total) < 0.4 ? 'text-orange-600' :
                      'text-green-600'
                    }`}>
                      {((report.unique_traders_24h / report.txns_24h_total) * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {(report.unique_traders_24h / report.txns_24h_total) < 0.2 ? 'Very Low ⚠️' :
                       (report.unique_traders_24h / report.txns_24h_total) < 0.4 ? 'Low ⚠️' :
                       'Normal ✓'}
                    </div>
                  </div>

                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Manipulation Score</div>
                    <div className={`text-xl font-bold ${
                      report.wash_trading_score >= 75 ? 'text-red-600' :
                      report.wash_trading_score >= 50 ? 'text-orange-600' :
                      report.wash_trading_score >= 25 ? 'text-yellow-600' :
                      'text-green-600'
                    }`}>
                      {report.wash_trading_score}/100
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 capitalize">
                      {report.wash_trading_likelihood} risk
                    </div>
                  </div>
                </div>

                {/* Time Period Breakdowns */}
                {report.time_periods && (
                  <div className="mb-6 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg p-5 border border-purple-200 dark:border-purple-700">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">⏰ Activity by Time Period</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* 24h Period */}
                      {report.time_periods["24h"] && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                          <div className="text-sm font-semibold text-purple-600 dark:text-purple-400 mb-3">Last 24 Hours</div>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Transactions:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["24h"].total_transactions}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Unique Traders:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["24h"].unique_traders}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Risk Score:</span>
                              <span className={`text-sm font-bold ${
                                report.time_periods["24h"].wash_trading_score >= 75 ? 'text-red-600' :
                                report.time_periods["24h"].wash_trading_score >= 50 ? 'text-orange-600' :
                                report.time_periods["24h"].wash_trading_score >= 25 ? 'text-yellow-600' :
                                'text-green-600'
                              }`}>
                                {report.time_periods["24h"].wash_trading_score}/100
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Suspicious Pairs:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["24h"].suspicious_wallet_pairs}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 7d Period */}
                      {report.time_periods["7d"] && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                          <div className="text-sm font-semibold text-blue-600 dark:text-blue-400 mb-3">Last 7 Days</div>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Transactions:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["7d"].total_transactions}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Unique Traders:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["7d"].unique_traders}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Risk Score:</span>
                              <span className={`text-sm font-bold ${
                                report.time_periods["7d"].wash_trading_score >= 75 ? 'text-red-600' :
                                report.time_periods["7d"].wash_trading_score >= 50 ? 'text-orange-600' :
                                report.time_periods["7d"].wash_trading_score >= 25 ? 'text-yellow-600' :
                                'text-green-600'
                              }`}>
                                {report.time_periods["7d"].wash_trading_score}/100
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Suspicious Pairs:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["7d"].suspicious_wallet_pairs}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 30d Period */}
                      {report.time_periods["30d"] && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                          <div className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 mb-3">Last 30 Days</div>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Transactions:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["30d"].total_transactions}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Unique Traders:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["30d"].unique_traders}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Risk Score:</span>
                              <span className={`text-sm font-bold ${
                                report.time_periods["30d"].wash_trading_score >= 75 ? 'text-red-600' :
                                report.time_periods["30d"].wash_trading_score >= 50 ? 'text-orange-600' :
                                report.time_periods["30d"].wash_trading_score >= 25 ? 'text-yellow-600' :
                                'text-green-600'
                              }`}>
                                {report.time_periods["30d"].wash_trading_score}/100
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Suspicious Pairs:</span>
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{report.time_periods["30d"].suspicious_wallet_pairs}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Transaction Type Breakdown */}
                {report.transaction_breakdown && (
                  <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg p-5 border border-blue-200 dark:border-blue-700">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">📊 Transaction Type Breakdown</h3>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{report.transaction_breakdown.swaps}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Swaps</div>
                        <div className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">
                          {report.transaction_breakdown.total > 0 ? ((report.transaction_breakdown.swaps / report.transaction_breakdown.total) * 100).toFixed(0) : 0}%
                        </div>
                      </div>
                      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">{report.transaction_breakdown.transfers}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Transfers</div>
                        <div className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">
                          {report.transaction_breakdown.total > 0 ? ((report.transaction_breakdown.transfers / report.transaction_breakdown.total) * 100).toFixed(0) : 0}%
                        </div>
                      </div>
                      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">{report.transaction_breakdown.burns}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Burns</div>
                        <div className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">
                          {report.transaction_breakdown.total > 0 ? ((report.transaction_breakdown.burns / report.transaction_breakdown.total) * 100).toFixed(0) : 0}%
                        </div>
                      </div>
                      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">{report.transaction_breakdown.other}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Other</div>
                        <div className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">
                          {report.transaction_breakdown.total > 0 ? ((report.transaction_breakdown.other / report.transaction_breakdown.total) * 100).toFixed(0) : 0}%
                        </div>
                      </div>
                      <div className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-green-600 dark:text-green-400">{report.transaction_breakdown.total}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Total</div>
                        <div className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">100%</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Pattern Breakdown */}
                {report.suspicious_patterns && report.suspicious_patterns.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Detected Manipulation Patterns</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {report.suspicious_patterns.includes('extreme_wash_trading') && (
                        <div
                          className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 cursor-pointer hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                          onClick={() => {
                            if (!report) return;
                            const txs = report.pattern_transactions?.['extreme_wash_trading'] || [];
                            if (txs.length > 0) {
                              setSelectedPattern({name: 'Extreme Wash Trading', transactions: txs});
                            }
                          }}
                        >
                          <div className="font-semibold text-red-900 dark:text-red-100">Extreme Wash Trading</div>
                          <div className="text-sm text-red-700 dark:text-red-300">Same wallet pairs trading 10+ times</div>
                          <div className="text-xs text-red-600 dark:text-red-400 mt-1">
                            +30 risk points
                            {report?.pattern_transactions?.['extreme_wash_trading']?.length && report.pattern_transactions['extreme_wash_trading'].length > 0 && (
                              <span className="ml-2">• {report.pattern_transactions['extreme_wash_trading'].length} transactions</span>
                            )}
                          </div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('repeated_wallet_pairs') && (
                        <div
                          className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3 cursor-pointer hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors"
                          onClick={() => {
                            if (!report) return;
                            const txs = report.pattern_transactions?.['repeated_wallet_pairs'] || [];
                            if (txs.length > 0) {
                              setSelectedPattern({name: 'Repeated Trading Pairs', transactions: txs});
                            }
                          }}
                        >
                          <div className="font-semibold text-orange-900 dark:text-orange-100">Repeated Trading Pairs</div>
                          <div className="text-sm text-orange-700 dark:text-orange-300">Wallets trading repeatedly together</div>
                          <div className="text-xs text-orange-600 dark:text-orange-400 mt-1">
                            +10-40 risk points
                            {report?.pattern_transactions?.['repeated_wallet_pairs']?.length && report.pattern_transactions['repeated_wallet_pairs'].length > 0 && (
                              <span className="ml-2">• {report.pattern_transactions['repeated_wallet_pairs'].length} transactions</span>
                            )}
                          </div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('very_low_unique_traders') && (
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                          <div className="font-semibold text-red-900 dark:text-red-100">Very Low Unique Traders</div>
                          <div className="text-sm text-red-700 dark:text-red-300">{'<20% unique wallets - artificial volume'}</div>
                          <div className="text-xs text-red-600 dark:text-red-400 mt-1">+35 risk points</div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('low_unique_traders') && (
                        <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
                          <div className="font-semibold text-orange-900 dark:text-orange-100">Low Unique Traders</div>
                          <div className="text-sm text-orange-700 dark:text-orange-300">{'<40% unique wallets - suspicious activity'}</div>
                          <div className="text-xs text-orange-600 dark:text-orange-400 mt-1">+20 risk points</div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('bot_trading_detected') && (
                        <div
                          className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 cursor-pointer hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                          onClick={() => {
                            if (!report) return;
                            const txs = report.pattern_transactions?.['bot_trading_detected'] || [];
                            if (txs.length > 0) {
                              setSelectedPattern({name: 'Bot Trading Detected', transactions: txs});
                            }
                          }}
                        >
                          <div className="font-semibold text-red-900 dark:text-red-100">Bot Trading Detected</div>
                          <div className="text-sm text-red-700 dark:text-red-300">Automated rapid trading detected</div>
                          <div className="text-xs text-red-600 dark:text-red-400 mt-1">
                            +25 risk points
                            {report?.pattern_transactions?.['bot_trading_detected']?.length && report.pattern_transactions['bot_trading_detected'].length > 0 && (
                              <span className="ml-2">• {report.pattern_transactions['bot_trading_detected'].length} transactions</span>
                            )}
                          </div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('isolated_trading_groups') && (
                        <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
                          <div className="font-semibold text-orange-900 dark:text-orange-100">Isolated Trading Groups</div>
                          <div className="text-sm text-orange-700 dark:text-orange-300">Wallets only trading with 1-2 others</div>
                          <div className="text-xs text-orange-600 dark:text-orange-400 mt-1">+20 risk points</div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('circular_trading_detected') && (
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                          <div className="font-semibold text-red-900 dark:text-red-100">Circular Trading Detected</div>
                          <div className="text-sm text-red-700 dark:text-red-300">A→B→C→A trading rings found</div>
                          <div className="text-xs text-red-600 dark:text-red-400 mt-1">+30 risk points</div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('high_top5_concentration') && (
                        <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
                          <div className="font-semibold text-orange-900 dark:text-orange-100">High Holder Concentration</div>
                          <div className="text-sm text-orange-700 dark:text-orange-300">Top 5 holders control {'>'} 50% of supply</div>
                          <div className="text-xs text-orange-600 dark:text-orange-400 mt-1">+15 risk points</div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Key Insights */}
                <div className="mt-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">💡 What This Means</h3>
                  <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
                    {(report.unique_traders_24h / report.txns_24h_total) < 0.2 && (
                      <li>• Very few unique traders relative to transaction volume suggests wash trading</li>
                    )}
                    {report.suspicious_patterns.includes('extreme_wash_trading') && (
                      <li>• Same wallets trading repeatedly indicates artificial volume creation</li>
                    )}
                    {report.suspicious_patterns.includes('bot_trading_detected') && (
                      <li>• Bot activity detected - likely automated market manipulation</li>
                    )}
                    {report.suspicious_patterns.includes('circular_trading_detected') && (
                      <li>• Circular trading patterns suggest coordinated manipulation scheme</li>
                    )}
                    {report.wash_trading_score >= 75 && (
                      <li>• <strong>CRITICAL:</strong> Multiple manipulation indicators - avoid this token</li>
                    )}
                  </ul>
                </div>
              </div>
            )}

            {/* Suspicious Wallets */}
            {report.suspicious_wallets && report.suspicious_wallets.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">👛 Suspicious Wallets</h2>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Wallets involved in manipulation patterns (DEX programs filtered out)
                </p>
                <div className="space-y-3">
                  {report.suspicious_wallets.slice(0, 10).map((wallet: any, idx: number) => (
                    <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-orange-600 dark:text-orange-400 uppercase">
                            {wallet.pattern?.replace(/_/g, ' ')}
                          </span>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {wallet.trade_count} trades
                          </span>
                        </div>
                        <div className="font-mono text-sm text-gray-900 dark:text-white break-all">
                          {wallet.wallet1}
                          {wallet.wallet1_label && (
                            <span className="ml-2 text-xs text-blue-600 dark:text-blue-400">({wallet.wallet1_label})</span>
                          )}
                        </div>
                        {wallet.wallet2 && (
                          <div className="text-xs text-gray-600 dark:text-gray-400">
                            Trading with: <span className="font-mono">{wallet.wallet2.slice(0, 8)}...{wallet.wallet2.slice(-8)}</span>
                            {wallet.wallet2_label && (
                              <span className="ml-2 text-blue-600 dark:text-blue-400">({wallet.wallet2_label})</span>
                            )}
                          </div>
                        )}
                        {wallet.counterparties && (
                          <div className="text-xs text-gray-600 dark:text-gray-400">
                            Unique counterparties: {wallet.counterparties}
                          </div>
                        )}
                        <a
                          href={`https://solscan.io/account/${wallet.wallet1}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          View on Solscan →
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
                {report.suspicious_wallets.length > 10 && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">
                    Showing 10 of {report.suspicious_wallets.length} suspicious wallets
                  </p>
                )}
              </div>
            )}

            {/* Red Flags */}
            {report.red_flags.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🚩 Red Flags</h2>
                <div className="space-y-3">
                  {report.red_flags.map((flag, idx) => (
                    <div key={idx} className={`p-4 rounded-lg ${getFlagBgColor(flag.severity)}`}>
                      <div className="font-semibold text-gray-900 dark:text-white mb-1">{flag.title}</div>
                      <div className="text-sm text-gray-700 dark:text-gray-300">{flag.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Suspicious Patterns */}
            {report.suspicious_patterns.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">⚠️ Suspicious Patterns</h2>
                <ul className="space-y-2">
                  {report.suspicious_patterns.map((pattern, idx) => (
                    <li key={idx} className="flex items-start gap-3 text-gray-700 dark:text-gray-300">
                      <span className="text-orange-500 mt-1">•</span>
                      <span>{pattern}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

                {/* Social/Technical Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Social */}
                  {(report.twitter_handle || report.telegram_members) && (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Social Media</h3>
                      <div className="space-y-3">
                        {report.twitter_handle && (
                          <div>
                            <div className="text-sm text-gray-600 dark:text-gray-400">Twitter</div>
                            <div className="text-gray-900 dark:text-white font-medium">
                              {report.twitter_handle} ({report.twitter_followers?.toLocaleString() || 0} followers)
                            </div>
                          </div>
                        )}
                        {report.telegram_members && (
                          <div>
                            <div className="text-sm text-gray-600 dark:text-gray-400">Telegram</div>
                            <div className="text-gray-900 dark:text-white font-medium">
                              {report.telegram_members.toLocaleString()} members
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Technical */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Technical Info</h3>
                    <div className="space-y-3">
                      <div>
                        <div className="text-sm text-gray-600 dark:text-gray-400">Pump.fun Token</div>
                        <div className="text-gray-900 dark:text-white font-medium">{report.is_pump_fun ? 'Yes' : 'No'}</div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-600 dark:text-gray-400">Freeze Authority</div>
                        <div className="text-gray-900 dark:text-white font-medium">
                          {report.has_freeze_authority === null ? 'Unknown' : report.has_freeze_authority ? 'Enabled ⚠️' : 'Disabled ✓'}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-600 dark:text-gray-400">Mint Authority</div>
                        <div className="text-gray-900 dark:text-white font-medium">
                          {report.has_mint_authority === null ? 'Unknown' : report.has_mint_authority ? 'Enabled ⚠️' : 'Disabled ✓'}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Network Tab */}
            {activeTab === 'network' && (
              <div className="space-y-6">
            {/* Related Manipulated Tokens */}
            {relatedTokens.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🕸️ Related Manipulated Tokens</h2>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  These tokens share suspicious wallets with the current token, indicating possible coordinated manipulation networks.
                </p>
                <div className="space-y-3">
                  {relatedTokens.map((token, idx) => (
                    <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-start gap-3">
                        {/* Token logo */}
                        {token.token_logo_url && (
                          <img
                            src={token.token_logo_url}
                            alt={token.token_symbol || 'Token'}
                            className="w-10 h-10 rounded-full flex-shrink-0"
                            onError={(e) => { e.currentTarget.style.display = 'none'; }}
                          />
                        )}

                        <div className="flex-1 min-w-0">
                          {/* Token name and symbol */}
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                              {token.token_name || 'Unknown Token'}
                            </h3>
                            {token.token_symbol && (
                              <span className="text-sm text-gray-600 dark:text-gray-400">
                                ({token.token_symbol})
                              </span>
                            )}
                          </div>

                          {/* Wallet overlap info */}
                          <div className="flex items-center gap-4 mb-2 text-sm">
                            <span className="text-gray-700 dark:text-gray-300">
                              <span className="font-semibold text-orange-600 dark:text-orange-400">
                                {token.shared_wallet_count}
                              </span> shared suspicious wallets ({token.overlap_percentage}% overlap)
                            </span>
                          </div>

                          {/* Risk metrics */}
                          <div className="flex items-center gap-4 text-sm flex-wrap">
                            <div>
                              <span className="text-gray-600 dark:text-gray-400">Risk Score: </span>
                              <span className={`font-semibold ${getRiskColor(token.risk_level)}`}>
                                {token.risk_score}/100
                              </span>
                            </div>
                            {token.wash_trading_score !== null && token.wash_trading_score !== undefined && (
                              <div>
                                <span className="text-gray-600 dark:text-gray-400">Wash Trading: </span>
                                <span className={`font-semibold ${token.wash_trading_score > 70 ? 'text-red-600 dark:text-red-400' : token.wash_trading_score > 40 ? 'text-orange-600 dark:text-orange-400' : 'text-yellow-600 dark:text-yellow-400'}`}>
                                  {token.wash_trading_score}/100
                                </span>
                              </div>
                            )}
                            <div>
                              <span className="text-gray-600 dark:text-gray-400">Risk Level: </span>
                              <span className={`font-semibold uppercase ${getRiskColor(token.risk_level)}`}>
                                {token.risk_level}
                              </span>
                            </div>
                          </div>

                          {/* Token address (truncated) */}
                          <div className="mt-2 text-xs text-gray-500 dark:text-gray-500 font-mono">
                            {token.token_address.slice(0, 8)}...{token.token_address.slice(-8)}
                          </div>

                          {/* Action buttons */}
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => handleRelatedTokenClick(token)}
                              className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-sm rounded-lg transition-colors"
                            >
                              View Shared Wallets ({token.shared_wallet_count})
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setTokenAddress(token.token_address);
                                setReport(null);
                                setRelatedTokens([]);
                                analyzeToken();
                              }}
                              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
                            >
                              View Full Report →
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {loadingRelated && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🕸️ Related Manipulated Tokens</h2>
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-3 text-gray-600 dark:text-gray-400">Loading related tokens...</span>
                </div>
              </div>
            )}

            {/* Show placeholder when no related tokens found */}
            {!loadingRelated && relatedTokens.length === 0 && report && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🕸️ Related Manipulated Tokens</h2>
                <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
                  <div className="text-center">
                    <div className="text-4xl mb-3">🔍</div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Related Tokens Found</h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                      This token doesn't share suspicious wallets with other analyzed tokens yet.
                    </p>
                    <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-700">
                      <p className="text-xs text-gray-700 dark:text-gray-300">
                        <strong>How it works:</strong> When you analyze multiple tokens, this section will show tokens that share
                        2+ suspicious wallets, helping you identify coordinated manipulation networks and scam rings.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
              </div>
            )}

            {/* Liquidity Tab */}
            {activeTab === 'liquidity' && (
              <div className="space-y-6">
                {liquidityPools.length > 0 ? (
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">💧 Liquidity Pools</h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                      DEX pools where this token can be traded. Higher liquidity generally indicates more stable trading.
                    </p>
                    <div className="space-y-4">
                      {liquidityPools.map((pool, idx) => (
                        <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                                {pool.dex}
                              </div>
                              <div className="text-sm text-gray-600 dark:text-gray-400">
                                {pool.created_at && `Created: ${new Date(pool.created_at).toLocaleDateString()}`}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                                ${pool.liquidity_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">Liquidity</div>
                            </div>
                          </div>
                          {pool.volume_24h && (
                            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                              24h Volume: ${pool.volume_24h.toLocaleString()}
                            </div>
                          )}
                          <div className="flex items-center gap-2 mt-3">
                            <a
                              href={`https://solscan.io/account/${pool.pool_address}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition-colors flex items-center gap-2"
                            >
                              View Pool on Solscan →
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">💧 Liquidity Pools</h2>
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
                      <div className="text-center">
                        <div className="text-4xl mb-3">🔍</div>
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Liquidity Pools Found</h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          No DEX pools were detected for this token. This could indicate limited trading availability.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Whales Tab */}
            {activeTab === 'whales' && (
              <div className="space-y-6">
                {whaleMovements.length > 0 ? (
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🐋 Whale Movements</h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                      Large transfers over $10,000 USD. Whale activity can signal major price movements.
                    </p>
                    <div className="space-y-4">
                      {whaleMovements.map((whale, idx) => {
                        const date = new Date(whale.timestamp * 1000);
                        const now = Date.now();
                        const diffHours = Math.floor((now - date.getTime()) / (1000 * 60 * 60));
                        const timeAgo = diffHours < 24
                          ? `${diffHours} hours ago`
                          : `${Math.floor(diffHours / 24)} days ago`;

                        return (
                          <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
                            <div className="flex items-start justify-between mb-4">
                              <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                                ${whale.amount_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </div>
                              <div className="text-right">
                                <div className="text-sm text-gray-600 dark:text-gray-400">{timeAgo}</div>
                                <div className="text-xs text-gray-500 dark:text-gray-500">
                                  {date.toLocaleDateString()} {date.toLocaleTimeString()}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-3 mb-3">
                              <div className="flex-1">
                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">From</div>
                                <div className="font-mono text-sm text-gray-900 dark:text-white truncate">
                                  {whale.from}
                                </div>
                              </div>
                              <div className="text-2xl text-gray-400">→</div>
                              <div className="flex-1">
                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">To</div>
                                <div className="font-mono text-sm text-gray-900 dark:text-white truncate">
                                  {whale.to}
                                </div>
                              </div>
                            </div>

                            <div className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                              Amount: {whale.amount.toLocaleString()} tokens
                            </div>

                            <div className="flex flex-wrap gap-2">
                              <a
                                href={`https://solscan.io/account/${whale.from}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white text-xs rounded-md transition-colors"
                              >
                                From Wallet →
                              </a>
                              <a
                                href={`https://solscan.io/account/${whale.to}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white text-xs rounded-md transition-colors"
                              >
                                To Wallet →
                              </a>
                              <a
                                href={`https://solscan.io/tx/${whale.tx_signature}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-md transition-colors"
                              >
                                View Transaction →
                              </a>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">🐋 Whale Movements</h2>
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
                      <div className="text-center">
                        <div className="text-4xl mb-3">🔍</div>
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Whale Activity Detected</h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          No transfers over $10,000 were found recently. This could indicate low whale interest.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
            {/* End of Printable Report Content */}
            </div>
          </div>
        )}

        {/* Shared Wallets Modal */}
        {selectedRelatedToken && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedRelatedToken(null)}>
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-start">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    Shared Suspicious Wallets
                  </h2>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-600 dark:text-gray-400">Between</span>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {report?.token_symbol || 'Current Token'}
                    </span>
                    <span className="text-gray-600 dark:text-gray-400">and</span>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {selectedRelatedToken.token_symbol || selectedRelatedToken.token_name}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedRelatedToken(null)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-2xl"
                >
                  ✕
                </button>
              </div>
              <div className="p-6 overflow-y-auto max-h-[60vh]">
                {loadingSharedWallets ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
                    <span className="ml-3 text-gray-600 dark:text-gray-400">Loading shared wallets...</span>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                      Found {sharedWallets.length} wallet{sharedWallets.length !== 1 ? 's' : ''} that appear suspicious in both tokens ({selectedRelatedToken.overlap_percentage}% overlap)
                    </p>
                    <div className="space-y-3">
                      {sharedWallets.map((wallet, idx) => (
                        <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="font-mono text-sm text-gray-900 dark:text-white break-all mb-2">
                                {wallet.wallet_address}
                              </div>
                              <div className="flex flex-wrap gap-3 text-xs text-gray-600 dark:text-gray-400">
                                {wallet.pattern_type && (
                                  <div>
                                    <span className="font-semibold">Pattern:</span>{' '}
                                    <span className="text-orange-600 dark:text-orange-400">
                                      {wallet.pattern_type.replace(/_/g, ' ')}
                                    </span>
                                  </div>
                                )}
                                <div>
                                  <span className="font-semibold">{report?.token_symbol || 'Token 1'} trades:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{wallet.token1_trade_count}</span>
                                </div>
                                <div>
                                  <span className="font-semibold">{selectedRelatedToken.token_symbol || 'Token 2'} trades:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{wallet.token2_trade_count}</span>
                                </div>
                                <div>
                                  <span className="font-semibold">Total trades:</span>{' '}
                                  <span className="text-orange-600 dark:text-orange-400 font-semibold">{wallet.total_trade_count}</span>
                                </div>
                              </div>
                            </div>
                            <a
                              href={`https://solscan.io/account/${wallet.wallet_address}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-sm rounded-lg whitespace-nowrap transition-colors text-center"
                            >
                              View on Solscan →
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Transaction Modal */}
        {selectedPattern && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedPattern(null)}>
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{selectedPattern.name}</h2>
                <button
                  type="button"
                  onClick={() => setSelectedPattern(null)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  ✕
                </button>
              </div>
              <div className="p-6 overflow-y-auto max-h-[60vh]">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Found {selectedPattern.transactions.length} suspicious transaction{selectedPattern.transactions.length !== 1 ? 's' : ''} matching this pattern
                </p>
                <div className="space-y-2">
                  {selectedPattern.transactions.map((signature, idx) => (
                    <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-center justify-between">
                        <div className="font-mono text-sm text-gray-900 dark:text-white truncate flex-1">
                          {signature}
                        </div>
                        <a
                          href={`https://solscan.io/tx/${signature}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-md whitespace-nowrap transition-colors"
                        >
                          View on Solscan →
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
