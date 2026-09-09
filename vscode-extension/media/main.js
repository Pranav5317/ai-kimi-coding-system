(function () {
  const vscode = acquireVsCodeApi();

  const chatHistory = document.getElementById('chat-history');
  const promptInput = document.getElementById('prompt-input');
  const sendBtn = document.getElementById('send-btn');
  const stateViewer = document.getElementById('state-viewer');
  const agentsList = document.getElementById('agents-list');

  let ws = null;
  let serverPort = 8000;
  let thinkingEl = null;

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId).classList.add('active');

      if (targetId === 'state-tab') {
        fetchState();
      } else if (targetId === 'agents-tab') {
        fetchAgents();
      }
    });
  });

  function connectWebSocket() {
    ws = new WebSocket(`ws://127.0.0.1:${serverPort}/ws`);

    ws.onopen = () => {
      appendSystemMessage('Connected to Multi-Agent Backend Server.');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (err) {
        console.error('Failed to parse WS message', err);
      }
    };

    ws.onclose = () => {
      removeThinkingIndicator();
      appendSystemMessage('Disconnected from server. Reconnecting in 3s...');
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
      removeThinkingIndicator();
      appendSystemMessage('Connection error. Ensure python server.py is running on port 8000.');
    };
  }

  function showThinkingIndicator(text) {
    removeThinkingIndicator();
    thinkingEl = document.createElement('div');
    thinkingEl.className = 'thinking-spinner';
    thinkingEl.innerHTML = `<span>⏳</span> <em>${text || 'Agent 5 is thinking...'}</em>`;
    chatHistory.appendChild(thinkingEl);
    scrollToBottom();
  }

  function updateThinkingIndicator(text) {
    if (thinkingEl) {
      const em = thinkingEl.querySelector('em');
      if (em) em.textContent = text;
    } else {
      showThinkingIndicator(text);
    }
  }

  function removeThinkingIndicator() {
    if (thinkingEl && thinkingEl.parentNode) {
      thinkingEl.parentNode.removeChild(thinkingEl);
    }
    thinkingEl = null;
  }

  function setWorkingState(isWorking) {
    if (isWorking) {
      sendBtn.disabled = true;
      promptInput.disabled = true;
      promptInput.placeholder = 'Agent 5 is working on your request...';
      showThinkingIndicator('Agent 5 is reasoning...');
    } else {
      sendBtn.disabled = false;
      promptInput.disabled = false;
      promptInput.placeholder = 'Ask Agent 5 to build or refactor...';
      removeThinkingIndicator();
      promptInput.focus();
    }
  }

  function handleServerMessage(data) {
    if (data.type === 'init') {
      if (data.project_state) {
        stateViewer.textContent = data.project_state;
      }
    } else if (data.type === 'history') {
      if (Array.isArray(data.history) && data.history.length > 0) {
        chatHistory.innerHTML = '';
        appendSystemMessage('Connected to Multi-Agent Backend Server. Restored previous session history.');
        data.history.forEach(item => {
          if (item.role === 'user') {
            appendUserMessage(item.content);
          } else if (item.role === 'assistant') {
            if (item.content) {
              appendAssistantMessage(item.content);
            }
          } else if (item.role === 'tool') {
            appendToolExecution(item.name || 'tool', {}, item.content || '');
          }
        });
      } else {
        chatHistory.innerHTML = '';
        appendSystemMessage('Connected to Multi-Agent Backend Server. (New chat session)');
      }
      setWorkingState(false);
    } else if (data.type === 'status') {
      updateThinkingIndicator(data.content);
    } else if (data.type === 'tool_execution') {
      appendToolExecution(data.tool, data.args, data.result);
      updateThinkingIndicator(`Executing ${data.tool}...`);
    } else if (data.type === 'assistant_response') {
      removeThinkingIndicator();
      appendAssistantMessage(data.content);
      setWorkingState(false);
    } else if (data.type === 'project_state') {
      stateViewer.textContent = data.content;
    }
  }

  function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'msg user';
    div.textContent = text;
    chatHistory.appendChild(div);
    scrollToBottom();
  }

  function appendAssistantMessage(text) {
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.textContent = text;
    chatHistory.appendChild(div);
    scrollToBottom();
  }

  function appendToolExecution(tool, args, result) {
    const div = document.createElement('div');
    div.className = 'msg tool';
    const badge = document.createElement('span');
    badge.className = 'tool-badge';
    badge.textContent = `⚙️ ${tool}`;
    div.appendChild(badge);

    const detail = document.createElement('div');
    detail.style.marginTop = '4px';
    const safeResult = String(result || '');
    detail.textContent = `Args: ${JSON.stringify(args || {})}\nResult: ${safeResult.substring(0, 150)}${safeResult.length > 150 ? '...' : ''}`;
    div.appendChild(detail);

    chatHistory.appendChild(div);
    scrollToBottom();
  }

  function appendSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'msg system';
    div.style.fontStyle = 'italic';
    div.style.opacity = '0.7';
    div.style.fontSize = '11px';
    div.textContent = `[System] ${text}`;
    chatHistory.appendChild(div);
    scrollToBottom();
  }

  function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  function sendPrompt() {
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    appendUserMessage(prompt);
    promptInput.value = '';
    setWorkingState(true);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'prompt', content: prompt }));
    } else {
      appendSystemMessage('Server not connected. Attempting HTTP REST fallback...');
      fetch(`http://127.0.0.1:${serverPort}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt })
      })
      .then(res => res.json())
      .then(data => {
        if (data.tool_executions) {
          data.tool_executions.forEach(t => appendToolExecution(t.tool, t.args, t.result));
        }
        if (data.response) {
          appendAssistantMessage(data.response);
        }
        setWorkingState(false);
      })
      .catch(err => {
        appendSystemMessage(`REST API Error: ${err}`);
        setWorkingState(false);
      });
    }
  }

  function fetchState() {
    fetch(`http://127.0.0.1:${serverPort}/api/state`)
      .then(res => res.json())
      .then(data => {
        stateViewer.textContent = data.content || 'No project state recorded.';
      })
      .catch(() => {});
  }

  function fetchAgents() {
    fetch(`http://127.0.0.1:${serverPort}/api/agents`)
      .then(res => res.json())
      .then(data => {
        agentsList.innerHTML = '';
        const h3 = document.createElement('h3');
        h3.style.margin = '0 0 10px 0';
        h3.style.fontSize = '12px';
        h3.style.opacity = '0.8';
        h3.textContent = 'Agent Team & Roles';
        agentsList.appendChild(h3);

        (data.agents || []).forEach(agent => {
          const card = document.createElement('div');
          card.className = 'agent-card';
          const h4 = document.createElement('h4');
          h4.textContent = `[${agent.agent_id}] ${agent.role}`;
          card.appendChild(h4);

          const capsDiv = document.createElement('div');
          capsDiv.className = 'agent-caps';
          agent.capabilities.forEach(cap => {
            const badge = document.createElement('span');
            badge.className = 'cap-badge';
            badge.textContent = cap;
            capsDiv.appendChild(badge);
          });
          card.appendChild(capsDiv);
          agentsList.appendChild(card);
        });

        // Fetch installed skills
        fetch(`http://127.0.0.1:${serverPort}/api/skills`)
          .then(res => res.json())
          .then(skillData => {
            const h3Skills = document.createElement('h3');
            h3Skills.style.margin = '16px 0 10px 0';
            h3Skills.style.fontSize = '12px';
            h3Skills.style.opacity = '0.8';
            h3Skills.textContent = '⚡ Installed Skills Library';
            agentsList.appendChild(h3Skills);

            (skillData.skills || []).forEach(skill => {
              const card = document.createElement('div');
              card.className = 'agent-card';
              card.style.borderColor = 'var(--button-bg)';
              const h4 = document.createElement('h4');
              h4.textContent = `⚡ ${skill.name} (${skill.target_agent})`;
              card.appendChild(h4);

              const p = document.createElement('p');
              p.style.margin = '4px 0 0 0';
              p.style.fontSize = '11px';
              p.style.opacity = '0.8';
              p.textContent = skill.description;
              card.appendChild(p);

              agentsList.appendChild(card);
            });
          })
          .catch(() => {});
      })
      .catch(() => {});
  }

  sendBtn.addEventListener('click', sendPrompt);
  promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });

  // Start connection
  connectWebSocket();
})();
