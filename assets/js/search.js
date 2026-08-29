// The Chronicle — 前端全文检索
// 数据源：构建期生成的 search-index.json（标题/副标题/作者/栏目/正文）
(function () {
  var indexData = [];
  var input = document.getElementById('search-input');
  var resultsEl = document.getElementById('search-results');
  var statusEl = document.getElementById('search-status');

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function highlight(text, terms) {
    var out = escapeHtml(text);
    terms.forEach(function (t) {
      if (!t) return;
      out = out.replace(new RegExp('(' + escapeRegExp(escapeHtml(t)) + ')', 'gi'), '<mark>$1</mark>');
    });
    return out;
  }

  function countOccurrences(haystack, needle) {
    if (!needle) return 0;
    var count = 0, idx = 0;
    var lower = haystack.toLowerCase();
    var n = needle.toLowerCase();
    while ((idx = lower.indexOf(n, idx)) !== -1) {
      count++;
      idx += n.length;
      if (count >= 5) break;
    }
    return count;
  }

  function makeSnippet(item, terms) {
    var content = item.content || '';
    var pos = -1, term = '';
    for (var i = 0; i < terms.length; i++) {
      var p = content.toLowerCase().indexOf(terms[i].toLowerCase());
      if (p !== -1 && (pos === -1 || p < pos)) { pos = p; term = terms[i]; }
    }
    if (pos === -1) return item.subtitle || '';
    var start = Math.max(0, pos - 50);
    var end = Math.min(content.length, pos + term.length + 90);
    return (start > 0 ? '…' : '') + content.slice(start, end) + (end < content.length ? '…' : '');
  }

  function search(query) {
    var terms = query.trim().split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    var scored = [];
    indexData.forEach(function (item) {
      var score = 0;
      var matchedAll = true;
      terms.forEach(function (t) {
        var s = 0;
        s += countOccurrences(item.title, t) * 10;
        s += countOccurrences(item.subtitle, t) * 6;
        s += countOccurrences(item.kicker, t) * 4;
        s += countOccurrences(item.author, t) * 8;
        s += countOccurrences(item.section_title + ' ' + item.section_en, t) * 6;
        s += Math.min(countOccurrences(item.content, t), 5) * 2;
        if (s === 0) matchedAll = false;
        score += s;
      });
      if (matchedAll && score > 0) scored.push({ item: item, score: score });
    });
    scored.sort(function (a, b) { return b.score - a.score; });
    return scored;
  }

  function render(query) {
    var terms = query.trim().split(/\s+/).filter(Boolean);
    if (!terms.length) {
      statusEl.textContent = '输入关键词开始检索 —— 支持标题、作者、栏目与正文全文';
      resultsEl.innerHTML = '';
      return;
    }
    var hits = search(query);
    if (!hits.length) {
      statusEl.textContent = '未找到与「' + query + '」相关的文章';
      resultsEl.innerHTML = '<div class="search-empty">没有匹配的结果。试试更短的关键词，或按栏目浏览。</div>';
      return;
    }
    statusEl.textContent = '找到 ' + hits.length + ' 篇相关文章';
    resultsEl.innerHTML = hits.map(function (h) {
      var it = h.item;
      return '<a class="search-result" href="' + it.url + '">' +
        '<div class="r-top"><span class="r-sec" style="background:' + it.section_color + '">' +
        escapeHtml(it.section_title) + '</span><span class="r-vol">' + it.vol + ' · ' + it.date +
        ' · ' + escapeHtml(it.author) + '</span></div>' +
        '<div class="r-title">' + highlight(it.title, terms) + '</div>' +
        '<div class="r-snippet">' + highlight(makeSnippet(it, terms), terms) + '</div>' +
        '</a>';
    }).join('');
  }

  function syncUrl(q) {
    var url = q ? ('search.html?q=' + encodeURIComponent(q)) : 'search.html';
    history.replaceState(null, '', url);
  }

  fetch('search-index.json')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      indexData = data.articles || [];
      var q = new URLSearchParams(location.search).get('q') || '';
      input.value = q;
      render(q);
      input.focus();
    })
    .catch(function () {
      statusEl.textContent = '检索索引加载失败，请稍后重试。';
    });

  var timer = null;
  input.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      syncUrl(input.value);
      render(input.value);
    }, 160);
  });

  document.getElementById('search-form').addEventListener('submit', function (e) {
    e.preventDefault();
    syncUrl(input.value);
    render(input.value);
  });
})();
