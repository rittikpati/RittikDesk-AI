(function () {
  'use strict';

  // Toggle workflow active/inactive
  document.querySelectorAll('.toggle-workflow').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var pk = this.dataset.pk;
      var icon = this.querySelector('i');
      fetch('/workflows/' + pk + '/toggle/', {
        method: 'POST',
        headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
      })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j.status === 'ok') {
            if (j.is_active) {
              icon.className = 'fas fa-pause';
              btn.closest('tr').querySelector('.wf-status').textContent = 'Active';
              btn.closest('tr').querySelector('.wf-status').className = 'wf-status wf-status--active';
            } else {
              icon.className = 'fas fa-play';
              btn.closest('tr').querySelector('.wf-status').textContent = 'Inactive';
              btn.closest('tr').querySelector('.wf-status').className = 'wf-status wf-status--inactive';
            }
          }
        })
        .catch(function () {});
    });
  });

  // Workflow search (redirect on enter)
  var searchInput = document.getElementById('workflowSearch');
  var triggerFilter = document.getElementById('triggerFilter');
  if (searchInput) {
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var params = new URLSearchParams();
        var val = this.value.trim();
        if (val) params.set('search', val);
        if (triggerFilter && triggerFilter.value) params.set('trigger', triggerFilter.value);
        window.location.href = '?' + params.toString();
      }
    });
  }
  if (triggerFilter) {
    triggerFilter.addEventListener('change', function () {
      var params = new URLSearchParams();
      if (searchInput && searchInput.value.trim()) params.set('search', searchInput.value.trim());
      if (this.value) params.set('trigger', this.value);
      window.location.href = '?' + params.toString();
    });
  }

  // Search clear button
  var searchClear = document.getElementById('searchClear');
  if (searchClear && searchInput) {
    searchClear.addEventListener('click', function () {
      searchInput.value = '';
      window.location.href = '?';
    });
  }
})();
