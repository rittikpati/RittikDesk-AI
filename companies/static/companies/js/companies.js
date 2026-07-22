(function() {
  'use strict';

  var searchInput = document.getElementById('companySearch');
  var filterIndustry = document.getElementById('filterIndustry');
  var filterStatus = document.getElementById('filterStatus');
  var filterCountry = document.getElementById('filterCountry');
  var sortSelect = document.getElementById('sortCompanies');
  var tableBody = document.getElementById('companyTableBody');
  var selectAll = document.getElementById('selectAll');
  var bulkBar = document.getElementById('bulkBar');
  var selectedCount = document.getElementById('selectedCount');
  var bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
  var bulkUpdateBtn = document.getElementById('bulkUpdateBtn');
  var bulkExportBtn = document.getElementById('bulkExportBtn');
  var bulkClearBtn = document.getElementById('bulkClearBtn');
  var bulkStatus = document.getElementById('bulkStatus');

  function escapeHtml(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

  function slugify(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  }

  function fetchCompanies() {
    var params = new URLSearchParams();
    if (searchInput) params.set('search', searchInput.value.trim());
    if (filterIndustry) params.set('industry', filterIndustry.value);
    if (filterStatus) params.set('status', filterStatus.value);
    if (filterCountry) params.set('country', filterCountry.value);
    if (sortSelect) params.set('sort', sortSelect.value);

    var url = '/companies/search/?' + params.toString();

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        renderTable(data.companies);
        updatePagination(data.count);
      })
      .catch(function() {});
  }

  function renderTable(companies) {
    if (!tableBody) return;
    if (!companies.length) {
      tableBody.innerHTML =
        '<tr><td colspan="8"><div class="company-empty" style="padding:40px 20px">' +
        '<div class="company-empty-icon"><i class="fas fa-building"></i></div>' +
        '<h3>No companies found</h3>' +
        '<p>Try adjusting your search or filters.</p></div></td></tr>';
      return;
    }
    var html = '';
    companies.forEach(function(c) {
      html += '<tr data-id="' + c.id + '">' +
        '<td class="company-checkbox"><input type="checkbox" name="company_id" value="' + c.id + '"></td>' +
        '<td><div class="company-cell-name">' +
        '<span class="company-avatar">' + escapeHtml(c.name.substring(0, 2).toUpperCase()) + '</span>' +
        '<div><div class="company-name"><a href="' + c.detail_url + '">' + escapeHtml(c.name) + '</a></div>' +
        (c.email ? '<div class="company-meta">' + escapeHtml(c.email) + '</div>' : '') +
        '</div></div></td>' +
        '<td><span class="company-badge company-badge--industry">' + escapeHtml(c.industry || '—') + '</span></td>' +
        '<td>' + (c.city ? escapeHtml(c.city) + (c.country ? ', ' + escapeHtml(c.country) : '') : '—') + '</td>' +
        '<td>' + (c.employees || '—') + '</td>' +
        '<td>' + (c.annual_revenue ? '$' + parseFloat(c.annual_revenue).toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0}) : '—') + '</td>' +
        '<td><span class="company-badge company-badge--' + slugify(c.status) + '">' + escapeHtml(c.status) + '</span></td>' +
        '<td>' +
        '<a href="' + c.detail_url + '" class="dash-td-btn" title="View"><i class="fas fa-eye"></i></a>' +
        '<a href="' + c.update_url + '" class="dash-td-btn" title="Edit"><i class="fas fa-edit"></i></a>' +
        '<a href="' + c.delete_url + '" class="dash-td-btn" title="Delete" style="color:var(--dash-red)"><i class="fas fa-trash"></i></a>' +
        '</td></tr>';
    });
    tableBody.innerHTML = html;
    updateBulkBar();
  }

  function updatePagination(count) {
    var pi = document.querySelector('.pagination-info');
    if (pi) pi.style.display = 'none';
    var pl = document.querySelector('.pagination-links');
    if (pl) pl.style.display = 'none';
  }

  function getSelectedIds() {
    var ids = [];
    document.querySelectorAll('input[name="company_id"]:checked').forEach(function(cb) {
      ids.push(cb.value);
    });
    return ids;
  }

  function updateBulkBar() {
    var ids = getSelectedIds();
    if (!bulkBar) return;
    if (ids.length) {
      bulkBar.style.display = 'flex';
      if (selectedCount) selectedCount.textContent = ids.length + ' selected';
    } else {
      bulkBar.style.display = 'none';
    }
  }

  if (selectAll) {
    selectAll.addEventListener('change', function() {
      document.querySelectorAll('input[name="company_id"]').forEach(function(cb) {
        cb.checked = selectAll.checked;
      });
      updateBulkBar();
    });
  }

  document.addEventListener('change', function(e) {
    if (e.target && e.target.name === 'company_id') updateBulkBar();
  });

  if (bulkClearBtn) {
    bulkClearBtn.addEventListener('click', function() {
      document.querySelectorAll('input[name="company_id"]').forEach(function(cb) { cb.checked = false; });
      if (selectAll) selectAll.checked = false;
      updateBulkBar();
    });
  }

  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', function() {
      var ids = getSelectedIds();
      if (!ids.length) return;
      if (!confirm('Delete ' + ids.length + ' company(ies)? This cannot be undone.')) return;
      var formData = new FormData();
      ids.forEach(function(id) { formData.append('ids', id); });
      fetch('/companies/bulk-delete/', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success) {
          fetchCompanies();
          updateBulkBar();
        }
      });
    });
  }

  if (bulkUpdateBtn) {
    bulkUpdateBtn.addEventListener('click', function() {
      var ids = getSelectedIds();
      if (!ids.length) return;
      var status = bulkStatus ? bulkStatus.value : '';
      if (!status) { alert('Please select a status to apply.'); return; }
      var formData = new FormData();
      ids.forEach(function(id) { formData.append('ids', id); });
      formData.append('status', status);
      fetch('/companies/bulk-update/', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success) fetchCompanies();
      });
    });
  }

  if (bulkExportBtn) {
    bulkExportBtn.addEventListener('click', function() {
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

  if (searchInput) searchInput.addEventListener('input', debouncedFetch);
  if (filterIndustry) filterIndustry.addEventListener('change', fetchCompanies);
  if (filterStatus) filterStatus.addEventListener('change', fetchCompanies);
  if (filterCountry) filterCountry.addEventListener('change', fetchCompanies);
  if (sortSelect) sortSelect.addEventListener('change', fetchCompanies);

})();
