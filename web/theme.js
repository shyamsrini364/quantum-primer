try { document.documentElement.dataset.theme = localStorage.getItem('qp-theme') || 'dark'; }
catch { document.documentElement.dataset.theme = 'dark'; }
