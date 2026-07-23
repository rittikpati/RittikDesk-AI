(function () {
  'use strict';

  var input = document.getElementById('dashSearch');
  if (!input) return;

  var wrapper = input.closest('.dash-search');
  var dropdown = document.getElementById('gsDropdown');
  var resultsContainer = document.getElementById('gsResults');

  if (!dropdown || !resultsContainer) return;

  var activeIndex = -1;
  var currentItems = [];
  var debounceTimer = null;
  var isOpen = false;

  var MODULE_LABELS = {
    contacts: 'Contacts',
    companies: 'Companies',
    leads: 'Leads',
    deals: 'Deals',
    tasks: 'Tasks',
    campaigns: 'Campaigns',
    emails: 'Emails'
  };

  var MODULE_ORDER = ['contacts', 'companies', 'leads', 'deals', 'tasks', 'campaigns', 'emails'];

  /* ── Open / Close ── */
  function openDropdown() {
    if (!isOpen) {
      dropdown.classList.add('open');
      isOpen = true;
    }
  }

  function closeDropdown() {
    if (isOpen) {
      dropdown.classList.remove('open');
      isOpen = false;
      activeIndex = -1;
      currentItems = [];
    }
  }

  /* ── Render ── */
  function renderLoading() {
    resultsContainer.innerHTML =
      '<div class="gs-loading">' +
        '<div class="gs-spinner"></div>' +
        '<span>Searching...</span>' +
      '</div>';
    openDropdown();
  }

  function renderEmpty(query) {
    resultsContainer.innerHTML =
      '<div class="gs-empty">' +
        '<div class="gs-empty-icon"><i class="fas fa-search"></i></div>' +
        '<h4>No results found</h4>' +
        '<p>No matches for "' + escapeHtml(query) + '"</p>' +
      '</div>';
    openDropdown();
  }

  function renderResults(data) {
    var results = data.results || {};
    var totalItems = 0;

    MODULE_ORDER.forEach(function (key) {
      totalItems += (results[key] || []).length;
    });

    if (totalItems === 0) {
      renderEmpty(data.query);
      return;
    }

    var html = '';
    currentItems = [];
    activeIndex = -1;

    MODULE_ORDER.forEach(function (key) {
      var items = results[key];
      if (!items || !items.length) return;

      html += '<div class="gs-group">';
      html += '<div class="gs-group-label"><i class="' + (items[0] ? items[0].icon : '') + '"></i>' + MODULE_LABELS[key] + '</div>';

      items.forEach(function (item) {
        var idx = currentItems.length;
        currentItems.push(item);
        html +=
          '<a class="gs-item" data-index="' + idx + '" href="' + item.detail_url + '" role="option">' +
            '<div class="gs-item-icon"><i class="' + item.icon + '"></i></div>' +
            '<div class="gs-item-text">' +
              '<div class="gs-item-name">' + escapeHtml(item.name) + '</div>' +
              (item.subtitle ? '<div class="gs-item-sub">' + escapeHtml(item.subtitle) + '</div>' : '') +
            '</div>' +
            '<span class="gs-item-module">' + MODULE_LABELS[key] + '</span>' +
          '</a>';
      });

      html += '</div>';
    });

    html +=
      '<div class="gs-footer">' +
        '<span><kbd>&uarr;</kbd><kbd>&darr;</kbd> navigate</span>' +
        '<span><kbd>&crarr;</kbd> open</span>' +
        '<span><kbd>Esc</kbd> close</span>' +
      '</div>';

    resultsContainer.innerHTML = html;
    openDropdown();
  }

  function escapeHtml(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

  /* ── Fetch ── */
  function doSearch(q) {
    if (q.length < 2) {
      closeDropdown();
      return;
    }
    renderLoading();
    fetch('/dashboard/search/?q=' + encodeURIComponent(q), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { renderResults(data); })
      .catch(function () { closeDropdown(); });
  }

  /* ── Keyboard Navigation ── */
  function setActive(index) {
    var items = resultsContainer.querySelectorAll('.gs-item');
    items.forEach(function (el) { el.classList.remove('gs-active'); });
    if (index >= 0 && index < items.length) {
      items[index].classList.add('gs-active');
      items[index].scrollIntoView({ block: 'nearest' });
    }
    activeIndex = index;
  }

  function handleKeydown(e) {
    if (!isOpen) return;

    var key = e.key;

    if (key === 'ArrowDown') {
      e.preventDefault();
      var next = activeIndex + 1;
      if (next >= currentItems.length) next = 0;
      setActive(next);
    } else if (key === 'ArrowUp') {
      e.preventDefault();
      var prev = activeIndex - 1;
      if (prev < 0) prev = currentItems.length - 1;
      setActive(prev);
    } else if (key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < currentItems.length) {
        e.preventDefault();
        window.location.href = currentItems[activeIndex].detail_url;
      }
    } else if (key === 'Escape') {
      e.preventDefault();
      closeDropdown();
      input.blur();
    }
  }

  /* ── Events ── */
  input.addEventListener('input', function () {
    var q = input.value.trim();
    clearTimeout(debounceTimer);
    if (q.length < 2) {
      closeDropdown();
      return;
    }
    debounceTimer = setTimeout(function () { doSearch(q); }, 300);
  });

  input.addEventListener('keydown', handleKeydown);

  input.addEventListener('focus', function () {
    var q = input.value.trim();
    if (q.length >= 2 && !isOpen) {
      doSearch(q);
    }
  });

  document.addEventListener('click', function (e) {
    if (!wrapper.contains(e.target) && !dropdown.contains(e.target)) {
      closeDropdown();
    }
  });

  /* ── Ctrl+K shortcut ── */
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      input.focus();
      input.select();
    }
  });

})();
