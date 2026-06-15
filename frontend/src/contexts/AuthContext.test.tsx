import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

function ShowAuth() {
  const { isOwner, privateKey } = useAuth();
  return <div data-testid="auth">{isOwner ? 'owner' : 'visitor'}:{privateKey}</div>;
}

describe('AuthContext', () => {
  // jsdom URL is 'http://localhost/' with no search params, so no ?key= is present.
  // VITE_PRIVATE_KEY is empty in test env (not set), so isOwner is always false here.
  it('defaults to visitor when no URL key param', () => {
    render(<AuthProvider><ShowAuth /></AuthProvider>);
    expect(screen.getByTestId('auth').textContent).toBe('visitor:');
  });
});
