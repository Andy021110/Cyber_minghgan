import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RoomEntryPrompt } from './RoomEntryPrompt';

const listenMocks: Record<string, (detail: unknown) => void> = {};

const { mockDispatch } = vi.hoisted(() => ({ mockDispatch: vi.fn() }));

vi.mock('../../eventbus', () => ({
  listen: vi.fn((name: string, handler: (d: unknown) => void) => {
    listenMocks[name] = handler;
    return () => { delete listenMocks[name]; };
  }),
  dispatch: mockDispatch,
}));

describe('RoomEntryPrompt', () => {
  beforeEach(() => { vi.clearAllMocks(); mockDispatch.mockReset(); });

  it('is hidden initially', () => {
    render(<RoomEntryPrompt />);
    expect(screen.queryByTestId('room-entry')).toBeNull();
  });

  it('shows prompt on cyber:door:approach', async () => {
    render(<RoomEntryPrompt />);
    await act(async () => {
      listenMocks['cyber:door:approach']?.({
        targetScene: 'GymScene', roomName: '健身房', modeDescription: '进入健康管家模式',
      });
    });
    expect(screen.getByTestId('room-entry')).toBeInTheDocument();
    expect(screen.getByText(/健身房/)).toBeInTheDocument();
  });

  it('confirm dispatches cyber:door:confirmed and closes', async () => {
    render(<RoomEntryPrompt />);
    await act(async () => {
      listenMocks['cyber:door:approach']?.({
        targetScene: 'GymScene', roomName: '健身房', modeDescription: '',
      });
    });
    fireEvent.click(screen.getByTestId('room-entry-confirm'));
    expect(mockDispatch).toHaveBeenCalledWith('cyber:door:confirmed', { targetScene: 'GymScene' });
    expect(screen.queryByTestId('room-entry')).toBeNull();
  });

  it('cancel dispatches cyber:door:cancelled and closes', async () => {
    render(<RoomEntryPrompt />);
    await act(async () => {
      listenMocks['cyber:door:approach']?.({
        targetScene: 'GymScene', roomName: '健身房', modeDescription: '',
      });
    });
    fireEvent.click(screen.getByTestId('room-entry-cancel'));
    expect(mockDispatch).toHaveBeenCalledWith('cyber:door:cancelled', {});
    expect(screen.queryByTestId('room-entry')).toBeNull();
  });
});
