// ── Sidebar toggle ──────────────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const main    = document.getElementById('main-content');
  const overlay = document.getElementById('overlay');

  if (window.innerWidth <= 768) {
    sidebar.classList.toggle('mobile-open');
    overlay.classList.toggle('active');
  } else {
    sidebar.classList.toggle('collapsed');
    main.classList.toggle('expanded');
  }
}

// ── Current date in topbar ──────────────────────────────────────────────────
(function() {
  const el = document.getElementById('current-date');
  if (!el) return;
  const now = new Date();
  const opts = { weekday:'long', day:'2-digit', month:'long', year:'numeric' };
  el.textContent = now.toLocaleDateString('pt-BR', opts);
})();

// ── Auto-dismiss toasts ─────────────────────────────────────────────────────
document.querySelectorAll('.toast').forEach(toast => {
  const dismiss = () => {
    toast.classList.add('toast-out');
    setTimeout(() => toast.remove(), 300);
  };
  setTimeout(dismiss, 5000);
});

// ── Money input mask for all .money-input fields ────────────────────────────
document.querySelectorAll('.money-input').forEach(input => {
  input.addEventListener('input', function(e) {
    let v = e.target.value.replace(/\D/g, '');
    if (!v) { e.target.value = ''; return; }
    v = (parseInt(v) / 100).toFixed(2);
    e.target.value = v.replace('.', ',');
  });
  input.addEventListener('blur', function(e) {
    let v = e.target.value.replace(/\D/g,'');
    if (!v) return;
    v = (parseInt(v)/100).toFixed(2);
    // Format with thousands separator
    const parts = v.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    e.target.value = parts.join(',');
  });
});

// ── Close mobile sidebar on resize ─────────────────────────────────────────
window.addEventListener('resize', function() {
  if (window.innerWidth > 768) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    sidebar?.classList.remove('mobile-open');
    overlay?.classList.remove('active');
  }
});
