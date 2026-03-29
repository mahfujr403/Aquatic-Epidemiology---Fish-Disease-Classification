

// Password toggle
const pwToggle = document.getElementById('pwToggle');
const pwInput = document.getElementById('password');
const eyeIcon = document.getElementById('eyeIcon');
if (pwToggle) {
    pwToggle.addEventListener('click', () => {
        const show = pwInput.type === 'password';
        pwInput.type = show ? 'text' : 'password';
        eyeIcon.innerHTML = show
            ? '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
            : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    });
}

// Ripple effect
const submitBtn = document.getElementById('submitBtn');
if (submitBtn) {
    submitBtn.addEventListener('click', function (e) {
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        const rect = this.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        ripple.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - rect.left - size / 2}px;top:${e.clientY - rect.top - size / 2}px`;
        this.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
    });
}

// Form submit state
const adminForm = document.getElementById('adminForm');
if (adminForm) {
    adminForm.addEventListener('submit', function () {
        if (submitBtn) {
            submitBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
            Verifying…`;
            submitBtn.disabled = true;
            submitBtn.style.opacity = '.75';
        }
    });
}

// Flash modal
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('flashModal');
    if (!modal) return;
    modal.classList.add('open');
    const closeBtn = document.getElementById('modalCloseBtn');
    const backdrop = modal.querySelector('[data-action="close"]');
    [closeBtn, backdrop].forEach(el => {
        if (el) el.addEventListener('click', () => modal.remove());
    });
});
