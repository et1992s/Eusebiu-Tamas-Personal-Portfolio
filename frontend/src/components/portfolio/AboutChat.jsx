import { useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';

function AboutChat() {
  const textareaRef = useRef(null);

  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage || loading) {
      return;
    }

    setMessage('');
    setError('');
    setLoading(true);

    const assistantMessageIndex = messages.length + 1;

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: 'user',
        content: trimmedMessage,
      },
      {
        role: 'assistant',
        content: '',
      },
    ]);

    try {
      const responseStream = await fetch(
        '/api/v1/ai/about/stream',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: trimmedMessage,
          }),
        },
      );

      if (!responseStream.ok) {
        throw new Error(
          `Request failed with status ${responseStream.status}.`,
        );
      }

      if (!responseStream.body) {
        throw new Error('The response stream is unavailable.');
      }

      const reader = responseStream.body.getReader();
      const decoder = new TextDecoder();

      let buffer = '';
      let accumulatedResponse = '';

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const lines = event.split('\n');

          let eventType = 'message';
          let data = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            }

            if (line.startsWith('data:')) {
              data += line.slice(5).trim();
            }
          }

          if (!data) {
            continue;
          }

          if (eventType === 'token') {
            const parsed = JSON.parse(data);
            const content = parsed.content || '';

            accumulatedResponse += content;

            setMessages((currentMessages) =>
              currentMessages.map((item, index) =>
                index === assistantMessageIndex
                  ? {
                      ...item,
                      content: accumulatedResponse,
                    }
                  : item,
              ),
            );
          }

          if (eventType === 'error') {
            const parsed = JSON.parse(data);

            throw new Error(
              parsed.error ||
                'Zebio could not complete the response.',
            );
          }

          if (eventType === 'done') {
            return;
          }
        }
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Zebio could not complete the response.',
      );

      setMessages((currentMessages) =>
        currentMessages.filter(
          (_, index) => index !== assistantMessageIndex,
        ),
      );
    } finally {
      setLoading(false);

      window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit(event);
    }
  };

  return (
    <section
      className="portfolio-about-chat"
      aria-label="Ask Zebio about Eusebiu"
    >
      <div className="portfolio-about-chat-messages">
        {messages.map((item, index) => {
          const isUser = item.role === 'user';

          return (
            <div
              key={`${item.role}-${index}`}
              className={`portfolio-about-chat-message ${
                isUser
                  ? 'portfolio-about-chat-message-user'
                  : 'portfolio-about-chat-message-assistant'
              }`}
            >
              {isUser ? (
                <div className="portfolio-about-chat-user-bubble">
                  {item.content}
                </div>
              ) : (
                <div
                  className="portfolio-about-chat-response"
                  aria-live={
                    index === messages.length - 1
                      ? 'polite'
                      : undefined
                  }
                >
                  <ReactMarkdown>
                    {item.content}
                  </ReactMarkdown>

                  {loading &&
                    index === messages.length - 1 && (
                      <span
                        className="portfolio-about-chat-cursor"
                        aria-hidden="true"
                      />
                    )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div
          className="portfolio-about-chat-error"
          role="alert"
        >
          {error}
        </div>
      )}

      <form
        className="portfolio-about-chat-form"
        onSubmit={handleSubmit}
      >
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about my background, projects or skills..."
          rows={1}
          disabled={loading}
          aria-label="Ask Zebio a question about Eusebiu"
        />

        <button
          type="submit"
          aria-label="Send message"
          disabled={!message.trim() || loading}
        >
          &gt;
        </button>
      </form>
    </section>
  );
}

export default AboutChat;