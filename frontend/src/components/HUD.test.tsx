import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { HUD } from './HUD';
import { AuthContext } from '../contexts/AuthContext';

// Mock eventbus
const listenMocks: Record<string, (detail: unknown) => void> = {};
vi.mock('../eventbus', () => ({
  listen: vi.fn((name: string, handler: (d: unknown) => void) => {
    listenMocks[name] = handler;
    return () => { delete listenMocks[name]; };
  }),
  dispatch: vi.fn(),
}));

const renderWithAuth = (isOwner: boolean) =>
  render(
    <AuthContext.Provider value={{ isOwner, privateKey: isOwner ? 'k' : '' }}>
      <HUD />
    </AuthContext.Provider>,
  );

describe('HUD', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders taskboard button in owner mode', () => {
    renderWithAuth(true);
    expect(screen.getByTestId('hud-taskboard-btn')).toBeInTheDocument();
    expect(screen.queryByTestId('hud-chat-btn')).toBeNull();
  });

  it('renders chat button in visitor mode', () => {
    renderWithAuth(false);
    expect(screen.getByTestId('hud-chat-btn')).toBeInTheDocument();
    expect(screen.queryByTestId('hud-taskboard-btn')).toBeNull();
  });

  it('shows visitor indicator in visitor mode', () => {
    renderWithAuth(false);
    expect(screen.getByText(/明翰的空间/)).toBeInTheDocument();
  });

  it('shows badge when notification count > 0', async () => {
    renderWithAuth(true);
    await act(async () => {
      listenMocks['cyber:notification:badge']?.({ count: 4 });
    });
    expect(screen.getByTestId('hud-badge')).toHaveTextContent('4');
  });

  it('hides badge when count is 0', async () => {
    renderWithAuth(true);
    await act(async () => {
      listenMocks['cyber:notification:badge']?.({ count: 0 });
    });
    expect(screen.queryByTestId('hud-badge')).toBeNull();
  });

  it('updates room name on scene change', async () => {
    renderWithAuth(true);
    await act(async () => {
      listenMocks['cyber:scene:changed']?.({ sceneKey: 'GymScene', roomName: '健身房' });
    });
    expect(screen.getByText(/健身房/)).toBeInTheDocument();
  });
});
