import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KGPanel } from './KGPanel';
import { getKgNodes } from '../../api/client';

const { mockDispatch, mockListen } = vi.hoisted(() => ({
  mockDispatch: vi.fn(),
  mockListen: vi.fn(() => vi.fn()),
}));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch, listen: mockListen }));
vi.mock('../../api/client', () => ({ getKgNodes: vi.fn() }));

const NODES = [
  { id: 'n1', label: '早起习惯', layer: 'Ego' as const, description: 'Ego desc', importance: 8,
    evidence: [], createdAt: null, lastAccessed: null, archived: false, archiveReason: null },
  { id: 'n2', label: '旧记忆', layer: 'Id' as const, description: 'Id desc', importance: 2,
    evidence: [], createdAt: null, lastAccessed: null, archived: true, archiveReason: '过期' },
];

describe('KGPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getKgNodes).mockResolvedValue(NODES);
  });

  it('renders all tab buttons', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    expect(screen.getByTestId('tab-all')).toBeInTheDocument();
    expect(screen.getByTestId('tab-Id')).toBeInTheDocument();
    expect(screen.getByTestId('tab-Ego')).toBeInTheDocument();
    expect(screen.getByTestId('tab-Superego')).toBeInTheDocument();
    expect(screen.getByTestId('tab-archived')).toBeInTheDocument();
  });

  it('shows active nodes on 全部 tab (excludes archived)', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    expect(screen.getByText('早起习惯')).toBeInTheDocument();
    expect(screen.queryByText('旧记忆')).toBeNull();
  });

  it('shows archived nodes on 归档 tab', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    fireEvent.click(screen.getByTestId('tab-archived'));
    expect(screen.getByText('旧记忆')).toBeInTheDocument();
    expect(screen.queryByText('早起习惯')).toBeNull();
  });

  it('clicking node card expands detail', async () => {
    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    fireEvent.click(screen.getByTestId('kg-node-n1'));
    expect(screen.getByTestId('kg-expanded')).toBeInTheDocument();
  });

  it('calls onBack when back button clicked', async () => {
    const onBack = vi.fn();
    render(<KGPanel onBack={onBack} />);
    await waitFor(() => screen.getByTestId('kg-back'));
    fireEvent.click(screen.getByTestId('kg-back'));
    expect(onBack).toHaveBeenCalled();
  });

  it('refetches nodes when cyber:kg:updated event fires', async () => {
    let capturedHandler: ((detail: { nodeId: string; label: string }) => void) | undefined;
    mockListen.mockImplementation((name: string, handler: (d: unknown) => void) => {
      if (name === 'cyber:kg:updated') capturedHandler = handler as typeof capturedHandler;
      return vi.fn();
    });

    render(<KGPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByText('早起习惯'));
    expect(vi.mocked(getKgNodes)).toHaveBeenCalledTimes(1);

    // 触发 kg:updated 事件
    vi.mocked(getKgNodes).mockResolvedValue([...NODES]);
    await act(async () => { capturedHandler?.({ nodeId: 'n1', label: '早起习惯' }); });

    expect(vi.mocked(getKgNodes)).toHaveBeenCalledTimes(2);
  });
});
