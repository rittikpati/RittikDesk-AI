(function () {

  var search = document.getElementById('companySearch');
  var searchBox = search ? search.closest('.search-box') : null;
  var clearBtn = document.getElementById('searchClear');
  var spinner = document.getElementById('searchSpinner');
  var filterIndustry = document.getElementById('filterIndustry');
  var filterStatus = document.getElementById('filterStatus');
  var filterCountry = document.getElementById('filterCountry');
  var sortSelect = document.getElementById('sortCompanies');
  var resultsBody = document.getElementById('companyTableBody');
  var pagination = document.getElementById('companyPagination');
  var noResults = document.getElementById('searchNoResults');
  var count = document.getElementById('companyCount');
  var clearFiltersBtn = document.getElementById('clearFiltersBtn');

  var selectAll = document.getElementById('selectAll');
  var bulkBar = document.getElementById('bulkBar');
  var selectedCount = document.getElementById('selectedCount');
  var bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
  var bulkUpdateBtn = document.getElementById('bulkUpdateBtn');
  var bulkExportBtn = document.getElementById('bulkExportBtn');
  var bulkClearBtn = document.getElementById('bulkClearBtn');
  var bulkStatus = document.getElementById('bulkStatus');

  if (!search || !resultsBody) return;

  function escapeHtml(str) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  }

  function slugify(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  }

  function qs(key, val) {
    return encodeURIComponent(key) + '=' + encodeURIComponent(val || '');
  }

  function buildUrl() {
    var params = [];
    var s = search.value.trim();
    if (s) params.push(qs('search', s));
    if (filterIndustry && filterIndustry.value) params.push(qs('industry', filterIndustry.value));
    if (filterStatus && filterStatus.value) params.push(qs('status', filterStatus.value));
    if (filterCountry && filterCountry.value) params.push(qs('country', filterCountry.value));
    if (sortSelect && sortSelect.value) params.push(qs('sort', sortSelect.value));
    return '/companies/search/?' + params.join('&');
  }

  function fetchCompanies() {
    if (spinner) spinner.classList.add('is-loading');
    fetch(buildUrl(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (spinner) spinner.classList.remove('is-loading');
        renderTable(data.companies);
        if (count) count.textContent = '(' + data.count + ')';
      })
      .catch(function () {
        if (spinner) spinner.classList.remove('is-loading');
      });
  }

  function renderTable(companies) {
    if (!companies.length) {
      resultsBody.innerHTML = '';
      if (pagination) pagination.style.display = 'none';
      if (noResults) noResults.style.display = '';
      return;
    }
    if (noResults) noResults.style.display = 'none';
    if (pagination) pagination.style.display = '';

    var html = '';
    companies.forEach(function (c) {
      var loc = '';
      if (c.city || c.country) {
        loc = escapeHtml(c.city || '') + (c.city && c.country ? ', ' : '') + escapeHtml(c.country || '');
      }
      var rev = c.annual_revenue
        ? '$' + parseFloat(c.annual_revenue).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})
        : '—';

      html += '<tr>' +
        '<td class="contact-checkbox"><input type="checkbox" name="company_id" value="' + c.id + '"></td>' +
        '<td><div class="dash-td-name">' +
          '<span class="contact-avatar">' + escapeHtml(c.name.substring(0, 2).toUpperCase()) + '</span>' +
          '<div>' +
            '<div class="contact-name">' + escapeHtml(c.name) + '</div>' +
            (c.email ? '<div class="contact-company">' + escapeHtml(c.email) + '</div>' : '') +
          '</div>' +
        '</div></td>' +
        '<td>' + (c.industry ? escapeHtml(c.industry) : '—') + '</td>' +
        '<td>' + (loc || '—') + '</td>' +
        '<td>' + (c.employees || '—') + '</td>' +
        '<td>' + rev + '</td>' +
        '<td><span class="contact-tag contact-tag--' + slugify(c.status) + '">' + escapeHtml(c.status) + '</span></td>' +
        '<td>' +
          '<a href="' + c.detail_url + '" class="dash-td-btn" title="View"><i class="fas fa-eye"></i></a>' +
          '<a href="' + c.update_url + '" class="dash-td-btn" title="Edit"><i class="fas fa-edit"></i></a>' +
          '<a href="' + c.delete_url + '" class="dash-td-btn" title="Delete" style="color:var(--dash-red)"><i class="fas fa-trash"></i></a>' +
        '</td></tr>';
    });
    resultsBody.innerHTML = html;
    updateBulkBar();
  }

  function getSelectedIds() {
    var ids = [];
    resultsBody.querySelectorAll('input[name="company_id"]:checked').forEach(function (cb) {
      ids.push(cb.value);
    });
    return ids;
  }

  function updateBulkBar() {
    var ids = getSelectedIds();
    if (!bulkBar) return;
    if (ids.length) {
      bulkBar.style.display = '';
      if (selectedCount) selectedCount.textContent = ids.length + ' selected';
    } else {
      bulkBar.style.display = 'none';
    }
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      resultsBody.querySelectorAll('input[name="company_id"]').forEach(function (cb) {
        cb.checked = selectAll.checked;
      });
      updateBulkBar();
    });
  }

  document.addEventListener('change', function (e) {
    if (e.target && e.target.name === 'company_id') updateBulkBar();
  });

  if (bulkClearBtn) {
    bulkClearBtn.addEventListener('click', function () {
      resultsBody.querySelectorAll('input[name="company_id"]').forEach(function (cb) { cb.checked = false; });
      if (selectAll) selectAll.checked = false;
      updateBulkBar();
    });
  }

  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', function () {
      var ids = getSelectedIds();
      if (!ids.length) return;
      if (!confirm('Delete ' + ids.length + ' company(ies)? This cannot be undone.')) return;
      var formData = new FormData();
      ids.forEach(function (id) { formData.append('ids', id); });
      fetch('/companies/bulk-delete/', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          fetchCompanies();
          updateBulkBar();
        }
      });
    });
  }

  if (bulkUpdateBtn) {
    bulkUpdateBtn.addEventListener('click', function () {
      var ids = getSelectedIds();
      if (!ids.length) return;
      var status = bulkStatus ? bulkStatus.value : '';
      if (!status) { alert('Please select a status to apply.'); return; }
      var formData = new FormData();
      ids.forEach(function (id) { formData.append('ids', id); });
      formData.append('status', status);
      fetch('/companies/bulk-update/', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) fetchCompanies();
      });
    });
  }

  if (bulkExportBtn) {
    bulkExportBtn.addEventListener('click', function () {
      var ids = getSelectedIds();
      var url = '/companies/export/csv/';
      if (ids.length) url += '?ids=' + ids.join(',');
      window.location.href = url;
    });
  }

  function getCookie(name) {
    var c = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return c ? c.pop() : '';
  }

  var debounceTimer;
  function debouncedFetch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fetchCompanies, 300);
  }

  if (search) {
    search.addEventListener('focus', function () {
      if (searchBox) searchBox.classList.add('is-focused');
    });
    search.addEventListener('blur', function () {
      if (searchBox) searchBox.classList.remove('is-focused');
    });
    search.addEventListener('input', function () {
      if (clearBtn) {
        if (search.value) clearBtn.classList.add('is-visible');
        else clearBtn.classList.remove('is-visible');
      }
      debouncedFetch();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      search.value = '';
      clearBtn.classList.remove('is-visible');
      fetchCompanies();
    });
  }

  if (filterIndustry) filterIndustry.addEventListener('change', fetchCompanies);
  if (filterStatus) filterStatus.addEventListener('change', fetchCompanies);
  if (filterCountry) filterCountry.addEventListener('change', fetchCompanies);
  if (sortSelect) sortSelect.addEventListener('change', fetchCompanies);

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', function () {
      search.value = '';
      if (filterIndustry) filterIndustry.value = '';
      if (filterStatus) filterStatus.value = '';
      if (filterCountry) filterCountry.value = '';
      if (clearBtn) clearBtn.classList.remove('is-visible');
      fetchCompanies();
    });
  }

})();
