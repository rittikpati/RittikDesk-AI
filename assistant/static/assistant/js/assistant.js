(function () {
  'use strict';

  var chatForm = document.getElementById('chatForm');
  var chatInput = document.querySelector('.chat-input');
  var chatMessages = document.getElementById('chatMessages');
  var chatTyping = document.getElementById('chatTyping');
  var chatSendBtn = document.getElementById('chatSendBtn');
  var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');

  function getCSRF() {
    if (csrfToken) return csrfToken.value;
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function escapeHtml(text) {
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

  function disableInput(disabled) {
    if (chatInput) chatInput.disabled = disabled;
    if (chatSendBtn) chatSendBtn.disabled = disabled;
  }

  function renderMarkdown(text) {
    var html = escapeHtml(text);
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      var langClass = lang ? ' class="language-' + escapeHtml(lang) + '"' : '';
      return '<pre><code' + langClass + '>' + escapeHtml(code) + '</code><button class="chat-copy-btn" onclick="copyCode(this)" title="Copy code"><i class="fas fa-copy"></i></button></pre>';
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

  function addMessage(role, content, animate) {
    if (!chatMessages) return;
    var div = document.createElement('div');
    div.className = 'chat-msg ' + (role === 'user' ? 'chat-msg-user' : 'chat-msg-assistant');
    div.setAttribute('data-role', role);

    var avatar = document.createElement('div');
    avatar.className = 'chat-msg-avatar';
    avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

    var msgContent = document.createElement('div');
    msgContent.className = 'chat-msg-content';

    var msgText = document.createElement('div');
    msgText.className = 'chat-msg-text';

    if (role === 'assistant') {
      msgText.innerHTML = renderMarkdown(content);
      var actions = document.createElement('div');
      actions.className = 'chat-msg-actions';
      actions.innerHTML = '<button class="chat-msg-action-btn chat-copy-response-btn" onclick="copyResponse(this)"><i class="fas fa-copy"></i> Copy</button>';
      msgContent.appendChild(msgText);
      msgContent.appendChild(actions);
    } else {
      msgText.textContent = content;
      msgContent.appendChild(msgText);
    }

    var time = document.createElement('div');
    time.className = 'chat-msg-time';
    time.textContent = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    msgContent.appendChild(time);

    div.appendChild(avatar);
    div.appendChild(msgContent);

    if (animate) {
      div.style.opacity = '0';
      chatMessages.appendChild(div);
      requestAnimationFrame(function () {
        div.style.transition = 'opacity 0.2s ease';
        div.style.opacity = '1';
      });
    } else {
      chatMessages.appendChild(div);
    }

    scrollToBottom();

    if (role === 'assistant') {
      setTimeout(function () {
        chatMessages.querySelectorAll('pre code').forEach(function (block) {
          if (window.hljs) hljs.highlightElement(block);
        });
      }, 50);
    }
  }

  if (chatForm && chatInput && chatMessages) {
    chatForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var message = chatInput.value.trim();
      if (!message) return;

      var formData = new FormData(chatForm);
      var url = chatForm.getAttribute('action');

      addMessage('user', message, false);
      chatInput.value = '';
      chatInput.style.height = 'auto';
      disableInput(true);
      showTyping();

      fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
          'X-CSRFToken': getCSRF(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        hideTyping();
        disableInput(false);
        if (data.error) {
          var errorDiv = document.createElement('div');
          errorDiv.className = 'chat-msg chat-msg-assistant';
          errorDiv.innerHTML = '<div class="chat-msg-avatar"><i class="fas fa-robot"></i></div><div class="chat-msg-content"><div class="chat-msg-text chat-error">' + escapeHtml(data.error) + '</div></div>';
          chatMessages.appendChild(errorDiv);
          scrollToBottom();
        } else if (data.reply) {
          addMessage('assistant', data.reply, true);
        }
      })
      .catch(function () {
        hideTyping();
        disableInput(false);
        var errorDiv = document.createElement('div');
        errorDiv.className = 'chat-msg chat-msg-assistant';
        errorDiv.innerHTML = '<div class="chat-msg-avatar"><i class="fas fa-robot"></i></div><div class="chat-msg-content"><div class="chat-msg-text chat-error">Something went wrong. Please try again.</div></div>';
        chatMessages.appendChild(errorDiv);
        scrollToBottom();
      });
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
      .then(function (r) { return r.json(); })
      .then(function () {
        window.location.href = '/assistant/';
      })
      .catch(function () {
        window.location.href = '/assistant/';
      });
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
