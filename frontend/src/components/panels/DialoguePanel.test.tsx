import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DialoguePanel } from './DialoguePanel';
import { AuthContext, type AuthContextValue } from '../../contexts/AuthContext';

const { mockDispatch, mockChatStream } = vi.hoisted(() => ({
  mockDispatch: vi.fn(),
  mockChatStream: vi.fn(),
}));

vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client',  () => ({ chatStream: mockChatStream }));

const wrap = (isOwner = false) =>
  render(
    <AuthContext.Provider value={{ isOwner, privateKey: 'test-key' } satisfies AuthContextValue}>
      <DialoguePanel npcId="cyber_minghan" npcName="赛博明翰" onClose={vi.fn()} />
    </AuthContext.Provider>,
  );

describe('DialoguePanel', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('dispatches panel:opened on mount', () => {
    wrap();
    expect(mockDispatch).toHaveBeenCalledWith('cyber:panel:opened', { panelId: 'dialogue' });
  });

  it('dispatches panel:closed on unmount', () => {
    const { unmount } = wrap();
    unmount();
    expect(mockDispatch).toHaveBeenCalledWith('cyber:panel:closed', { panelId: 'dialogue' });
  });

  it('shows NPC name', () => {
    wrap();
    expect(screen.getByText('赛博明翰')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(
      <AuthContext.Provider value={{ isOwner: false, privateKey: '' } satisfies AuthContextValue}>
        <DialoguePanel npcId="cyber_minghan" npcName="赛博明翰" onClose={onClose} />
      </AuthContext.Provider>,
    );
    fireEvent.click(screen.getByTestId('dialogue-close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows streaming text while chatStream is active', async () => {
    let capturedOnToken: ((t: string) => void) | undefined;
    mockChatStream.mockImplementation(
      (_npcId: string, _msg: string, _pk: string, onToken: (t: string) => void) => {
        capturedOnToken = onToken;
        return vi.fn();
      },
    );
    wrap();
    fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '你好' } });
    fireEvent.click(screen.getByTestId('dialogue-send'));
    await act(async () => { capturedOnToken?.('你好'); });
    expect(screen.getByTestId('dialogue-streaming')).toBeInTheDocument();
    expect(screen.getByTestId('dialogue-streaming')).toHaveTextContent('你好');
  });

  it('clears streaming element after onDone fires', async () => {
    let capturedOnDone: ((t: string) => void) | undefined;
    mockChatStream.mockImplementation(
      (_npcId: string, _msg: string, _pk: string, _onToken: (t: string) => void, onDone: (t: string) => void) => {
        capturedOnDone = onDone;
        return vi.fn();
      },
    );
    wrap();
    fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '你好' } });
    fireEvent.click(screen.getByTestId('dialogue-send'));
    await act(async () => { capturedOnDone?.('你好，世界'); });
    expect(screen.queryByTestId('dialogue-streaming')).toBeNull();
  });

  it('toggles history panel on expand button click', () => {
    wrap();
    expect(screen.queryByTestId('dialogue-history')).toBeNull();
    fireEvent.click(screen.getByTestId('dialogue-expand-btn'));
    expect(screen.getByTestId('dialogue-history')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('dialogue-expand-btn'));
    expect(screen.queryByTestId('dialogue-history')).toBeNull();
  });
});
