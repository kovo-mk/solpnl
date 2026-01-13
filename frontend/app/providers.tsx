'use client';

import { ReactNode } from 'react';
import WalletContextProvider from '@/contexts/WalletContextProvider';
import { AuthProvider } from '@/contexts/AuthContext';

interface ProvidersProps {
  children: ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return (
    <WalletContextProvider>
      <AuthProvider>
        {children}
      </AuthProvider>
    </WalletContextProvider>
  );
}
