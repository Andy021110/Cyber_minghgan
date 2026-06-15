import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ReviewPanel } from './ReviewPanel';
import { getReviewItems, decideReviewItem } from '../../api/client';

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));
vi.mock('../../eventbus', () => ({ dispatch: mockDispatch }));
vi.mock('../../api/client', () => ({
  getReviewItems: vi.fn(),
  decideReviewItem: vi.fn(),
}));

const ITEM = {
  id: 'item-1', pendingId: 'p1', timestamp: '2026-01-01', sourceMode: '健身房',
  content: '用户早起频率提升', rawEvidence: 'evidence text',
  proposedRoute: 'approved_kg', proposedLayer: 'Ego',
  aiRationale: 'AI rationale text', importance: 7, importanceNote: 'note',
};

describe('ReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getReviewItems).mockResolvedValue([ITEM]);
    vi.mocked(decideReviewItem).mockResolvedValue(undefined);
  });

  it('renders item content after loading', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('review-content')).toBeInTheDocument());
    expect(screen.getByTestId('review-content')).toHaveTextContent('用户早起频率提升');
  });

  it('shows description block by default', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('review-description-block')).toBeInTheDocument());
  });

  it('hides description block when N is selected', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-n'));
    fireEvent.click(screen.getByTestId('review-btn-n'));
    expect(screen.queryByTestId('review-description-block')).toBeNull();
  });

  it('shows description block again when Y is selected after N', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-n'));
    fireEvent.click(screen.getByTestId('review-btn-n'));
    fireEvent.click(screen.getByTestId('review-btn-y'));
    expect(screen.getByTestId('review-description-block')).toBeInTheDocument();
  });

  it('calls decideReviewItem and dispatches review:done on Y submit', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-y'));
    fireEvent.click(screen.getByTestId('review-btn-y'));
    await act(async () => { fireEvent.click(screen.getByTestId('review-submit')); });
    expect(decideReviewItem).toHaveBeenCalledWith('item-1', expect.objectContaining({ decision: 'approved_kg' }));
    expect(mockDispatch).toHaveBeenCalledWith('cyber:review:done', { processedCount: 1 });
  });

  it('Q skips to empty state without calling API', async () => {
    render(<ReviewPanel onBack={vi.fn()} />);
    await waitFor(() => screen.getByTestId('review-btn-q'));
    fireEvent.click(screen.getByTestId('review-btn-q'));
    expect(decideReviewItem).not.toHaveBeenCalled();
    expect(screen.getByTestId('review-empty')).toBeInTheDocument();
  });
});
