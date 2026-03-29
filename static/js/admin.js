/* admin.js — AquaDiag Admin Panel */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Flash modal auto-open ── */
  const modal = document.getElementById('flashModal');
  if (modal) {
    modal.classList.add('open');
    modal.querySelectorAll('[data-action="close"]').forEach(el =>
      el.addEventListener('click', () => modal.remove())
    );
    const closeBtn = document.getElementById('modalCloseBtn');
    if (closeBtn) closeBtn.addEventListener('click', () => modal.remove());
    // auto-dismiss after 4s
    setTimeout(() => { if (modal.parentNode) modal.remove(); }, 4000);
  }

  /* ── Client-side search ── */
  const searchInput = document.getElementById('fbSearch');
  const fbList      = document.getElementById('fbList');
  const noResults   = document.getElementById('noSearchResults');
  const resultsInfo = document.getElementById('resultsCount');

  function updateSearch() {
    if (!fbList || !searchInput) return;
    const q = searchInput.value.trim().toLowerCase();
    const cards = Array.from(fbList.querySelectorAll('.fb-card'));
    let visible = 0;
    cards.forEach(card => {
      const text = (card.dataset.search || '').toLowerCase();
      const show = !q || text.includes(q);
      card.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    if (noResults) noResults.classList.toggle('visible', visible === 0 && q.length > 0);
    if (resultsInfo) {
      resultsInfo.querySelector('span').textContent = visible;
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', updateSearch);
  }

  /* ── Ripple on action buttons ── */
  document.querySelectorAll('.btn-approve, .btn-reject').forEach(btn => {
    btn.addEventListener('click', function(e) {
      const ripple = document.createElement('span');
      ripple.style.cssText = `
        position:absolute; border-radius:50%; background:rgba(255,255,255,.2);
        transform:scale(0); animation:ripple .5s linear; pointer-events:none;
      `;
      const style = document.createElement('style');
      style.textContent = '@keyframes ripple{to{transform:scale(4);opacity:0}}';
      document.head.appendChild(style);
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      ripple.style.width  = size + 'px';
      ripple.style.height = size + 'px';
      ripple.style.left   = (e.clientX - rect.left - size/2) + 'px';
      ripple.style.top    = (e.clientY - rect.top  - size/2) + 'px';
      this.style.position = 'relative';
      this.style.overflow = 'hidden';
      this.appendChild(ripple);
      setTimeout(() => ripple.remove(), 500);
    });
  });

  /* ── Confirm reject ── */
  document.querySelectorAll('form.reject-form').forEach(form => {
    form.addEventListener('submit', e => {
      if (!confirm('Reject this feedback? This cannot be undone.')) {
        e.preventDefault();
      }
    });
  });

});