import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DialoguePanel } from './DialoguePanel';
import { AuthContext, type AuthContextValue } from '../../contexts/AuthContext';

const { mockDispatch, mockChatStream } = vi.hoisted(() => ({
  mockDispatch: vi.fn(),
  mockChatStream: vi.fn(),
}));

vi.mock('../../eventbus', () => ({ dispatch: mockDispatch, listen: vi.fn(() => vi.fn()) }));
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

  it('dispatches cyber:reflection:triggered when reflection fires with triggered=true', async () => {
    let capturedOnReflection: ((triggered: boolean, feature: string | null) => void) | undefined;
    mockChatStream.mockImplementation(
      (_npcId: string, _msg: string, _pk: string,
       _onToken: (t: string) => void, _onDone: (t: string) => void,
       onReflection: (triggered: boolean, feature: string | null) => void) => {
        capturedOnReflection = onReflection;
        return vi.fn();
      },
    );
    wrap();
    fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '测试' } });
    fireEvent.click(screen.getByTestId('dialogue-send'));
    await act(async () => { capturedOnReflection?.(true, null); });
    expect(mockDispatch).toHaveBeenCalledWith('cyber:reflection:triggered', {});
  });

  it('does NOT dispatch cyber:reflection:triggered when triggered=false', async () => {
    let capturedOnReflection: ((triggered: boolean, feature: string | null) => void) | undefined;
    mockChatStream.mockImplementation(
      (_npcId: string, _msg: string, _pk: string,
       _onToken: (t: string) => void, _onDone: (t: string) => void,
       onReflection: (triggered: boolean, feature: string | null) => void) => {
        capturedOnReflection = onReflection;
        return vi.fn();
      },
    );
    wrap();
    fireEvent.change(screen.getByTestId('dialogue-input'), { target: { value: '测试' } });
    fireEvent.click(screen.getByTestId('dialogue-send'));
    await act(async () => { capturedOnReflection?.(false, null); });
    expect(mockDispatch).not.toHaveBeenCalledWith('cyber:reflection:triggered', {});
  });

  it('auto-sends initialQuery when provided', async () => {
    mockChatStream.mockReturnValue(vi.fn());

    render(
      <AuthContext.Provider value={{ isOwner: false, privateKey: '' } satisfies AuthContextValue}>
        <DialoguePanel
          npcId="cyber_minghan"
          npcName="赛博明翰"
          onClose={vi.fn()}
          initialQuery="我最近学了什么？"
        />
      </AuthContext.Provider>,
    );

    await act(async () => {});
    // 参数顺序：npcId, message, privateKey, onToken, onDone, onReflection,
    //           onTool, onKGUpdate, onError（onError 为后加，用于暴露后端故障）
    expect(mockChatStream).toHaveBeenCalledWith(
      'cyber_minghan',
      '我最近学了什么？',
      expect.any(String),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
    );
  });

  it('shows backend error instead of failing silently', async () => {
    // 回归测试：chatStream 曾静默吞掉所有后端错误（catch { return; }），
    // 界面表现为"什么都不发生"，用户会误以为功能没实现。
    mockChatStream.mockImplementation((...args: unknown[]) => {
      const onError = args[8] as ((msg: string) => void) | undefined;
      onError?.('无法连接后端 http://localhost:8000/api（Failed to fetch）');
      return () => {};
    });

    render(
      <AuthContext.Provider value={{ isOwner: false, privateKey: 'test-key' } satisfies AuthContextValue}>
        <DialoguePanel
          npcId="cyber_minghan"
          npcName="赛博明翰"
          onClose={vi.fn()}
          initialQuery="你好"
        />
      </AuthContext.Provider>,
    );

    await act(async () => {});
    const banner = screen.getByTestId('dialogue-error');
    expect(banner.textContent).toContain('无法连接后端');
    expect(banner.getAttribute('role')).toBe('alert');
  });
});
