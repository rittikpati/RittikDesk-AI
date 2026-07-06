(function () {

  var search = document.getElementById('campaignSearch');
  var searchBox = search ? search.closest('.search-box') : null;
  var clearBtn = document.getElementById('searchClear');
  var spinner = document.getElementById('searchSpinner');
  var statusFilter = document.getElementById('statusFilter');
  var resultsBody = document.getElementById('campaignsResults');
  var pagination = document.getElementById('campaignsPagination');
  var noResults = document.getElementById('searchNoResults');
  var count = document.getElementById('campaignCount');
  var tableHead = document.querySelector('.dash-table thead');
  var clearFiltersBtn = document.getElementById('clearFiltersBtn');

  if (!search || !resultsBody) return;

  function escapeHtml(str) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }

  function getStatusClass(status) {
    var m = {
      'draft': 'campaign-status--draft',
      'scheduled': 'campaign-status--scheduled',
      'sent': 'campaign-status--sent',
    };
    return m[status.toLowerCase()] || '';
  }

  function qs(key, val) {
    return encodeURIComponent(key) + '=' + encodeURIComponent(val || '');
  }

  function buildUrl() {
    var s = search.value.trim();
    var st = statusFilter ? statusFilter.value : '';
    return '/campaigns/search/?' + qs('search', s) + '&' + qs('status', st);
  }

  function updateUrl() {
    var s = search.value.trim();
    var st = statusFilter ? statusFilter.value : '';
    var params = [];
    if (s) params.push(qs('search', s));
    if (st) params.push(qs('status', st));
    var q = params.length ? '?' + params.join('&') : window.location.pathname;
    window.history.replaceState({ search: s, status: st }, '', q);
  }

  function showLoading(on) {
    if (spinner) spinner.classList.toggle('is-loading', on);
    if (searchBox) searchBox.classList.toggle('is-loading', on);
  }

  function renderCount(n) {
    if (count) count.textContent = '(' + n + ')';
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
      showNoResults(true, data.search, data.status);
      renderCount(0);
      return;
    }
    if (data.count === 0) {
      showTable(false);
      showNoResults(false);
      renderCount(0);
      return;
    }

    showNoResults(false);
    showTable(true);
    renderCount(data.count);

    var html = '';
    data.campaigns.forEach(function (c) {
      var sc = getStatusClass(c.status);
      var scheduled = c.scheduled_at || '';
      var preview = c.body ? c.body.substring(0, 80) + (c.body.length > 80 ? '...' : '') : '';

      html += '<tr>' +
        '<td><div class="dash-td-name"><div class="lead-name">' + escapeHtml(c.name) + '</div></div></td>' +
        '<td>' + escapeHtml(c.subject) + '</td>' +
        '<td><span class="campaign-status ' + sc + '">' + escapeHtml(c.status) + '</span></td>' +
        '<td style="font-size:0.75rem;color:var(--dash-text-sec)">' + (scheduled ? escapeHtml(scheduled) : '\u2014') + '</td>' +
        '<td>' +
          '<a href="' + c.detail_url + '" class="dash-td-btn" title="View"><i class="fas fa-eye"></i></a>' +
          (c.status !== 'Sent' ? '<a href="' + c.update_url + '" class="dash-td-btn" title="Edit"><i class="fas fa-edit"></i></a>' : '') +
          '<a href="' + c.delete_url + '" class="dash-td-btn" title="Delete" style="color:var(--dash-red)"><i class="fas fa-trash"></i></a>' +
        '</td>' +
      '</tr>';
    });
    resultsBody.innerHTML = html;
    if (pagination) pagination.style.display = 'none';
  }

  function showTable(show) {
    if (tableHead) tableHead.style.display = show ? '' : 'none';
    if (resultsBody) resultsBody.style.display = show ? '' : 'none';
    if (pagination) pagination.style.display = 'none';
  }

  function showNoResults(show, q, status) {
    if (!noResults) return;
    noResults.style.display = show ? 'block' : 'none';
    if (show) {
      var msg = 'No campaigns match';
      if (q) msg += ' <strong>' + escapeHtml(q) + '</strong>';
      if (status) msg += ' with status <strong>' + escapeHtml(status) + '</strong>';
      msg += '.';
      document.getElementById('searchNoResultsMsg').innerHTML = msg;
    }
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', function () {
      search.value = '';
      if (statusFilter) statusFilter.value = '';
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

  if (searchBox) {
    search.addEventListener('focus', function () { searchBox.classList.add('is-focused'); });
    search.addEventListener('blur', function () { searchBox.classList.remove('is-focused'); });
  }

  window.addEventListener('popstate', function (e) {
    var params = new URLSearchParams(window.location.search);
    var s = params.get('search') || '';
    var st = params.get('status') || '';

    search.value = s;
    if (statusFilter) statusFilter.value = st;
    if (clearBtn) clearBtn.classList.toggle('is-visible', s.length > 0);
    doSearch();
  });

  (function init() {
    var params = new URLSearchParams(window.location.search);
    var s = params.get('search') || '';
    var st = params.get('status') || '';
    if (s || st) {
      search.value = s;
      if (statusFilter) statusFilter.value = st;
      if (clearBtn) clearBtn.classList.toggle('is-visible', s.length > 0);
    }
  })();

  var form = document.querySelector('.campaign-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      var valid = true;
      var name = form.querySelector('#id_name');
      var subject = form.querySelector('#id_subject');
      if (name && !name.value.trim()) { showError(name, 'Campaign name is required.'); valid = false; }
      else if (name) { clearError(name); }
      if (subject && !subject.value.trim()) { showError(subject, 'Subject is required.'); valid = false; }
      else if (subject) { clearError(subject); }
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
