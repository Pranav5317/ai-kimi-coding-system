(function () {
  const vscode = acquireVsCodeApi();

  const chatHistory = document.getElementById('chat-history');
  const promptInput = document.getElementById('prompt-input');
  const sendBtn = document.getElementById('send-btn');
  const stateViewer = document.getElementById('state-viewer');
  const agentsList = document.getElementById('agents-list');
  const connectionDot = document.getElementById('connection-dot');
  const modelBadge = document.getElementById('model-badge');
  const refreshStateBtn = document.getElementById('refresh-state-btn');
  const openStateBtn = document.getElementById('open-state-btn');

  let ws = null;
  let serverPort = window.serverPort || 8000;
  let serverHost = window.serverHost || '127.0.0.1';
  let thinkingEl = null;

  if (connectionDot) {
    connectionDot.addEventListener('click', () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket();
      }
    });
  }

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

  const clearBtn = document.getElementById('clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        if (confirm('Clear chat history for this project folder?')) {
          ws.send(JSON.stringify({ type: 'clear_history' }));
        }
      }
    });
  }

  if (refreshStateBtn) {
    refreshStateBtn.addEventListener('click', fetchState);
  }

  if (openStateBtn) {
    openStateBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'openFile', filePath: 'PROJECT_STATE.md' });
    });
  }

  function setConnectionStatus(status, text) {
    if (!connectionDot) return;
    connectionDot.className = `status-dot ${status}`;
    connectionDot.title = `Server status: ${text || status} (Click to reconnect)`;
  }

  function connectWebSocket() {
    setConnectionStatus('connecting', 'Connecting to backend server...');
    serverPort = window.serverPort || 8000;
    serverHost = window.serverHost || '127.0.0.1';
    const wsUrl = `ws://${serverHost}:${serverPort}/ws` + (window.workspacePath ? `?workspace=${encodeURIComponent(window.workspacePath)}` : '');
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnectionStatus('connected', 'Connected to Multi-Agent Backend Server');
      if (window.workspacePath) {
        ws.send(JSON.stringify({
          type: 'switch_workspace',
          workspace_path: window.workspacePath
        }));
      }
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
      setConnectionStatus('disconnected', 'Disconnected from server');
      removeThinkingIndicator();
      setTimeout(connectWebSocket, 4000);
    };

    ws.onerror = () => {
      setConnectionStatus('disconnected', 'Connection error');
      removeThinkingIndicator();
    };
  }

  function showThinkingIndicator(text) {
    removeThinkingIndicator();
    thinkingEl = document.createElement('div');
    thinkingEl.className = 'thinking-spinner';
    thinkingEl.innerHTML = `<div class="spinner-ring"></div><span>${text || 'Agent 5 is reasoning...'}</span>`;
    chatHistory.appendChild(thinkingEl);
    scrollToBottom();
  }

  function updateThinkingIndicator(text) {
    if (thinkingEl) {
      const span = thinkingEl.querySelector('span');
      if (span) span.textContent = text;
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

  let isGenerating = false;

  function setWorkingState(isWorking) {
    isGenerating = isWorking;
    if (isWorking) {
      sendBtn.disabled = false;
      sendBtn.classList.add('stop-btn');
      sendBtn.innerHTML = '<span>Stop</span> <span class="send-icon">🛑</span>';
      promptInput.disabled = true;
      promptInput.placeholder = 'Agent 5 is working... Click Stop to cancel';
      showThinkingIndicator('Agent 5 is reasoning...');
    } else {
      sendBtn.disabled = false;
      sendBtn.classList.remove('stop-btn');
      sendBtn.innerHTML = '<span>Send</span> <span class="send-icon">🚀</span>';
      promptInput.disabled = false;
      promptInput.placeholder = 'Ask Agent 5 to build, refactor, or test...';
      removeThinkingIndicator();
      promptInput.focus();
    }
  }

  function handleServerMessage(data) {
    if (data.type === 'init') {
      if (data.model && modelBadge) {
        modelBadge.textContent = data.model;
      }
      if (data.project_state) {
        renderProjectState(data.project_state);
      }
    } else if (data.type === 'history') {
      if (Array.isArray(data.history) && data.history.length > 0) {
        chatHistory.innerHTML = '';
        appendSystemMessage('Restored previous project session history.');
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
        appendSystemMessage('New project chat session initialized.');
      }
      setWorkingState(false);
    } else if (data.type === 'status') {
      updateThinkingIndicator(data.content);
    } else if (data.type === 'tool_execution') {
      appendToolExecution(data.tool, data.args, data.result);
      updateThinkingIndicator(`Executing ${data.tool}...`);
    } else if (data.type === 'permission_request') {
      appendPermissionCard(data);
      updateThinkingIndicator(`⚠️ Waiting for approval: ${data.tool}`);
    } else if (data.type === 'assistant_response') {
      removeThinkingIndicator();
      appendAssistantMessage(data.content);
      setWorkingState(false);
    } else if (data.type === 'project_state') {
      renderProjectState(data.content);
    }
  }

  function appendPermissionCard(data) {
    const card = document.createElement('div');
    card.className = 'permission-card';
    card.id = `perm-card-${data.request_id}`;

    const targetDesc = data.target_file || (data.args ? JSON.stringify(data.args) : '');

    card.innerHTML = `
      <div class="permission-header">
        <span class="permission-title">⚠️ Approval Required</span>
        <span class="tool-status-badge error">Action Pending</span>
      </div>
      <div class="permission-body">
        <strong>Agent 5</strong> requests permission to execute <code>${data.tool}</code>:
        <div class="permission-target">${targetDesc}</div>
      </div>
      <div class="permission-actions">
        <button class="deny-btn">❌ Deny</button>
        <button class="approve-btn">✅ Approve</button>
      </div>
    `;

    const approveBtn = card.querySelector('.approve-btn');
    const denyBtn = card.querySelector('.deny-btn');

    const respond = (approved) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'permission_response',
          request_id: data.request_id,
          approved: approved
        }));
      }
      approveBtn.disabled = true;
      denyBtn.disabled = true;
      const badge = card.querySelector('.tool-status-badge');
      if (approved) {
        badge.className = 'tool-status-badge success';
        badge.textContent = 'APPROVED';
      } else {
        badge.className = 'tool-status-badge error';
        badge.textContent = 'DENIED';
      }
    };

    approveBtn.addEventListener('click', () => respond(true));
    denyBtn.addEventListener('click', () => respond(false));

    chatHistory.appendChild(card);
    scrollToBottom();
  }

  function parseMarkdown(md) {
    if (!md) return '';
    let text = String(md);

    // Clean any unparsed raw XML tool call tags before escaping HTML
    text = text.replace(/<function=[a-zA-Z0-9_\-]+>[\s\S]*?<\/function>/gi, '');
    text = text.replace(/<\/?(?:tool_call|function(?:=[a-zA-Z0-9_\-]+)?|parameter(?:=[a-zA-Z0-9_\-]+)?)\s*\/?>/gi, '');

    // Extract and render CHANGES_CARD widget if comment exists
    let cardHtml = '';
    const cardMatch = text.match(/<!--\s*CHANGES_CARD:\s*([\s\S]*?)\s*-->/);
    if (cardMatch) {
      try {
        const cardData = JSON.parse(cardMatch[1]);
        const totalFiles = cardData.total_files || 0;
        const totalAdded = cardData.total_added || 0;
        const totalRemoved = cardData.total_removed || 0;
        const logUrl = cardData.log_url || 'CHANGES_LOG.md';

        const fileItems = (cardData.files || []).map(f => {
          const actionClass = f.action === 'NEW' ? 'new' : 'modify';
          const actionLabel = f.action === 'NEW' ? '[NEW]' : '[MODIFY]';
          return `
            <div class="changes-file-item">
              <span>
                <span class="file-action-badge ${actionClass}">${actionLabel}</span>
                <a class="file-link" data-path="${f.abs_path || f.path}" href="#">${f.path}</a>
              </span>
              <span>
                <span class="changes-added">+${f.added}</span>
                <span class="changes-removed">-${f.removed}</span>
              </span>
            </div>`;
        }).join('');

        cardHtml = `
          <div class="changes-card-widget">
            <div class="changes-card-header">
              <div class="changes-card-summary">
                <span class="changes-file-count">${totalFiles} file${totalFiles > 1 ? 's' : ''} changed</span>
                <span class="changes-added">+${totalAdded}</span>
                <span class="changes-removed">-${totalRemoved}</span>
                <span class="changes-chevron">❯</span>
              </div>
              <button class="review-changes-btn" data-path="${logUrl}">
                <span class="review-icon">📄</span> Review
              </button>
            </div>
            <div class="changes-card-details">
              ${fileItems}
            </div>
          </div>`;
      } catch (err) {
        console.error("Failed to parse CHANGES_CARD JSON", err);
      }

      // Strip standard fallback text summary block & replace CHANGES_CARD comment with placeholder
      text = text.replace(/---\s*\n### 📝 Code Changes Summary[\s\S]*?(?:📄 Detailed unified diffs saved to \[CHANGES_LOG\.md\].*?$|$)/m, '');
      text = text.replace(/<!--\s*CHANGES_CARD:\s*[\s\S]*?\s*-->/, '___CHANGES_CARD_PLACEHOLDER___');
    }

    // Extract and render IMPLEMENTATION_PLAN widget if comment exists
    let planHtml = '';
    const planMatch = text.match(/<!--\s*IMPLEMENTATION_PLAN:\s*([\s\S]*?)\s*-->/);
    if (planMatch) {
      try {
        const planData = JSON.parse(planMatch[1]);
        const planTitle = planData.title || 'Technical Architecture Plan';
        const planPath = planData.plan_path || 'implementation_plan.md';

        planHtml = `
          <div class="plan-card-widget">
            <div class="plan-card-header">
              <span class="plan-card-title">📋 Implementation Plan Proposed</span>
              <span class="tool-status-badge success">Pending Review</span>
            </div>
            <div class="plan-card-body">
              <strong>Agent 5</strong> has drafted an implementation plan: <code>${planTitle}</code>.
            </div>
            <div class="plan-card-actions">
              <button class="review-plan-btn" data-path="${planPath}">📄 Review Plan</button>
              <button class="reject-plan-btn">❌ Reject / Edit</button>
              <button class="approve-plan-btn">✅ Approve & Execute</button>
            </div>
          </div>`;
      } catch (err) {
        console.error("Failed to parse IMPLEMENTATION_PLAN JSON", err);
      }

      text = text.replace(/<!--\s*IMPLEMENTATION_PLAN:\s*[\s\S]*?\s*-->/, '___IMPLEMENTATION_PLAN_PLACEHOLDER___');
    }

    // Escape HTML to prevent XSS injection
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Re-insert unescaped cardHtml & planHtml widgets at placeholder location
    if (cardHtml) {
      text = text.replace('___CHANGES_CARD_PLACEHOLDER___', cardHtml);
    }
    if (planHtml) {
      text = text.replace('___IMPLEMENTATION_PLAN_PLACEHOLDER___', planHtml);
    }

    // Fenced code blocks ```lang ... ```
    text = text.replace(/```([a-zA-Z0-9_\-\+]*)\r?\n([\s\S]*?)\r?\n```/g, (match, lang, code) => {
      const language = lang ? lang.toLowerCase() : 'code';
      return `<div class="code-block-wrapper"><div class="code-header"><span>${language}</span><div class="code-header-actions"><button class="apply-code-btn" title="Apply code directly to VS Code active editor document">⚡ Apply to Editor</button><button class="copy-btn">📋 Copy</button></div></div><pre><code class="language-${language}">${code}</code></pre></div>`;
    });

    // Inline code `code`
    text = text.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Headings ###, ##, #
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Markdown links [label](url)
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a class="file-link" data-path="$2" href="#">📄 $1</a>');

    // Bold **text** or __text__
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Italic *text* or _text_
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/_(.*?)_/g, '<em>$1</em>');

    // Unordered lists (- item or * item)
    text = text.replace(/^\s*[\-\*]\s+(.*$)/gim, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');
    text = text.replace(/<\/ul>\s*<ul>/g, '');

    // Paragraphs / line breaks
    const paragraphs = text.split(/\n{2,}/);
    return paragraphs.map(p => {
      if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<div')) {
        return p;
      }
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');
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
    div.innerHTML = parseMarkdown(text);
    chatHistory.appendChild(div);
    scrollToBottom();
  }

  function getToolIcon(tool) {
    const t = tool.toLowerCase();
    if (t.includes('file') || t.includes('read') || t.includes('create') || t.includes('edit')) return '📄';
    if (t.includes('command') || t.includes('terminal') || t.includes('server')) return '⚡';
    if (t.includes('delegate') || t.includes('agent') || t.includes('task')) return '🔄';
    if (t.includes('skill')) return '🛠️';
    return '⚙️';
  }

  function appendToolExecution(tool, args, result) {
    const card = document.createElement('div');
    card.className = 'tool-card';

    const icon = getToolIcon(tool);
    let displayName = tool;
    let badgeText = 'Success';
    if (tool === 'apply_skill' && args && args.skill_name) {
      displayName = `Auto-Activated Skill: ${args.skill_name}`;
      badgeText = 'Skill Active';
    }

    const argsStr = args && Object.keys(args).length > 0 ? JSON.stringify(args) : '';
    const safeResult = String(result || '');

    card.innerHTML = `
      <div class="tool-card-header">
        <div class="tool-info">
          <span class="tool-icon">${icon}</span>
          <span class="tool-name">${displayName}</span>
          <span class="tool-status-badge success">${badgeText}</span>
        </div>
        <span class="tool-toggle-arrow">►</span>
      </div>
      <div class="tool-card-body">
        <strong>Arguments:</strong>\n${argsStr || '(none)'}\n\n<strong>Output:</strong>\n${safeResult}
      </div>
    `;

    const header = card.querySelector('.tool-card-header');
    header.addEventListener('click', () => {
      card.classList.toggle('expanded');
    });

    chatHistory.appendChild(card);
    scrollToBottom();
  }

  function appendSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'msg system';
    div.textContent = text;
    chatHistory.appendChild(div);
    scrollToBottom();
  }

  function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  function sendPrompt() {
    if (isGenerating) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'cancel' }));
      }
      setWorkingState(false);
      appendSystemMessage('⏹️ Prompt generation cancelled by user.');
      return;
    }

    const prompt = promptInput.value.trim();
    if (!prompt) return;

    const requirePermToggle = document.getElementById('require-perm-toggle');
    const requirePerm = requirePermToggle ? requirePermToggle.checked : true;

    appendUserMessage(prompt);
    promptInput.value = '';
    setWorkingState(true);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'prompt',
        content: prompt,
        require_permission: requirePerm
      }));
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

  function renderProjectState(content) {
    if (!stateViewer) return;
    if (!content || !content.trim()) {
      stateViewer.textContent = 'No project state recorded yet.';
      return;
    }
    stateViewer.innerHTML = parseMarkdown(content);
  }

  function fetchState() {
    fetch(`http://127.0.0.1:${serverPort}/api/state`)
      .then(res => res.json())
      .then(data => {
        renderProjectState(data.content);
      })
      .catch(() => {});
  }

  function fetchAgents() {
    fetch(`http://127.0.0.1:${serverPort}/api/agents`)
      .then(res => res.json())
      .then(data => {
        agentsList.innerHTML = '';
        const h3 = document.createElement('h3');
        h3.style.margin = '0 0 12px 0';
        h3.style.fontSize = '12px';
        h3.style.color = 'var(--accent-color)';
        h3.textContent = '🤖 Agent Team & Capabilities';
        agentsList.appendChild(h3);

        (data.agents || []).forEach(agent => {
          const card = document.createElement('div');
          card.className = 'agent-card';
          
          const header = document.createElement('div');
          header.className = 'agent-card-header';
          
          const title = document.createElement('span');
          title.className = 'agent-title';
          title.textContent = `[${agent.agent_id}] ${agent.role}`;
          
          const badge = document.createElement('span');
          badge.className = 'cap-badge';
          badge.textContent = 'Active';
          
          header.appendChild(title);
          header.appendChild(badge);
          card.appendChild(header);

          const capsDiv = document.createElement('div');
          capsDiv.className = 'agent-caps';
          agent.capabilities.forEach(cap => {
            const capBadge = document.createElement('span');
            capBadge.className = 'cap-badge';
            capBadge.textContent = cap;
            capsDiv.appendChild(capBadge);
          });
          card.appendChild(capsDiv);
          agentsList.appendChild(card);
        });

        // Fetch installed skills
        fetch(`http://127.0.0.1:${serverPort}/api/skills`)
          .then(res => res.json())
          .then(skillData => {
            const h3Skills = document.createElement('h3');
            h3Skills.style.margin = '18px 0 10px 0';
            h3Skills.style.fontSize = '12px';
            h3Skills.style.color = 'var(--accent-color)';
            h3Skills.textContent = '⚡ Installed Skills Library';
            agentsList.appendChild(h3Skills);

            (skillData.skills || []).forEach(skill => {
              const card = document.createElement('div');
              card.className = 'skill-card';
              
              const skHeader = document.createElement('div');
              skHeader.className = 'skill-header';
              const skTitle = document.createElement('span');
              skTitle.className = 'skill-title';
              skTitle.textContent = `⚡ ${skill.name}`;
              
              const skAgent = document.createElement('span');
              skAgent.className = 'cap-badge';
              skAgent.textContent = skill.target_agent;
              
              skHeader.appendChild(skTitle);
              skHeader.appendChild(skAgent);
              card.appendChild(skHeader);

              const desc = document.createElement('div');
              desc.className = 'skill-desc';
              desc.textContent = skill.description;
              card.appendChild(desc);

              const applyBtn = document.createElement('button');
              applyBtn.className = 'secondary-btn apply-skill-btn';
              applyBtn.textContent = '⚡ Apply Skill';
              applyBtn.addEventListener('click', () => {
                promptInput.value = `Apply skill: ${skill.name}`;
                document.querySelector('.tab-btn[data-tab="chat-tab"]').click();
                promptInput.focus();
              });
              card.appendChild(applyBtn);

              agentsList.appendChild(card);
            });
          })
          .catch(() => {});
      })
      .catch(() => {});
  }

  chatHistory.addEventListener('click', (e) => {
    const reviewPlanBtn = e.target.closest('.review-plan-btn');
    if (reviewPlanBtn) {
      e.preventDefault();
      const planPath = reviewPlanBtn.getAttribute('data-path') || 'implementation_plan.md';
      vscode.postMessage({ command: 'openFile', filePath: planPath });
      return;
    }

    const approvePlanBtn = e.target.closest('.approve-plan-btn');
    if (approvePlanBtn) {
      e.preventDefault();
      const widget = approvePlanBtn.closest('.plan-card-widget');
      if (widget) {
        const badge = widget.querySelector('.tool-status-badge');
        if (badge) {
          badge.className = 'tool-status-badge success';
          badge.textContent = 'APPROVED';
        }
        approvePlanBtn.disabled = true;
      }
      promptInput.value = 'Approved implementation plan. Proceed with execution.';
      sendPrompt();
      return;
    }

    const rejectPlanBtn = e.target.closest('.reject-plan-btn');
    if (rejectPlanBtn) {
      e.preventDefault();
      const widget = rejectPlanBtn.closest('.plan-card-widget');
      if (widget) {
        const badge = widget.querySelector('.tool-status-badge');
        if (badge) {
          badge.className = 'tool-status-badge error';
          badge.textContent = 'REJECTED';
        }
        rejectPlanBtn.disabled = true;
      }
      promptInput.value = 'Revising plan: ';
      promptInput.focus();
      return;
    }

    const reviewBtn = e.target.closest('.review-changes-btn');
    if (reviewBtn) {
      e.preventDefault();
      const logPath = reviewBtn.getAttribute('data-path') || 'CHANGES_LOG.md';
      vscode.postMessage({ command: 'openFile', filePath: logPath });
      return;
    }

    const cardHeader = e.target.closest('.changes-card-header');
    if (cardHeader) {
      const widget = cardHeader.closest('.changes-card-widget');
      if (widget) {
        widget.classList.toggle('expanded');
      }
      return;
    }

    const applyCodeBtn = e.target.closest('.apply-code-btn');
    if (applyCodeBtn) {
      e.preventDefault();
      const wrapper = applyCodeBtn.closest('.code-block-wrapper');
      if (wrapper) {
        const codeEl = wrapper.querySelector('code');
        if (codeEl) {
          vscode.postMessage({ command: 'applyCode', code: codeEl.textContent || '' });
          applyCodeBtn.textContent = '⚡ Applied!';
          setTimeout(() => { applyCodeBtn.textContent = '⚡ Apply to Editor'; }, 2000);
        }
      }
      return;
    }

    const fileTarget = e.target.closest('.file-link');
    if (fileTarget) {
      e.preventDefault();
      const filePath = fileTarget.getAttribute('data-path');
      if (filePath) {
        vscode.postMessage({ command: 'openFile', filePath: filePath });
      }
      return;
    }

    const copyTarget = e.target.closest('.copy-btn');
    if (copyTarget) {
      e.preventDefault();
      const wrapper = copyTarget.closest('.code-block-wrapper');
      if (wrapper) {
        const codeEl = wrapper.querySelector('code');
        if (codeEl) {
          navigator.clipboard.writeText(codeEl.textContent || '');
          copyTarget.textContent = '✅ Copied!';
          setTimeout(() => { copyTarget.textContent = '📋 Copy'; }, 2000);
        }
      }
    }
  });

  // Popovers for @ Mentions and / Slash Commands
  let mentionPopupEl = null;
  let slashPopupEl = null;

  function removePopups() {
    if (mentionPopupEl) {
      mentionPopupEl.remove();
      mentionPopupEl = null;
    }
    if (slashPopupEl) {
      slashPopupEl.remove();
      slashPopupEl = null;
    }
  }

  function showSlashPopup() {
    removePopups();
    slashPopupEl = document.createElement('div');
    slashPopupEl.className = 'autocomplete-popup slash-popup';

    const commands = [
      { cmd: '/plan', label: '/plan', desc: 'Draft technical architecture implementation plan' },
      { cmd: '/test', label: '/test', desc: 'Generate comprehensive Pytest/Jest unit test suite' },
      { cmd: '/fix', label: '/fix', desc: 'Analyze and fix bug or runtime stack trace' },
      { cmd: '/refactor', label: '/refactor', desc: 'Refactor and optimize code structure' }
    ];

    commands.forEach(c => {
      const item = document.createElement('div');
      item.className = 'popup-item';
      item.innerHTML = `<span class="popup-title">${c.label}</span><span class="popup-desc">${c.desc}</span>`;
      item.addEventListener('click', () => {
        if (c.cmd === '/plan') promptInput.value = 'Plan implementation for: ';
        else if (c.cmd === '/test') promptInput.value = 'Generate unit tests for: ';
        else if (c.cmd === '/fix') promptInput.value = 'Analyze and fix error in: ';
        else if (c.cmd === '/refactor') promptInput.value = 'Refactor and optimize: ';
        removePopups();
        promptInput.focus();
      });
      slashPopupEl.appendChild(item);
    });

    const inputArea = document.querySelector('.input-area');
    if (inputArea) {
      inputArea.insertBefore(slashPopupEl, promptInput);
    }
  }

  function showMentionPopup(files) {
    removePopups();
    mentionPopupEl = document.createElement('div');
    mentionPopupEl.className = 'autocomplete-popup mention-popup';

    const header = document.createElement('div');
    header.className = 'popup-header';
    header.textContent = '🏷️ Attach Workspace Context (@File)';
    mentionPopupEl.appendChild(header);

    const itemList = files && files.length > 0 ? files.slice(0, 8) : ['PROJECT_STATE.md', 'server.py', 'README.md'];
    itemList.forEach(f => {
      const item = document.createElement('div');
      item.className = 'popup-item';
      item.innerHTML = `<span class="popup-icon">📄</span><span class="popup-title">@file:${f}</span>`;
      item.addEventListener('click', () => {
        promptInput.value = promptInput.value.replace(/@[a-zA-Z0-9_\-\.\/]*$/, `@file:${f} `);
        removePopups();
        promptInput.focus();
      });
      mentionPopupEl.appendChild(item);
    });

    const inputArea = document.querySelector('.input-area');
    if (inputArea) {
      inputArea.insertBefore(mentionPopupEl, promptInput);
    }
  }

  promptInput.addEventListener('input', () => {
    const val = promptInput.value;
    if (val === '/') {
      showSlashPopup();
    } else if (val.endsWith('@')) {
      vscode.postMessage({ command: 'getWorkspaceFiles' });
    } else if (!val.includes('@') && !val.startsWith('/')) {
      removePopups();
    }
  });

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg && msg.command === 'workspaceFiles') {
      showMentionPopup(msg.files || []);
    }
  });

  sendBtn.addEventListener('click', sendPrompt);
  promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      removePopups();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      removePopups();
      e.preventDefault();
      sendPrompt();
    }
  });

  // Start connection
  connectWebSocket();
})();
