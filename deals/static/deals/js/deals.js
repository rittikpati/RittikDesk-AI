(function() {
  'use strict';

  var searchInput = document.getElementById('dealSearch');
  var searchClear = document.getElementById('searchClear');
  var searchSpinner = document.getElementById('searchSpinner');
  var stageFilter = document.getElementById('stageFilter');
  var priorityFilter = document.getElementById('priorityFilter');
  var sourceFilter = document.getElementById('sourceFilter');
  var sortSelect = document.getElementById('sortSelect');
  var dealsResults = document.getElementById('dealsResults');
  var dealsCard = document.getElementById('dealsCard');
  var searchNoResults = document.getElementById('searchNoResults');
  var searchNoResultsMsg = document.getElementById('searchNoResultsMsg');
  var dealCount = document.getElementById('dealCount');
  var selectAll = document.getElementById('selectAll');
  var bulkBar = document.getElementById('bulkBar');
  var bulkCount = document.getElementById('bulkCount');
  var bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
  var bulkExportBtn = document.getElementById('bulkExportBtn');
  var bulkUpdateBtn = document.getElementById('bulkUpdateBtn');
  var bulkStageSelect = document.getElementById('bulkStageSelect');
  var bulkPrioritySelect = document.getElementById('bulkPrioritySelect');
  var bulkClearBtn = document.getElementById('bulkClearBtn');
  var bulkDeleteConfirm = document.getElementById('bulkDeleteConfirm');
  var bulkDeleteModal = document.getElementById('bulkDeleteModal');
  var clearFiltersBtn = document.getElementById('clearFiltersBtn');

  var debounceTimer = null;

  function buildUrl() {
    var params = new URLSearchParams();
    if (searchInput) { var s = searchInput.value.trim(); if (s) params.set('search', s); }
    if (stageFilter) { var st = stageFilter.value; if (st) params.set('stage', st); }
    if (priorityFilter) { var p = priorityFilter.value; if (p) params.set('priority', p); }
    if (sourceFilter) { var s2 = sourceFilter.value; if (s2) params.set('source', s2); }
    if (sortSelect) { var so = sortSelect.value; if (so) params.set('sort', so); }
    return window.location.pathname.replace('/list', '').replace(/\/+$/, '') + '/search/?' + params.toString();
  }

  function loadResults() {
    if (!dealsResults) return;
    if (searchSpinner) searchSpinner.style.display = 'inline-block';
    fetch(buildUrl())
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (searchSpinner) searchSpinner.style.display = 'none';
        renderResults(data);
      })
      .catch(function() {
        if (searchSpinner) searchSpinner.style.display = 'none';
      });
  }

  function renderResults(data) {
    if (!dealsResults) return;
    var html = '';
    var deals = data.deals || [];

    if (deals.length === 0) {
      dealsResults.innerHTML = '';
      if (dealsCard) { dealsCard.querySelector('.dash-table-wrap').style.display = 'none'; }
      var pag = document.getElementById('dealsPagination');
      if (pag) pag.style.display = 'none';
      var pi = document.querySelector('.pagination-info');
      if (pi) pi.style.display = 'none';
      if (data.search || data.stage || data.priority || data.source) {
        if (searchNoResults) { searchNoResults.style.display = 'block'; }
        if (searchNoResultsMsg) {
          searchNoResultsMsg.textContent = 'No deals match your ' +
            (data.search ? 'search "' + data.search + '"' : 'filter criteria') +
            '. Try adjusting your filters.';
        }
      } else {
        if (searchNoResults) searchNoResults.style.display = 'none';
      }
      if (dealCount) dealCount.textContent = '(0)';
      return;
    }

    if (searchNoResults) searchNoResults.style.display = 'none';
    if (dealsCard) dealsCard.querySelector('.dash-table-wrap').style.display = '';
    var pag = document.getElementById('dealsPagination');
    if (pag) pag.style.display = 'none';
    var pi = document.querySelector('.pagination-info');
    if (pi) pi.style.display = 'none';

    deals.forEach(function(d) {
      html += '<tr>' +
        '<td class="deal-checkbox"><input type="checkbox" name="deal_id" value="' + d.id + '"></td>' +
        '<td><div class="dash-td-name"><span class="deal-avatar">' + d.deal_name.substring(0, 2).toUpperCase() + '</span>' +
        '<div><div class="deal-name">' + escapeHtml(d.deal_name) + '</div>' +
        (d.deal_owner ? '<div class="deal-owner">' + escapeHtml(d.deal_owner) + '</div>' : '') +
        '</div></div></td>' +
        '<td>' + (d.company ? escapeHtml(d.company) : '—') + '</td>' +
        '<td>' + (d.value ? d.currency + ' ' + parseFloat(d.value).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '—') + '</td>' +
        '<td><span class="deal-badge deal-badge--' + slugify(d.stage) + '">' + escapeHtml(d.stage) + '</span></td>' +
        '<td><span class="deal-prob">' + d.probability + '%</span></td>' +
        '<td><span class="deal-priority deal-priority--' + d.priority.toLowerCase() + '">' + d.priority + '</span></td>' +
        '<td style="font-size:0.75rem;color:var(--dash-text-sec)">' + (d.expected_close_date ? d.expected_close_date : '—') + '</td>' +
        '<td>' +
        '<a href="' + d.detail_url + '" class="dash-td-btn" title="View"><i class="fas fa-eye"></i></a>' +
        '<a href="' + d.update_url + '" class="dash-td-btn" title="Edit"><i class="fas fa-edit"></i></a>' +
        '<a href="' + d.delete_url + '" class="dash-td-btn" title="Delete" style="color:var(--dash-red)"><i class="fas fa-trash"></i></a>' +
        '</td></tr>';
    });

    dealsResults.innerHTML = html;
    if (dealCount) dealCount.textContent = '(' + data.count + ')';
    if (selectAll) selectAll.checked = false;
    attachCheckboxListeners();
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function slugify(str) {
    return str.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  }

  function attachCheckboxListeners() {
    if (selectAll) {
      selectAll.addEventListener('change', function() {
        var checkboxes = document.querySelectorAll('input[name="deal_id"]');
        checkboxes.forEach(function(cb) { cb.checked = selectAll.checked; });
        updateBulkBar();
      });
    }
    document.querySelectorAll('input[name="deal_id"]').forEach(function(cb) {
      cb.addEventListener('change', updateBulkBar);
    });
  }

  function updateBulkBar() {
    if (!bulkBar) return;
    var checked = document.querySelectorAll('input[name="deal_id"]:checked');
    if (checked.length > 0) {
      bulkBar.style.display = 'block';
      bulkCount.textContent = checked.length + ' selected';
    } else {
      bulkBar.style.display = 'none';
    }
  }

  function getSelectedIds() {
    var ids = [];
    document.querySelectorAll('input[name="deal_id"]:checked').forEach(function(cb) {
      ids.push(cb.value);
    });
    return ids;
  }

  // ── Event Listeners ──

  if (searchInput) {
    searchInput.addEventListener('input', function() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(loadResults, 300);
    });
  }
  if (searchClear) {
    searchClear.addEventListener('click', function() {
      if (searchInput) searchInput.value = '';
      loadResults();
      searchInput.focus();
    });
  }
  if (stageFilter) stageFilter.addEventListener('change', loadResults);
  if (priorityFilter) priorityFilter.addEventListener('change', loadResults);
  if (sourceFilter) sourceFilter.addEventListener('change', loadResults);
  if (sortSelect) sortSelect.addEventListener('change', loadResults);
  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', function() {
      if (searchInput) searchInput.value = '';
      if (stageFilter) stageFilter.value = '';
      if (priorityFilter) priorityFilter.value = '';
      if (sourceFilter) sourceFilter.value = '';
      if (sortSelect) sortSelect.value = 'newest';
      loadResults();
    });
  }

  // ── Bulk actions ──
  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', function() {
      var ids = getSelectedIds();
      if (ids.length === 0) return;
      document.getElementById('bulkDeleteCount').textContent = ids.length;
      var modal = new bootstrap.Modal(bulkDeleteModal);
      modal.show();
    });
  }
  if (bulkDeleteConfirm) {
    bulkDeleteConfirm.addEventListener('click', function() {
      var ids = getSelectedIds();
      if (ids.length === 0) return;
      var formData = new FormData();
      ids.forEach(function(id) { formData.append('ids', id); });
      formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

      fetch(window.location.pathname.replace(/\/+$/, '') + '/bulk-delete/', {
        method: 'POST', body: formData,
      })
      .then(function(r) { return r.json(); })
      .then(function() {
        location.reload();
      });
    });
  }
  if (bulkExportBtn) {
    bulkExportBtn.addEventListener('click', function() {
      var ids = getSelectedIds();
      var url = window.location.pathname.replace(/\/+$/, '') + '/export/csv/';
      if (ids.length > 0) url += '?ids=' + ids.join(',');
      window.location.href = url;
    });
  }
  if (bulkUpdateBtn) {
    bulkUpdateBtn.addEventListener('click', function() {
      var ids = getSelectedIds();
      if (ids.length === 0) return;
      var stage = bulkStageSelect ? bulkStageSelect.value : '';
      var priority = bulkPrioritySelect ? bulkPrioritySelect.value : '';
      if (!stage && !priority) return;
      var formData = new FormData();
      ids.forEach(function(id) { formData.append('ids', id); });
      if (stage) formData.append('stage', stage);
      if (priority) formData.append('priority', priority);
      formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

      fetch(window.location.pathname.replace(/\/+$/, '') + '/bulk-update/', {
        method: 'POST', body: formData,
      })
      .then(function(r) { return r.json(); })
      .then(function() {
        location.reload();
      });
    });
  }
  if (bulkClearBtn) {
    bulkClearBtn.addEventListener('click', function() {
      document.querySelectorAll('input[name="deal_id"]').forEach(function(cb) { cb.checked = false; });
      if (selectAll) selectAll.checked = false;
      updateBulkBar();
    });
  }

  // ── Init ──
  attachCheckboxListeners();
})();
