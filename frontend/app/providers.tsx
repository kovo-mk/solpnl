'use client';

import { ReactNode } from 'react';
import WalletContextProvider from '@/contexts/WalletContextProvider';
import { AuthProvider } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';

interface ProvidersProps {
  children: ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <WalletContextProvider>
        <AuthProvider>
          {children}
        </AuthProvider>
      </WalletContextProvider>
    </ThemeProvider>
  );
}
