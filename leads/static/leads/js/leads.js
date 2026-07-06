(function () {

  var search = document.getElementById('leadSearch');
  var searchBox = search ? search.closest('.search-box') : null;
  var clearBtn = document.getElementById('searchClear');
  var spinner = document.getElementById('searchSpinner');
  var statusFilter = document.getElementById('statusFilter');
  var priorityFilter = document.getElementById('priorityFilter');
  var sourceFilter = document.getElementById('sourceFilter');
  var sortSelect = document.getElementById('sortSelect');
  var resultsBody = document.getElementById('leadsResults');
  var pagination = document.getElementById('leadsPagination');
  var noResults = document.getElementById('searchNoResults');
  var count = document.getElementById('leadCount');
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

  function getStatusClass(status) {
    var m = {
      'new': 'lead-badge--new',
      'contacted': 'lead-badge--contacted',
      'qualified': 'lead-badge--qualified',
      'proposal sent': 'lead-badge--proposal-sent',
      'proposal_sent': 'lead-badge--proposal-sent',
      'negotiation': 'lead-badge--negotiation',
      'won': 'lead-badge--won',
      'lost': 'lead-badge--lost',
    };
    return m[status.toLowerCase()] || '';
  }

  function getPriorityClass(priority) {
    var m = {
      'low': 'lead-priority--low',
      'medium': 'lead-priority--medium',
      'high': 'lead-priority--high',
      'urgent': 'lead-priority--urgent',
    };
    return m[priority.toLowerCase()] || '';
  }

  function qs(key, val) {
    return encodeURIComponent(key) + '=' + encodeURIComponent(val || '');
  }

  function buildUrl() {
    var s = search.value.trim();
    var st = statusFilter ? statusFilter.value : '';
    var p = priorityFilter ? priorityFilter.value : '';
    var src = sourceFilter ? sourceFilter.value : '';
    var o = sortSelect ? sortSelect.value : 'newest';
    return '/leads/search/?' + qs('search', s) + '&' + qs('status', st) + '&' + qs('priority', p) + '&' + qs('source', src) + '&' + qs('sort', o);
  }

  function updateUrl() {
    var s = search.value.trim();
    var st = statusFilter ? statusFilter.value : '';
    var p = priorityFilter ? priorityFilter.value : '';
    var src = sourceFilter ? sourceFilter.value : '';
    var o = sortSelect ? sortSelect.value : 'newest';
    var params = [];
    if (s) params.push(qs('search', s));
    if (st) params.push(qs('status', st));
    if (p) params.push(qs('priority', p));
    if (src) params.push(qs('source', src));
    if (o && o !== 'newest') params.push(qs('sort', o));
    var q = params.length ? '?' + params.join('&') : window.location.pathname;
    window.history.replaceState({ search: s, status: st, priority: p, source: src, sort: o }, '', q);
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
    var checked = resultsBody.querySelectorAll('input[name=lead_id]:checked');
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
    var checked = resultsBody.querySelectorAll('input[name=lead_id]:checked');
    return Array.from(checked).map(function (cb) { return cb.value; });
  }

  function clearAllCheckboxes() {
    if (selectAll) selectAll.checked = false;
    var all = resultsBody.querySelectorAll('input[name=lead_id]');
    all.forEach(function (cb) { cb.checked = false; });
    updateBulkBar();
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      var checked = selectAll.checked;
      var all = resultsBody.querySelectorAll('input[name=lead_id]');
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
      fetch('/leads/bulk-delete/', {
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
      window.location.href = '/leads/export/?ids=' + ids.join(',');
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
      showNoResults(true, data.search, data.status, data.priority, data.source);
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
    data.leads.forEach(function (lead) {
      var sc = getStatusClass(lead.status);
      var pc = getPriorityClass(lead.priority);
      var revenue = lead.expected_revenue ? '$' + parseFloat(lead.expected_revenue).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '';

      html += '<tr>' +
        '<td class="lead-checkbox"><input type="checkbox" name="lead_id" value="' + lead.id + '"></td>' +
        '<td><div class="dash-td-name">' +
          '<span class="lead-avatar">' + escapeHtml(lead.lead_name.substring(0, 2).toUpperCase()) + '</span>' +
          '<div><div class="lead-name">' + escapeHtml(lead.lead_name) + '</div>' +
          (lead.company ? '<div class="lead-company">' + escapeHtml(lead.company) + '</div>' : '') +
        '</div></div></td>' +
        '<td>' + (lead.contact_person ? escapeHtml(lead.contact_person) : '\u2014') + '</td>' +
        '<td>' + (lead.email ? escapeHtml(lead.email) : '\u2014') + '</td>' +
        '<td><span class="lead-badge ' + sc + '">' + escapeHtml(lead.status) + '</span></td>' +
        '<td><span class="lead-priority ' + pc + '">' + escapeHtml(lead.priority) + '</span></td>' +
        '<td>' + (revenue || '\u2014') + '</td>' +
        '<td>' +
          '<a href="' + lead.detail_url + '" class="dash-td-btn" title="View"><i class="fas fa-eye"></i></a>' +
          '<a href="' + lead.update_url + '" class="dash-td-btn" title="Edit"><i class="fas fa-edit"></i></a>' +
          '<a href="' + lead.delete_url + '" class="dash-td-btn" title="Delete" style="color:var(--dash-red)"><i class="fas fa-trash"></i></a>' +
        '</td>' +
      '</tr>';
    });
    resultsBody.innerHTML = html;

    if (selectAll) selectAll.checked = false;
    if (pagination) pagination.style.display = 'none';

    resultsBody.querySelectorAll('input[name=lead_id]').forEach(function (cb) {
      cb.addEventListener('change', updateBulkBar);
    });
  }

  function showTable(show) {
    if (tableHead) tableHead.style.display = show ? '' : 'none';
    if (resultsBody) resultsBody.style.display = show ? '' : 'none';
    if (pagination) pagination.style.display = 'none';
  }

  function showNoResults(show, q, status, priority, source) {
    if (!noResults) return;
    noResults.style.display = show ? 'block' : 'none';
    if (show) {
      var msg = 'No leads match';
      if (q) msg += ' <strong>' + escapeHtml(q) + '</strong>';
      if (status) msg += ' in <strong>' + escapeHtml(status) + '</strong>';
      if (priority) msg += ' with priority <strong>' + escapeHtml(priority) + '</strong>';
      if (source) msg += ' from <strong>' + escapeHtml(source) + '</strong>';
      msg += '.';
      document.getElementById('searchNoResultsMsg').innerHTML = msg;
    }
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', function () {
      search.value = '';
      if (statusFilter) statusFilter.value = '';
      if (priorityFilter) priorityFilter.value = '';
      if (sourceFilter) sourceFilter.value = '';
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

  if (statusFilter) {
    statusFilter.addEventListener('change', doSearch);
  }

  if (priorityFilter) {
    priorityFilter.addEventListener('change', doSearch);
  }

  if (sourceFilter) {
    sourceFilter.addEventListener('change', doSearch);
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
    var st = params.get('status') || '';
    var p = params.get('priority') || '';
    var src = params.get('source') || '';
    var o = params.get('sort') || 'newest';

    search.value = s;
    if (statusFilter) statusFilter.value = st;
    if (priorityFilter) priorityFilter.value = p;
    if (sourceFilter) sourceFilter.value = src;
    if (sortSelect) sortSelect.value = o;
    if (clearBtn) clearBtn.classList.toggle('is-visible', s.length > 0);
    doSearch();
  });

  (function init() {
    var params = new URLSearchParams(window.location.search);
    var s = params.get('search') || '';
    var st = params.get('status') || '';
    var p = params.get('priority') || '';
    var src = params.get('source') || '';
    if (s || st || p || src) {
      search.value = s;
      if (statusFilter) statusFilter.value = st;
      if (priorityFilter) priorityFilter.value = p;
      if (sourceFilter) sourceFilter.value = src;
      if (clearBtn) clearBtn.classList.toggle('is-visible', s.length > 0);
    }
  })();

  var form = document.querySelector('.lead-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      var valid = true;
      var name = form.querySelector('#id_lead_name');
      if (name && !name.value.trim()) { showError(name, 'Lead name is required.'); valid = false; }
      else if (name) { clearError(name); }

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

  var deleteBtn = document.getElementById('confirmDeleteBtn');
  var cancelBtn = document.getElementById('cancelDeleteBtn');
  var deleteStage = document.getElementById('deleteStage');
  var initialStage = document.getElementById('initialStage');

  if (deleteBtn && cancelBtn && deleteStage && initialStage) {
    deleteBtn.addEventListener('click', function () { initialStage.style.display = 'none'; deleteStage.style.display = 'block'; });
    cancelBtn.addEventListener('click', function () { initialStage.style.display = 'block'; deleteStage.style.display = 'none'; });
  }

})();
