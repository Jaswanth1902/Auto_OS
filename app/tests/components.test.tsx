import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AccessibilitySettings } from '../src/AccessibilitySettings';
import { HITLDialog } from '../src/run/HITLDialog';

describe('AccessibilitySettings', () => {
  it('toggles high contrast mode', () => {
    render(<AccessibilitySettings />);
    const button = screen.getByRole('button', { name: /high contrast mode/i });

    // Initial state is Off
    expect(button).toHaveTextContent('Off');

    // Toggle on
    fireEvent.click(button);
    expect(button).toHaveTextContent('On');

    // Check if css variables were updated
    expect(document.documentElement.style.getPropertyValue('--background-hsl')).toBe('0, 0%, 0%');

    // Toggle off
    fireEvent.click(button);
    expect(button).toHaveTextContent('Off');
  });

  it('changes text size boosting', () => {
    render(<AccessibilitySettings />);

    const largeButton = screen.getByText('A+');
    fireEvent.click(largeButton);
    expect(document.documentElement.style.fontSize).toBe('20px');

    const normalButton = screen.getByText('A');
    fireEvent.click(normalButton);
    expect(document.documentElement.style.fontSize).toBe('16px');
  });
});

describe('HITLDialog', () => {
  it('calls onDismiss when button is clicked', () => {
    const handleDismiss = jest.fn();
    render(<HITLDialog onDismiss={handleDismiss} />);

    const button = screen.getByText('DISMISS');
    fireEvent.click(button);

    expect(handleDismiss).toHaveBeenCalledTimes(1);
  });
});
