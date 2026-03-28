

/* ── Hamburger ── */
const burger = document.getElementById('menuToggle');
const navMenu = document.getElementById('navLinks');
if (burger) {
    burger.addEventListener('click', () => {
        const open = navMenu.classList.toggle('active');
        burger.setAttribute('aria-expanded', open);
        burger.textContent = open ? '✕' : '☰';
    });
}

/* ── Confidence bar animation on load ── */
function animateBars() {
    document.querySelectorAll('.hist-conf-fill').forEach(el => {
        const w = parseFloat(el.dataset.width || 0);
        requestAnimationFrame(() => { el.style.width = w + '%'; });
    });
}
animateBars();

/* ── Card expand/collapse ── */
function toggleCard(id) {
    const card = document.getElementById('card-' + id);
    const body = document.getElementById('body-' + id);
    const wasOpen = card.classList.contains('expanded');

    // close all others
    document.querySelectorAll('.hist-card.expanded').forEach(c => {
        c.classList.remove('expanded');
    });

    if (!wasOpen) {
        card.classList.add('expanded');
        // animate breakdown bars when expanding
        setTimeout(() => {
            body.querySelectorAll('.breakdown-bar-fill').forEach(el => {
                el.style.width = (parseFloat(el.dataset.width) || 0) + '%';
            });
        }, 80);
    }
}

/* ── Feedback panel toggle ── */
function toggleFeedback(id) {
    const panel = document.getElementById('fp-' + id);
    const btn = document.getElementById('ftbtn-' + id);
    const open = panel.classList.toggle('open');
    btn.innerHTML = open
        ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg> Close Feedback`
        : `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg> Was this correct? Give Feedback`;
}

/* ── Toggle corrected label field ── */
function toggleLabel(id, val) {
    const lf = document.getElementById('lf-' + id);
    if (lf) lf.style.display = val === 'true' ? 'block' : 'none';
}

/* ── Search + Filter + Sort ── */
const searchInput = document.getElementById('searchInput');
const filterBtns = document.querySelectorAll('.filter-btn');
const sortSelect = document.getElementById('sortSelect');
const histList = document.getElementById('histList');
const noResults = document.getElementById('noResults');

let activeFilter = 'all';

function applyFilter() {
    if (!histList) return;
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const cards = Array.from(histList.querySelectorAll('.hist-card'));
    let visible = 0;

    cards.forEach(card => {
        const disease = card.dataset.disease.toLowerCase();
        const cls = card.dataset.class;
        const matchQ = !query || disease.includes(query);
        const matchF = activeFilter === 'all' || cls === activeFilter;
        const show = matchQ && matchF;
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    });

    if (noResults) noResults.classList.toggle('visible', visible === 0);
}

function applySort() {
    if (!histList || !sortSelect) return;
    const val = sortSelect.value;
    const cards = Array.from(histList.querySelectorAll('.hist-card'));
    cards.sort((a, b) => {
        if (val === 'newest') return new Date(b.dataset.date) - new Date(a.dataset.date);
        if (val === 'oldest') return new Date(a.dataset.date) - new Date(b.dataset.date);
        if (val === 'conf-high') return parseFloat(b.dataset.conf) - parseFloat(a.dataset.conf);
        if (val === 'conf-low') return parseFloat(a.dataset.conf) - parseFloat(b.dataset.conf);
        return 0;
    });
    cards.forEach(c => histList.appendChild(c));
}

if (searchInput) searchInput.addEventListener('input', applyFilter);

filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.filter;
        applyFilter();
    });
});

if (sortSelect) sortSelect.addEventListener('change', () => { applySort(); applyFilter(); });
