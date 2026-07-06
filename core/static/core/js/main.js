// =============================================
// RittikDesk AI - Main JavaScript
// =============================================

document.addEventListener('DOMContentLoaded', function () {

  // ===========================================
  // Typing Animation
  // ===========================================

  const typingText = document.getElementById('typing-text');
  if (typingText) {
    const phrases = [
      'Smart Campaigns.',
      'Intelligent CRM.',
      'AI Insights.',
      'Automated Workflows.',
      'Real Analytics.'
    ];
    let phraseIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let currentText = '';

    function type() {
      const fullText = phrases[phraseIndex];

      if (isDeleting) {
        currentText = fullText.substring(0, charIndex - 1);
        charIndex--;
      } else {
        currentText = fullText.substring(0, charIndex + 1);
        charIndex++;
      }

      typingText.textContent = currentText;

      if (!isDeleting && charIndex === fullText.length) {
        isDeleting = true;
        setTimeout(type, 2000);
        return;
      }

      if (isDeleting && charIndex === 0) {
        isDeleting = false;
        phraseIndex = (phraseIndex + 1) % phrases.length;
        setTimeout(type, 500);
        return;
      }

      const speed = isDeleting ? 50 : 100;
      setTimeout(type, speed);
    }

    setTimeout(type, 1000);
  }

  // ===========================================
  // Navbar Scroll Effect
  // ===========================================

  const navbar = document.getElementById('mainNav');
  if (navbar) {
    window.addEventListener('scroll', function () {
      if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
      }
    });
  }

  // ===========================================
  // Smooth Scroll for Anchor Links
  // ===========================================

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ===========================================
  // Intersection Observer for Fade-In
  // ===========================================

  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, observerOptions);

  document.querySelectorAll('.feature-card, .pricing-card, .testimonial-card').forEach(el => {
    el.classList.add('fade-in');
    observer.observe(el);
  });

  // ===========================================
  // Auto-dismiss Alerts
  // ===========================================

  document.querySelectorAll('.alert-dismissible').forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });

});
