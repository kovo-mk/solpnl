'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { api } from '@/lib/api';
import bs58 from 'bs58';

interface AuthState {
  isAuthenticated: boolean;
  userPubkey: string | null;
  sessionToken: string | null;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  signIn: () => Promise<boolean>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const { publicKey, signMessage, connected, disconnect } = useWallet();
  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    userPubkey: null,
    sessionToken: null,
    isLoading: true,
  });

  // Check for existing session on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('solpnl_session_token');
    const storedPubkey = localStorage.getItem('solpnl_user_pubkey');

    if (storedToken && storedPubkey) {
      // Verify session is still valid
      api.verifySession(storedToken)
        .then((valid) => {
          if (valid) {
            setAuthState({
              isAuthenticated: true,
              userPubkey: storedPubkey,
              sessionToken: storedToken,
              isLoading: false,
            });
          } else {
            // Session expired, clear storage
            localStorage.removeItem('solpnl_session_token');
            localStorage.removeItem('solpnl_user_pubkey');
            setAuthState({
              isAuthenticated: false,
              userPubkey: null,
              sessionToken: null,
              isLoading: false,
            });
          }
        })
        .catch(() => {
          setAuthState({
            isAuthenticated: false,
            userPubkey: null,
            sessionToken: null,
            isLoading: false,
          });
        });
    } else {
      setAuthState((prev) => ({ ...prev, isLoading: false }));
    }
  }, []);

  const signIn = useCallback(async (): Promise<boolean> => {
    if (!publicKey || !signMessage) {
      console.error('Wallet not connected or does not support signing');
      return false;
    }

    try {
      // 1. Get nonce from server
      const { nonce, message } = await api.getAuthNonce(publicKey.toBase58());

      // 2. Sign the message with wallet
      const encodedMessage = new TextEncoder().encode(message);
      const signature = await signMessage(encodedMessage);
      const signatureBase58 = bs58.encode(signature);

      // 3. Verify signature with server and get session token
      const { session_token, pubkey } = await api.verifySignature(
        publicKey.toBase58(),
        signatureBase58,
        nonce
      );

      // 4. Store session
      localStorage.setItem('solpnl_session_token', session_token);
      localStorage.setItem('solpnl_user_pubkey', pubkey);

      setAuthState({
        isAuthenticated: true,
        userPubkey: pubkey,
        sessionToken: session_token,
        isLoading: false,
      });

      return true;
    } catch (error) {
      console.error('Sign in failed:', error);
      return false;
    }
  }, [publicKey, signMessage]);

  const signOut = useCallback(() => {
    localStorage.removeItem('solpnl_session_token');
    localStorage.removeItem('solpnl_user_pubkey');
    setAuthState({
      isAuthenticated: false,
      userPubkey: null,
      sessionToken: null,
      isLoading: false,
    });
    disconnect();
  }, [disconnect]);

  // Auto sign-out if wallet disconnects
  useEffect(() => {
    if (!connected && authState.isAuthenticated) {
      signOut();
    }
  }, [connected, authState.isAuthenticated, signOut]);

  return (
    <AuthContext.Provider
      value={{
        ...authState,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
