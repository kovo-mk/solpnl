'use client';

import { useState } from 'react';
import { Search, Twitter, Wallet, FileText, AlertCircle } from 'lucide-react';

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
  total_holders: number;
  top_10_holder_percentage: number;
  whale_count: number;
  is_pump_fun: boolean;
  has_freeze_authority: boolean | null;
  has_mint_authority: boolean | null;
  red_flags: RedFlag[];
  suspicious_patterns: string[];
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
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<TokenReport | null>(null);
  const [error, setError] = useState('');

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
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-3 text-gray-900 dark:text-white">Token Research</h1>
          <p className="text-gray-600 dark:text-gray-400 text-lg">
            AI-powered analysis to detect fraud patterns, holder concentration, and risk factors
          </p>
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
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{report.total_holders.toLocaleString()}</div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Top 10 Concentration</div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{report.top_10_holder_percentage.toFixed(1)}%</div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6 border border-gray-200 dark:border-gray-700">
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Whale Count</div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{report.whale_count}</div>
              </div>
            </div>

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
