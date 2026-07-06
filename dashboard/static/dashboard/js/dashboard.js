document.addEventListener('DOMContentLoaded', function () {

  // ---- 1. GREETING ----
  var g = document.getElementById('dashGreeting');
  if (g) {
    var h = new Date().getHours();
    g.textContent = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  }

  // ---- 2. DATE ----
  var d = document.getElementById('dashDate');
  if (d) {
    d.textContent = new Date().toLocaleDateString('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
    });
  }

  // ---- 3. SIDEBAR TOGGLE ----
  var toggle = document.getElementById('dashToggle');
  var sidebar = document.getElementById('dashSidebar');
  var main = document.getElementById('dashMain');

  if (toggle && sidebar && main) {
    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('hidden');
      main.classList.toggle('collapsed');
      localStorage.setItem('dash_sidebar', sidebar.classList.contains('hidden') ? '1' : '0');
    });
    if (localStorage.getItem('dash_sidebar') === '1') {
      sidebar.classList.add('hidden');
      main.classList.add('collapsed');
    }
  }

  // ---- 4. SEARCH (Ctrl+K) ----
  var search = document.getElementById('dashSearch');
  if (search) {
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        search.focus();
      }
    });
  }

  // ---- 5. USER DROPDOWN ----
  var userBtn = document.getElementById('dashUserBtn');
  var dropdown = document.getElementById('dashDropdown');
  if (userBtn && dropdown) {
    userBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      dropdown.classList.toggle('open');
    });
    document.addEventListener('click', function () {
      dropdown.classList.remove('open');
    });
    dropdown.addEventListener('click', function (e) {
      e.stopPropagation();
    });
  }

  // ---- 6. LOGOUT ----
  var ll = document.getElementById('dashLogoutLink');
  var lf = document.getElementById('dashLogoutForm');
  if (ll && lf) {
    ll.addEventListener('click', function (e) {
      e.preventDefault();
      lf.submit();
    });
  }
  var pl = document.getElementById('dashProfileLogoutLink');
  var pf = document.getElementById('dashProfileLogoutForm');
  if (pl && pf) {
    pl.addEventListener('click', function (e) {
      e.preventDefault();
      pf.submit();
    });
  }

  // ---- 7. ANIMATED COUNTERS ----
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var target = Math.round(parseFloat(el.getAttribute('data-count')));
    if (isNaN(target) || target === 0) {
      el.textContent = target;
      return;
    }
    var duration = Math.min(1000, Math.max(300, target * 2));
    var startTime = null;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var current = Math.round(eased * target);
      el.textContent = current.toLocaleString();
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = target.toLocaleString();
      }
    }

    requestAnimationFrame(step);
  });

  // ---- 8. SPARKLINES ----
  function drawSpark(canvas) {
    var values = (canvas.dataset.values || '').split(',').map(Number);
    var color = canvas.dataset.color || '#6C63FF';
    if (values.length < 2) return;

    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.parentElement.getBoundingClientRect();
    var w = rect.width || 200;
    var h = rect.height || 32;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';

    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    var range = max - min || 1;

    var pts = values.map(function (v, i) {
      return {
        x: (i / (values.length - 1)) * w,
        y: h - ((v - min) / range) * h
      };
    });

    var grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, color + '30');
    grad.addColorStop(1, color + '00');
    ctx.beginPath();
    ctx.moveTo(pts[0].x, h);
    pts.forEach(function (p) { ctx.lineTo(p.x, p.y); });
    ctx.lineTo(pts[pts.length - 1].x, h);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    pts.forEach(function (p, i) {
      i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    var last = pts[pts.length - 1];
    ctx.beginPath();
    ctx.arc(last.x, last.y, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(last.x, last.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = color + '20';
    ctx.fill();
  }

  document.querySelectorAll('.dash-spark-canvas').forEach(drawSpark);

  var rt;
  window.addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(function () {
      document.querySelectorAll('.dash-spark-canvas').forEach(drawSpark);
    }, 200);
  });

  // ---- 9. CONTACTS CHART ----
  if (typeof Chart !== 'undefined') {
    var cc = document.getElementById('dashChartContacts');
    if (cc) {
      var gC = 'rgba(255,255,255,0.04)';
      var tC = 'rgba(235,235,245,0.35)';
      new Chart(cc, {
        type: 'line',
        data: {
          labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
          datasets: [{
            label: 'Contacts',
            data: [320, 380, 450, 520, 610, 720, 850, 950, 1050, 1150, 1220, 1284],
            borderColor: '#6C63FF',
            backgroundColor: 'rgba(108,99,255,0.06)',
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            hitRadius: 10,
            borderWidth: 2
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          resizeDelay: 0,
          animation: { duration: 500 },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: gC, drawBorder: false }, ticks: { color: tC, font: { size: 10 } }, maxTicksLimit: 7 },
            y: { grid: { color: gC, drawBorder: false }, ticks: { color: tC, font: { size: 10 } }, beginAtZero: true }
          },
          interaction: { intersect: false, mode: 'index' }
        }
      });
    }

    var cp = document.getElementById('dashChartCampaign');
    if (cp) {
      new Chart(cp, {
        type: 'doughnut',
        data: {
          labels: ['Email','Social','Direct','Referral'],
          datasets: [{
            data: [45, 25, 18, 12],
            backgroundColor: ['#6C63FF','#00D9A6','#FFB800','#00B4D8'],
            borderWidth: 0,
            hoverOffset: 4
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          resizeDelay: 0,
          animation: { duration: 500 },
          cutout: '72%',
          plugins: { legend: { display: false } }
        }
      });
    }

    var ac = document.getElementById('dashChartAi');
    if (ac) {
      var gA = 'rgba(255,255,255,0.04)';
      var tA = 'rgba(235,235,245,0.35)';
      new Chart(ac, {
        type: 'bar',
        data: {
          labels: ['W1','W2','W3','W4','W5','W6','W7','W8'],
          datasets: [{
            label: 'AI Conversations',
            data: [120, 190, 280, 370, 480, 610, 750, 920],
            backgroundColor: 'rgba(0,217,166,0.18)',
            borderColor: '#00D9A6',
            borderWidth: 1.5,
            borderRadius: 4,
            hoverBackgroundColor: 'rgba(0,217,166,0.28)'
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          resizeDelay: 0,
          animation: { duration: 500 },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: tA, font: { size: 9 } } },
            y: { grid: { color: gA, drawBorder: false }, ticks: { color: tA, font: { size: 9 } }, beginAtZero: true }
          }
        }
      });
    }
  }

  // ---- 10. CHART TABS ----
  document.querySelectorAll('.dash-chart-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var p = this.closest('.dash-chart-head');
      if (p) {
        p.querySelectorAll('.dash-chart-tab').forEach(function (t) { t.classList.remove('active'); });
      }
      this.classList.add('active');
    });
  });

  // ---- 11. COMING SOON TOAST ----
  window.dashComingSoon = function (feature) {
    var old = document.querySelector('.dash-toast');
    if (old) old.remove();
    var t = document.createElement('div');
    t.className = 'dash-toast show';
    t.innerHTML = '<i class="fas fa-sparkles"></i> <span><strong>' + feature + '</strong> coming soon</span>';
    document.body.appendChild(t);
    setTimeout(function () {
      t.classList.remove('show');
      setTimeout(function () { t.remove(); }, 300);
    }, 2800);
  };

  console.log('%c RittikDesk AI %c Dashboard ',
    'background:#6C63FF;color:#fff;padding:4px 7px;border-radius:3px 0 0 3px;font-weight:700',
    'background:rgba(255,255,255,0.05);color:rgba(235,235,245,0.5);padding:4px 7px;border-radius:0 3px 3px 0'
  );

});
