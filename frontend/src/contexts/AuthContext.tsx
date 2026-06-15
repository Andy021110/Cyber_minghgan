import { createContext, useContext, useMemo, type ReactNode } from 'react';

export interface AuthContextValue {
  isOwner:    boolean;
  privateKey: string;
}

export const AuthContext = createContext<AuthContextValue>({ isOwner: false, privateKey: '' });

export function AuthProvider({ children }: { children: ReactNode }) {
  const value = useMemo<AuthContextValue>(() => {
    const params  = new URLSearchParams(window.location.search);
    const urlKey  = params.get('key') ?? '';
    const envKey  = (import.meta.env.VITE_PRIVATE_KEY as string | undefined) ?? '';
    const isOwner = Boolean(envKey && urlKey === envKey);
    return { isOwner, privateKey: urlKey };
  }, []);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
