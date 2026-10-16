export interface AuthUser {
  user_id: string;
  full_name: string;
  email: string;
  last_login_at: string | null;
  created_at: string;
}

export interface TokenResponse {
  success: boolean;
  message: string;
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse extends TokenResponse {
  data: AuthUser;
}

export interface ChangePasswordInput {
  old_password: string;
  new_password: string;
  confirm_new_password: string;
}

export interface Session {
  accessToken: string;
  expiresAt: number;
  user: AuthUser;
}
