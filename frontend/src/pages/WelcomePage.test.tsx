import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { WelcomePage } from './WelcomePage';

describe('WelcomePage', () => {
  it('renders name and tagline', () => {
    render(<WelcomePage onEnter={vi.fn()} />);
    expect(screen.getByText('明翰')).toBeInTheDocument();
    expect(screen.getByText(/赛博明翰/)).toBeInTheDocument();
  });

  it('renders all 4 rooms', () => {
    render(<WelcomePage onEnter={vi.fn()} />);
    expect(screen.getByText(/大厅/)).toBeInTheDocument();
    expect(screen.getByText(/健身房/)).toBeInTheDocument();
    expect(screen.getByText(/办公室/)).toBeInTheDocument();
    expect(screen.getByText(/学习室/)).toBeInTheDocument();
  });

  it('calls onEnter when button clicked', () => {
    const onEnter = vi.fn();
    render(<WelcomePage onEnter={onEnter} />);
    fireEvent.click(screen.getByTestId('welcome-enter'));
    expect(onEnter).toHaveBeenCalled();
  });
});
