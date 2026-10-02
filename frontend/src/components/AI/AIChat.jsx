import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import ZebioNeuralCore from '../NeuralCore/ZebioNeuralCore';
import ReactMarkdown from 'react-markdown';

const API_BASE_URL =
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
    ? ''
    : 'https://api.eusebiutamas.com';

const QUICK_PROMPTS = [
  'Explain the Zebio agent architecture.',
  'Analyse the Zebio memory system.',
  'Explain the trading pipeline.',
  'Explain the live prediction system.',
  'Explain the approval system.',
  'Explain the public and private Zebio architecture.',
  'How would you improve Zebio?',
  'Propose an engineering change to Zebio.',
];

function createId() {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function createPublicTaskState(overrides = {}) {
  return {
    status: 'idle',
    current_thought: '',
    current_output: '',
    current_step: null,
    steps: [],
    final_response: '',
    ...overrides,
  };
}

export default function AIChat() {
  const textareaRef = useRef(null);
  const chatEndRef = useRef(null);

  const [chatMessage, setChatMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  const [taskState, setTaskState] = useState(
    createPublicTaskState()
  );

  const [backendOnline, setBackendOnline] = useState(false);
  const [lastResponseTime, setLastResponseTime] =
    useState(null);

  const modelName = useMemo(() => {
    const assistantMessage = [...messages]
      .reverse()
      .find(
        (message) =>
          message.role === 'assistant' &&
          message.model
      );

    return (
      assistantMessage?.model ||
      'qwen2.5-coder:14b'
    );
  }, [messages]);

  const latestAssistantMessage = useMemo(
    () =>
      [...messages]
        .reverse()
        .find(
          (message) =>
            message.role === 'assistant'
        ),
    [messages]
  );

  /*
   * Backend health check.
   */
  useEffect(() => {
    let mounted = true;

    async function checkBackend() {
      const startedAt = performance.now();

      try {
        const response = await fetch(`${API_BASE_URL}/health`);

        if (!response.ok) {
          throw new Error('Backend unavailable');
        }

        if (!mounted) {
          return;
        }

        setBackendOnline(true);
        setLastResponseTime(
          Math.round(
            performance.now() - startedAt
          )
        );
      } catch {
        if (!mounted) {
          return;
        }

        setBackendOnline(false);
      }
    }

    checkBackend();

    const interval = window.setInterval(
      checkBackend,
      15000
    );

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  /*
   * Ctrl/Cmd + K focuses the composer.
   */
  useEffect(() => {
    const handleShortcut = (event) => {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key.toLowerCase() === 'k'
      ) {
        event.preventDefault();
        textareaRef.current?.focus();
      }
    };

    window.addEventListener(
      'keydown',
      handleShortcut
    );

    return () => {
      window.removeEventListener(
        'keydown',
        handleShortcut
      );
    };
  }, []);

  /*
   * Send a message to the public, read-only Zebio
   * interface and consume its SSE token stream.
   */
  async function sendMessage(
    messageOverride = null
  ) {
    const message = (
      messageOverride ?? chatMessage
    ).trim();

    if (!message || chatLoading) {
      return;
    }

    const startedAt = performance.now();

    setChatLoading(true);
    setChatError('');

    setTaskState(
      createPublicTaskState({
        status: 'running',
        current_thought:
          'Analysing the published Zebio architecture.',
        current_step:
          'Evaluating the request',
      })
    );

    const userMessage = {
      id: createId(),
      role: 'user',
      content: message,
      timestamp: new Date(),
    };

    const assistantId = createId();

    const assistantMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      model: 'qwen2.5-coder:14b',
      timestamp: new Date(),
    };

    setMessages((current) => [
      ...current,
      userMessage,
      assistantMessage,
    ]);

    if (!messageOverride) {
      setChatMessage('');
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/ai/zebio/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type':
              'application/json',
          },
          body: JSON.stringify({
            message,
          }),
        }
      );

      if (!response.ok) {
        let detail =
          `Zebio request failed with HTTP ${response.status}`;

        try {
          const errorBody =
            await response.json();

          detail =
            errorBody.detail ||
            errorBody.message ||
            detail;
        } catch {
          // Keep the HTTP status message.
        }

        throw new Error(detail);
      }

      if (!response.body) {
        throw new Error(
          'Zebio returned an empty response stream.'
        );
      }

      setBackendOnline(true);

      const reader =
        response.body.getReader();

      const decoder =
        new TextDecoder();

      let buffer = '';
      let completeResponse = '';
      let streamFinished = false;

      const processEvent = (eventBlock) => {
        const lines =
          eventBlock.split(/\r?\n/);

        let eventName = 'message';
        let data = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventName =
              line.slice(6).trim();
          } else if (
            line.startsWith('data:')
          ) {
            data += line
              .slice(5)
              .trim();
          }
        }

        if (!data) {
          return;
        }

        let payload;

        try {
          payload = JSON.parse(data);
        } catch {
          return;
        }

        if (eventName === 'token') {
          const token =
            payload.content || '';

          if (!token) {
            return;
          }

          completeResponse += token;

          setMessages((current) =>
            current.map((item) =>
              item.id === assistantId
                ? {
                    ...item,
                    content:
                      completeResponse,
                  }
                : item
            )
          );

          setTaskState((previous) => ({
            ...previous,
            status: 'running',
            current_thought:
              'Generating the response.',
            current_output:
              completeResponse,
            current_step:
              'Producing the analysis',
          }));

          return;
        }

        if (eventName === 'done') {
          streamFinished = true;

          setTaskState((previous) => ({
            ...previous,
            status: 'completed',
            current_thought:
              'Analysis complete.',
            current_output:
              completeResponse,
            final_response:
              completeResponse,
            current_step:
              'Response complete',
          }));

          return;
        }

        if (eventName === 'error') {
          throw new Error(
            payload.error ||
              'The public Zebio stream failed.'
          );
        }
      };

      while (!streamFinished) {
        const { value, done } =
          await reader.read();

        if (done) {
          buffer += decoder.decode();
        } else {
          buffer += decoder.decode(
            value,
            { stream: true }
          );
        }

        const blocks =
          buffer.split(/\r?\n\r?\n/);

        buffer =
          blocks.pop() || '';

        for (const block of blocks) {
          if (block.trim()) {
            processEvent(block);
          }

          if (streamFinished) {
            break;
          }
        }

        if (done) {
          break;
        }
      }

      if (buffer.trim() && !streamFinished) {
        processEvent(buffer);
      }

      if (!completeResponse) {
        throw new Error(
          'Zebio completed without returning a response.'
        );
      }

      const elapsed = Math.round(
        performance.now() - startedAt
      );

      setLastResponseTime(elapsed);
      setBackendOnline(true);
    } catch (error) {
      setBackendOnline(false);

      setMessages((current) =>
        current.filter(
          (item) => item.id !== assistantId
        )
      );

      setTaskState(
        createPublicTaskState({
          status: 'failed',
          current_thought:
            'Unable to complete the public analysis.',
        })
      );

      setChatError(
        error.message ||
          'Unable to reach Zebio.'
      );
    } finally {
      setChatLoading(false);

      requestAnimationFrame(() => {
        textareaRef.current?.focus({
          preventScroll: true,
        });
      });
    }
  }

  /*
   * Enter sends.
   * Shift + Enter creates a newline.
   */
  function handleChatKeyDown(event) {
    if (
      event.key === 'Enter' &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  function clearConversation() {
    setMessages([]);
    setChatError('');
    setTaskState(
      createPublicTaskState()
    );
    setLastResponseTime(null);
  }

  return (
    <section
      className="portfolio-ai"
      aria-labelledby="ai-heading"
    >
      <div className="portfolio-ai-header">
        <div>
          <span className="eyebrow">
            PUBLIC AI ENGINEERING INTERFACE
          </span>
        </div>
      </div>

      <ZebioNeuralCore
        taskState={taskState}
        taskError={chatError}
      />

      <div className="portfolio-ai-body">
        {!messages.length &&
        !chatLoading ? (
          <div className="ai-welcome">

            <h3>
              Explore the system.
            </h3>

            <p>
              Ask a technical question,
              investigate a subsystem, or
              challenge the architecture
              with your own engineering idea.
            </p>

            <div className="ai-prompts">
              {QUICK_PROMPTS.map(
                (prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() =>
                      sendMessage(prompt)
                    }
                    disabled={chatLoading}
                  >
                    {prompt}

                    <span aria-hidden="true">
                      ↗
                    </span>
                  </button>
                )
              )}
            </div>
          </div>
        ) : (
          <div className="ai-messages">
            {messages.map(
              (message) => (
                <article
                  key={message.id}
                  className={`ai-message ${message.role}`}
                >
                  <div className="ai-message-avatar">
                    {message.role === 'user'
                      ? 'ET'
                      : 'Z'}
                  </div>

                  <div className="ai-message-content">
                    <div className="ai-message-meta">
                      <strong>
                        {message.role ===
                        'user'
                          ? 'You'
                          : 'Zebio'}
                      </strong>

                      <span>
                        {message.timestamp.toLocaleTimeString(
                          [],
                          {
                            hour: '2-digit',
                            minute: '2-digit',
                          }
                        )}
                      </span>
                    </div>

                    <div className="ai-message-text">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>

                    {message.model && (
                      <div className="ai-message-model">
                        {message.model}
                      </div>
                    )}
                  </div>
                </article>
              )
            )}

            {chatLoading && (
              <article className="ai-message assistant">
                <div className="ai-message-avatar">
                  Z
                </div>

                <div className="ai-message-content">
                  <div className="ai-message-meta">
                    <strong>
                      Zebio
                    </strong>

                    <span>
                      analysing
                    </span>
                  </div>

                  <div className="ai-thinking">
                    <span />
                    <span />
                    <span />

                    <em>
                      Analysing the published
                      architecture...
                    </em>
                  </div>
                </div>
              </article>
            )}

            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {chatError && (
        <div className="ai-error">
          <strong>
            Connection problem
          </strong>

          <span>
            {chatError}
          </span>
        </div>
      )}

      <div className="ai-composer">
        <textarea
          ref={textareaRef}
          value={chatMessage}
          onChange={(event) => setChatMessage(event.target.value)}
          onKeyDown={handleChatKeyDown}
          placeholder="Ask Zebio..."
          rows={1}
          disabled={chatLoading}
          aria-label="Ask Zebio"
        />

        <div className="ai-composer-actions">
          <span>Ask Zebio</span>

          <button
            type="button"
            className={`ai-send-button${chatLoading ? ' loading' : ''}`}
            onClick={() => sendMessage()}
            disabled={chatLoading || !chatMessage.trim()}
            aria-label={chatLoading ? 'Zebio is responding' : 'Send message'}
          >
            {chatLoading ? (
              <span
                className="send-spinner"
                aria-hidden="true"
              >
                ●
              </span>
            ) : (
              '↑'
            )}
          </button>
        </div>
      </div>

      {(messages.length > 0 || chatError) && (
        <button
          type="button"
          className="ai-clear"
          onClick={clearConversation}
          disabled={!messages.length && !chatError}
        >
          Clear conversation
        </button>
      )}

      {latestAssistantMessage && (
        <div className="ai-latest">
          <span>
            LATEST RESPONSE
          </span>

          <p>
            {latestAssistantMessage.content.slice(
              0,
              180
            )}

            {latestAssistantMessage.content
              .length > 180
              ? '...'
              : ''}
          </p>
        </div>
      )}
    </section>
  );
}