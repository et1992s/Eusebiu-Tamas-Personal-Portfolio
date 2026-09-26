import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { taskApi } from '../services/api';
import '../App.css';

const QUICK_PROMPTS = [
  'Inspect the current project architecture and tell me what you would improve first.',
  'Explain the current backend architecture and how the frontend communicates with it.',
  'Help me debug the application and identify the most likely failure points.',
];

function App() {
  const [chatMessage, setChatMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  const [activeTaskId, setActiveTaskId] = useState(null);
  const [taskState, setTaskState] = useState(null);
  const [taskError, setTaskError] = useState('');

  const [backendOnline, setBackendOnline] = useState(null);
  const [lastResponseTime, setLastResponseTime] = useState(null);

  const [sessionId] = useState(() =>
    crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  );

  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);

  const modelName =
    [...messages]
      .reverse()
      .find((message) => message.model)?.model ||
    'qwen2.5-coder:14b';

  const latestAssistantMessage = useMemo(
    () =>
      [...messages]
        .reverse()
        .find((message) => message.role === 'assistant'),
    [messages]
  );

  const taskStatus = taskState?.status ?? null;

  const taskDisplayStatus =
    taskState?.steps?.some(
      (step) => step.approval_status === 'pending'
    )
      ? 'approval_required'
      : taskStatus;

  /*
   * Whether the current engineering task is still running.
   */
  const taskIsActive =
    taskStatus === 'pending' ||
    taskStatus === 'running';

  /*
   * Whether the current engineering task has finished.
   */
  const taskIsTerminal =
    taskStatus === 'completed' ||
    taskStatus === 'failed' ||
    taskStatus === 'cancelled';

  /*
   * Scroll chat to newest message.
   */
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: 'smooth',
    });
  }, [messages, chatLoading]);

  /*
   * Check FastAPI backend periodically.
   */
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch('/health', {
          cache: 'no-store',
        });

        setBackendOnline(response.ok);
      } catch {
        setBackendOnline(false);
      }
    };

    checkBackend();

    const interval = window.setInterval(
      checkBackend,
      15000
    );

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  /*
   * Observe the active engineering task.
   *
   * The backend TaskManager is the source of truth.
   * The frontend periodically requests a task snapshot
   * until the task reaches a terminal state.
   */
  useEffect(() => {
    if (!activeTaskId) {
      return;
    }

    let cancelled = false;
    let intervalId = null;

    const pollTask = async () => {
      try {
        const state = await taskApi.getTask(activeTaskId);

        if (cancelled) {
          return;
        }

        setTaskState(state);
        setTaskError('');

        const terminalStates = [
          'completed',
          'failed',
          'cancelled',
        ];

        if (terminalStates.includes(state.status)) {
          window.clearInterval(intervalId);
          intervalId = null;
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        setTaskError(
          error.response?.data?.detail ||
            error.message ||
            'Unable to retrieve task state.'
        );
      }
    };

    pollTask();

    intervalId = window.setInterval(
      pollTask,
      1000
    );

    return () => {
      cancelled = true;

      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [activeTaskId]);

  /*
   * Ctrl/Cmd + K focuses the AI composer.
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
  async function sendMessage(messageOverride = null) {
    console.log(
      '[ZEBIO CHAT] sendMessage invoked',
      {
        messageOverride,
        chatLoading,
        timestamp: performance.now(),
      }
    );

    const message = (
      messageOverride ?? chatMessage
    ).trim();

    if (!message || chatLoading) {
      return;
    }

    const startedAt = performance.now();

    setChatLoading(true);
    setChatError('');

    /*
     * Immediately display the user's message.
     */
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
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
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message,
            session_id: sessionId,
          }),
        }
      );

      const rawText = await response.text();

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
        setActiveTaskId(result.task_id);
        setTaskState(null);
        setTaskError('');
      }

      /*
       * Display Zebio's response.
       */
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          role: 'assistant',
          content:
            result.response ||
            'Zebio returned no response.',
          model: result.model,
          timestamp: new Date(),
        },
      ]);
    } catch (error) {
      setBackendOnline(false);

      setChatError(
        error.message ||
          'Unable to reach Zebio.'
      );
    } finally {
      setChatLoading(false);

      requestAnimationFrame(() => {
        textareaRef.current?.focus();
      });
    }
  }

  /*
   * Convert internal task states into user-facing labels.
   */
  function getTaskStatusLabel(status) {
    const labels = {
      pending: 'Queued',
      running: 'Executing',
      approval_required: 'Approval required',
      completed: 'Completed',
      failed: 'Failed',
      cancelled: 'Cancelled',
    };

    return labels[status] || status;
  }

  /*
   * Approve a pending engineering task action.
   */
  async function handleApprove(approvalId) {
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
        setMessages((currentMessages) => [
          ...currentMessages,
          {
            role: 'assistant',
            content: result.response,
          },
        ]);
      }

      /*
       * The backend resumes the task immediately.
       * Existing task polling picks up the new state.
       */
    } catch (error) {
      setTaskError(
        error.response?.data?.detail ||
          error.message ||
          'Unable to approve this action.'
      );
    }
  }

  /*
   * Reject a pending engineering task action.
   */
  async function handleReject(approvalId) {
    if (!approvalId) {
      return;
    }

    try {
      setTaskError('');

      await taskApi.rejectApproval(
        approvalId
      );

      /*
       * The backend cancels the task immediately.
       * Existing task polling picks up the new state.
       */
    } catch (error) {
      setTaskError(
        error.response?.data?.detail ||
          error.message ||
          'Unable to reject this action.'
      );
    }
  }

  /*
   * Enter = send
   * Shift + Enter = newline
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

  /*
   * Clear the conversation.
   */
  function clearConversation() {
    setMessages([]);
    setChatError('');
    setLastResponseTime(null);
  }

  return (
    <main className="workspace">

      {/* ===================================================
          HERO
      ==================================================== */}

      <section className="hero-panel">

        <div className="hero-content">

          <div className="eyebrow">
            <span className="eyebrow-line" />
            COMMAND CENTRE
          </div>

          <h1>
            Welcome home, sir.
            <br />
            <span>
              {' '}All systems are online and fully operational.
            </span>
          </h1>

          <p className="hero-copy">
            I'm ready to connect your development
            workspace, backend services,
            local models and market intelligence
            into one private command surface.
          </p>

        </div>

        <div className="hero-meta">

          <div>
            <span>SESSION</span>

            <strong>
              {sessionId.slice(0, 8)}
            </strong>
          </div>

          <div>
            <span>LATENCY</span>

            <strong>
              {lastResponseTime
                ? `${lastResponseTime} ms`
                : '—'}
            </strong>
          </div>

          <div>
            <span>MODE</span>

            <strong>
              AI ENGINEERING
            </strong>
          </div>

        </div>

      </section>

      {/* ===================================================
          AI WORKSPACE
      ==================================================== */}

      <section className="main-grid">

        <div className="ai-column">

          <div className="panel ai-panel">

            {/* =================================================
                PANEL HEADER
            ================================================== */}

            <div className="panel-header">

              <div className="panel-title-group">

                <div className="section-icon ai-icon">
                  ✦
                </div>

                <div>
                  <h2>
                    Personal AI Assistant
                  </h2>

                  <p>
                    Private session · local inference
                  </p>
                </div>

              </div>

              <button
                className="ghost-button"
                onClick={clearConversation}
                disabled={
                  !messages.length &&
                  !chatError
                }
                title="Clear conversation"
              >
                Clear
              </button>

            </div>

            {/* =================================================
                ENGINEERING TASK STATUS
            ================================================== */}

            {taskState && (
              <div className="task-status-panel">

                <div className="task-status-header">

                  <span>
                    ENGINEERING TASK
                  </span>

                  <strong>
                    {getTaskStatusLabel(
                      taskDisplayStatus
                    )}
                  </strong>

                </div>

                <div className="task-status-goal">
                  {taskState.goal}
                </div>

                {taskState.current_step && (
                  <div className="task-status-current">

                    <span>
                      Current action
                    </span>

                    <strong>
                      {taskState.current_step}
                    </strong>

                  </div>
                )}

                {taskState.steps?.length > 0 && (
                  <div className="task-status-steps">

                    {taskState.steps.map(
                      (step) => (
                        <div
                          key={step.step_id}
                          className={`task-step ${step.status}`}
                        >

                          <span className="task-step-indicator">
                            {step.status ===
                            'completed'
                              ? '✓'
                              : step.status ===
                                'failed'
                                ? '!'
                                : step.status ===
                                  'approval_required'
                                  ? '!'
                                  : '●'}
                          </span>

                          <span>
                            {step.tool_name}
                          </span>

                          <span className="task-step-status">
                            {getTaskStatusLabel(
                              step.status
                            )}
                          </span>

                          {step.approval_id &&
                            step.approval_status ===
                              'pending' && (
                              <>

                                <button
                                  type="button"
                                  onClick={() =>
                                    handleApprove(
                                      step.approval_id
                                    )
                                  }
                                >
                                  Approve
                                </button>

                                <button
                                  type="button"
                                  onClick={() =>
                                    handleReject(
                                      step.approval_id
                                    )
                                  }
                                >
                                  Reject
                                </button>

                              </>
                            )}

                        </div>
                      )
                    )}

                  </div>
                )}

                {taskError && (
                  <div className="task-status-error">
                    {taskError}
                  </div>
                )}

              </div>
            )}

            {/* =================================================
                CHAT AREA
            ================================================== */}

            <div className="chat-area">

              {!messages.length &&
              !chatLoading ? (

                <div className="empty-chat">

                  <div className="zebios-core">

                    <svg
                      className="zebios-logo"
                      viewBox="0 0 240 240"
                      aria-label="Zebios"
                    >

                      <defs>

                        <linearGradient
                          id="zebiosZGradient"
                          x1="45"
                          y1="45"
                          x2="195"
                          y2="195"
                        >
                          <stop
                            offset="0%"
                            stopColor="#596875"
                          />

                          <stop
                            offset="42%"
                            stopColor="#35424f"
                          />

                          <stop
                            offset="72%"
                            stopColor="#202b36"
                          />

                          <stop
                            offset="100%"
                            stopColor="#111820"
                          />
                        </linearGradient>

                        <linearGradient
                          id="zebiosEnergyGradient"
                          x1="0"
                          y1="0"
                          x2="1"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#55d7ff"
                          />

                          <stop
                            offset="50%"
                            stopColor="#6f8cff"
                          />

                          <stop
                            offset="100%"
                            stopColor="#a66cff"
                          />
                        </linearGradient>

                        <filter
                          id="zebiosGlow"
                          x="-100%"
                          y="-100%"
                          width="300%"
                          height="300%"
                        >
                          <feGaussianBlur
                            stdDeviation="3"
                            result="blur"
                          />

                          <feMerge>
                            <feMergeNode in="blur" />
                            <feMergeNode in="SourceGraphic" />
                          </feMerge>
                        </filter>

                        <filter
                          id="zebiosStrongGlow"
                          x="-100%"
                          y="-100%"
                          width="300%"
                          height="300%"
                        >
                          <feGaussianBlur
                            stdDeviation="5"
                            result="blur"
                          />

                          <feMerge>
                            <feMergeNode in="blur" />
                            <feMergeNode in="SourceGraphic" />
                          </feMerge>
                        </filter>

                      </defs>

                      {/* OUTER INTELLIGENCE FIELD */}

                      <circle
                        className="zebios-field zebios-field-one"
                        cx="120"
                        cy="120"
                        r="101"
                        fill="none"
                        stroke="url(#zebiosEnergyGradient)"
                        strokeWidth="0.7"
                        strokeDasharray="2 18 42 120"
                      />

                      <circle
                        className="zebios-field zebios-field-two"
                        cx="120"
                        cy="120"
                        r="91"
                        fill="none"
                        stroke="url(#zebiosEnergyGradient)"
                        strokeWidth="0.8"
                        strokeDasharray="35 80 4 130"
                      />

                      <circle
                        className="zebios-field zebios-field-three"
                        cx="120"
                        cy="120"
                        r="76"
                        fill="none"
                        stroke="url(#zebiosEnergyGradient)"
                        strokeWidth="0.5"
                        strokeDasharray="3 60 22 100"
                      />

                      {/* TECHNICAL CROSS LINES */}

                      <path
                        className="zebios-tech-line"
                        d="M 20 120 H 68"
                      />

                      <path
                        className="zebios-tech-line"
                        d="M 172 120 H 220"
                      />

                      <path
                        className="zebios-tech-line"
                        d="M 120 20 V 68"
                      />

                      <path
                        className="zebios-tech-line"
                        d="M 120 172 V 220"
                      />

                      {/* SYSTEM NODES */}

                      <circle
                        className="zebios-node zebios-node-one"
                        cx="40"
                        cy="78"
                        r="2"
                      />

                      <circle
                        className="zebios-node zebios-node-two"
                        cx="199"
                        cy="61"
                        r="1.5"
                      />

                      <circle
                        className="zebios-node zebios-node-three"
                        cx="204"
                        cy="165"
                        r="2"
                      />

                      <circle
                        className="zebios-node zebios-node-four"
                        cx="51"
                        cy="181"
                        r="1.5"
                      />

                      {/* MAIN GEOMETRIC Z */}

                      <path
                        className="zebios-z"
                        d="
                          M 67 68
                          L 173 68
                          L 173 84
                          L 100 156
                          L 173 156
                          L 173 172
                          L 67 172
                          L 67 156
                          L 140 84
                          L 67 84
                          Z
                        "
                        fill="url(#zebiosZGradient)"
                      />

                      {/* PRIMARY ENERGY PATH */}

                      <path
                        className="zebios-energy-path"
                        d="
                          M 73 75
                          L 167 75
                          L 94 165
                          L 167 165
                        "
                        fill="none"
                        stroke="url(#zebiosEnergyGradient)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeDasharray="0 310"
                        filter="url(#zebiosStrongGlow)"
                      />

                      {/* INTERNAL Z ENERGY TRACE 1 */}

                      <path
                        className="zebios-z-trace zebios-z-trace-one"
                        d="
                          M 73 80
                          L 162 80
                          L 90 160
                        "
                        fill="none"
                        stroke="#5de0ff"
                        strokeWidth="1.1"
                        strokeLinecap="round"
                        strokeDasharray="4 14 22 80"
                      />

                      {/* INTERNAL Z ENERGY TRACE 2 */}

                      <path
                        className="zebios-z-trace zebios-z-trace-two"
                        d="
                          M 78 88
                          L 151 88
                          L 102 150
                          L 164 150
                        "
                        fill="none"
                        stroke="#9278ff"
                        strokeWidth="0.9"
                        strokeLinecap="round"
                        strokeDasharray="2 18 30 70"
                      />

                      {/* INTERNAL Z CIRCUIT TRACE */}

                      <path
                        className="zebios-z-trace zebios-z-trace-three"
                        d="
                          M 75 72
                          L 166 72

                          M 97 168
                          L 165 168
                        "
                        fill="none"
                        stroke="#74dfff"
                        strokeWidth="0.7"
                        strokeLinecap="round"
                        strokeDasharray="3 12"
                      />

                      {/* CENTRAL INTELLIGENCE CORE */}

                      <circle
                        className="zebios-core-glow"
                        cx="120"
                        cy="120"
                        r="7"
                        fill="#67dfff"
                        filter="url(#zebiosStrongGlow)"
                      />

                      <circle
                        className="zebios-core-point"
                        cx="120"
                        cy="120"
                        r="2.5"
                        fill="#d8f8ff"
                      />

                    </svg>

                  </div>

                  <h3>
                    What are we building?
                  </h3>

                  <p>
                    Zebio can analyse code,
                    debug a service, explain an
                    architecture, design a feature
                    or help you reason through an
                    engineering problem.
                  </p>

                  <div className="prompt-grid">

                    {QUICK_PROMPTS.map(
                      (prompt) => (
                        <button
                          key={prompt}
                          className="prompt-card"
                          onClick={() =>
                            sendMessage(prompt)
                          }
                          disabled={chatLoading}
                        >

                          <span>
                            ↗
                          </span>

                          {prompt}

                        </button>
                      )
                    )}

                  </div>

                </div>

              ) : (

                <div className="message-list">

                  {messages.map(
                    (message) => (
                      <article
                        key={message.id}
                        className={`message ${message.role}`}
                      >

                        <div className="message-avatar">
                          {message.role === 'user'
                            ? 'ET'
                            : 'Z'}
                        </div>

                        <div className="message-body">

                          <div className="message-meta">

                            <strong>
                              {message.role === 'user'
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

                          <div className="message-content">
                            {message.content}
                          </div>

                          {message.model && (
                            <div className="message-model">
                              {message.model}
                            </div>
                          )}

                        </div>

                      </article>
                    )
                  )}

                  {chatLoading && (
                    <article className="message assistant">

                      <div className="message-avatar">
                        Z
                      </div>

                      <div className="message-body">

                        <div className="message-meta">

                          <strong>
                            Zebio
                          </strong>

                          <span>
                            thinking
                          </span>

                        </div>

                        <div className="thinking">

                          <span />
                          <span />
                          <span />

                          <em>
                            Running local inference…
                          </em>

                        </div>

                      </div>

                    </article>
                  )}

                  <div ref={chatEndRef} />

                </div>

              )}

            </div>

            {/* =================================================
                ERROR
            ================================================== */}

            {chatError && (
              <div className="error-banner">

                <span>
                  !
                </span>

                <div>

                  <strong>
                    Connection problem
                  </strong>

                  <p>
                    {chatError}
                  </p>

                </div>

              </div>
            )}

            {/* =================================================
                COMPOSER
            ================================================== */}

            <div className="composer">

              <textarea
                ref={textareaRef}
                value={chatMessage}
                onChange={(event) =>
                  setChatMessage(
                    event.target.value
                  )
                }
                onKeyDown={
                  handleChatKeyDown
                }
                placeholder="Ask Zebio"
                rows={2}
                disabled={chatLoading}
              />

                <button
                  className="send-button"
                  onClick={() => sendMessage()}
                  disabled={chatLoading || !chatMessage.trim()}
                  aria-label={chatLoading ? 'Sending' : 'Send message'}
                  title={chatLoading ? 'Sending…' : 'Send'}
                >
                  {chatLoading ? (
                    <span className="send-spinner" aria-hidden="true" />
                  ) : (
                    <svg
                      className="send-arrow"
                      viewBox="0 0 16 16"
                      width="14"
                      height="14"
                      aria-hidden="true"
                    >
                      <path
                        d="M8 13.5V3.5M8 3.5L3.5 8M8 3.5L12.5 8"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>

            </div>

          </div>

          {/* =================================================
              LATEST RESPONSE
          ================================================== */}

          {latestAssistantMessage && (
            <div className="insight-strip">

              <span className="insight-label">
                LATEST RESPONSE
              </span>

              <span className="insight-text">
                {latestAssistantMessage.content.slice(
                  0,
                  150
                )}

                {latestAssistantMessage.content
                  .length > 150
                  ? '…'
                  : ''}
              </span>

            </div>
          )}

        </div>

      </section>

    </main>
  );
}

export default App;
