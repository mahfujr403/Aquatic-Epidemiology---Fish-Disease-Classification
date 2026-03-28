/* Prediction page JS
   - Controls mobile hamburger behavior
   - Upload preview and drag/drop
   - Result animations that read data-attributes (no template tags here)
*/

document.addEventListener('DOMContentLoaded', () => {
    // HAMBURGER (mobile) - prediction page follows index pattern
    const burger = document.getElementById('menuToggle');
    const navMenu = document.getElementById('navLinks');
    if (burger && navMenu) {
        const menuActiveClass = 'active';
        const toggleMenu = (ev) => {        
            if (ev && ev.cancelable) try { ev.preventDefault(); } catch (e) {}
            const open = burger.classList.toggle('open');
            navMenu.classList.toggle(menuActiveClass, open);
            // set aria-expanded attribute
            try { burger.setAttribute('aria-expanded', open ? 'true' : 'false'); } catch (e) {}
        };
        burger.addEventListener('click', toggleMenu);
        // close menu when a link is clicked
        navMenu.querySelectorAll?.('.nav-link')?.forEach(a =>
            a.addEventListener('click', () => {
                burger.classList.remove('open');
                navMenu.classList.remove(menuActiveClass);
                try { burger.setAttribute('aria-expanded', 'false'); } catch (e) {}
            })
        );
        // basic keyboard support
        burger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') toggleMenu(e);
        });
    }

    // reveal on scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.classList.add('visible');
                observer.unobserve(e.target);
            }
        });
    }, { threshold: 0.12 });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

    // Accordion helper
    window.toggleAcc = function (id) {
        if (window.innerWidth >= 960) return; // desktop: always open via CSS
        const el = document.getElementById(id);
        if (el) el.classList.toggle('open');
    };

    // Upload / drag-drop
    const dropZone = document.getElementById('dropZone');
    const imageInput = document.getElementById('imageInput');
    const previewWrap = document.getElementById('previewWrap');
    const previewImg = document.getElementById('previewImg');
    const previewFn = document.getElementById('previewFilename');
    const previewSz = document.getElementById('previewSize');
    const changeBtn = document.getElementById('changeImageBtn');
    const submitBtn = document.getElementById('submitBtn');

    function fmtSize(b) {
        if (b < 1024) return b + ' B';
        if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
        return (b / 1048576).toFixed(1) + ' MB';
    }

    function showPreview(file) {
        if (!previewImg) return;
        previewImg.src = URL.createObjectURL(file);
        if (previewFn) previewFn.textContent = file.name.length > 34 ? file.name.slice(0, 31) + '…' : file.name;
        if (previewSz) previewSz.textContent = fmtSize(file.size);
        if (dropZone) dropZone.style.display = 'none';
        if (previewWrap) previewWrap.classList.add('visible');
        if (submitBtn) submitBtn.disabled = false;
    }

    function resetToDropZone() {
        if (imageInput) imageInput.value = '';
        if (previewImg) previewImg.src = '#';
        if (previewWrap) previewWrap.classList.remove('visible');
        if (dropZone) dropZone.style.display = '';
        if (submitBtn) submitBtn.disabled = true;
    }

    if (imageInput) {
        imageInput.addEventListener('change', () => {
            if (imageInput.files[0]) showPreview(imageInput.files[0]);
        });
    }

    if (dropZone) {
        dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
        dropZone.addEventListener('drop', e => {
            e.preventDefault(); dropZone.classList.remove('drag-over');
            const f = e.dataTransfer.files[0];
            if (f && f.type.startsWith('image/')) {
                const dt = new DataTransfer(); dt.items.add(f);
                imageInput.files = dt.files;
                showPreview(f);
            }
        });
    }

    if (changeBtn) changeBtn.addEventListener('click', e => { e.stopPropagation(); resetToDropZone(); });

    // Form submit overlay
    const uploadForm = document.getElementById('uploadForm');
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (uploadForm) {
        uploadForm.addEventListener('submit', e => {
            if (!imageInput.files || !imageInput.files[0]) { e.preventDefault(); return; }
            if (loadingOverlay) loadingOverlay.classList.add('active');
            if (submitBtn) submitBtn.disabled = true;
        });
    }

    // Result animations (read target from data attribute to avoid template tags)
    const confBar = document.getElementById('confBar');
    const confPct = document.getElementById('confPct');
    if (confBar && confPct) {
        const targetPct = parseFloat(confBar.dataset.target || '0') || 0;
        setTimeout(() => {
            confBar.style.width = targetPct.toFixed(1) + '%';
            let cur = 0;
            (function step() {
                cur += 1.8;
                if (cur >= targetPct) { confPct.textContent = targetPct.toFixed(1) + '%'; return; }
                confPct.textContent = cur.toFixed(1) + '%';
                requestAnimationFrame(step);
            })();
        }, 320);
    }

    document.querySelectorAll('.breakdown-bar-fill').forEach(el => {
        const w = parseFloat(el.dataset.width || 0);
        setTimeout(() => { el.style.width = w.toFixed(1) + '%'; }, 420);
    });

    // Feedback panel toggles
    const feedbackToggle = document.getElementById('feedbackToggle');
    const feedbackPanel = document.getElementById('feedbackPanel');
    const feedbackCorrect = document.getElementById('feedbackCorrect');
    const labelField = document.getElementById('labelField');

    if (feedbackToggle) {
        feedbackToggle.addEventListener('click', () => {
            const open = feedbackPanel.classList.toggle('open');
            feedbackToggle.innerHTML = open
                ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg> Close Feedback`
                : `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg> Was this correct? Give Feedback`;
        });
    }
    if (feedbackCorrect) {
        feedbackCorrect.addEventListener('change', () => {
            if (labelField) labelField.style.display = feedbackCorrect.value === 'true' ? 'block' : 'none';
        });
    }

    // Auto-scroll to result if present
    if (document.querySelector('.result-section')) {
        setTimeout(() => {
            document.querySelector('.result-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 180);
    }
});
