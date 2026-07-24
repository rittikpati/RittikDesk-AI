/* ── Activity Timeline JS ─────────────────────────────── */
(function () {
    'use strict';

    const BASE_URL = '/activities/json/';
    const MODULE_ICONS = {
        contacts: 'fa-address-book',
        companies: 'fa-building',
        leads: 'fa-tag',
        deals: 'fa-handshake',
        tasks: 'fa-check-circle',
        campaigns: 'fa-bullhorn',
        emails: 'fa-envelope',
        calendar: 'fa-calendar-alt',
        workflows: 'fa-cogs',
        ai: 'fa-robot',
        system: 'fa-cog',
    };

    let currentPage = 1;
    let isLoading = false;
    let hasNext = true;
    let debounceTimer = null;
    let lastDateString = '';

    const $timeline = document.getElementById('actTimeline');
    const $loading = document.getElementById('actLoading');
    const $empty = document.getElementById('actEmpty');
    const $loadMore = document.getElementById('actLoadMore');
    const $loadMoreBtn = document.getElementById('actLoadMoreBtn');
    const $total = document.getElementById('actTotal');
    const $search = document.getElementById('actSearch');
    const $searchClear = document.getElementById('actSearchClear');
    const $moduleFilter = document.getElementById('actModuleFilter');
    const $timeFilter = document.getElementById('actTimeFilter');
    const $filterClear = document.getElementById('actFilterClear');

    function buildUrl(page) {
        const params = new URLSearchParams();
        params.set('page', page);
        params.set('per_page', '20');
        const q = $search.value.trim();
        if (q) params.set('q', q);
        const mod = $moduleFilter.value;
        if (mod) params.set('module', mod);
        const time = $timeFilter.value;
        if (time) params.set('time', time);
        return BASE_URL + '?' + params.toString();
    }

    function showLoading() {
        $loading.style.display = 'flex';
        $empty.style.display = 'none';
    }

    function hideLoading() {
        $loading.style.display = 'none';
    }

    function showEmpty() {
        $empty.style.display = 'block';
        $loadMore.style.display = 'none';
    }

    function hideEmpty() {
        $empty.style.display = 'none';
    }

    function formatDate(isoString) {
        const d = new Date(isoString);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const itemDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

        if (itemDate.getTime() === today.getTime()) return 'Today';
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        if (itemDate.getTime() === yesterday.getTime()) return 'Yesterday';
        return d.toLocaleDateString('en-US', {
            weekday: 'long', month: 'short', day: 'numeric', year: 'numeric',
        });
    }

    function formatTime(isoString) {
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function createCard(a) {
        const card = document.createElement('div');
        card.className = 'act-card';
        card.style.setProperty('--act-dot-color', a.color);

        const icon = MODULE_ICONS[a.module] || a.icon || 'fa-info-circle';
        const detailLink = a.detail_url
            ? '<a href="' + escapeHtml(a.detail_url) + '" class="act-card-link"><i class="fas fa-arrow-right"></i> View details</a>'
            : '';
        const desc = a.description
            ? '<div class="act-card-desc">' + escapeHtml(a.description) + '</div>'
            : '';

        card.innerHTML =
            '<div class="act-card-inner">' +
                '<div class="act-card-icon" style="background:' + escapeHtml(a.color) + '">' +
                    '<i class="fas ' + escapeHtml(icon) + '"></i>' +
                '</div>' +
                '<div class="act-card-body">' +
                    '<div class="act-card-title">' + escapeHtml(a.title) + '</div>' +
                    '<div class="act-card-meta">' +
                        '<span class="act-card-module">' +
                            '<i class="fas ' + escapeHtml(MODULE_ICONS[a.module] || 'fa-folder') + '"></i> ' +
                            escapeHtml(a.module_label) +
                        '</span>' +
                        '<span>' + escapeHtml(a.time_ago) + '</span>' +
                        '<span>' + formatTime(a.timestamp) + '</span>' +
                    '</div>' +
                    desc +
                    detailLink +
                '</div>' +
            '</div>';

        return card;
    }

    function createSeparator(dateString) {
        const sep = document.createElement('div');
        sep.className = 'act-date-group';
        sep.textContent = dateString;
        return sep;
    }

    function appendActivities(activities, append) {
        if (!append) {
            // Remove existing cards and separators
            const existing = $timeline.querySelectorAll('.act-card, .act-date-group');
            existing.forEach(function (el) { el.remove(); });
            lastDateString = '';
        }

        activities.forEach(function (a) {
            const dateStr = formatDate(a.timestamp);
            if (dateStr !== lastDateString) {
                $timeline.appendChild(createSeparator(dateStr));
                lastDateString = dateStr;
            }
            $timeline.appendChild(createCard(a));
        });
    }

    function loadPage(page, append) {
        if (isLoading) return;
        isLoading = true;

        if (!append) {
            showLoading();
            $loadMore.style.display = 'none';
        }
        $loadMoreBtn.disabled = true;

        fetch(buildUrl(page))
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function (data) {
                hideLoading();
                isLoading = false;
                $loadMoreBtn.disabled = false;

                if (data.activities.length === 0 && !append) {
                    showEmpty();
                    $total.textContent = '0 activities';
                    return;
                }

                hideEmpty();
                appendActivities(data.activities, append);
                $total.textContent = data.total + ' activit' + (data.total === 1 ? 'y' : 'ies');

                hasNext = data.has_next;
                currentPage = data.page;
                $loadMore.style.display = hasNext ? 'block' : 'none';
            })
            .catch(function () {
                hideLoading();
                isLoading = false;
                $loadMoreBtn.disabled = false;
                if (!append) {
                    showEmpty();
                    $total.textContent = '';
                }
            });
    }

    function resetAndLoad() {
        currentPage = 1;
        lastDateString = '';
        loadPage(1, false);
    }

    function updateClearBtn() {
        const hasFilter = $moduleFilter.value || $timeFilter.value;
        $filterClear.style.display = hasFilter ? 'inline-flex' : 'none';
    }

    // ── Events ──

    $search.addEventListener('input', function () {
        $searchClear.style.display = $search.value ? 'block' : 'none';
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(resetAndLoad, 300);
    });

    $searchClear.addEventListener('click', function () {
        $search.value = '';
        $searchClear.style.display = 'none';
        resetAndLoad();
    });

    $moduleFilter.addEventListener('change', function () {
        updateClearBtn();
        resetAndLoad();
    });

    $timeFilter.addEventListener('change', function () {
        updateClearBtn();
        resetAndLoad();
    });

    $filterClear.addEventListener('click', function () {
        $moduleFilter.value = '';
        $timeFilter.value = '';
        updateClearBtn();
        resetAndLoad();
    });

    $loadMoreBtn.addEventListener('click', function () {
        loadPage(currentPage + 1, true);
    });

    // ── Init ──
    loadPage(1, false);
})();
