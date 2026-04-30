(function () {
  var btn = document.getElementById('sso-btn');
  if (!btn) return;

  btn.addEventListener('click', function () {
    if (btn.dataset.loading === '1') return;
    btn.disabled = true;
    btn.dataset.loading = '1';
    var label = btn.querySelector('span');
    if (label) label.textContent = 'Přihlašuji…';
  });
})();
