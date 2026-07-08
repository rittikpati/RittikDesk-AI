(function () {
  'use strict';

  var chatForm = document.getElementById('chatForm');
  var chatInput = document.querySelector('.chat-input');
  var chatMessages = document.getElementById('chatMessages');
  var chatSendBtn = document.getElementById('chatSendBtn');
  var chatStopBtn = document.getElementById('chatStopBtn');
  var sidebarSearch = document.getElementById('chatSidebarSearch');
  var sidebarBody = document.getElementById('chatSidebarBody');
  var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
  var a11yAnnounce = document.getElementById('chatA11yAnnounce');
  var mobileToggle = document.getElementById('chatMobileToggle');
  var sidebar = document.getElementById('chatSidebar');
  var sidebarClose = document.getElementById('chatSidebarClose');

  var currentAbort = null;
  var isStreaming = false;
  var lastAssistantEl = null;
  var searchTimer = null;
  var markedLoaded = typeof marked !== 'undefined';

  /* ── Utilities ── */

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

  function isNearBottom() {
    if (!chatMessages) return true;
    return chatMessages.scrollTop + chatMessages.clientHeight >= chatMessages.scrollHeight - 80;
  }

  function scrollToBottom(smooth) {
    if (!chatMessages) return;
    if (smooth) {
      chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
    } else {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  function scrollIfNearBottom(smooth) {
    if (isNearBottom()) scrollToBottom(smooth);
  }

  function announce(text) {
    if (!a11yAnnounce) return;
    a11yAnnounce.textContent = '';
    requestAnimationFrame(function () {
      a11yAnnounce.textContent = text;
    });
  }

  function setInputEnabled(enabled) {
    if (chatInput) chatInput.disabled = !enabled;
    if (chatSendBtn) chatSendBtn.style.display = enabled ? '' : 'none';
    if (chatStopBtn) chatStopBtn.style.display = enabled ? 'none' : '';
    isStreaming = !enabled;
  }

  /* ── Markdown Renderer ── */

  function renderMarkdown(text) {
    if (!text) return '';

    text = text.replace(/^(#{1,3})(?!\s)(.+)$/gm, '$1 $2');
    var fence = text.match(/```/g);
    if (fence && fence.length % 2 !== 0) text += '\n```';

    if (markedLoaded && typeof marked.parse === 'function') {
      try {
        var result = marked.parse(text, { breaks: true, gfm: true });
        if (typeof result !== 'string') {
          console.warn('[marked] parse returned non-string, falling back');
        } else {
          return result;
        }
      } catch (e) {
        console.warn('[marked] parse threw, falling back to custom renderer:', e);
      }
    }

    var html = escHtml(text);
    var codeBlocks = [];

    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      var idx = codeBlocks.length;
      var langClass = lang ? ' class="language-' + escHtml(lang) + '"' : '';
      codeBlocks.push(
        '<pre><code' + langClass + '>' + escHtml(code) +
        '</code><button class="chat-copy-btn" onclick="window.copyCode(this)" title="Copy code" aria-label="Copy code"><i class="fas fa-copy"></i></button></pre>'
      );
      return '%%CODEBLOCK' + idx + '%%';
    });

    var lines = html.split('\n');
    var out = [];
    var i = 0;

    function processInline(t) {
      return t
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
    }

    function buildTable(rows) {
      var hasSep = rows.length > 1 && /^\|[\s:-]+\|/.test(rows[1]) && /\|[\s:-]+\|?$/.test(rows[1]);
      var h = '';
      if (hasSep) {
        h = '<thead><tr>';
        rows[0].split('|').slice(1, -1).forEach(function (c) { h += '<th>' + c.trim() + '</th>'; });
        h += '</tr></thead>';
        rows = rows.slice(2);
      }
      var b = '<tbody>';
      for (var r = 0; r < rows.length; r++) {
        b += '<tr>';
        rows[r].split('|').slice(1, -1).forEach(function (c) { b += '<td>' + c.trim() + '</td>'; });
        b += '</tr>';
      }
      b += '</tbody>';
      return '<table>' + h + b + '</table>';
    }

    while (i < lines.length) {
      var line = lines[i];
      var t = line.trim();

      if (t === '') { i++; continue; }

      var hm = t.match(/^(#{1,3})\s(.+)$/);
      if (hm) {
        out.push('<h' + hm[1].length + '>' + processInline(hm[2]) + '</h' + hm[1].length + '>');
        i++; continue;
      }

      if (/^[-*_]{3,}$/.test(t)) {
        out.push('<hr>');
        i++; continue;
      }

      if (/^&gt;/.test(t)) {
        var ql = [];
        while (i < lines.length && /^&gt;/.test(lines[i].trim())) {
          ql.push(lines[i].trim().replace(/^&gt;\s*/, ''));
          i++;
        }
        out.push('<blockquote>' + ql.join('<br>') + '</blockquote>');
        continue;
      }

      if (t.startsWith('|') && t.endsWith('|') && t.indexOf('|', 1) !== -1) {
        var tableRows = [];
        var isSep = /^\|[\s:-]+\|/.test(t) && /\|[\s:-]+\|?$/.test(t);
        if (!isSep) tableRows.push(t);
        i++;
        while (i < lines.length) {
          var n = lines[i].trim();
          if (n.startsWith('|') && n.endsWith('|') && n.indexOf('|', 1) !== -1) {
            var nSep = /^\|[\s:-]+\|/.test(n) && /\|[\s:-]+\|?$/.test(n);
            if (tableRows.length === 0 && nSep) { i++; continue; }
            if (nSep) { tableRows.push(n); i++; continue; }
            tableRows.push(n);
            i++;
          } else break;
        }
        if (tableRows.length > 0) out.push(buildTable(tableRows));
        continue;
      }

      var lm = t.match(/^(?:(\d+)\.\s+|\*\s+|\-\s+)(.*)$/);
      if (lm) {
        var isOrdered = lm[1] !== undefined;
        var tag = isOrdered ? 'ol' : 'ul';
        var items = [lm[2]];
        i++;
        while (i < lines.length) {
          var li = lines[i].trim();
          var nim = li.match(/^(?:(\d+)\.\s+|\*\s+|\-\s+)(.*)$/);
          if (nim) {
            items.push(nim[2]);
            i++;
          } else if (li !== '' && items.length > 0) {
            items[items.length - 1] += ' ' + li;
            i++;
          } else break;
        }
        var lh = '<' + tag + '>';
        for (var liIdx = 0; liIdx < items.length; liIdx++) {
          lh += '<li>' + processInline(items[liIdx]) + '</li>';
        }
        lh += '</' + tag + '>';
        out.push(lh);
        continue;
      }

      var para = [];
      while (i < lines.length) {
        var cur = lines[i].trim();
        if (cur === '') break;
        if (/^(#{1,3}\s|[-*_]{3,}$|&gt;)/.test(cur)) break;
        if (/^(\d+\.\s+|\*\s+|\-\s+)/.test(cur)) break;
        if (cur.startsWith('|') && cur.endsWith('|') && cur.indexOf('|', 1) !== -1) break;
        para.push(lines[i]);
        i++;
      }
      if (para.length > 0) {
        out.push('<p>' + processInline(para.join('<br>')) + '</p>');
      }
    }

    html = out.join('\n');

    html = html.replace(/%%CODEBLOCK(\d+)%%/g, function (_, idx) {
      return codeBlocks[parseInt(idx, 10)];
    });

    return html;
  }

  function highlightBlocks(container) {
    if (!window.hljs) return;
    container.querySelectorAll('pre code:not(.hljs)').forEach(function (block) {
      try { hljs.highlightElement(block); } catch (_) {}
    });
  }

  /* ── DOM Message Creation ── */

  function createMsgEl(role) {
    var div = document.createElement('div');
    div.className = 'chat-msg ' + (role === 'user' ? 'chat-msg-user' : 'chat-msg-assistant');
    div.setAttribute('data-role', role);

    var avatar = document.createElement('div');
    avatar.className = 'chat-msg-avatar';
    avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
    avatar.setAttribute('aria-hidden', 'true');

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

    if (role === 'user') {
      var editBtn = document.createElement('button');
      editBtn.className = 'chat-msg-action-btn chat-edit-btn';
      editBtn.innerHTML = '<i class="fas fa-pencil"></i> Edit';
      editBtn.setAttribute('aria-label', 'Edit message');
      editBtn.onclick = function () { editMessage(div); };
      contentWrap.appendChild(editBtn);
    } else {
      addAssistantActions(contentWrap);
    }

    return div;
  }

  function addAssistantActions(container) {
    var actions = document.createElement('div');
    actions.className = 'chat-msg-actions';
    actions.innerHTML =
      '<button class="chat-msg-action-btn chat-copy-response-btn" onclick="window.copyResponse(this)" title="Copy response" aria-label="Copy response"><i class="fas fa-copy"></i> Copy</button>' +
      '<button class="chat-msg-action-btn chat-regenerate-btn" onclick="window.regenerate(this)" title="Regenerate" aria-label="Regenerate response"><i class="fas fa-rotate"></i> Regenerate</button>';
    container.appendChild(actions);
  }

  function createTypingDots() {
    var container = document.createElement('div');
    container.className = 'chat-typing-dots';
    container.setAttribute('aria-label', 'AI is thinking');
    container.innerHTML = '<span></span><span></span><span></span>';
    return container;
  }

  function addUserMessage(text) {
    if (!chatMessages) return;
    var el = createMsgEl('user');
    el.querySelector('.chat-msg-text').textContent = text;
    chatMessages.appendChild(el);
    scrollIfNearBottom();
    return el;
  }

  function addThinkingAssistant() {
    if (!chatMessages) return;
    var el = document.createElement('div');
    el.className = 'chat-msg chat-msg-assistant chat-msg-thinking';
    el.setAttribute('data-role', 'assistant');

    var avatar = document.createElement('div');
    avatar.className = 'chat-msg-avatar';
    avatar.innerHTML = '<i class="fas fa-robot"></i>';
    avatar.setAttribute('aria-hidden', 'true');

    var contentWrap = document.createElement('div');
    contentWrap.className = 'chat-msg-content';

    var textWrap = document.createElement('div');
    textWrap.className = 'chat-msg-text';

    textWrap.appendChild(createTypingDots());
    contentWrap.appendChild(textWrap);
    el.appendChild(avatar);
    el.appendChild(contentWrap);
    chatMessages.appendChild(el);
    scrollIfNearBottom();
    lastAssistantEl = el;
    announce('AI is thinking');
    return el;
  }

  function transitionThinkingToStreaming() {
    if (!lastAssistantEl) return;
    var textEl = lastAssistantEl.querySelector('.chat-msg-text');
    if (!textEl) return;
    lastAssistantEl.classList.remove('chat-msg-thinking');
    lastAssistantEl.classList.add('chat-msg-streaming');
    textEl.innerHTML = '';
    addAssistantActions(lastAssistantEl.querySelector('.chat-msg-content'));
    scrollIfNearBottom();
  }

  function updateAssistantText(text) {
    if (!lastAssistantEl) return;
    var textEl = lastAssistantEl.querySelector('.chat-msg-text');
    if (!textEl) return;
    textEl.innerHTML = escHtml(text).replace(/\n/g, '<br>');
    scrollIfNearBottom(true);
  }

  function finalizeAssistant(text) {
    if (!lastAssistantEl) return;
    lastAssistantEl.classList.remove('chat-msg-streaming');
    var textEl = lastAssistantEl.querySelector('.chat-msg-text');
    if (!textEl) return;
    var html = renderMarkdown(text);
    textEl.innerHTML = html;
    highlightBlocks(textEl);
    scrollIfNearBottom();
  }

  /* ── Streaming Engine ── */

  function startStream(reader) {
    var decoder = new TextDecoder();
    var buffer = '';
    var fullText = '';
    var renderTimer = null;

    transitionThinkingToStreaming();

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
            if (data.e) updateAssistantText(fullText);
            return 'done';
          } else if (data.done) {
            finalizeAssistant(fullText);
            announce('Response complete');
            return 'done';
          }
        } catch (_) {}
      }
      return null;
    }

    function pump() {
      return reader.read().then(function (result) {
        if (result.done) {
          if (buffer) processChunk();
          if (renderTimer) { cancelAnimationFrame(renderTimer); renderTimer = null; }
          finalizeAssistant(fullText);
          setInputEnabled(true);
          return;
        }
        buffer += decoder.decode(result.value, { stream: true });
        var status = processChunk();
        if (status === 'done') { setInputEnabled(true); reader.cancel(); return; }
        return pump();
      });
    }

    pump().catch(function (err) {
      if (err.name === 'AbortError') return;
      setInputEnabled(true);
    });
  }

  function showError(message) {
    if (!chatMessages) return;
    var div = document.createElement('div');
    div.className = 'chat-msg chat-msg-assistant';
    div.setAttribute('data-role', 'assistant');
    div.innerHTML =
      '<div class="chat-msg-avatar" aria-hidden="true"><i class="fas fa-robot"></i></div>' +
      '<div class="chat-msg-content"><div class="chat-msg-text chat-error">' + escHtml(message) + '</div></div>';
    chatMessages.appendChild(div);
    scrollToBottom();
    announce('Error: ' + message);
  }

  /* ── Send Message ── */

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

    var formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRF());
    formData.append('message', message);
    if (isRegen) formData.append('regenerate', 'true');

    var streamUrl = chatForm.getAttribute('data-stream-url') || chatForm.getAttribute('action').replace('/message/', '/stream/');

    var controller = new AbortController();
    currentAbort = controller;

    addThinkingAssistant();

    fetch(streamUrl, {
      method: 'POST',
      body: formData,
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      signal: controller.signal,
    })
    .then(function (response) {
      if (!response.ok) {
        return response.json().then(function (data) { throw new Error(data.error || 'Request failed'); }).catch(function () { throw new Error('Request failed with status ' + response.status); });
      }
      var reader = response.body.getReader();
      startStream(reader);
    })
    .catch(function (err) {
      if (err.name === 'AbortError') { setInputEnabled(true); return; }
      setInputEnabled(true);
      showError(err.message || 'Something went wrong. Please try again.');
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
    if (currentAbort) { currentAbort.abort(); currentAbort = null; }
    setInputEnabled(true);
  }

  /* ── Edit Message ── */

  function editMessage(msgEl) {
    if (isStreaming) return;
    var textEl = msgEl.querySelector('.chat-msg-text');
    if (!textEl) return;
    var originalText = textEl.textContent;

    var textarea = document.createElement('textarea');
    textarea.className = 'chat-msg-edit-textarea';
    textarea.value = originalText;
    textarea.setAttribute('aria-label', 'Edit message');
    textEl.innerHTML = '';
    textEl.appendChild(textarea);

    var actions = document.createElement('div');
    actions.className = 'chat-msg-edit-actions';
    actions.innerHTML =
      '<button class="chat-msg-edit-btn chat-msg-edit-save"><i class="fas fa-check"></i> Save</button>' +
      '<button class="chat-msg-edit-btn chat-msg-edit-cancel"><i class="fas fa-times"></i> Cancel</button>';
    textEl.appendChild(actions);

    var saveBtn = actions.querySelector('.chat-msg-edit-save');
    var cancelBtn = actions.querySelector('.chat-msg-edit-cancel');

    function cancelEdit() {
      textEl.innerHTML = '';
      textEl.textContent = originalText;
    }

    function saveEdit() {
      var newText = textarea.value.trim();
      if (!newText || newText === originalText) { cancelEdit(); return; }

      var pk = msgEl.getAttribute('data-pk');
      if (!pk) return;

      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

      fetch('/assistant/message/' + pk + '/edit/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRF(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: 'message=' + encodeURIComponent(newText),
      })
      .then(function (response) {
        if (!response.ok) {
          cancelEdit();
          showError('Failed to edit message.');
          return null;
        }
        textEl.innerHTML = '';
        textEl.textContent = newText;
        var next = msgEl.nextElementSibling;
        while (next) {
          var toRemove = next;
          next = next.nextElementSibling;
          if (toRemove.getAttribute && toRemove.getAttribute('data-role') === 'assistant') {
            toRemove.remove();
          }
        }
        var reader = response.body.getReader();
        addThinkingAssistant();
        startStream(reader);
      })
      .catch(function () {
        cancelEdit();
        showError('Network error while editing.');
      });
    }

    saveBtn.onclick = saveEdit;
    cancelBtn.onclick = cancelEdit;

    textarea.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        saveEdit();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        cancelEdit();
      }
    });

    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }

  window.editMessage = editMessage;

  /* ── Chat Search ── */

  function updateSearchEmpty() {
    var emptyEl = document.getElementById('chatSearchEmpty');
    var emptyState = document.getElementById('chatEmptyState');
    if (!emptyEl) return;
    var query = sidebarSearch ? sidebarSearch.value.toLowerCase().trim() : '';
    if (!query) {
      emptyEl.style.display = 'none';
      if (emptyState) emptyState.style.display = '';
      return;
    }
    var items = sidebarBody.querySelectorAll('.chat-conv-item');
    var anyVisible = false;
    items.forEach(function (item) {
      if (item.style.display !== 'none') anyVisible = true;
    });
    emptyEl.style.display = anyVisible ? 'none' : 'flex';
    if (emptyState) emptyState.style.display = 'none';
  }

  function filterConversations(query) {
    if (!sidebarBody) return;
    var lower = query.toLowerCase().trim();

    /* Show/hide conversation items */
    var items = sidebarBody.querySelectorAll('.chat-conv-item');
    var hasVisible = false;
    items.forEach(function (item) {
      var titleEl = item.querySelector('.chat-conv-title');
      if (!titleEl) return;
      var title = titleEl.textContent;
      var titleLower = title.toLowerCase();
      var match = !lower || titleLower.indexOf(lower) !== -1;
      item.style.display = match ? '' : 'none';
      if (match) hasVisible = true;

      if (lower && match) {
        var idx = titleLower.indexOf(lower);
        if (idx !== -1) {
          titleEl.innerHTML = escHtml(title.slice(0, idx)) +
            '<span class="chat-search-highlight">' + escHtml(title.slice(idx, idx + lower.length)) + '</span>' +
            escHtml(title.slice(idx + lower.length));
        }
      } else if (!lower) {
        /* Only restore text content if no query (avoid double-escaping) */
        titleEl.textContent = title;
      } else {
        titleEl.textContent = title;
      }
    });

    /* Show/hide time group headers and pinned section */
    var sections = sidebarBody.querySelectorAll('.chat-pinned-section, .chat-time-group');
    sections.forEach(function (sec) {
      var secItems = sec.querySelectorAll('.chat-conv-item');
      var visible = false;
      secItems.forEach(function (item) {
        if (item.style.display !== 'none') visible = true;
      });
      sec.style.display = (!lower || visible) ? '' : 'none';
    });

    /* Show pinned section divider only if pinned section is visible */
    var pinnedSection = sidebarBody.querySelector('.chat-pinned-section');
    var pinnedDivider = pinnedSection ? pinnedSection.nextElementSibling : null;
    if (pinnedDivider && pinnedDivider.classList.contains('chat-section-divider')) {
      pinnedDivider.style.display = (pinnedSection && pinnedSection.style.display !== 'none') ? '' : 'none';
    }

    updateSearchEmpty();
  }

  if (sidebarSearch) {
    sidebarSearch.addEventListener('input', function () {
      if (searchTimer) clearTimeout(searchTimer);
      var val = this.value;
      searchTimer = setTimeout(function () { filterConversations(val); }, 150);
    });
  }

  /* ── Pin Toggle ── */

  function getConvHtml(convId, title, pinned) {
    var active = window.location.pathname.indexOf('/' + convId + '/') !== -1;
    return '<div class="chat-conv-item' + (active ? ' active' : '') + '" data-id="' + convId + '" role="option">' +
      '<a class="chat-conv-link" href="/assistant/' + convId + '/" tabindex="0">' +
      '<i class="fas fa-comment"></i>' +
      '<span class="chat-conv-title">' + escHtml(title) + '</span></a>' +
      '<div class="chat-conv-actions">' +
      '<button class="chat-conv-btn chat-pin-btn' + (pinned ? ' pinned' : '') + '" title="' + (pinned ? 'Unpin' : 'Pin') + '" aria-label="' + (pinned ? 'Unpin conversation' : 'Pin conversation') + '"><i class="fas fa-thumbtack"></i></button>' +
      '<button class="chat-conv-btn chat-rename-btn" title="Rename" aria-label="Rename conversation"><i class="fas fa-pencil"></i></button>' +
      '<button class="chat-conv-btn chat-delete-btn" title="Delete" aria-label="Delete conversation"><i class="fas fa-trash"></i></button>' +
      '</div></div>';
  }

  function pinItem(convId, title) {
    var item = sidebarBody.querySelector('.chat-conv-item[data-id="' + convId + '"]');
    if (item) item.remove();

    var pinnedSection = sidebarBody.querySelector('.chat-pinned-section');
    if (!pinnedSection) {
      var firstGroup = sidebarBody.querySelector('.chat-time-group');
      pinnedSection = document.createElement('div');
      pinnedSection.className = 'chat-pinned-section';
      pinnedSection.setAttribute('data-section', 'pinned');
      pinnedSection.innerHTML = '<div class="chat-pinned-header"><i class="fas fa-thumbtack"></i><span>Pinned</span></div><div class="chat-conv-list"></div>';
      if (firstGroup) {
        sidebarBody.insertBefore(pinnedSection, firstGroup);
      } else {
        sidebarBody.insertBefore(pinnedSection, sidebarBody.firstChild);
      }
      var emptyState = document.getElementById('chatEmptyState');
      if (emptyState) emptyState.style.display = 'none';
    }
    var list = pinnedSection.querySelector('.chat-conv-list');
    var temp = document.createElement('div');
    temp.innerHTML = getConvHtml(convId, title, true);
    var newItem = temp.firstChild;
    list.insertBefore(newItem, list.firstChild);
    attachConvEvents();
    updateSearchEmpty();
  }

  function unpinItem(convId, title) {
    var item = sidebarBody.querySelector('.chat-conv-item[data-id="' + convId + '"]');
    if (item) item.remove();

    /* Determine which time group to put it in */
    var targetGroup = sidebarBody.querySelector('.chat-time-group');
    if (!targetGroup) {
      /* No time groups exist yet, create one */
      var pinnedSection = sidebarBody.querySelector('.chat-pinned-section');
      targetGroup = document.createElement('div');
      targetGroup.className = 'chat-time-group';
      targetGroup.setAttribute('data-section', 'today');
      targetGroup.innerHTML = '<div class="chat-time-header">Today</div><div class="chat-conv-list"></div>';
      if (pinnedSection) {
        pinnedSection.parentNode.insertBefore(targetGroup, pinnedSection.nextElementSibling);
      } else {
        sidebarBody.appendChild(targetGroup);
      }
    }
    var list = targetGroup.querySelector('.chat-conv-list');
    var temp = document.createElement('div');
    temp.innerHTML = getConvHtml(convId, title, false);
    var newItem = temp.firstChild;
    list.insertBefore(newItem, list.firstChild);
    attachConvEvents();
    updateSearchEmpty();
  }

  function togglePin(btn, convId) {
    var item = btn.closest('.chat-conv-item');
    var titleEl = item ? item.querySelector('.chat-conv-title') : null;
    var title = titleEl ? titleEl.textContent : 'Chat';

    fetch('/assistant/' + convId + '/pin/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        showError(data.error);
        return;
      }
      if (data.pinned) {
        pinItem(convId, title);
        /* Update header title if this is the active conversation */
        var headerTitle = document.querySelector('.chat-header-title');
        if (headerTitle && window.location.pathname.indexOf('/' + convId + '/') !== -1) {
          /* No visual change needed */
        }
      } else {
        unpinItem(convId, title);
      }
    })
    .catch(function () {});
  }

  /* ── New Chat (AJAX) ── */

  function createNewChat() {
    fetch('/assistant/new/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.id) {
        window.location.href = data.url;
      }
    })
    .catch(function () {
      /* Fallback */
      window.location.href = '/assistant/new/';
    });
  }

  /* ── Rename Chat ── */

  function startRename() {
    var headerTitle = document.querySelector('.chat-header-title');
    if (!headerTitle) return;
    var current = headerTitle.textContent;

    /* Close menu */
    var menuEl = document.getElementById('chatMenu');
    var menuBtn = document.getElementById('chatMenuBtn');
    if (menuEl) { menuEl.classList.remove('open'); if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false'); }

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'chat-rename-input';
    input.value = current;
    input.setAttribute('aria-label', 'Rename conversation');
    headerTitle.textContent = '';
    headerTitle.appendChild(input);
    input.focus();
    input.select();

    function finishRename(save) {
      var newTitle = save ? input.value.trim() : current;
      if (!newTitle) newTitle = current;
      headerTitle.textContent = newTitle;

      if (save && newTitle !== current) {
        /* Get conversation ID from URL */
        var parts = window.location.pathname.split('/');
        var convId = null;
        for (var p = 0; p < parts.length; p++) {
          if (parts[p] === 'assistant' && p + 1 < parts.length && /^\d+$/.test(parts[p + 1])) {
            convId = parts[p + 1];
            break;
          }
        }
        if (convId) {
          fetch('/assistant/' + convId + '/rename/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'title=' + encodeURIComponent(newTitle),
          })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.title) {
              /* Update sidebar */
              var sidebarItem = sidebarBody.querySelector('.chat-conv-item.active .chat-conv-title');
              if (sidebarItem) sidebarItem.textContent = data.title;
            }
          })
          .catch(function () {});
        }
      }
    }

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        finishRename(true);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        finishRename(false);
      }
    });

    input.addEventListener('blur', function () {
      finishRename(true);
    });
  }

  /* ── Delete Chat ── */

  function showConfirmDialog(message, dangerLabel, callback) {
    var overlay = document.getElementById('chatConfirmOverlay');
    var titleEl = document.getElementById('chatConfirmTitle');
    var cancelBtn = document.getElementById('chatConfirmCancel');
    var deleteBtn = document.getElementById('chatConfirmDelete');
    if (!overlay || !titleEl || !cancelBtn || !deleteBtn) return;

    titleEl.textContent = message;
    deleteBtn.textContent = dangerLabel;
    overlay.style.display = 'flex';

    function cleanup() {
      overlay.style.display = 'none';
      cancelBtn.removeEventListener('click', onCancel);
      deleteBtn.removeEventListener('click', onDelete);
      document.removeEventListener('keydown', onKeydown);
    }

    function onCancel() { cleanup(); }
    function onDelete() { cleanup(); callback(); }
    function onKeydown(e) {
      if (e.key === 'Escape') cleanup();
    }

    cancelBtn.addEventListener('click', onCancel);
    deleteBtn.addEventListener('click', onDelete);
    document.addEventListener('keydown', onKeydown);
    deleteBtn.focus();
  }

  function deleteConversation(convId, redirectAfter) {
    fetch('/assistant/' + convId + '/delete/', {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': getCSRF(),
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.deleted) {
        /* Remove from sidebar */
        var item = sidebarBody.querySelector('.chat-conv-item[data-id="' + convId + '"]');
        if (item) {
          var list = item.closest('.chat-conv-list');
          item.remove();
          /* Remove section if empty */
          var group = list ? list.closest('.chat-pinned-section, .chat-time-group') : null;
          if (group && list && list.querySelectorAll('.chat-conv-item').length === 0) {
            group.remove();
            var divider = group ? group.nextElementSibling : null;
            if (divider && divider.classList.contains('chat-section-divider')) divider.remove();
          }
        }
        if (redirectAfter) {
          window.location.href = '/assistant/';
        }
      }
    })
    .catch(function () {
      window.location.href = '/assistant/';
    });
  }

  /* ── Conversation Events (attach to dynamically added items) ── */

  function attachConvEvents() {
    document.querySelectorAll('.chat-conv-item .chat-pin-btn').forEach(function (btn) {
      if (btn._listenerAttached) return;
      btn._listenerAttached = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var item = this.closest('.chat-conv-item');
        togglePin(this, item.getAttribute('data-id'));
      });
    });

    document.querySelectorAll('.chat-conv-item .chat-rename-btn').forEach(function (btn) {
      if (btn._listenerAttached) return;
      btn._listenerAttached = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var item = this.closest('.chat-conv-item');
        var id = item.getAttribute('data-id');
        var titleEl = item.querySelector('.chat-conv-title');
        var current = titleEl ? titleEl.textContent : 'Chat';
        var newTitle = prompt('Rename conversation:', current);
        if (!newTitle || newTitle.trim() === '' || newTitle.trim() === current) return;
        fetch('/assistant/' + id + '/rename/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'title=' + encodeURIComponent(newTitle.trim()),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.title && titleEl) {
            titleEl.textContent = data.title;
            /* Update header title if active */
            var headerTitle = document.querySelector('.chat-header-title');
            if (headerTitle && item.classList.contains('active')) {
              headerTitle.textContent = data.title;
            }
          }
        })
        .catch(function () {});
      });
    });

    document.querySelectorAll('.chat-conv-item .chat-delete-btn').forEach(function (btn) {
      if (btn._listenerAttached) return;
      btn._listenerAttached = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var item = this.closest('.chat-conv-item');
        var id = item.getAttribute('data-id');
        var isActive = item.classList.contains('active');
        showConfirmDialog('Delete this conversation?', 'Delete', function () {
          deleteConversation(id, isActive);
        });
      });
    });
  }

  /* ── Suggestion Prompts ── */

  function insertSuggestion(text) {
    if (!chatInput) return;
    chatInput.value = text;
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    chatInput.focus();
  }

  /* ── Initialization ── */

  if (chatForm && chatInput && chatMessages) {
    chatForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var message = chatInput.value.trim();
      if (!message) return;
      sendMessage(message, false);
    });

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

  if (chatStopBtn) {
    chatStopBtn.addEventListener('click', function () { abortStream(); });
  }

  document.querySelectorAll('.chat-suggestion-card').forEach(function (card) {
    card.addEventListener('click', function () {
      var text = this.getAttribute('data-prompt');
      if (text) insertSuggestion(text);
    });
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        var text = this.getAttribute('data-prompt');
        if (text) insertSuggestion(text);
      }
    });
  });

  /* ── Sidebar ── */

  function isMobile() { return window.innerWidth <= 992; }

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    if (sidebarClose) sidebarClose.style.display = 'block';
    if (mobileToggle) mobileToggle.style.display = 'none';
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (sidebarClose) sidebarClose.style.display = 'none';
    if (mobileToggle && isMobile()) mobileToggle.style.display = 'flex';
  }

  if (mobileToggle) {
    mobileToggle.addEventListener('click', openSidebar);
    if (isMobile()) mobileToggle.style.display = 'flex';
  }

  if (sidebarClose) {
    sidebarClose.addEventListener('click', closeSidebar);
  }

  window.addEventListener('resize', function () {
    if (!isMobile()) {
      closeSidebar();
    }
    if (mobileToggle) {
      mobileToggle.style.display = isMobile() ? 'flex' : 'none';
    }
  });

  /* ── New Chat Buttons ── */

  var newChatBtns = document.querySelectorAll('#chatNewBtn, #chatNewBtnFooter');
  newChatBtns.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      createNewChat();
    });
  });

  /* ── Three-dot Menu ── */

  var menuBtn = document.getElementById('chatMenuBtn');
  var menuEl = document.getElementById('chatMenu');

  if (menuBtn && menuEl) {
    menuBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = menuEl.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', open);
    });

    document.addEventListener('click', function (e) {
      if (!menuBtn.contains(e.target) && !menuEl.contains(e.target)) {
        menuEl.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
      }
    });

    menuEl.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        menuEl.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
        menuBtn.focus();
      }
    });

    /* Rename */
    var renameItem = document.getElementById('chatMenuRename');
    if (renameItem) {
      renameItem.addEventListener('click', function () {
        menuEl.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
        setTimeout(startRename, 100);
      });
    }

    /* Delete */
    var deleteItem = menuEl.querySelector('.chat-menu-delete');
    if (deleteItem) {
      deleteItem.addEventListener('click', function () {
        menuEl.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
        var url = this.getAttribute('data-delete-url');
        if (!url) return;
        var convId = url.match(/\/(\d+)\/delete\//);
        if (!convId) return;
        showConfirmDialog('Delete this conversation?', 'Delete', function () {
          deleteConversation(convId[1], true);
        });
      });
    }
  }

  /* ── Sidebar Conversation Link Clicks ── */

  sidebarBody.addEventListener('click', function (e) {
    var link = e.target.closest('.chat-conv-link');
    if (link) {
      /* Let the default navigation happen */
      return;
    }
  });

  /* ── Init ── */

  if (chatMessages) {
    chatMessages.querySelectorAll('pre code').forEach(function (block) {
      if (window.hljs) hljs.highlightElement(block);
    });
  }

  scrollToBottom();
  attachConvEvents();

  /* Expose for inline onclick handlers */
  window.copyCode = function (btn) {
    var pre = btn.closest('pre');
    var code = pre ? pre.querySelector('code') : null;
    if (!code) return;
    var text = code.textContent;
    navigator.clipboard.writeText(text).then(function () {
      btn.innerHTML = '<i class="fas fa-check"></i>';
      btn.classList.add('copied');
      btn.setAttribute('aria-label', 'Copied');
      setTimeout(function () { btn.innerHTML = '<i class="fas fa-copy"></i>'; btn.classList.remove('copied'); btn.setAttribute('aria-label', 'Copy code'); }, 2000);
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
      btn.setAttribute('aria-label', 'Copied');
      setTimeout(function () { btn.innerHTML = '<i class="fas fa-copy"></i> Copy'; btn.classList.remove('copied'); btn.setAttribute('aria-label', 'Copy response'); }, 2000);
    });
  };

})();
