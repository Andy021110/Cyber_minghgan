import { describe, it, expect, vi } from 'vitest';
import { dispatch, listen } from './eventbus';

describe('eventbus', () => {
  it('dispatches and receives a typed event', () => {
    const handler = vi.fn();
    const off = listen('cyber:scene:changed', handler);
    dispatch('cyber:scene:changed', { sceneKey: 'WorldScene', roomName: '中央区' });
    expect(handler).toHaveBeenCalledWith({ sceneKey: 'WorldScene', roomName: '中央区' });
    off();
  });

  it('off() removes the listener', () => {
    const handler = vi.fn();
    const off = listen('cyber:notification:badge', handler);
    off();
    dispatch('cyber:notification:badge', { count: 3 });
    expect(handler).not.toHaveBeenCalled();
  });
});
