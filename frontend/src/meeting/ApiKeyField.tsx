import { KeyRound } from 'lucide-react';

import { useApiKey } from '@/meeting/ApiKeyContext';

export function ApiKeyField({ id }: { id: string }) {
  const { apiKey, setApiKey } = useApiKey();
  return (
    <div className="field">
      <label htmlFor={id}><KeyRound size={15} /> Backend API key</label>
      <input id={id} type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Paste INTERNAL_API_KEY" required />
      <p className="field-help">From backend/.env. Kept in memory for this tab; never saved in the browser.</p>
    </div>
  );
}
