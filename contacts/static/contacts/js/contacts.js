(function () {

  var search = document.getElementById('contactSearch');
  var searchBox = search ? search.closest('.search-box') : null;
  var clearBtn = document.getElementById('searchClear');
  var spinner = document.getElementById('searchSpinner');
  var tagFilter = document.getElementById('tagFilter');
  var sortSelect = document.getElementById('sortSelect');
  var resultsBody = document.getElementById('contactsResults');
  var pagination = document.getElementById('contactsPagination');
  var noResults = document.getElementById('searchNoResults');
  var count = document.getElementById('contactCount');
  var tableHead = document.querySelector('.dash-table thead');
  var clearFiltersBtn = document.getElementById('clearFiltersBtn');

  var selectAll = document.getElementById('selectAll');
  var bulkBar = document.getElementById('bulkBar');
  var bulkCount = document.getElementById('bulkCount');
  var bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
  var bulkExportBtn = document.getElementById('bulkExportBtn');
  var bulkClearBtn = document.getElementById('bulkClearBtn');
  var bulkDeleteModal = document.getElementById('bulkDeleteModal');
  var bulkDeleteConfirm = document.getElementById('bulkDeleteConfirm');
  var bulkDeleteCount = document.getElementById('bulkDeleteCount');

  if (!search || !resultsBody) return;

  function escapeHtml(str) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }

  function getTagClass(tag) {
    var t = tag.toLowerCase();
    if (t === 'lead') return 'contact-tag--lead';
    if (t === 'client') return 'contact-tag--client';
    if (t === 'vip') return 'contact-tag--vip';
    if (t === 'partner') return 'contact-tag--partner';
    if (t === 'prospect') return 'contact-tag--prospect';
    return '';
  }

  function qs(key, val) {
    return encodeURIComponent(key) + '=' + encodeURIComponent(val || '');
  }

  function buildUrl() {
    var s = search.value.trim();
    var t = tagFilter ? tagFilter.value : '';
    var o = sortSelect ? sortSelect.value : 'newest';
    return '/contacts/search/?' + qs('search', s) + '&' + qs('tag', t) + '&' + qs('sort', o);
  }

  function updateUrl() {
    var s = search.value.trim();
    var t = tagFilter ? tagFilter.value : '';
    var o = sortSelect ? sortSelect.value : 'newest';
    var params = [];
    if (s) params.push(qs('search', s));
    if (t) params.push(qs('tag', t));
    if (o && o !== 'newest') params.push(qs('sort', o));
    var q = params.length ? '?' + params.join('&') : window.location.pathname;
    window.history.replaceState({ search: s, tag: t, sort: o }, '', q);
  }

  function showLoading(on) {
    if (spinner) spinner.classList.toggle('is-loading', on);
    if (searchBox) searchBox.classList.toggle('is-loading', on);
  }

  function renderCount(n) {
    if (count) count.textContent = '(' + n + ')';
  }

  function updateBulkBar() {
    if (!bulkBar || !bulkCount) return;
    var checked = resultsBody.querySelectorAll('input[name=contact_id]:checked');
    var n = checked.length;
    if (n > 0) {
      bulkBar.style.display = 'flex';
      bulkCount.textContent = n + ' selected';
      if (bulkDeleteBtn) bulkDeleteBtn.style.display = '';
      if (bulkExportBtn) bulkExportBtn.style.display = '';
    } else {
      bulkBar.style.display = 'none';
    }
  }

  function getSelectedIds() {
    var checked = resultsBody.querySelectorAll('input[name=contact_id]:checked');
    return Array.from(checked).map(function (cb) { return cb.value; });
  }

  function clearAllCheckboxes() {
    if (selectAll) selectAll.checked = false;
    var all = resultsBody.querySelectorAll('input[name=contact_id]');
    all.forEach(function (cb) { cb.checked = false; });
    updateBulkBar();
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      var checked = selectAll.checked;
      var all = resultsBody.querySelectorAll('input[name=contact_id]');
      all.forEach(function (cb) { cb.checked = checked; });
      updateBulkBar();
    });
  }

  if (bulkClearBtn) {
    bulkClearBtn.addEventListener('click', clearAllCheckboxes);
  }

  if (bulkDeleteBtn && bulkDeleteModal) {
    bulkDeleteBtn.addEventListener('click', function () {
      var ids = getSelectedIds();
      if (ids.length === 0) return;
      if (bulkDeleteCount) bulkDeleteCount.textContent = ids.length;
      var modal = new bootstrap.Modal(bulkDeleteModal);
      modal.show();
    });
  }

  if (bulkDeleteConfirm) {
    bulkDeleteConfirm.addEventListener('click', function () {
      var ids = getSelectedIds();
      if (ids.length === 0) return;
      var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
      var token = csrf ? csrf.value : '';
      var body = new URLSearchParams();
      ids.forEach(function (id) { body.append('ids', id); });
      fetch('/contacts/bulk-delete/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': token,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: body
      })
      .then(function (r) { return r.json(); })
      .then(function () {
        var modal = bootstrap.Modal.getInstance(bulkDeleteModal);
        if (modal) modal.hide();
        location.reload();
      })
      .catch(function () {
        location.reload();
      });
    });
  }

  if (bulkExportBtn) {
    bulkExportBtn.addEventListener('click', function () {
      var ids = getSelectedIds();
      if (ids.length === 0) return;
      window.location.href = '/contacts/export/?ids=' + ids.join(',');
    });
  }

  function doSearch() {
    showLoading(true);
    if (clearBtn && search.value.trim()) clearBtn.classList.add('is-visible');
    else if (clearBtn) clearBtn.classList.remove('is-visible');

    updateUrl();

    fetch(buildUrl(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        showLoading(false);
        renderResults(data);
      })
      .catch(function () { showLoading(false); });
  }

  function renderResults(data) {
    if (data.count === 0 && data.search) {
      showTable(false);
      showNoResults(true, data.search, data.tag);
      renderCount(0);
      clearAllCheckboxes();
      return;
    }
    if (data.count === 0) {
      showTable(false);
      showNoResults(false);
      renderCount(0);
      clearAllCheckboxes();
      return;
    }

    showNoResults(false);
    showTable(true);
    renderCount(data.count);
    clearAllCheckboxes();

    var html = '';
    data.contacts.forEach(function (c) {
      var tagsHtml = '';
      if (c.tags && c.tags.length) {
        c.tags.forEach(function (t) {
          var tc = getTagClass(t);
          tagsHtml += '<span class="contact-tag ' + tc + '">' + escapeHtml(t) + '</span>';
        });
      } else {
        tagsHtml = '<span style="color:var(--dash-text-ter);font-size:0.7rem">\u2014</span>';
      }

      html += '<tr>' +
        '<td class="contact-checkbox"><input type="checkbox" name="contact_id" value="' + c.id + '"></td>' +
        '<td><div class="dash-td-name">' +
          '<span class="contact-avatar">' + escapeHtml(c.avatar_initials) + '</span>' +
          '<div><div class="contact-name">' + escapeHtml(c.full_name) + '</div>' +
          (c.job_title ? '<div class="contact-company">' + escapeHtml(c.job_title) + '</div>' : '') +
        '</div></div></td>' +
        '<td>' + (c.email ? escapeHtml(c.email) : '\u2014') + '</td>' +
        '<td>' + (c.company ? escapeHtml(c.company) : '\u2014') + '</td>' +
        '<td>' + (c.phone ? escapeHtml(c.phone) : '\u2014') + '</td>' +
        '<td>' + tagsHtml + '</td>' +
        '<td>' +
          '<a href="' + c.detail_url + '" class="dash-td-btn" title="View"><i class="fas fa-eye"></i></a>' +
          '<a href="' + c.update_url + '" class="dash-td-btn" title="Edit"><i class="fas fa-edit"></i></a>' +
          '<a href="' + c.delete_url + '" class="dash-td-btn" title="Delete" style="color:var(--dash-red)"><i class="fas fa-trash"></i></a>' +
        '</td>' +
      '</tr>';
    });
    resultsBody.innerHTML = html;

    if (selectAll) selectAll.checked = false;
    if (pagination) pagination.style.display = 'none';

    resultsBody.querySelectorAll('input[name=contact_id]').forEach(function (cb) {
      cb.addEventListener('change', updateBulkBar);
    });
  }

  function showTable(show) {
    if (tableHead) tableHead.style.display = show ? '' : 'none';
    if (resultsBody) resultsBody.style.display = show ? '' : 'none';
    if (pagination) pagination.style.display = 'none';
  }

  function showNoResults(show, q, tag) {
    if (!noResults) return;
    noResults.style.display = show ? 'block' : 'none';
    if (show) {
      var msg = 'No contacts match';
      if (q) msg += ' <strong>' + escapeHtml(q) + '</strong>';
      if (tag) msg += ' in <strong>' + escapeHtml(tag) + '</strong>';
      msg += '.';
      document.getElementById('searchNoResultsMsg').innerHTML = msg;
    }
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', function () {
      search.value = '';
      if (tagFilter) tagFilter.value = '';
      if (sortSelect) sortSelect.value = 'newest';
      if (clearBtn) clearBtn.classList.remove('is-visible');
      doSearch();
      search.focus();
    });
  }

  var debounceTimer;
  search.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    if (clearBtn) clearBtn.classList.toggle('is-visible', search.value.trim().length > 0);
    debounceTimer = setTimeout(doSearch, 300);
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      search.value = '';
      clearBtn.classList.remove('is-visible');
      search.focus();
      doSearch();
    });
  }

  if (tagFilter) {
    tagFilter.addEventListener('change', doSearch);
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', doSearch);
  }

  if (searchBox) {
    search.addEventListener('focus', function () { searchBox.classList.add('is-focused'); });
    search.addEventListener('blur', function () { searchBox.classList.remove('is-focused'); });
  }

  window.addEventListener('popstate', function (e) {
    var params = new URLSearchParams(window.location.search);
    var s = params.get('search') || '';
    var t = params.get('tag') || '';
    var o = params.get('sort') || 'newest';

    search.value = s;
    if (tagFilter) tagFilter.value = t;
    if (sortSelect) sortSelect.value = o;
    if (clearBtn) clearBtn.classList.toggle('is-visible', s.length > 0);
    doSearch();
  });

  (function init() {
    var params = new URLSearchParams(window.location.search);
    var s = params.get('search') || '';
    var t = params.get('tag') || '';
    if (s || t) {
      search.value = s;
      if (tagFilter) tagFilter.value = t;
      if (clearBtn) clearBtn.classList.toggle('is-visible', s.length > 0);
    }
  })();

  var form = document.querySelector('.contact-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      var valid = true;
      var name = form.querySelector('#id_full_name');
      var email = form.querySelector('#id_email');

      if (name && !name.value.trim()) { showError(name, 'Full name is required.'); valid = false; }
      else if (name) { clearError(name); }

      if (email && email.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) { showError(email, 'Enter a valid email address.'); valid = false; }
      else if (email) { clearError(email); }

      if (!valid) e.preventDefault();
    });
    form.querySelectorAll('.form-control').forEach(function (el) {
      el.addEventListener('input', function () { clearError(this); });
    });
  }

  function showError(el, msg) {
    el.classList.add('is-invalid');
    var fb = el.parentElement.querySelector('.invalid-feedback');
    if (!fb) { fb = document.createElement('div'); fb.className = 'invalid-feedback'; el.parentElement.appendChild(fb); }
    fb.textContent = msg;
  }
  function clearError(el) {
    el.classList.remove('is-invalid');
    var fb = el.parentElement.querySelector('.invalid-feedback');
    if (fb) fb.remove();
  }

})();
