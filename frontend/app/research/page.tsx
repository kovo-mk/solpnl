'use client';

import { useState } from 'react';

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
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<TokenReport | null>(null);
  const [error, setError] = useState('');

  const analyzeToken = async () => {
    if (!tokenAddress.trim()) {
      setError('Please enter a token address');
      return;
    }

    setLoading(true);
    setError('');
    setReport(null);

    try {
      // 1. Submit analysis request
      const response = await fetch('http://localhost:8000/api/research/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_address: tokenAddress.trim() }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit analysis request');
      }

      const { request_id } = await response.json();

      // 2. Poll for completion
      const checkStatus = async (): Promise<void> => {
        const statusRes = await fetch(`http://localhost:8000/api/research/status/${request_id}`);

        if (!statusRes.ok) {
          throw new Error('Failed to check status');
        }

        const status = await statusRes.json();

        if (status.status === 'completed') {
          // 3. Fetch full report
          const reportRes = await fetch(`http://localhost:8000/api/research/report/${status.report_id}`);

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
        return 'text-red-600';
      case 'high':
        return 'text-orange-600';
      case 'medium':
        return 'text-yellow-600';
      default:
        return 'text-green-600';
    }
  };

  const getRiskBgColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-red-50 border-red-200';
      case 'high':
        return 'bg-orange-50 border-orange-200';
      case 'medium':
        return 'bg-yellow-50 border-yellow-200';
      default:
        return 'bg-green-50 border-green-200';
    }
  };

  const getFlagBgColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-50 border-l-4 border-red-600';
      case 'high':
        return 'bg-orange-50 border-l-4 border-orange-600';
      case 'medium':
        return 'bg-yellow-50 border-l-4 border-yellow-600';
      default:
        return 'bg-blue-50 border-l-4 border-blue-600';
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Token Research</h1>
        <p className="text-gray-600">
          Analyze any Solana token for fraud patterns, holder concentration, and risk factors
        </p>
      </div>

      {/* Search Form */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Token Address
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={tokenAddress}
            onChange={(e) => setTokenAddress(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && analyzeToken()}
            placeholder="Enter Solana token mint address..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            onClick={analyzeToken}
            disabled={loading || !tokenAddress.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Example Tokens */}
        <div className="mt-4">
          <p className="text-xs text-gray-500 mb-2">Try these examples:</p>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setTokenAddress('CYtqp57NEdyetzbDfxVoJ19MWHvvVCQBL9jfFjXWpump')}
              className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full transition-colors"
              disabled={loading}
            >
              Oxedium (High Risk Example)
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="bg-white rounded-lg shadow-md p-12 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Analyzing token...</p>
          <p className="text-sm text-gray-500 mt-2">This may take 10-30 seconds</p>
        </div>
      )}

      {/* Report Display */}
      {report && !loading && (
        <div className="space-y-6">
          {/* Risk Score Card */}
          <div className={`rounded-lg shadow-md p-6 border-2 ${getRiskBgColor(report.risk_level)}`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className={`text-6xl font-bold ${getRiskColor(report.risk_level)}`}>
                  {report.risk_score}
                  <span className="text-2xl text-gray-500">/100</span>
                </div>
                <div className="text-xl font-medium text-gray-700 mt-2">
                  Risk Level: <span className={getRiskColor(report.risk_level)}>{report.risk_level.toUpperCase()}</span>
                </div>
              </div>
              <div className={`px-4 py-2 rounded-full text-sm font-medium ${
                report.verdict === 'safe' ? 'bg-green-200 text-green-800' :
                report.verdict === 'suspicious' ? 'bg-yellow-200 text-yellow-800' :
                report.verdict === 'likely_scam' ? 'bg-orange-200 text-orange-800' :
                'bg-red-200 text-red-800'
              }`}>
                {report.verdict.replace('_', ' ').toUpperCase()}
              </div>
            </div>
            <p className="text-gray-700 text-lg">{report.summary}</p>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="text-sm text-gray-500 mb-1">Total Holders</div>
              <div className="text-3xl font-bold">{report.total_holders.toLocaleString()}</div>
            </div>
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="text-sm text-gray-500 mb-1">Top 10 Hold</div>
              <div className="text-3xl font-bold">{report.top_10_holder_percentage.toFixed(1)}%</div>
            </div>
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="text-sm text-gray-500 mb-1">Whales (&gt;5%)</div>
              <div className="text-3xl font-bold">{report.whale_count}</div>
            </div>
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="text-sm text-gray-500 mb-1">Token Type</div>
              <div className="text-lg font-bold mt-2">
                {report.is_pump_fun ? '🚀 Pump.fun' : '📝 Custom'}
              </div>
            </div>
          </div>

          {/* Red Flags */}
          {report.red_flags.length > 0 && (
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-2xl font-bold mb-4 flex items-center">
                <span className="mr-2">🚩</span> Red Flags ({report.red_flags.length})
              </h3>
              <div className="space-y-3">
                {report.red_flags.map((flag, i) => (
                  <div key={i} className={`p-4 rounded-lg ${getFlagBgColor(flag.severity)}`}>
                    <div className="flex items-start justify-between mb-1">
                      <div className="font-bold text-gray-900">{flag.title}</div>
                      <span className="text-xs font-medium px-2 py-1 rounded-full bg-white">
                        {flag.severity.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-sm text-gray-700">{flag.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Contract Details */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-2xl font-bold mb-4">Contract Details</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className="text-sm text-gray-500 mb-1">Freeze Authority</div>
                <div className="font-medium">
                  {report.has_freeze_authority === true ? '❌ Enabled' :
                   report.has_freeze_authority === false ? '✅ Disabled' :
                   '❓ Unknown'}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500 mb-1">Mint Authority</div>
                <div className="font-medium">
                  {report.has_mint_authority === true ? '❌ Enabled' :
                   report.has_mint_authority === false ? '✅ Disabled' :
                   '❓ Unknown'}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500 mb-1">Token Address</div>
                <div className="font-mono text-xs truncate">{report.token_address}</div>
              </div>
            </div>
          </div>

          {/* Share/Export */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-xl font-bold mb-3">Share Report</h3>
            <div className="flex gap-3">
              <button
                onClick={() => navigator.clipboard.writeText(window.location.href)}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition-colors"
              >
                📋 Copy Link
              </button>
              <button
                onClick={() => {
                  const text = `Token Analysis Report\n\nRisk Score: ${report.risk_score}/100 (${report.risk_level})\n\n${report.summary}\n\nAnalyze tokens yourself at: ${window.location.origin}`;
                  navigator.clipboard.writeText(text);
                }}
                className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors"
              >
                📱 Copy for Telegram
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
