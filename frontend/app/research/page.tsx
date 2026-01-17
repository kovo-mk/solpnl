'use client';

import { useState, useEffect } from 'react';
import { Search, Twitter, Wallet, FileText, AlertCircle, Sun, Moon } from 'lucide-react';

interface RedFlag {
  severity: string;
  title: string;
  description: string;
}

interface TokenReport {
  token_address: string;
  risk_score: number;
  risk_level: string;
  verdict: string;
  summary: string;
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
  // Other
  red_flags: RedFlag[];
  suspicious_patterns: string[];
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
            <h1 className="text-4xl font-bold mb-3 text-gray-900 dark:text-white">Token Research v2.1</h1>
            <p className="text-gray-600 dark:text-gray-400 text-lg">
              AI-powered analysis to detect fraud patterns, holder concentration, and risk factors
            </p>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="ml-4 p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shadow-sm"
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
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-8 border border-gray-200 dark:border-gray-700">
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
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-12 text-center border border-gray-200 dark:border-gray-700">
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-4 border-gray-200 dark:border-gray-700 border-t-blue-600 mb-4"></div>
            <p className="text-gray-900 dark:text-white font-medium text-lg">Analyzing token...</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">This may take 10-30 seconds</p>
          </div>
        )}

        {/* Report Display */}
        {report && !loading && (
          <div className="space-y-6">
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
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">Last 7 days</div>
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

                {/* Pattern Breakdown */}
                {report.suspicious_patterns && report.suspicious_patterns.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Detected Manipulation Patterns</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {report.suspicious_patterns.includes('extreme_wash_trading') && (
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                          <div className="font-semibold text-red-900 dark:text-red-100">Extreme Wash Trading</div>
                          <div className="text-sm text-red-700 dark:text-red-300">Same wallet pairs trading 10+ times</div>
                          <div className="text-xs text-red-600 dark:text-red-400 mt-1">+30 risk points</div>
                        </div>
                      )}

                      {report.suspicious_patterns.includes('repeated_wallet_pairs') && (
                        <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
                          <div className="font-semibold text-orange-900 dark:text-orange-100">Repeated Trading Pairs</div>
                          <div className="text-sm text-orange-700 dark:text-orange-300">Wallets trading repeatedly together</div>
                          <div className="text-xs text-orange-600 dark:text-orange-400 mt-1">+10-40 risk points</div>
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
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                          <div className="font-semibold text-red-900 dark:text-red-100">Bot Trading Detected</div>
                          <div className="text-sm text-red-700 dark:text-red-300">Automated rapid trading detected</div>
                          <div className="text-xs text-red-600 dark:text-red-400 mt-1">+25 risk points</div>
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
      </div>
    </div>
  );
}
