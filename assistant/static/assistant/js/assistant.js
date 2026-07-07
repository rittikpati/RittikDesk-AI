(function () {
  'use strict';

  var chatForm = document.getElementById('chatForm');
  var chatInput = document.querySelector('.chat-input');
  var chatMessages = document.getElementById('chatMessages');
  var chatTyping = document.getElementById('chatTyping');
  var chatSendBtn = document.getElementById('chatSendBtn');
  var chatStopBtn = document.getElementById('chatStopBtn');
  var sidebarSearch = document.getElementById('chatSidebarSearch');
  var sidebarBody = document.getElementById('chatSidebarBody');
  var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');

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
      return marked.parse(text, { breaks: true });
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
      try { hljs.highlightElement(block); } catch (_) {}
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

    if (role === 'user') {
      var editBtn = document.createElement('button');
      editBtn.className = 'chat-msg-action-btn chat-edit-btn';
      editBtn.innerHTML = '<i class="fas fa-pencil"></i> Edit';
      editBtn.onclick = function () { editMessage(div); };
      contentWrap.appendChild(editBtn);
    } else {
      var actions = document.createElement('div');
      actions.className = 'chat-msg-actions';
      actions.innerHTML =
        '<button class="chat-msg-action-btn chat-copy-response-btn" onclick="window.copyResponse(this)" title="Copy response"><i class="fas fa-copy"></i> Copy</button>' +
        '<button class="chat-msg-action-btn chat-regenerate-btn" onclick="window.regenerate(this)" title="Regenerate"><i class="fas fa-rotate"></i> Regenerate</button>';
      contentWrap.appendChild(actions);
    }

    return div;
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
        var lastMsg = msgEl.nextElementSibling;
        while (lastMsg) {
          var next = lastMsg.nextElementSibling;
          if (lastMsg.getAttribute && lastMsg.getAttribute('data-role') === 'assistant') {
            lastMsg.remove();
          }
          lastMsg = next;
        }
        cancelEdit = function() {};
        startStreamFromResponse(response);
        return null;
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

  function startStreamFromResponse(response) {
    if (!response) return;
    hideTyping();
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';
    var fullText = '';
    var renderTimer = null;

    addAssistantMessage();

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
          if (buffer) processChunk();
          if (renderTimer) { cancelAnimationFrame(renderTimer); renderTimer = null; }
          updateAssistantText(fullText);
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

  /* ── Message Display ── */

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

    if (isNearBottom) scrollToBottom();
  }

  function showError(message) {
    if (!chatMessages) return;
    var div = document.createElement('div');
    div.className = 'chat-msg chat-msg-assistant';
    div.innerHTML =
      '<div class="chat-msg-avatar"><i class="fas fa-robot"></i></div>' +
      '<div class="chat-msg-content"><div class="chat-msg-text chat-error">' + escHtml(message) + '</div></div>';
    chatMessages.appendChild(div);
    scrollToBottom();
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
    showTyping();

    var formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRF());
    formData.append('message', message);
    if (isRegen) formData.append('regenerate', 'true');

    var streamUrl = chatForm.getAttribute('data-stream-url') || chatForm.getAttribute('action').replace('/message/', '/stream/');

    currentAbort = new AbortController();

    addAssistantMessage();

    fetch(streamUrl, {
      method: 'POST',
      body: formData,
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      signal: currentAbort.signal,
    })
    .then(function (response) {
      if (!response.ok) {
        return response.json().then(function (data) { throw new Error(data.error || 'Request failed'); }).catch(function () { throw new Error('Request failed with status ' + response.status); });
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
              if (data.e) updateAssistantText(fullText);
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
            if (buffer) processChunk();
            if (renderTimer) { cancelAnimationFrame(renderTimer); renderTimer = null; }
            updateAssistantText(fullText);
            setInputEnabled(true);
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          var status = processChunk();
          if (status === 'done') { setInputEnabled(true); reader.cancel(); return; }
          return pump();
        });
      }

      return pump();
    })
    .catch(function (err) {
      if (err.name === 'AbortError') { setInputEnabled(true); return; }
      hideTyping();
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
    hideTyping();
    setInputEnabled(true);
  }

  /* ── Chat Search ── */

  function filterConversations(query) {
    if (!sidebarBody) return;
    var items = sidebarBody.querySelectorAll('.chat-conv-item');
    var lower = query.toLowerCase().trim();

    items.forEach(function (item) {
      var titleEl = item.querySelector('.chat-conv-title');
      if (!titleEl) return;
      var title = titleEl.textContent;
      var titleLower = title.toLowerCase();
      var match = !lower || titleLower.indexOf(lower) !== -1;

      item.style.display = match ? '' : 'none';

      if (lower && match) {
        var idx = titleLower.indexOf(lower);
        if (idx !== -1) {
          var before = escHtml(title.slice(0, idx));
          var highlighted = '<span class="chat-search-highlight">' + escHtml(title.slice(idx, idx + lower.length)) + '</span>';
          var after = escHtml(title.slice(idx + lower.length));
          titleEl.innerHTML = before + highlighted + after;
          return;
        }
      }
      titleEl.textContent = title;
    });

    var categories = sidebarBody.querySelectorAll('.chat-category');
    categories.forEach(function (cat) {
      var catItems = cat.querySelectorAll('.chat-conv-item');
      var visible = false;
      catItems.forEach(function (item) {
        if (item.style.display !== 'none') visible = true;
      });
      if (!lower) {
        cat.style.display = '';
      } else {
        cat.style.display = visible ? '' : 'none';
      }
    });

    var sections = sidebarBody.querySelectorAll('.chat-pinned-section, .chat-section-divider');
    sections.forEach(function (sec) {
      if (!lower) { sec.style.display = ''; return; }
      var nextItems = [];
      var el = sec.nextElementSibling;
      while (el && !el.classList.contains('chat-pinned-section') && !el.classList.contains('chat-section-divider') && !el.classList.contains('chat-category')) {
        if (el.classList.contains('chat-conv-item')) nextItems.push(el);
        el = el.nextElementSibling;
      }
      var visible = nextItems.some(function (item) { return item.style.display !== 'none'; });
      sec.style.display = visible ? '' : 'none';
    });
  }

  if (sidebarSearch) {
    sidebarSearch.addEventListener('input', function () {
      if (searchTimer) clearTimeout(searchTimer);
      var val = this.value;
      searchTimer = setTimeout(function () { filterConversations(val); }, 300);
    });
  }

  /* ── Pin Toggle ── */

  function togglePin(btn, convId) {
    fetch('/assistant/' + convId + '/pin/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.pinned !== undefined) {
        var icon = btn.querySelector('i');
        if (data.pinned) {
          btn.classList.add('pinned');
          if (icon) icon.className = 'fas fa-thumbtack';
          btn.title = 'Unpin';
        } else {
          btn.classList.remove('pinned');
          if (icon) icon.className = 'fas fa-thumbtack';
          btn.title = 'Pin';
        }
        setTimeout(function () {
          var item = btn.closest('.chat-conv-item');
          if (item) {
            var id = item.getAttribute('data-id');
            var html = item.outerHTML;
            item.remove();
            var pinnedSection = sidebarBody ? sidebarBody.querySelector('.chat-pinned-section .chat-category-items') : null;
            if (data.pinned && pinnedSection) {
              var temp = document.createElement('div');
              temp.innerHTML = html;
              var newItem = temp.firstChild;
              newItem.style.animation = 'none';
              pinnedSection.insertBefore(newItem, pinnedSection.firstChild);
            } else if (!data.pinned && sidebarBody) {
              var generalSection = sidebarBody.querySelector('.chat-category-items:not(.chat-pinned-section *)');
              if (generalSection) {
                var temp = document.createElement('div');
                temp.innerHTML = html;
                var newItem2 = temp.firstChild;
                newItem2.style.animation = 'none';
                generalSection.appendChild(newItem2);
              } else {
                window.location.reload();
              }
            }
          }
        }, 100);
      }
    })
    .catch(function () {});
  }

  /* ── Categories ── */

  function createCategory(name) {
    fetch('/assistant/category/create/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'name=' + encodeURIComponent(name),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.id) {
        window.location.reload();
      }
    })
    .catch(function () {});
  }

  function renameCategory(btn) {
    var header = btn.closest('.chat-category-header');
    var nameEl = header ? header.querySelector('.chat-category-name') : null;
    if (!nameEl) return;
    var current = nameEl.textContent;
    var newName = prompt('Rename category:', current);
    if (!newName || newName.trim() === '' || newName.trim() === current) return;
    var catId = header.closest('.chat-category').getAttribute('data-category-id');

    fetch('/assistant/category/' + catId + '/rename/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'name=' + encodeURIComponent(newName.trim()),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.name) nameEl.textContent = data.name;
    })
    .catch(function () {});
  }

  function deleteCategory(btn) {
    if (!confirm('Delete this category? Conversations will be moved to General.')) return;
    var header = btn.closest('.chat-category-header');
    var catEl = header ? header.closest('.chat-category') : null;
    if (!catEl) return;
    var catId = catEl.getAttribute('data-category-id');

    fetch('/assistant/category/' + catId + '/delete/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (r) { return r.json(); })
    .then(function () {
      catEl.remove();
    })
    .catch(function () {});
  }

  /* ── Drag-and-Drop ── */

  function initDragDrop() {
    var items = document.querySelectorAll('.chat-conv-item[draggable="true"]');
    var dropZones = document.querySelectorAll('.chat-category-items');

    items.forEach(function (item) {
      item.addEventListener('dragstart', function (e) {
        e.dataTransfer.setData('text/plain', this.getAttribute('data-id'));
        this.classList.add('dragging');
      });
      item.addEventListener('dragend', function () {
        this.classList.remove('dragging');
        dropZones.forEach(function (z) { z.classList.remove('drag-over'); });
      });
    });

    dropZones.forEach(function (zone) {
      zone.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        this.classList.add('drag-over');
      });
      zone.addEventListener('dragleave', function () {
        this.classList.remove('drag-over');
      });
      zone.addEventListener('drop', function (e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        var convId = e.dataTransfer.getData('text/plain');
        if (!convId) return;
        var categoryEl = this.closest('.chat-category');
        var categoryId = categoryEl ? categoryEl.getAttribute('data-category-id') : '';
        var targetItems = this;
        var draggedItem = document.querySelector('.chat-conv-item[data-id="' + convId + '"].dragging');
        if (draggedItem) {
          var clone = draggedItem.cloneNode(true);
          draggedItem.remove();
          targetItems.appendChild(clone);
          initDragDrop();
          attachConversationEvents();
        }
        fetch('/assistant/' + convId + '/move-category/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'category_id=' + encodeURIComponent(categoryId),
        }).catch(function () {});
      });
    });
  }

  /* ── Conversation Events (attach to dynamically created items) ── */

  function attachConversationEvents() {
    document.querySelectorAll('.chat-conv-item[draggable="true"]').forEach(function (item) {
      if (item._listenersAttached) return;
      item._listenersAttached = true;

      var pinBtn = item.querySelector('.chat-pin-btn');
      if (pinBtn && !pinBtn._listenerAttached) {
        pinBtn._listenerAttached = true;
        pinBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          togglePin(this, item.getAttribute('data-id'));
        });
      }
    });

    document.querySelectorAll('.chat-category-toggle').forEach(function (btn) {
      if (btn._listenerAttached) return;
      btn._listenerAttached = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var items = this.closest('.chat-category').querySelector('.chat-category-items');
        if (items) {
          items.classList.toggle('collapsed');
          this.classList.toggle('collapsed');
        }
      });
    });

    document.querySelectorAll('.chat-category-rename-btn').forEach(function (btn) {
      if (btn._listenerAttached) return;
      btn._listenerAttached = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        renameCategory(this);
      });
    });

    document.querySelectorAll('.chat-category-delete-btn').forEach(function (btn) {
      if (btn._listenerAttached) return;
      btn._listenerAttached = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        deleteCategory(this);
      });
    });
  }

  /* ── Suggested Prompts ── */

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
    chatStopBtn.addEventListener('click', function () { abortStream(); });
  }

  document.querySelectorAll('.chat-suggestion-card').forEach(function (card) {
    card.addEventListener('click', function () {
      var text = this.getAttribute('data-prompt');
      if (text) insertSuggestion(text);
    });
  });

  /* ── Sidebar Add Category ── */

  var addCatBtn = document.getElementById('addCategoryBtn');
  if (addCatBtn) {
    addCatBtn.addEventListener('click', function () {
      var name = prompt('Enter category name:');
      if (name && name.trim()) createCategory(name.trim());
    });
  }

  /* ── Rename/Delete Buttons (static) ── */

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
        headers: { 'X-CSRFToken': getCSRF(), 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
        body: 'title=' + encodeURIComponent(newTitle.trim()),
      })
      .then(function (r) { return r.json(); })
      .then(function (data) { if (data.title && titleEl) titleEl.textContent = data.title; })
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
        headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      })
      .then(function () { window.location.href = '/assistant/'; })
      .catch(function () { window.location.href = '/assistant/'; });
    });
  });

  /* ── Pin buttons (static) ── */
  document.querySelectorAll('.chat-pin-btn').forEach(function (btn) {
    if (btn._listenerAttached) return;
    btn._listenerAttached = true;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var item = this.closest('.chat-conv-item');
      togglePin(this, item.getAttribute('data-id'));
    });
  });

  /* ── Copy Functions ── */

  window.copyCode = function (btn) {
    var pre = btn.closest('pre');
    var code = pre ? pre.querySelector('code') : null;
    if (!code) return;
    var text = code.textContent;
    navigator.clipboard.writeText(text).then(function () {
      btn.innerHTML = '<i class="fas fa-check"></i>';
      btn.classList.add('copied');
      setTimeout(function () { btn.innerHTML = '<i class="fas fa-copy"></i>'; btn.classList.remove('copied'); }, 2000);
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
      setTimeout(function () { btn.innerHTML = '<i class="fas fa-copy"></i> Copy'; btn.classList.remove('copied'); }, 2000);
    });
  };

  window.editMessage = editMessage;

  /* ── Init ── */

  scrollToBottom();

  if (chatMessages) {
    chatMessages.querySelectorAll('pre code').forEach(function (block) {
      if (window.hljs) hljs.highlightElement(block);
    });
  }

  initDragDrop();
  attachConversationEvents();

})();
