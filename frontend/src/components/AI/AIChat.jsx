import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { taskApi } from '../../services/api';
import ZebioNeuralCore from '../NeuralCore/ZebioNeuralCore';

const QUICK_PROMPTS = [
  'Tell me about Eusebiu and his background.',
  'What are Eusebiu\'s strongest projects?',
  'What technologies and skills does Eusebiu work with?',
  'Tell me about the Zebio project.',
];

function createId() {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function AIChat() {
  const textareaRef = useRef(null);
  const chatEndRef = useRef(null);

  const [chatMessage, setChatMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  const [activeTaskId, setActiveTaskId] = useState(null);
  const [taskState, setTaskState] = useState(null);
  const [taskError, setTaskError] = useState('');

  const [backendOnline, setBackendOnline] = useState(false);
  const [lastResponseTime, setLastResponseTime] = useState(null);

  const [sessionId] = useState(() => createId());

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
   * Keep the conversation anchored to the newest message.
   */
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
    });
  }, [messages, chatLoading]);

  /*
   * Backend health check.
   */
  useEffect(() => {
    let mounted = true;

    async function checkBackend() {
      const startedAt = performance.now();

      try {
        const response = await fetch('/health');

        if (!response.ok) {
          throw new Error('Backend unavailable');
        }

        if (!mounted) {
          return;
        }

        setBackendOnline(true);
        setLastResponseTime(
          Math.round(performance.now() - startedAt)
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
   * Stream engineering-task updates through SSE.
   */
  useEffect(() => {
    if (!activeTaskId) {
      return undefined;
    }

    let closed = false;
    let source = null;

    const streamUrl =
      `/api/v1/ai/tasks/${activeTaskId}/stream`;

    source = new EventSource(streamUrl);

    const applySnapshot = (snapshot) => {
      setTaskState(snapshot);
      setTaskError('');
    };

    const handleSnapshot = (event) => {
      if (closed) {
        return;
      }

      try {
        applySnapshot(
          JSON.parse(event.data)
        );
      } catch (error) {
        console.warn(
          '[ZEBIO SSE] bad snapshot',
          error
        );
      }
    };

    const handleThought = (event) => {
      if (closed) {
        return;
      }

      try {
        const { thought } =
          JSON.parse(event.data);

        setTaskState((previous) =>
          previous
            ? {
                ...previous,
                current_thought: thought,
              }
            : {
                current_thought: thought,
              }
        );
      } catch (error) {
        console.warn(
          '[ZEBIO SSE] bad thought',
          error
        );
      }
    };

    const handleStep = (event) => {
      if (closed) {
        return;
      }

      try {
        const incoming =
          JSON.parse(event.data);

        setTaskState((previous) => {
          const base =
            previous || { steps: [] };

          const steps = base.steps
            ? [...base.steps]
            : [];

          const index = steps.findIndex(
            (step) =>
              step.step_id ===
              incoming.step_id
          );

          if (index >= 0) {
            steps[index] = {
              ...steps[index],
              ...incoming,
            };
          } else {
            steps.push(incoming);
          }

          return {
            ...base,
            steps,
          };
        });
      } catch (error) {
        console.warn(
          '[ZEBIO SSE] bad step',
          error
        );
      }
    };

    const handleStatus = (event) => {
      if (closed) {
        return;
      }

      try {
        const data =
          JSON.parse(event.data);

        setTaskState((previous) =>
          previous
            ? {
                ...previous,
                ...data,
              }
            : previous
        );
      } catch (error) {
        console.warn(
          '[ZEBIO SSE] bad status',
          error
        );
      }
    };

    const handleFinalResponse = (event) => {
      if (closed) {
        return;
      }

      try {
        const {
          final_response: finalResponse,
        } = JSON.parse(event.data);

        setTaskState((previous) =>
          previous
            ? {
                ...previous,
                final_response:
                  finalResponse,
              }
            : previous
        );
      } catch (error) {
        console.warn(
          '[ZEBIO SSE] bad final response',
          error
        );
      }
    };

    const handleDone = (event) => {
      if (closed) {
        return;
      }

      let snapshot = null;

      try {
        snapshot = JSON.parse(event.data);
        applySnapshot(snapshot);
      } catch (error) {
        console.warn(
          '[ZEBIO SSE] bad done snapshot',
          error
        );
      }

      closed = true;

      if (source) {
        source.close();
      }

      if (snapshot?.final_response) {
        setMessages((current) => {
          const last =
            current[current.length - 1];

          if (
            last?.role === 'assistant' &&
            last.content ===
              snapshot.final_response
          ) {
            return current;
          }

          return [
            ...current,
            {
              id: createId(),
              role: 'assistant',
              content:
                snapshot.final_response,
              timestamp: new Date(),
            },
          ];
        });
      }

      setChatLoading(false);
      setActiveTaskId(null);
    };

    source.addEventListener(
      'snapshot',
      handleSnapshot
    );

    source.addEventListener(
      'thought',
      handleThought
    );

    source.addEventListener(
      'step',
      handleStep
    );

    source.addEventListener(
      'status',
      handleStatus
    );

    source.addEventListener(
      'final_response',
      handleFinalResponse
    );

    source.addEventListener(
      'done',
      handleDone
    );

    source.onerror = (error) => {
      if (closed) {
        return;
      }

      console.warn(
        '[ZEBIO SSE] connection error',
        error
      );
    };

    return () => {
      closed = true;

      if (source) {
        source.close();
      }
    };
  }, [activeTaskId]);

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
   * Send a message to Zebio.
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

    const startedAt =
      performance.now();

    setChatLoading(true);
    setChatError('');

    setMessages((current) => [
      ...current,
      {
        id: createId(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      },
    ]);

    if (!messageOverride) {
      setChatMessage('');
    }

    try {
      const response = await fetch(
        '/api/v1/ai/chat',
        {
          method: 'POST',
          headers: {
            'Content-Type':
              'application/json',
          },
          body: JSON.stringify({
            message,
            session_id: sessionId,
          }),
        }
      );

      const rawText =
        await response.text();

      let result = {};

      try {
        result = rawText
          ? JSON.parse(rawText)
          : {};
      } catch {
        throw new Error(
          'Zebio returned an invalid JSON response.'
        );
      }

      if (!response.ok) {
        throw new Error(
          result.detail ||
            result.message ||
            `Zebio request failed with HTTP ${response.status}`
        );
      }

      const elapsed = Math.round(
        performance.now() - startedAt
      );

      setLastResponseTime(elapsed);
      setBackendOnline(true);

      if (result.task_id) {
        setActiveTaskId(
          result.task_id
        );
        setTaskState(null);
        setTaskError('');
        return;
      }

      if (result.response) {
        setMessages((current) => [
          ...current,
          {
            id: createId(),
            role: 'assistant',
            content: result.response,
            model: result.model,
            timestamp: new Date(),
          },
        ]);
      }
    } catch (error) {
      setBackendOnline(false);

      setChatError(
        error.message ||
          'Unable to reach Zebio.'
      );

      setChatLoading(false);
    } finally {
      requestAnimationFrame(() => {
        textareaRef.current?.focus();
      });
    }
  }

  /*
   * Approve a pending engineering action.
   */
  async function handleApprove(
    approvalId
  ) {
    if (!approvalId) {
      return;
    }

    try {
      setTaskError('');

      const result =
        await taskApi.approveApproval(
          approvalId
        );

      if (result?.response) {
        setMessages(
          (currentMessages) => [
            ...currentMessages,
            {
              id: createId(),
              role: 'assistant',
              content: result.response,
              timestamp: new Date(),
            },
          ]
        );
      }
    } catch (error) {
      setTaskError(
        error.response?.data?.detail ||
          error.message ||
          'Unable to approve this action.'
      );
    }
  }

  /*
   * Reject a pending engineering action.
   */
  async function handleReject(
    approvalId
  ) {
    if (!approvalId) {
      return;
    }

    try {
      setTaskError('');

      await taskApi.rejectApproval(
        approvalId
      );
    } catch (error) {
      setTaskError(
        error.response?.data?.detail ||
          error.message ||
          'Unable to reject this action.'
      );
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
    setTaskError('');
    setTaskState(null);
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
            PRIVATE LOCAL AI
          </span>

          <h2 id="ai-heading">
            Ask Zebio about Eusebiu.
          </h2>

          <p>
            A local AI assistant that can
            answer questions about my
            background, projects,
            experience and technical work.
          </p>
        </div>

        <div className="ai-status">
          <span
            className={
              backendOnline
                ? 'status-dot online'
                : 'status-dot'
            }
          />

          <span>
            {backendOnline
              ? 'ONLINE'
              : 'OFFLINE'}
          </span>

          <span className="ai-model">
            {modelName}
          </span>
        </div>
      </div>

      <ZebioNeuralCore
        taskState={taskState}
        taskError={taskError}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      <div className="portfolio-ai-body">
        {!messages.length &&
        !chatLoading ? (
          <div className="ai-welcome">
            <div className="ai-welcome-mark">
              Z
            </div>

            <h3>
              Curious about my work?
            </h3>

            <p>
              Ask a question directly, or
              start with one of these.
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
                          ? 'Eusebiu'
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
                      {message.content}
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
                      thinking
                    </span>
                  </div>

                  <div className="ai-thinking">
                    <span />
                    <span />
                    <span />
                    <em>
                      Running local inference...
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
          onChange={(event) =>
            setChatMessage(
              event.target.value
            )
          }
          onKeyDown={handleChatKeyDown}
          placeholder="Ask about my projects, experience or skills..."
          rows={2}
          disabled={chatLoading}
          aria-label="Ask Zebio a question"
        />

        <div className="ai-composer-footer">
          <span>
            Local inference
            {lastResponseTime !== null
              ? ` · ${lastResponseTime} ms`
              : ''}
          </span>

          <span>
            Enter to send · Shift + Enter
            for newline
          </span>

          <button
            type="button"
            onClick={() =>
              sendMessage()
            }
            disabled={
              chatLoading ||
              !chatMessage.trim()
            }
            aria-label={
              chatLoading
                ? 'Sending'
                : 'Send message'
            }
          >
            {chatLoading ? (
              <span className="send-spinner" />
            ) : (
              '↑'
            )}
          </button>
        </div>
      </div>

      {(messages.length > 0 ||
        chatError) && (
        <button
          type="button"
          className="ai-clear"
          onClick={clearConversation}
          disabled={
            !messages.length &&
            !chatError
          }
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