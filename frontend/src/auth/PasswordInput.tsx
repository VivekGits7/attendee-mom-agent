import { useState, type InputHTMLAttributes } from 'react';
import { Eye, EyeOff, LockKeyhole } from 'lucide-react';

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>;

export function PasswordInput(props: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="input-icon password-input">
      <LockKeyhole size={18} />
      <input {...props} type={visible ? 'text' : 'password'} maxLength={72} />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible((shown) => !shown)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
