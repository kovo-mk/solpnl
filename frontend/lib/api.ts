/**
 * API client for SolPnL backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// Session token management
let sessionToken: string | null = null;

export function setSessionToken(token: string | null) {
  sessionToken = token;
}

export function getSessionToken(): string | null {
  // First check memory, then localStorage
  if (sessionToken) return sessionToken;
  if (typeof window !== 'undefined') {
    return localStorage.getItem('solpnl_session_token');
  }
  return null;
}

// Auth response types
export interface AuthNonceResponse {
  nonce: string;
  message: string;
  pubkey: string;
}

export interface AuthVerifyResponse {
  session_token: string;
  pubkey: string;
  expires_at: string | null;
}

export interface Wallet {
  id: number;
  address: string;
  label: string | null;
  is_active: boolean;
  last_synced: string | null;
  created_at: string;
}

export interface Token {
  address: string;
  symbol: string | null;
  name: string | null;
  decimals: number;
  logo_url: string | null;
  current_price_usd: number | null;
}

export interface TokenPnL {
  token_address: string;
  token_symbol: string;
  token_name: string;
  token_logo: string | null;
  current_balance: number;
  avg_buy_price_sol: number;
  avg_buy_price_usd: number | null;
  total_cost_sol: number;
  current_price_usd: number | null;
  current_value_usd: number | null;
  unrealized_pnl_sol: number;
  unrealized_pnl_usd: number | null;
  unrealized_pnl_percent: number | null;
  realized_pnl_sol: number;
  realized_pnl_usd: number;
  total_bought: number;
  total_sold: number;
  total_buy_sol: number;
  total_sell_sol: number;
  trade_count: number;
  first_trade: string | null;
  last_trade: string | null;
}

export interface Portfolio {
  wallet_address: string;
  wallet_label: string | null;
  total_value_usd: number;
  total_cost_sol: number;
  total_unrealized_pnl_usd: number;
  total_realized_pnl_sol: number;
  total_realized_pnl_usd: number;
  token_count: number;
  tokens: TokenPnL[];
  last_synced: string | null;
}

export interface MultiWalletPortfolio {
  total_value_usd: number;
  total_unrealized_pnl_usd: number;
  total_realized_pnl_usd: number;
  wallet_count: number;
  token_count: number;
  wallets: Portfolio[];
}

export interface SyncStatus {
  wallet_address: string;
  status: 'pending' | 'syncing' | 'completed' | 'error' | 'unknown';
  transactions_fetched: number;
  swaps_found: number;
  message: string | null;
}

export interface Transaction {
  id: number;
  signature: string;
  tx_type: 'buy' | 'sell';
  amount_token: number;
  amount_sol: number;
  price_per_token: number | null;
  price_usd: number | null;
  realized_pnl_sol: number | null;
  realized_pnl_usd: number | null;
  dex_name: string | null;
  block_time: string | null;
  token: Token | null;
}

export interface TokenBalance {
  mint: string;
  symbol: string;
  name: string;
  logo_url: string | null;
  balance: number;
  price_usd: number | null;
  value_usd: number | null;
  is_verified: boolean;
  is_hidden: boolean;
}

export interface WalletBalances {
  wallet_address: string;
  sol_balance: number;
  sol_price_usd: number;
  sol_value_usd: number;
  tokens: TokenBalance[];
  total_token_value_usd: number;
  verified_token_value_usd: number;
  total_portfolio_value_usd: number;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    // Build headers with optional auth
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    // Add auth header if we have a session token
    const token = getSessionToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  // ============ Auth Endpoints ============

  async getAuthNonce(pubkey: string): Promise<AuthNonceResponse> {
    return this.request<AuthNonceResponse>(`/auth/nonce?pubkey=${pubkey}`, {
      method: 'POST',
    });
  }

  async verifySignature(pubkey: string, signature: string, nonce: string): Promise<AuthVerifyResponse> {
    return this.request<AuthVerifyResponse>(
      `/auth/verify?pubkey=${pubkey}&signature=${encodeURIComponent(signature)}&nonce=${nonce}`,
      { method: 'POST' }
    );
  }

  async verifySession(token: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/verify-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) return false;
      const data = await response.json();
      return data.valid === true;
    } catch {
      return false;
    }
  }

  async logout(): Promise<void> {
    await this.request('/auth/logout', { method: 'POST' });
    setSessionToken(null);
  }

  // Wallet endpoints
  async getWallets(): Promise<Wallet[]> {
    return this.request<Wallet[]>('/wallets');
  }

  async getWallet(address: string): Promise<Wallet> {
    return this.request<Wallet>(`/wallets/${address}`);
  }

  async addWallet(address: string, label?: string): Promise<Wallet> {
    return this.request<Wallet>('/wallets', {
      method: 'POST',
      body: JSON.stringify({ address, label }),
    });
  }

  async updateWallet(
    address: string,
    updates: { label?: string; is_active?: boolean }
  ): Promise<Wallet> {
    return this.request<Wallet>(`/wallets/${address}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async deleteWallet(address: string): Promise<void> {
    await this.request(`/wallets/${address}`, { method: 'DELETE' });
  }

  // Sync endpoints
  async syncWallet(address: string): Promise<{ message: string }> {
    return this.request(`/wallets/${address}/sync`, { method: 'POST' });
  }

  async getSyncStatus(address: string): Promise<SyncStatus> {
    return this.request<SyncStatus>(`/wallets/${address}/sync/status`);
  }

  // Portfolio endpoints
  async getWalletPortfolio(address: string): Promise<Portfolio> {
    return this.request<Portfolio>(`/wallets/${address}/portfolio`);
  }

  async getAllPortfolios(): Promise<MultiWalletPortfolio> {
    return this.request<MultiWalletPortfolio>('/portfolio');
  }

  // Transaction endpoints
  async getWalletTransactions(
    address: string,
    token?: string,
    limit: number = 100
  ): Promise<Transaction[]> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (token) params.append('token', token);
    return this.request<Transaction[]>(
      `/wallets/${address}/transactions?${params}`
    );
  }

  // Balance endpoints (actual on-chain balances like Phantom shows)
  async getWalletBalances(address: string): Promise<WalletBalances> {
    return this.request<WalletBalances>(`/wallets/${address}/balances`);
  }

  // Token verification toggle
  async toggleTokenVerification(mint: string): Promise<{ mint: string; symbol: string; is_verified: boolean }> {
    return this.request(`/tokens/${mint}/verify`, { method: 'PATCH' });
  }

  // Token hide toggle (for scam airdrops)
  async toggleTokenHidden(mint: string): Promise<{ mint: string; symbol: string; is_hidden: boolean; is_verified: boolean }> {
    return this.request(`/tokens/${mint}/hide`, { method: 'PATCH' });
  }

  // Wallet transaction history (detailed, organized by token)
  async getWalletTransactionsDetailed(address: string): Promise<WalletTransactionHistory> {
    return this.request<WalletTransactionHistory>(`/research/wallet-transactions-detailed/${address}`);
  }

  // Fetch complete wallet transaction history (caches for future use)
  async fetchWalletCompleteHistory(address: string): Promise<{ message: string; transaction_count: number }> {
    return this.request(`/research/wallet-complete-history/${address}`, { method: 'POST' });
  }
}

export const api = new ApiClient();

// Types for detailed transaction history
export interface TokenTransaction {
  signature: string;
  timestamp: number;
  type: string;
  amount: number;
  from: string;
  to: string;
  mint: string;
}

export interface TokenTransactionGroup {
  mint: string;
  symbol: string;
  name?: string;
  buy_count: number;
  sell_count: number;
  transfer_out_count: number;
  transfer_in_count: number;
  buys: TokenTransaction[];
  sells: TokenTransaction[];
  transfers_out: TokenTransaction[];
  transfers_in: TokenTransaction[];
  // P&L data
  realized_pnl_sol: number;
  realized_pnl_usd: number;
  unrealized_pnl_sol: number;
  unrealized_pnl_usd: number;
  current_balance: number;
  avg_buy_price_sol: number;
  total_cost_sol: number;
}

export interface WalletTransactionHistory {
  wallet_address: string;
  total_transactions: number;
  unique_tokens: number;
  cached_at: string | null;
  tokens: TokenTransactionGroup[];
}
