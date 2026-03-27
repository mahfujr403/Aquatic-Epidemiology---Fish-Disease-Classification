
  /* ── Password visibility toggles ── */
  function makeToggle(btnId, inputId, iconId) {
    document.getElementById(btnId).addEventListener('click', () => {
      const inp  = document.getElementById(inputId);
      const icon = document.getElementById(iconId);
      const show = inp.type === 'password';
      inp.type = show ? 'text' : 'password';
      icon.innerHTML = show
        ? '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
        : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    });
  }
  makeToggle('pwToggle1','password','eye1');
  makeToggle('pwToggle2','confirm_password','eye2');

  /* ── Password strength meter ── */
  const passwordInput = document.getElementById('password');
  const segs = ['s1','s2','s3','s4'].map(id => document.getElementById(id));
  const strengthLabel = document.getElementById('strengthLabel');
  const colors = ['#ff6b6b','#ffc107','#4fc3f7','#00c9a7'];
  const labels = ['Weak','Fair','Good','Strong'];

  function scorePassword(pw) {
    let score = 0;
    if (pw.length >= 8)  score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score++;
    return Math.min(score, 4);
  }

  passwordInput.addEventListener('input', () => {
    clearError(passwordInput);
    const pw = passwordInput.value;
    const score = pw.length === 0 ? 0 : scorePassword(pw);
    segs.forEach((s, i) => {
      s.style.background = i < score ? colors[score - 1] : 'rgba(255,255,255,.08)';
    });
    strengthLabel.textContent = pw.length === 0 ? '' : labels[score - 1] || '';
    strengthLabel.style.color = pw.length === 0 ? '' : colors[score - 1] || '';
    // re-validate confirm if already touched
    if (confirmInput.value) checkMatch();
  });

  /* ── Confirm password live match ── */
  const confirmInput = document.getElementById('confirm_password');
  const matchHint    = document.getElementById('matchHint');

  function checkMatch() {
    const match = confirmInput.value === passwordInput.value;
    if (!confirmInput.value) { matchHint.className = 'field-hint'; matchHint.textContent = ''; confirmInput.classList.remove('error'); return; }
    matchHint.classList.add('visible');
    matchHint.textContent = match ? '✓ Passwords match' : '⚠ Passwords do not match';
    matchHint.className   = 'field-hint visible ' + (match ? '' : 'err');
    confirmInput.classList.toggle('error', !match);
  }
  confirmInput.addEventListener('input', checkMatch);

  /* ── Validation helpers ── */
  function showError(inputEl, msg) {
    inputEl.classList.add('error');
    const hint = inputEl.closest('.field-group').querySelector('.field-hint');
    if (hint) { hint.textContent = msg; hint.className = 'field-hint visible err'; }
  }
  function clearError(inputEl) {
    inputEl.classList.remove('error');
    const hint = inputEl.closest('.field-group').querySelector('.field-hint');
    // Don't wipe the match hint — it manages itself
    if (hint && hint.id !== 'matchHint' && hint.id !== 'strengthLabel') {
      hint.textContent = ''; hint.className = 'field-hint';
    }
  }

  // Clear on input
  ['username','email'].forEach(id => {
    document.getElementById(id).addEventListener('input', function() { clearError(this); });
  });

  /* ── Terms error element ── */
  const termsHint = document.getElementById('termsHint');

  document.getElementById('terms').addEventListener('change', function() {
    if (this.checked) { termsHint.textContent = ''; termsHint.className = 'field-hint'; }
  });

  /* ── Ripple ── */
  document.getElementById('submitBtn').addEventListener('click', function(e) {
    const btn = this; const rect = btn.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    const size = Math.max(rect.width, rect.height);
    ripple.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX-rect.left-size/2}px;top:${e.clientY-rect.top-size/2}px`;
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
  });

  /* ── Submit validation ── */
  document.getElementById('registerForm').addEventListener('submit', function(e) {
    let valid = true;

    const username = document.getElementById('username');
    const email    = document.getElementById('email');
    const pass     = passwordInput;
    const conf     = confirmInput;
    const terms    = document.getElementById('terms');

    // Username
    if (!username.value.trim()) {
      showError(username, '⚠ Username is required.'); valid = false;
    } else if (username.value.trim().length < 3) {
      showError(username, '⚠ Username must be at least 3 characters.'); valid = false;
    } else if (!/^[a-zA-Z0-9_]+$/.test(username.value.trim())) {
      showError(username, '⚠ Only letters, numbers, and underscores allowed.'); valid = false;
    } else { clearError(username); }

    // Email
    if (!email.value.trim()) {
      showError(email, '⚠ Email address is required.'); valid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
      showError(email, '⚠ Please enter a valid email address.'); valid = false;
    } else { clearError(email); }

    // Password
    if (!pass.value) {
      showError(pass, '⚠ Password is required.'); valid = false;
    } else if (pass.value.length < 8) {
      showError(pass, '⚠ Password must be at least 8 characters.'); valid = false;
    } else { clearError(pass); }

    // Confirm password
    if (!conf.value) {
      showError(conf, '⚠ Please confirm your password.'); valid = false;
    } else if (conf.value !== pass.value) {
      showError(conf, '⚠ Passwords do not match.'); valid = false;
    } else { clearError(conf); }

    // Terms
    if (!terms.checked) {
      termsHint.textContent = '⚠ You must agree to the Terms of Service to continue.';
      termsHint.className = 'field-hint visible err';
      valid = false;
    }

    if (!valid) { e.preventDefault(); return; }

    const btn = document.getElementById('submitBtn');
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Creating account…';
    btn.disabled = true;
  });
</script>