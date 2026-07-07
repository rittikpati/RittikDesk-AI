(function () {
  'use strict';

  var chatForm = document.getElementById('chatForm');
  var chatInput = document.querySelector('.chat-input');
  var chatMessages = document.getElementById('chatMessages');
  var chatTyping = document.getElementById('chatTyping');
  var chatSendBtn = document.getElementById('chatSendBtn');
  var chatStopBtn = document.getElementById('chatStopBtn');
  var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');

  var currentAbort = null;
  var isStreaming = false;
  var lastAssistantEl = null;

  var markedLoaded = typeof marked !== 'undefined';

  function getCSRF() {
    if (csrfToken) return csrfToken.value;
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function escHtml(text) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }

  function scrollToBottom() {
    if (!chatMessages) return;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showTyping() {
    if (chatTyping) chatTyping.style.display = 'flex';
    scrollToBottom();
  }

  function hideTyping() {
    if (chatTyping) chatTyping.style.display = 'none';
  }

  function setInputEnabled(enabled) {
    if (chatInput) chatInput.disabled = !enabled;
    if (chatSendBtn) chatSendBtn.style.display = enabled ? 'flex' : 'none';
    if (chatStopBtn) chatStopBtn.style.display = enabled ? 'none' : 'flex';
    isStreaming = !enabled;
  }

  function renderMarkdown(text) {
    if (markedLoaded && typeof marked.parse === 'function') {
      var html = marked.parse(text, { breaks: true });
      return html;
    }
    var html = escHtml(text);
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      var langClass = lang ? ' class="language-' + escHtml(lang) + '"' : '';
      return '<pre><code' + langClass + '>' + escHtml(code) + '</code><button class="chat-copy-btn" onclick="window.copyCode(this)" title="Copy code"><i class="fas fa-copy"></i></button></pre>';
    });
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  function highlightBlocks(container) {
    if (!window.hljs) return;
    container.querySelectorAll('pre code:not(.hljs)').forEach(function (block) {
      try {
        hljs.highlightElement(block);
      } catch (_) {}
    });
  }

  function createMsgEl(role) {
    var div = document.createElement('div');
    div.className = 'chat-msg ' + (role === 'user' ? 'chat-msg-user' : 'chat-msg-assistant');
    div.setAttribute('data-role', role);

    var avatar = document.createElement('div');
    avatar.className = 'chat-msg-avatar';
    avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

    var contentWrap = document.createElement('div');
    contentWrap.className = 'chat-msg-content';

    var textWrap = document.createElement('div');
    textWrap.className = 'chat-msg-text';

    var time = document.createElement('div');
    time.className = 'chat-msg-time';
    time.textContent = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

    contentWrap.appendChild(textWrap);
    contentWrap.appendChild(time);
    div.appendChild(avatar);
    div.appendChild(contentWrap);

    if (role === 'assistant') {
      var actions = document.createElement('div');
      actions.className = 'chat-msg-actions';
      actions.innerHTML =
        '<button class="chat-msg-action-btn chat-copy-response-btn" onclick="window.copyResponse(this)" title="Copy response"><i class="fas fa-copy"></i> Copy</button>' +
        '<button class="chat-msg-action-btn chat-regenerate-btn" onclick="window.regenerate(this)" title="Regenerate"><i class="fas fa-rotate"></i> Regenerate</button>';
      contentWrap.appendChild(actions);
    }

    return div;
  }

  function addUserMessage(text) {
    if (!chatMessages) return;
    hideTyping();
    var el = createMsgEl('user');
    el.querySelector('.chat-msg-text').textContent = text;
    chatMessages.appendChild(el);
    scrollToBottom();
    return el;
  }

  function addAssistantMessage() {
    if (!chatMessages) return;
    var el = createMsgEl('assistant');
    var textEl = el.querySelector('.chat-msg-text');
    textEl.textContent = '';
    chatMessages.appendChild(el);
    scrollToBottom();
    lastAssistantEl = el;
    return el;
  }

  function updateAssistantText(text) {
    if (!lastAssistantEl) return;
    var textEl = lastAssistantEl.querySelector('.chat-msg-text');
    if (!textEl) return;
    var prevScroll = chatMessages ? chatMessages.scrollTop : 0;
    var prevHeight = chatMessages ? chatMessages.scrollHeight : 0;
    var isNearBottom = prevScroll + chatMessages.clientHeight >= prevHeight - 60;

    textEl.innerHTML = renderMarkdown(text);
    highlightBlocks(textEl);

    if (isNearBottom) {
      scrollToBottom();
    }
  }

  function showError(message) {
    if (!chatMessages) return;
    var div = document.createElement('div');
    div.className = 'chat-msg chat-msg-assistant';
    div.innerHTML =
      '<div class="chat-msg-avatar"><i class="fas fa-robot"></i></div>' +
      '<div class="chat-msg-content"><div class="chat-msg-text chat-error">' +
      escHtml(message) + '</div></div>';
    chatMessages.appendChild(div);
    scrollToBottom();
  }

  function sendMessage(message, isRegen) {
    if (!chatMessages || !chatInput || !chatForm) return;
    if (isStreaming) return;

    if (!isRegen) {
      if (!message || !message.trim()) return;
      addUserMessage(message);
      chatInput.value = '';
      chatInput.style.height = 'auto';
    }

    setInputEnabled(false);
    showTyping();

    var formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRF());
    formData.append('message', message);
    if (isRegen) {
      formData.append('regenerate', 'true');
    }

    var streamUrl = chatForm.getAttribute('data-stream-url') || chatForm.getAttribute('action').replace('/message/', '/stream/');

    currentAbort = new AbortController();

    if (!isRegen) {
      addAssistantMessage();
    }

    fetch(streamUrl, {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCSRF(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      signal: currentAbort.signal,
    })
      .then(function (response) {
        if (!response.ok) {
          return response.json().then(function (data) {
            throw new Error(data.error || 'Request failed');
          }).catch(function () {
            throw new Error('Request failed with status ' + response.status);
          });
        }
        hideTyping();
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var fullText = '';
        var renderTimer = null;

        function processChunk() {
          var idx;
          while ((idx = buffer.indexOf('\n')) !== -1) {
            var line = buffer.slice(0, idx).trim();
            buffer = buffer.slice(idx + 1);
            if (!line) continue;
            if (!line.startsWith('data: ')) continue;
            var payload = line.slice(6);
            if (payload === '[DONE]') continue;
            try {
              var data = JSON.parse(payload);
              if (data.t) {
                fullText += data.t;
                if (!renderTimer) {
                  renderTimer = requestAnimationFrame(function () {
                    updateAssistantText(fullText);
                    renderTimer = null;
                  });
                }
              } else if (data.e) {
                showError(data.e);
                setInputEnabled(true);
                if (data.e) {
                  updateAssistantText(fullText);
                }
                return 'done';
              } else if (data.done) {
                updateAssistantText(fullText);
                return 'done';
              }
            } catch (_) {}
          }
          return null;
        }

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) {
              if (buffer) {
                processChunk();
              }
              if (renderTimer) {
                cancelAnimationFrame(renderTimer);
                renderTimer = null;
              }
              updateAssistantText(fullText);
              setInputEnabled(true);
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            var status = processChunk();
            if (status === 'done') {
              setInputEnabled(true);
              reader.cancel();
              return;
            }
            return pump();
          });
        }

        return pump();
      })
      .catch(function (err) {
        if (err.name === 'AbortError') {
          setInputEnabled(true);
          return;
        }
        hideTyping();
        setInputEnabled(true);
        if (!isRegen) {
          showError(err.message || 'Something went wrong. Please try again.');
        } else {
          showError('Failed to regenerate. Please try again.');
        }
      });
  }

  window.regenerate = function (btn) {
    if (isStreaming) return;
    if (!chatMessages) return;

    var msgEl = btn.closest('.chat-msg');
    if (!msgEl) return;

    var prevMsgEl = msgEl.previousElementSibling;
    while (prevMsgEl && prevMsgEl.getAttribute('data-role') !== 'user') {
      prevMsgEl = prevMsgEl.previousElementSibling;
    }
    if (!prevMsgEl) return;

    var userText = prevMsgEl.querySelector('.chat-msg-text');
    if (!userText) return;

    var userMessage = userText.textContent;

    msgEl.remove();

    sendMessage(userMessage, true);
  };

  function abortStream() {
    if (currentAbort) {
      currentAbort.abort();
      currentAbort = null;
    }
    hideTyping();
    setInputEnabled(true);
  }

  if (chatForm && chatInput && chatMessages) {
    chatForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var message = chatInput.value.trim();
      if (!message) return;
      sendMessage(message, false);
    });

    if (chatInput) {
      chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
      });

      chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          chatForm.dispatchEvent(new Event('submit'));
        }
      });
    }
  }

  if (chatStopBtn) {
    chatStopBtn.addEventListener('click', function () {
      abortStream();
    });
  }

  var renameBtns = document.querySelectorAll('.chat-rename-btn');
  renameBtns.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var id = this.getAttribute('data-id');
      var item = this.closest('.chat-conv-item');
      var titleEl = item ? item.querySelector('.chat-conv-title') : null;
      var current = titleEl ? titleEl.textContent : 'Chat';
      var newTitle = prompt('Rename conversation:', current);
      if (!newTitle || newTitle.trim() === '' || newTitle === current) return;

      fetch('/assistant/' + id + '/rename/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRF(),
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: 'title=' + encodeURIComponent(newTitle.trim()),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.title && titleEl) titleEl.textContent = data.title;
        })
        .catch(function () {});
    });
  });

  var deleteBtns = document.querySelectorAll('.chat-delete-btn');
  deleteBtns.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (!confirm('Delete this conversation?')) return;
      var id = this.getAttribute('data-id');

      fetch('/assistant/' + id + '/delete/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRF(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
        .then(function () { window.location.href = '/assistant/'; })
        .catch(function () { window.location.href = '/assistant/'; });
    });
  });

  window.copyCode = function (btn) {
    var pre = btn.closest('pre');
    var code = pre ? pre.querySelector('code') : null;
    if (!code) return;
    var text = code.textContent;
    navigator.clipboard.writeText(text).then(function () {
      btn.innerHTML = '<i class="fas fa-check"></i>';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.innerHTML = '<i class="fas fa-copy"></i>';
        btn.classList.remove('copied');
      }, 2000);
    });
  };

  window.copyResponse = function (btn) {
    var msgContent = btn.closest('.chat-msg-content');
    var textEl = msgContent ? msgContent.querySelector('.chat-msg-text') : null;
    if (!textEl) return;
    var text = textEl.textContent;
    navigator.clipboard.writeText(text).then(function () {
      btn.innerHTML = '<i class="fas fa-check"></i> Copied';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.innerHTML = '<i class="fas fa-copy"></i> Copy';
        btn.classList.remove('copied');
      }, 2000);
    });
  };

  scrollToBottom();

  if (chatMessages) {
    chatMessages.querySelectorAll('pre code').forEach(function (block) {
      if (window.hljs) hljs.highlightElement(block);
    });
  }

})();
