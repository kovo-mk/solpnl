'use client';

import { useWallet } from '@solana/wallet-adapter-react';
import { useWalletModal } from '@solana/wallet-adapter-react-ui';
import { useAuth } from '@/contexts/AuthContext';
import { Wallet, LogOut, Loader2, ChevronDown } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

export default function WalletConnectButton() {
  const { publicKey, connected, disconnect } = useWallet();
  const { setVisible } = useWalletModal();
  const { isAuthenticated, isLoading, signIn, signOut, userPubkey } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle sign in after wallet connects
  useEffect(() => {
    if (connected && publicKey && !isAuthenticated && !isLoading && !signingIn) {
      handleSignIn();
    }
  }, [connected, publicKey, isAuthenticated, isLoading]);

  const handleSignIn = async () => {
    setSigningIn(true);
    try {
      await signIn();
    } finally {
      setSigningIn(false);
    }
  };

  const handleConnect = () => {
    setVisible(true);
  };

  const handleDisconnect = () => {
    signOut();
    disconnect();
    setShowDropdown(false);
  };

  const shortenAddress = (address: string) => {
    return `${address.slice(0, 4)}...${address.slice(-4)}`;
  };

  // Loading state
  if (isLoading) {
    return (
      <button
        disabled
        className="flex items-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400"
      >
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading...
      </button>
    );
  }

  // Not connected state
  if (!connected || !publicKey) {
    return (
      <button
        onClick={handleConnect}
        className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-sol-purple to-sol-green hover:opacity-90 rounded-lg font-medium transition-opacity"
      >
        <Wallet className="w-4 h-4" />
        Connect Wallet
      </button>
    );
  }

  // Connected but signing in
  if (signingIn || (connected && !isAuthenticated)) {
    return (
      <button
        disabled
        className="flex items-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400"
      >
        <Loader2 className="w-4 h-4 animate-spin" />
        Signing in...
      </button>
    );
  }

  // Connected and authenticated
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg font-medium transition-colors text-gray-900 dark:text-white border border-gray-300 dark:border-transparent"
      >
        <div className="w-2 h-2 rounded-full bg-green-500" />
        <span className="font-mono text-sm">{shortenAddress(publicKey.toBase58())}</span>
        <ChevronDown className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')} />
      </button>

      {showDropdown && (
        <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden z-50">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400">Connected as</p>
            <p className="font-mono text-sm truncate text-gray-900 dark:text-white">{publicKey.toBase58()}</p>
          </div>
          <button
            onClick={handleDisconnect}
            className="w-full flex items-center gap-2 px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-700 text-red-600 dark:text-red-400 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Disconnect
          </button>
        </div>
      )}
    </div>
  );
}
