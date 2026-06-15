import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PrunePanel } from './PrunePanel';
import { getPruneCandidates, archiveNode, boostNode } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({
  getPruneCandidates: vi.fn(),
  archiveNode: vi.fn(),
  boostNode: vi.fn(),
}));

const NODE = {
  id: 'n1', label: '早起习惯', layer: 'Ego' as const, description: 'desc',
  importance: 3, evidence: [], createdAt: null, lastAccessed: '2026-01-01',
  archived: false, archiveReason: null,
};
const PRUNE_DATA = {
  stats: { critical: 1, warning: 2, healthy: 10 },
  candidates: [{ node: NODE, stalenessScore: 9.2, severity: 'critical' as const }],
};

describe('PrunePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPruneCandidates).mockResolvedValue(PRUNE_DATA);
    vi.mocked(archiveNode).mockResolvedValue(undefined);
    vi.mocked(boostNode).mockResolvedValue(undefined);
  });

  it('renders stats grid with correct counts', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('prune-critical')).toBeInTheDocument());
    expect(screen.getByTestId('prune-critical')).toHaveTextContent('1');
    expect(screen.getByTestId('prune-warning')).toHaveTextContent('2');
    expect(screen.getByTestId('prune-healthy')).toHaveTextContent('10');
  });

  it('shows candidate node label', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('早起习惯')).toBeInTheDocument());
  });

  it('archive button calls archiveNode and removes node from list', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('prune-archive-n1'));
    await act(async () => { fireEvent.click(screen.getByTestId('prune-archive-n1')); });
    expect(archiveNode).toHaveBeenCalledWith('n1', '');
    expect(screen.queryByText('早起习惯')).toBeNull();
  });

  it('skip removes node from list without calling API', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('prune-skip-n1'));
    fireEvent.click(screen.getByTestId('prune-skip-n1'));
    expect(archiveNode).not.toHaveBeenCalled();
    expect(screen.queryByText('早起习惯')).toBeNull();
  });

  it('boost shows input pre-filled with current importance, then calls boostNode', async () => {
    render(<PrunePanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('prune-boost-n1'));
    fireEvent.click(screen.getByTestId('prune-boost-n1'));
    expect(screen.getByTestId('prune-boost-input-n1')).toBeInTheDocument();
    expect(screen.getByTestId('prune-boost-input-n1')).toHaveValue(3);  // pre-filled with importance
    fireEvent.change(screen.getByTestId('prune-boost-input-n1'), { target: { value: '8' } });
    await act(async () => { fireEvent.click(screen.getByTestId('prune-boost-confirm-n1')); });
    expect(boostNode).toHaveBeenCalledWith('n1', 8);
  });
});
