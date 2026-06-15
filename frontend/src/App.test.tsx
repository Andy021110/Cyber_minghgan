import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';
import { AuthContext, type AuthContextValue } from './contexts/AuthContext';

vi.mock('./game/PhaserGame',           () => ({ PhaserGame: () => <div data-testid="phaser-game" /> }));
vi.mock('./components/HUD',            () => ({ HUD: () => <div data-testid="hud" /> }));
vi.mock('./components/panels/RoomEntryPrompt', () => ({ RoomEntryPrompt: () => <div /> }));
vi.mock('./components/panels/DialoguePanel',   () => ({
  DialoguePanel: ({ npcName }: { npcName: string }) => <div data-testid="dialogue-panel">{npcName}</div>,
}));
vi.mock('./components/panels/TaskboardPanel',  () => ({
  TaskboardPanel: () => <div data-testid="taskboard-panel" />,
}));
vi.mock('./components/panels/ReviewPanel',     () => ({
  ReviewPanel: () => <div data-testid="review-panel" />,
}));
vi.mock('./components/panels/KGPanel',         () => ({
  KGPanel: () => <div data-testid="kg-panel" />,
}));
vi.mock('./components/panels/PrunePanel',      () => ({
  PrunePanel: () => <div data-testid="prune-panel" />,
}));
vi.mock('./pages/WelcomePage', () => ({
  WelcomePage: ({ onEnter }: { onEnter: () => void }) => (
    <button data-testid="welcome-enter" onClick={onEnter}>进入空间</button>
  ),
}));

const asOwner   = { isOwner: true,  privateKey: 'k' } satisfies AuthContextValue;
const asVisitor = { isOwner: false, privateKey: '' }  satisfies AuthContextValue;

describe('App', () => {
  it('shows WelcomePage for visitor before entering', () => {
    render(<AuthContext.Provider value={asVisitor}><App /></AuthContext.Provider>);
    expect(screen.getByTestId('welcome-enter')).toBeInTheDocument();
    expect(screen.queryByTestId('phaser-game')).toBeNull();
  });

  it('shows game world for owner without welcome page', () => {
    render(<AuthContext.Provider value={asOwner}><App /></AuthContext.Provider>);
    expect(screen.getByTestId('phaser-game')).toBeInTheDocument();
    expect(screen.queryByTestId('welcome-enter')).toBeNull();
  });

  it('enters game world after visitor clicks welcome button', async () => {
    render(<AuthContext.Provider value={asVisitor}><App /></AuthContext.Provider>);
    fireEvent.click(screen.getByTestId('welcome-enter'));
    await waitFor(() => expect(screen.getByTestId('phaser-game')).toBeInTheDocument());
    expect(screen.queryByTestId('welcome-enter')).toBeNull();
  });
});
