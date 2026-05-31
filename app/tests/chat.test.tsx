import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import ChatView from '../src/ChatView';

describe('ChatView Mic Interactions', () => {
  it('toggles mic recording trigger states', async () => {
    const setMessages = jest.fn();
    const setThreadId = jest.fn();
    const handleRun = jest.fn();
    const handleStop = jest.fn();

    render(
      <ChatView
        messages={[]}
        setMessages={setMessages}
        threadId="test-id"
        setThreadId={setThreadId}
        threadHistory={[]}
        isRunning={false}
        status="idle"
        handleRun={handleRun}
        handleStop={handleStop}
      />
    );

    const micButton = screen.getByTitle('Hold to talk');
    expect(micButton).toBeInTheDocument();

    // Trigger recording start
    await act(async () => {
      fireEvent.mouseDown(micButton);
      // Wait a tiny bit for the async state to resolve
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    // Check that listening UI appears
    expect(screen.getByText(/Listening.../i)).toBeInTheDocument();

    // Trigger recording stop
    await act(async () => {
      fireEvent.mouseUp(micButton);
      await new Promise(resolve => setTimeout(resolve, 0));
    });
  });
});
