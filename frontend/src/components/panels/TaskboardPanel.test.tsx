import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TaskboardPanel } from './TaskboardPanel';
import { getReviewItems, getPruneCandidates } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({
  getReviewItems: vi.fn(),
  getPruneCandidates: vi.fn(),
}));

const REVIEW_ITEM = {
  id: '1', pendingId: 'p1', timestamp: '', sourceMode: 'gym',
  content: 'test', rawEvidence: '', proposedRoute: 'approved_kg',
  proposedLayer: 'Ego', aiRationale: '', importance: 7, importanceNote: '',
};
const PRUNE_RESULT = { stats: { critical: 2, warning: 3, healthy: 10 }, candidates: [] };

describe('TaskboardPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getReviewItems).mockResolvedValue([REVIEW_ITEM]);
    vi.mocked(getPruneCandidates).mockResolvedValue(PRUNE_RESULT);
  });

  it('dispatches panel:opened on mount', () => {
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    expect(mockDispatch).toHaveBeenCalledWith('cyber:panel:opened', { panelId: 'taskboard' });
  });

  it('shows review item row after loading', async () => {
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('taskboard-review-row')).toBeInTheDocument());
    expect(screen.getByTestId('taskboard-review-row')).toHaveTextContent('1');
  });

  it('shows prune row with critical+warning count', async () => {
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('taskboard-prune-row')).toBeInTheDocument());
    expect(screen.getByTestId('taskboard-prune-row')).toHaveTextContent('5');
  });

  it('calls onNavigate("review") when review row clicked', async () => {
    const onNavigate = vi.fn();
    render(<TaskboardPanel onNavigate={onNavigate} onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('taskboard-review-row'));
    fireEvent.click(screen.getByTestId('taskboard-review-row'));
    expect(onNavigate).toHaveBeenCalledWith('review');
  });

  it('shows empty state when all counts are zero', async () => {
    vi.mocked(getReviewItems).mockResolvedValueOnce([]);
    vi.mocked(getPruneCandidates).mockResolvedValueOnce({ stats: { critical: 0, warning: 0, healthy: 5 }, candidates: [] });
    render(<TaskboardPanel onNavigate={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('taskboard-empty')).toBeInTheDocument());
  });
});
