/* Sales Pipeline Analytics — UI interactions */
(function(){
  'use strict';

  /* ── Animate pipeline bars on load ── */
  setTimeout(function(){
    document.querySelectorAll('.pipeline-stage-bar').forEach(function(bar){
      var w = bar.style.width;
      bar.style.width = '0';
      setTimeout(function(){ bar.style.width = w; }, 100);
    });
  }, 200);

  /* ── Animate probability bars ── */
  setTimeout(function(){
    document.querySelectorAll('.prob-bar-fill').forEach(function(bar){
      var w = bar.style.width;
      bar.style.width = '0';
      setTimeout(function(){ bar.style.width = w; }, 300);
    });
  }, 300);

  /* ── Card entrance animation ── */
  document.querySelectorAll('.analytics-card').forEach(function(card, i){
    card.style.opacity = '0';
    card.style.transform = 'translateY(12px)';
    card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
    setTimeout(function(){
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, 80 + i * 60);
  });

})();
