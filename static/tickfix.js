(function () {
  const STORAGE_KEY = 'tickfix-theme';

  function applyTheme(theme) {
    const body = document.body;
    if (!body) return;
    body.classList.remove('tickfix-theme-light', 'tickfix-theme-dark');
    const next = theme === 'light' ? 'tickfix-theme-light' : 'tickfix-theme-dark';
    body.classList.add(next);

    const toggles = document.querySelectorAll('[data-theme-toggle]');
    toggles.forEach((btn) => {
      const isLight = theme === 'light';
      btn.setAttribute('aria-pressed', isLight ? 'true' : 'false');
      btn.textContent = isLight ? 'Dark mode' : 'Light mode';
    });
  }

  function init() {
    let saved = null;
    try {
      saved = window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      saved = null;
    }

    if (saved !== 'light' && saved !== 'dark') {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      saved = prefersDark ? 'dark' : 'light';
    }

    applyTheme(saved);

    document.addEventListener('click', function (evt) {
      const btn = evt.target.closest('[data-theme-toggle]');
      if (!btn) return;
      const body = document.body;
      const current = body.classList.contains('tickfix-theme-light') ? 'light' : 'dark';
      const next = current === 'light' ? 'dark' : 'light';
      try {
        window.localStorage.setItem(STORAGE_KEY, next);
      } catch (e) {}
      applyTheme(next);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
