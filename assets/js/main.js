// The Chronicle — 全站通用脚本
(function () {
  // 滚动时导航栏阴影
  window.addEventListener('scroll', function () {
    var nav = document.querySelector('.nav-bar');
    if (!nav) return;
    nav.style.boxShadow = window.scrollY > 10 ? '0 2px 8px rgba(0,0,0,.08)' : 'none';
  });

  // "/" 快捷键跳转到搜索页
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) {
      e.preventDefault();
      var base = document.body.getAttribute('data-root') || '';
      window.location.href = base + 'search.html';
    }
  });
})();
