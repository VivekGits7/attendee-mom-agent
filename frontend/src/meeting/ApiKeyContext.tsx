import { createContext, useContext, useState, type ReactNode } from 'react';

interface ApiKeyValue {
  apiKey: string;
  setApiKey: (key: string) => void;
}

const ApiKeyContext = createContext<ApiKeyValue | null>(null);

export function ApiKeyProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKey] = useState('');
  return <ApiKeyContext.Provider value={{ apiKey, setApiKey }}>{children}</ApiKeyContext.Provider>;
}

export function useApiKey(): ApiKeyValue {
  const context = useContext(ApiKeyContext);
  if (!context) throw new Error('ApiKeyProvider is missing');
  return context;
}
