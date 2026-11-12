/* isitai demo — page logic. Talks to the engine only through window.isitaiEngine. */
(function () {
  'use strict';

  var engine = window.isitaiEngine;
  var VERDICTS = ['ai-proven', 'capture-proven', 'ai-signal', 'inconsistent', 'no-signal'];
  var STRENGTH_RANK = { proof: 3, strong: 2, weak: 1 };

  // ---- text -------------------------------------------------------------
  var all = window.ISITAI_STRINGS;
  var wanted = (new URLSearchParams(location.search).get('lang') || navigator.language || 'en')
    .slice(0, 2).toLowerCase();
  var lang = all[wanted] ? wanted : 'en';

  function t(key, vars) {
    var s = (all[lang] && all[lang][key]) || all.en[key] || key;
    return s.replace(/\{(\w+)\}/g, function (_, k) { return vars && k in vars ? vars[k] : ''; });
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  // Makes invisible characters visible: a zero-width match would otherwise look empty.
  function visible(s) {
    return String(s).replace(/[\u0000-\u001f\u007f­​-‏⁠﻿]/g, function (c) {
      return '⟨U+' + c.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0') + '⟩';
    });
  }

  function size(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  // ---- static text ------------------------------------------------------
  document.documentElement.lang = lang;
  document.title = t('page.title');
  document.querySelectorAll('[data-i18n]').forEach(function (n) {
    n.textContent = t(n.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function (n) {
    n.placeholder = t(n.getAttribute('data-i18n-placeholder'));
  });

  // ---- rendering --------------------------------------------------------
  var body = document.getElementById('result-body');
  var legend = document.getElementById('legend-list');

  function renderLegend(current) {
    legend.textContent = '';
    VERDICTS.forEach(function (v) {
      var li = el('li', 'legend-item v-' + v);
      if (v === current) li.setAttribute('aria-current', 'true');
      var head = el('p', 'legend-head');
      head.appendChild(el('span', 'swatch'));
      head.appendChild(el('code', null, v));
      if (v === current) head.appendChild(el('span', 'here', t('legend.current')));
      li.appendChild(head);
      li.appendChild(el('p', 'legend-label', t('verdict.' + v + '.label')));
      li.appendChild(el('p', 'legend-explain', t('verdict.' + v + '.explain')));
      legend.appendChild(li);
    });
  }

  function fact(dl, term, value, mono) {
    if (value == null || value === '') return;
    dl.appendChild(el('dt', null, term));
    dl.appendChild(el('dd', mono ? 'mono' : null, value));
  }

  function evidenceItem(e) {
    var li = el('li', 'ev s-' + e.strength);
    var head = el('p', 'ev-head');
    var badge = el('span', 'strength');
    var pips = el('span', 'pips');
    pips.setAttribute('aria-hidden', 'true');
    for (var i = 1; i <= 3; i++) pips.appendChild(el('i', i <= (STRENGTH_RANK[e.strength] || 0) ? 'on' : null));
    badge.appendChild(pips);
    badge.appendChild(el('span', null, t('strength.' + e.strength)));
    head.appendChild(badge);
    head.appendChild(el('span', 'ev-tags', t('origin.' + e.origin) + ' · ' + t('layer.' + e.layer)));
    li.appendChild(head);
    li.appendChild(el('p', 'ev-detail', e.detail));
    li.appendChild(el('p', 'ev-hint small', t('strength.' + e.strength + '.hint')));

    var dl = el('dl', 'facts');
    fact(dl, 'id', e.id, true);
    if (e.location && 'field' in e.location) fact(dl, t('evidence.where.field'), e.location.field, true);
    if (e.location && 'text' in e.location) fact(dl, t('evidence.where.span'), visible(e.location.text), true);
    li.appendChild(dl);
    return li;
  }

  // `history` and `history_summary` are being added to the core (seen in progress:
  // entries { action, digital_source_type?, software? }). Unknown shapes fall back to JSON.
  function historyBlock(report) {
    var wrapNode = el('div', 'block');
    wrapNode.appendChild(el('h3', null, t('history.title')));
    wrapNode.appendChild(el('p', 'small', t('history.note')));
    if (report.history_summary) {
      var key = 'history.summary.' + report.history_summary;
      var text = t(key);
      wrapNode.appendChild(el('p', 'history-summary', text === key ? String(report.history_summary) : text));
    }
    var ol = el('ol', 'plain');
    (Array.isArray(report.history) ? report.history : []).forEach(function (h) {
      var li = el('li');
      if (h && typeof h === 'object' && h.action) {
        li.appendChild(el('code', null, h.action));
        var rest = [h.digital_source_type, h.software].filter(Boolean).join(' · ');
        if (rest) li.appendChild(el('span', 'small', ' ' + rest));
      } else {
        li.textContent = typeof h === 'string' ? h : JSON.stringify(h);
      }
      ol.appendChild(li);
    });
    wrapNode.appendChild(ol);
    return wrapNode;
  }

  function render(report, note) {
    var known = VERDICTS.indexOf(report.verdict) !== -1;
    body.textContent = '';

    if (note) body.appendChild(el('p', 'note', note));

    var card = el('div', 'verdict v-' + (known ? report.verdict : 'unknown'));
    card.appendChild(el('p', 'verdict-kicker', t('result.verdict')));
    var name = el('p', 'verdict-name');
    name.appendChild(el('code', null, String(report.verdict)));
    card.appendChild(name);
    card.appendChild(el('p', 'verdict-label',
      known ? t('verdict.' + report.verdict + '.label') : t('result.unknownVerdict')));
    if (known) card.appendChild(el('p', 'verdict-explain', t('verdict.' + report.verdict + '.explain')));
    var dl = el('dl', 'facts');
    fact(dl, t('result.media'), report.mime || report.media, true); // `mime` if the field is renamed
    fact(dl, t('result.generator'), report.generator);
    if (report.version) fact(dl, t('result.version'), report.version.lib + ' / ' + report.version.rules, true);
    card.appendChild(dl);
    body.appendChild(card);

    var evidence = (report.evidence || []).slice().sort(function (a, b) {
      return (STRENGTH_RANK[b.strength] || 0) - (STRENGTH_RANK[a.strength] || 0);
    });
    var evBlock = el('div', 'block');
    var evTitle = el('h3', null, t('evidence.title') + ' ');
    if (evidence.length) evTitle.appendChild(el('span', 'small', '(' + evidence.length + ', ' + t('evidence.order') + ')'));
    evBlock.appendChild(evTitle);
    if (evidence.length) {
      var ol = el('ol', 'ev-list');
      evidence.forEach(function (e) { ol.appendChild(evidenceItem(e)); });
      evBlock.appendChild(ol);
    } else {
      evBlock.appendChild(el('p', 'muted', t('evidence.none')));
    }
    body.appendChild(evBlock);

    var warnings = report.warnings || [];
    var wBlock = el('div', 'block');
    wBlock.appendChild(el('h3', null, t('warnings.title')));
    if (warnings.length) {
      var ul = el('ul', 'warn-list');
      warnings.forEach(function (w) {
        // Plain strings today; tolerate { code, message } if warnings become structured.
        ul.appendChild(el('li', null, typeof w === 'string' ? w : (w.message || w.code || JSON.stringify(w))));
      });
      wBlock.appendChild(ul);
    } else {
      wBlock.appendChild(el('p', 'muted', t('warnings.none')));
    }
    body.appendChild(wBlock);

    if ((report.history && report.history.length) || report.history_summary) body.appendChild(historyBlock(report));

    var raw = el('details', 'raw');
    raw.appendChild(el('summary', null, t('raw.title')));
    var pre = el('pre', null, JSON.stringify(report, null, 2));
    pre.tabIndex = 0;
    raw.appendChild(pre);
    body.appendChild(raw);

    renderLegend(known ? report.verdict : null);
  }

  function renderError(err) {
    body.textContent = '';
    // Without an engine there is nothing to show: never a made-up report.
    body.appendChild(el('p', 'note note-error',
      engineDown || t('result.error', { message: (err && err.message) || String(err) })));
    renderLegend(null);
  }

  // ---- engine load failure ----------------------------------------------
  var engineDown = null; // message shown instead of a report when the engine did not load
  engine.ready.catch(function (err) {
    engineDown = location.protocol === 'file:'
      ? t('engine.down.file')
      : t('engine.down', { message: (err && err.message) || String(err) });
    document.getElementById('engine-down-body').textContent = engineDown;
    document.getElementById('engine-down').hidden = false;
  });

  // ---- running a check --------------------------------------------------
  async function run(input, name, focus) {
    try {
      render(await engine.check(input), t('result.input', { name: name }));
    } catch (err) {
      renderError(err);
    }
    if (focus) document.getElementById('result').focus();
  }

  function runFile(file) {
    if (file) run(file, file.name + ', ' + size(file.size), true);
  }

  var fileInput = document.getElementById('file');
  fileInput.addEventListener('change', function () {
    runFile(fileInput.files[0]);
    fileInput.value = '';
  });

  var drop = document.getElementById('drop');
  ['dragenter', 'dragover'].forEach(function (type) {
    drop.addEventListener(type, function (e) { e.preventDefault(); drop.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (type) {
    drop.addEventListener(type, function (e) { e.preventDefault(); drop.classList.remove('over'); });
  });
  drop.addEventListener('drop', function (e) { runFile(e.dataTransfer.files[0]); });
  // A file dropped beside the zone must not navigate away from the page.
  ['dragover', 'drop'].forEach(function (type) {
    window.addEventListener(type, function (e) { e.preventDefault(); });
  });

  var textArea = document.getElementById('text');
  var textMsg = document.getElementById('text-msg');
  document.getElementById('text-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var value = textArea.value;
    if (!value.trim()) {
      textMsg.textContent = t('input.text.empty');
      textArea.focus();
      return;
    }
    textMsg.textContent = '';
    run(value, t('result.input.text', { n: Array.from(value).length }), true);
  });

  renderLegend(null);
})();
