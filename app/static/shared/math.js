/*
 * math.js — محرك المعادلات الرياضية العربية (من اليمين إلى اليسار)
 *
 * المدخل: صيغة خطية شبيهة بـ LaTeX تنشئها أزرار المحرر، مثل:
 *   \frac{3}{4}   \sqrt{20}   \sqrt[3]{27}   س^{2}   س_{1}   (س+1)   30\%
 * المخرج: صندوق مُخطَّط بدقة (عرض، ارتفاع فوق خط القاعدة، عمق تحته) وعناصر رسم أولية
 *   تُرسم إما SVG (للمعاينة وPDF) أو Canvas → PNG (لملف Word) بالقياسات نفسها تمامًا.
 *
 * قواعد التدوين العربي المطبقة:
 *  - ترتيب العناصر من اليمين إلى اليسار.
 *  - الأعداد متعددة الخانات تبقى بترتيبها الصحيح (١٢٣).
 *  - الأس والدليل السفلي على يسار الأساس.
 *  - علامة الجذر معكوسة: تبدأ من اليمين ويمتد خطها العلوي إلى اليسار فوق ما تحت الجذر.
 *  - دليل الجذر النوني في الزاوية اليمنى العليا.
 *  - الرموز ذات الاتجاه (< > ≤ ≥ والأقواس) تُعكس كما في الكتابة العربية.
 */
(function (global) {
  'use strict';
  const QText = global.QText;

  // ---------------------------------------------------------------- المحلل
  const SYMBOLS = {
    times: '×', div: '÷', cdot: '⋅', pm: '±', mp: '∓', le: '≤', leq: '≤', ge: '≥', geq: '≥',
    ne: '≠', neq: '≠', approx: '≈', equiv: '≡', infty: '∞', pi: 'π', degree: '°', circ: '°',
    angle: '∠', triangle: '△', perp: '⊥', parallel: '∥', therefore: '∴', because: '∵',
    sim: '∼', cong: '≅', in: '∈', notin: '∉', cup: '∪', cap: '∩', subset: '⊂', supset: '⊃',
    to: '→', rightarrow: '→', leftarrow: '←', Rightarrow: '⇒', Leftarrow: '⇐', Leftrightarrow: '⇔',
    alpha: 'α', beta: 'β', theta: 'θ', lambda: 'λ', mu: 'μ', sigma: 'σ', Delta: 'Δ', Sigma: '∑',
    square: '□', ldots: '…', dots: '…', cdots: '⋯', prime: '′',
  };
  const REL = new Set(['=', '<', '>', '≤', '≥', '≠', '≈', '≡', '∼', '≅', '∈', '∉', '⊂', '⊃', '→', '←', '⇒', '⇐', '⇔', '∥', '⊥']);
  const BIN = new Set(['+', '-', '−', '×', '÷', '⋅', '±', '∓', '∪', '∩', '*', '/']);
  const PUNCT = new Set([',', '،', ';', '؛', ':']);
  const MIRROR = { '<': '>', '>': '<', '≤': '≥', '≥': '≤', '(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{', '⊂': '⊃', '⊃': '⊂', '∈': '∋', '←': '→', '→': '←', '⇒': '⇐', '⇐': '⇒', '∴': '∴' };
  const OPEN = { '(': ')', '[': ']', '{': '}', '|': '|' };

  function isDigit(c) { return /[0-9٠-٩۰-۹]/.test(c); }
  function isArabicLetter(c) { return /[ء-يٮ-ۓۺ-ۿـ]/.test(c); }
  function isArabicMark(c) { return /[ً-ٰٟ]/.test(c); }
  function isLatin(c) { return /[A-Za-z]/.test(c); }

  class ParseError extends Error {}

  function parse(src) {
    let i = 0;
    const s = String(src || '');
    function peek() { return s[i]; }
    function eof() { return i >= s.length; }
    function skipWs() { while (!eof() && /\s/.test(s[i])) i++; }
    function readCommand() {
      // بعد "\"
      i++;
      if (eof()) return '\\';
      if (!isLatin(s[i])) { return s[i++]; } // \% \{ \, \; ...
      let name = '';
      while (!eof() && isLatin(s[i])) name += s[i++];
      return name;
    }
    function readGroupRaw() {
      // يقرأ {...} ويعيد المحتوى الخام (لـ \text)
      skipWs();
      if (s[i] !== '{') throw new ParseError('توقعت {');
      i++;
      let depth = 1, out = '';
      while (!eof()) {
        const c = s[i++];
        if (c === '{') depth++;
        else if (c === '}') { depth--; if (depth === 0) return out; }
        out += c;
      }
      throw new ParseError('قوس { غير مغلق');
    }
    function readArg() {
      skipWs();
      if (s[i] === '{') { i++; const r = parseRow('}'); return r; }
      // وسيط من رمز واحد
      const a = parseAtom();
      if (!a) throw new ParseError('وسيط مفقود');
      return { type: 'row', children: [a] };
    }
    function parseAtom() {
      skipWs();
      if (eof()) return null;
      const c = s[i];
      if (c === '{') { i++; return parseRow('}'); }
      if (c === '\\') {
        const cmd = readCommand();
        switch (cmd) {
          case 'frac': case 'dfrac': case 'tfrac': {
            const num = readArg(); const den = readArg();
            return { type: 'frac', num, den, big: cmd === 'dfrac' };
          }
          case 'sqrt': {
            skipWs();
            let index = null;
            if (s[i] === '[') { i++; index = parseRow(']'); }
            const body = readArg();
            return { type: 'sqrt', body, index };
          }
          case 'text': case 'mathrm': case 'textrm': return { type: 'text', text: readGroupRaw() };
          case 'overline': return { type: 'over', kind: 'line', body: readArg() };
          case 'overarc': case 'wideparen': case 'arc': case 'overparen': return { type: 'over', kind: 'arc', body: readArg() };
          case 'overrightarrow': case 'vec': return { type: 'over', kind: 'arrow', body: readArg() };
          case 'left': {
            skipWs(); let open = s[i++]; if (open === '\\') { open = readCommand(); if (open === 'lbrace' || open === '{') open = '{'; }
            const body = parseRow('\\right');
            skipWs(); let close = s[i++]; if (close === '\\') { close = readCommand(); if (close === 'rbrace' || close === '}') close = '}'; }
            return { type: 'fence', open: open === '.' ? '' : open, close: close === '.' ? '' : close, body, forced: true };
          }
          case '%': return { type: 'op', text: '%', kind: 'ord', percent: true };
          case '{': return { type: 'op', text: '{', kind: 'open' };
          case '}': return { type: 'op', text: '}', kind: 'close' };
          case ',': return { type: 'space', w: 0.17 };
          case ';': return { type: 'space', w: 0.28 };
          case ':': return { type: 'space', w: 0.22 };
          case '!': return { type: 'space', w: -0.1 };
          case ' ': return { type: 'space', w: 0.25 };
          case 'quad': return { type: 'space', w: 1 };
          case 'qquad': return { type: 'space', w: 2 };
          case '\\': return { type: 'space', w: 0.5 };
          default: {
            if (SYMBOLS[cmd] != null) {
              const t = SYMBOLS[cmd];
              return { type: 'op', text: t, kind: REL.has(t) ? 'rel' : BIN.has(t) ? 'bin' : 'ord' };
            }
            // أمر غير معروف: يُعرض كنص كما هو
            return { type: 'ident', text: '\\' + cmd };
          }
        }
      }
      if (isDigit(c)) {
        let t = '';
        while (!eof()) {
          const d = s[i];
          if (isDigit(d)) { t += d; i++; continue; }
          if ((d === '.' || d === ',' || d === '٫' || d === '٬') && i + 1 < s.length && isDigit(s[i + 1]) && t) { t += d; i++; continue; }
          break;
        }
        return { type: 'num', text: t };
      }
      if (isArabicLetter(c)) {
        let t = '';
        while (!eof() && (isArabicLetter(s[i]) || isArabicMark(s[i]))) t += s[i++];
        return { type: 'ident', text: t, arabic: true };
      }
      if (isLatin(c)) {
        let t = '';
        while (!eof() && isLatin(s[i])) t += s[i++];
        return { type: 'ident', text: t };
      }
      i++;
      if (c === '%' || c === '٪' || c === '⁒') return { type: 'op', text: '%', kind: 'ord', percent: true };
      if (c === '*') return { type: 'op', text: '×', kind: 'bin' };
      if (c === '-' || c === '−') return { type: 'op', text: '−', kind: 'bin' };
      if (c === '(' || c === '[') return { type: 'op', text: c, kind: 'open' };
      if (c === ')' || c === ']') return { type: 'op', text: c, kind: 'close' };
      if (c === '|') return { type: 'op', text: c, kind: 'bar' };
      if (c === '^' || c === '_') { i--; return { type: 'space', w: 0 }; }
      if (c === '}') throw new ParseError('قوس } زائد');
      if (REL.has(c)) return { type: 'op', text: c, kind: 'rel' };
      if (BIN.has(c)) return { type: 'op', text: c, kind: 'bin' };
      if (PUNCT.has(c)) return { type: 'op', text: c, kind: 'punct' };
      return { type: 'ident', text: c };
    }
    function parseRow(until) {
      const children = [];
      for (;;) {
        skipWs();
        if (eof()) {
          if (until && until !== '\\right') throw new ParseError('قوس غير مغلق');
          if (until === '\\right') throw new ParseError('\\left بلا \\right');
          break;
        }
        if (until === '}' && s[i] === '}') { i++; break; }
        if (until === ']' && s[i] === ']') { i++; break; }
        if (until === '\\right' && s.startsWith('\\right', i)) { i += 6; break; }
        const hadSpace = i > 0 && /\s/.test(s[i - 1]);
        let atom = parseAtom();
        if (!atom) break;
        if (hadSpace && children.length && isOrdinary(children[children.length - 1]) && isOrdinary(atom)) {
          children.push({ type: 'space', w: 0.26, word: true });
        }
        // لواحق ^ و _
        for (;;) {
          skipWs();
          if (s[i] === '^' || s[i] === '_') {
            const which = s[i]; i++;
            const arg = readArg();
            if (atom.type !== 'scripts') atom = { type: 'scripts', base: atom, sup: null, sub: null };
            if (which === '^') atom.sup = arg; else atom.sub = arg;
          } else break;
        }
        children.push(atom);
      }
      return groupFences({ type: 'row', children });
    }
    const row = parseRow(null);
    return row;
  }

  function isOrdinary(n) {
    if (!n) return false;
    if (n.type === 'op') return n.kind === 'ord' || n.kind === 'close';
    if (n.type === 'space') return false;
    return true;
  }

  // يجمع الأقواس المتطابقة في عقد "fence" لتمديدها عند الحاجة
  function groupFences(row) {
    const out = [];
    const stack = [];
    for (const ch of row.children) {
      if (ch.type === 'op' && ch.kind === 'open') {
        stack.push({ open: ch.text, start: out.length });
        out.push(ch);
      } else if (ch.type === 'op' && ch.kind === 'close' && stack.length) {
        const top = stack.pop();
        const inner = out.splice(top.start);
        inner.shift();
        out.push({ type: 'fence', open: top.open, close: ch.text, body: { type: 'row', children: inner } });
      } else out.push(ch);
    }
    row.children = out;
    return row;
  }

  // ---------------------------------------------------------------- القياس
  const measureCache = new Map();
  let measureCtx = null;
  function ctx2d() {
    if (!measureCtx) {
      const c = (typeof OffscreenCanvas !== 'undefined') ? new OffscreenCanvas(10, 10) : document.createElement('canvas');
      measureCtx = c.getContext('2d');
    }
    return measureCtx;
  }
  function fontString(size, bold, family) {
    return (bold ? '700 ' : '400 ') + size.toFixed(3) + 'px ' + family;
  }
  function measureText(text, size, bold, family) {
    const key = family + '|' + size + '|' + (bold ? 1 : 0) + '|' + text;
    let m = measureCache.get(key);
    if (m) return m;
    const c = ctx2d();
    c.font = fontString(size, bold, family);
    c.direction = 'ltr';
    const mt = c.measureText(text);
    m = {
      w: mt.width,
      a: Math.max(0, mt.actualBoundingBoxAscent),
      d: Math.max(0, mt.actualBoundingBoxDescent),
      l: mt.actualBoundingBoxLeft, r: mt.actualBoundingBoxRight,
    };
    measureCache.set(key, m);
    return m;
  }
  function clearCache() { measureCache.clear(); }

  // ---------------------------------------------------------------- الصناديق
  function box(w, a, d, items) { return { w, a, d, items: items || [] }; }
  function place(target, b, dx, dy) {
    for (const it of b.items) target.items.push(shiftItem(it, dx, dy));
  }
  function shiftItem(it, dx, dy) {
    switch (it.k) {
      case 't': return Object.assign({}, it, { x: it.x + dx, y: it.y + dy });
      case 'r': return Object.assign({}, it, { x: it.x + dx, y: it.y + dy });
      case 'p': return Object.assign({}, it, { cmds: it.cmds.map((c) => shiftCmd(c, dx, dy)) });
      default: return it;
    }
  }
  function shiftCmd(c, dx, dy) {
    const out = [c[0]];
    for (let j = 1; j < c.length; j += 2) { out.push(c[j] + dx, c[j + 1] + dy); }
    return out;
  }

  /**
   * layout(ast, opts) → box
   * opts: { size (px), family, digits, percent, decimal, color, bold }
   */
  function layout(ast, opts) {
    const base = opts.size;
    const fam = opts.family;
    const bold = !!opts.bold;
    const disp = (t) => QText.display(t, { digits: opts.digits, percent: opts.percent, decimal: opts.decimal });
    const axisCache = {};
    function axis(sz) {
      if (axisCache[sz] == null) {
        const m = measureText('+', sz, false, fam);
        axisCache[sz] = (m.a > 0 && m.a < sz) ? (m.a - m.d) / 2 : sz * 0.28;
      }
      return axisCache[sz];
    }
    function rule(sz) { return Math.max(0.9, sz * 0.055); }

    function textBox(text, sz, isBold, cls) {
      const m = measureText(text, sz, isBold, fam);
      return box(m.w, m.a, m.d, [{ k: 't', x: 0, y: 0, s: text, size: sz, bold: isBold, cls: cls || '' }]);
    }

    function lay(node, sz, ctx) {
      switch (node.type) {
        case 'row': return layRow(node, sz);
        case 'num': return textBox(disp(node.text), sz, bold);
        case 'ident': return textBox(disp(node.text), sz, bold);
        case 'text': return textBox(disp(node.text), sz, bold);
        case 'op': {
          let t = node.percent ? disp('%') : node.text;
          if (MIRROR[t]) t = MIRROR[t];
          return textBox(t, sz, bold);
        }
        case 'space': return box(node.w * sz, 0, 0);
        case 'frac': return layFrac(node, sz);
        case 'sqrt': return laySqrt(node, sz);
        case 'scripts': return layScripts(node, sz);
        case 'fence': return layFence(node, sz);
        case 'over': return layOver(node, sz);
        default: return box(0, 0, 0);
      }
    }

    function spacingBetween(prev, cur, prevIsOperandStart) {
      return 0;
    }

    function layRow(row, sz) {
      const kids = row.children;
      const parts = [];
      // تحديد الأحادي/الثنائي للعمليات
      for (let k = 0; k < kids.length; k++) {
        const n = kids[k];
        let kind = n.type === 'op' ? n.kind : (n.type === 'space' ? 'space' : 'ord');
        if (kind === 'bin') {
          const prev = parts.length ? parts[parts.length - 1].kind : null;
          if (prev === null || prev === 'bin' || prev === 'rel' || prev === 'open' || prev === 'punct') kind = 'unary';
        }
        parts.push({ node: n, kind, b: lay(n, sz) });
      }
      // نهاية الصف: عملية ثنائية في آخره تُعامل كأحادية (مثل: ٢ + ...)
      // المسافات
      const em = sz;
      const gaps = [];
      for (let k = 0; k < parts.length; k++) {
        const p = parts[k];
        let before = 0, after = 0;
        if (p.kind === 'bin') { before = after = 0.2 * em; }
        else if (p.kind === 'rel') { before = after = 0.26 * em; }
        else if (p.kind === 'punct') { before = 0; after = 0.18 * em; }
        if (k === 0) before = 0;
        if (k === parts.length - 1) after = 0;
        gaps.push([before, after]);
      }
      // تخطيط من اليمين إلى اليسار
      let total = 0;
      for (let k = 0; k < parts.length; k++) total += gaps[k][0] + parts[k].b.w + gaps[k][1];
      const out = box(total, 0, 0);
      let x = total;
      for (let k = 0; k < parts.length; k++) {
        const b = parts[k].b;
        x -= gaps[k][0];
        x -= b.w;
        place(out, b, x, 0);
        x -= gaps[k][1];
        out.a = Math.max(out.a, b.a);
        out.d = Math.max(out.d, b.d);
      }
      return out;
    }

    function layFrac(node, sz) {
      const s2 = node.big ? sz : sz * (opts.fracScale || 0.82);
      const nb = lay(node.num, s2);
      const db = lay(node.den, s2);
      const t = rule(sz);
      const pad = 0.1 * sz;
      const gap = 0.12 * sz;
      const w = Math.max(nb.w, db.w) + 2 * pad;
      const ax = axis(sz);
      const out = box(w, 0, 0);
      const barY = -ax;
      const numBase = barY - t / 2 - gap - nb.d;
      const denBase = barY + t / 2 + gap + db.a;
      place(out, nb, (w - nb.w) / 2, numBase);
      place(out, db, (w - db.w) / 2, denBase);
      out.items.push({ k: 'r', x: pad * 0.35, y: barY - t / 2, w: w - pad * 0.7, h: t });
      out.a = -(numBase - nb.a);
      out.d = denBase + db.d;
      // هامش جانبي صغير
      const side = 0.06 * sz;
      const wrapped = box(w + 2 * side, out.a, out.d);
      place(wrapped, out, side, 0);
      return wrapped;
    }

    function laySqrt(node, sz) {
      const B = lay(node.body, sz);
      const t = rule(sz);
      const clear = 0.11 * sz;
      const bodyA = Math.max(B.a, 0.62 * sz);
      const bodyD = Math.max(B.d, 0.12 * sz);
      const yTop = -(bodyA + clear + t / 2);
      const yBot = bodyD + 0.06 * sz;
      const H = yBot - yTop;
      const sw = Math.min(0.9 * sz, 0.42 * sz + 0.1 * H);
      const overhang = 0.06 * sz;
      const gapBS = 0.08 * sz;
      let indexBox = null, indexW = 0;
      if (node.index) {
        indexBox = lay(node.index, sz * 0.6);
        indexW = Math.max(0, indexBox.w - sw * 0.45);
      }
      const X0 = overhang + B.w + gapBS; // الطرف الأيسر لعلامة الجذر (أعلى الخط المائل)
      const W = X0 + sw + indexW + 0.04 * sz;
      const out = box(W, 0, 0);
      place(out, B, overhang, 0);
      // علامة الجذر المعكوسة (تبدأ من اليمين)
      const T0x = X0 + sw, T0y = yTop + H * 0.6;
      const T1x = X0 + sw * 0.84, T1y = yTop + H * 0.53;
      const Vbx = X0 + sw * 0.5, Vby = yBot;
      const Vtx = X0, Vty = yTop;
      out.items.push({ k: 'p', cmds: [['M', T0x, T0y], ['L', T1x, T1y]], sw: t * 0.95, cap: 'round' });
      out.items.push({ k: 'p', cmds: [['M', T1x, T1y], ['L', Vbx, Vby]], sw: t * 1.75, cap: 'round' });
      out.items.push({ k: 'p', cmds: [['M', Vbx, Vby], ['L', Vtx, Vty]], sw: t * 0.95, cap: 'round' });
      out.items.push({ k: 'r', x: 0, y: yTop - t / 2, w: Vtx + t * 0.3, h: t });
      out.a = Math.max(B.a, -(yTop - t / 2));
      out.d = Math.max(B.d, yBot + t * 0.6);
      if (indexBox) {
        const ix = X0 + sw * 0.5;
        const iy = T1y - 0.12 * sz - indexBox.d;
        place(out, indexBox, ix, iy);
        out.a = Math.max(out.a, -(iy - indexBox.a));
      }
      return out;
    }

    function layScripts(node, sz) {
      const B = lay(node.base, sz);
      const ss = sz * 0.68;
      const sup = node.sup ? lay(node.sup, ss) : null;
      const sub = node.sub ? lay(node.sub, ss) : null;
      const gap = 0.04 * sz;
      const sw = Math.max(sup ? sup.w : 0, sub ? sub.w : 0);
      const W = B.w + gap + sw;
      const out = box(W, B.a, B.d);
      place(out, B, W - B.w, 0); // الأساس يمينًا
      if (sup) {
        const isTall = node.base.type === 'frac' || node.base.type === 'fence' || node.base.type === 'sqrt';
        let u = Math.max(0.36 * sz, (isTall ? B.a - 0.3 * sz : 0.36 * sz), sup.d + 0.22 * sz);
        if (sub) u = Math.max(u, 0.42 * sz);
        place(out, sup, sw - sup.w, -u);
        out.a = Math.max(out.a, u + sup.a);
        out.d = Math.max(out.d, sup.d - u);
      }
      if (sub) {
        const v = Math.max(0.18 * sz, sub.a - 0.45 * sz);
        place(out, sub, sw - sub.w, v);
        out.d = Math.max(out.d, v + sub.d);
        out.a = Math.max(out.a, sub.a - v);
      }
      return out;
    }

    function parenGlyphBox(ch, sz) {
      const m = measureText('(', sz, bold, fam);
      return m;
    }

    function layFence(node, sz) {
      const I = lay(node.body, sz);
      const pm = parenGlyphBox('(', sz);
      const tall = node.forced ? (I.a > pm.a * 1.02 || I.d > pm.d * 1.3) : (I.a > pm.a * 1.02 || I.d > pm.d * 1.3);
      // في الكتابة من اليمين إلى اليسار: القوس الافتتاحي يمينًا بشكل معكوس
      const openCh = node.open ? (MIRROR[node.open] || node.open) : '';
      const closeCh = node.close ? (MIRROR[node.close] || node.close) : '';
      if (!tall) {
        const R = openCh ? textBox(openCh, sz, bold) : box(0, 0, 0);
        const L = closeCh ? textBox(closeCh, sz, bold) : box(0, 0, 0);
        const pad = 0.02 * sz;
        const W = L.w + pad + I.w + pad + R.w;
        const out = box(W, Math.max(I.a, R.a, L.a), Math.max(I.d, R.d, L.d));
        place(out, L, 0, 0);
        place(out, I, L.w + pad, 0);
        place(out, R, L.w + pad + I.w + pad, 0);
        return out;
      }
      const t = rule(sz);
      const top = -I.a - 0.08 * sz;
      const bot = I.d + 0.08 * sz;
      const H = bot - top;
      const pw = Math.min(0.5 * sz, 0.22 * sz + 0.06 * H);
      const pad = 0.05 * sz;
      const W = (closeCh ? pw + pad : 0) + I.w + (openCh ? pw + pad : 0);
      const out = box(W, -top + t, bot + t);
      const leftX = 0;
      if (closeCh) drawFence(out, closeCh, leftX, top, bot, pw, t, sz);
      place(out, I, (closeCh ? pw + pad : 0), 0);
      if (openCh) drawFence(out, openCh, W - pw, top, bot, pw, t, sz);
      return out;
    }

    function drawFence(out, ch, x, top, bot, pw, t, sz) {
      const mid = (top + bot) / 2;
      if (ch === '(' ) {
        // شكل "(": انتفاخ إلى اليسار
        out.items.push({ k: 'p', fill: true, cmds: [
          ['M', x + pw * 0.85, top], ['Q', x - pw * 0.25, mid, x + pw * 0.85, bot],
          ['Q', x + pw * 0.15, mid, x + pw * 0.85, top], ['Z'] ] });
      } else if (ch === ')') {
        out.items.push({ k: 'p', fill: true, cmds: [
          ['M', x + pw * 0.15, top], ['Q', x + pw * 1.25, mid, x + pw * 0.15, bot],
          ['Q', x + pw * 0.85, mid, x + pw * 0.15, top], ['Z'] ] });
      } else if (ch === '[') {
        out.items.push({ k: 'p', cmds: [['M', x + pw * 0.8, top], ['L', x + pw * 0.25, top], ['L', x + pw * 0.25, bot], ['L', x + pw * 0.8, bot]], sw: t, cap: 'butt', join: 'miter' });
      } else if (ch === ']') {
        out.items.push({ k: 'p', cmds: [['M', x + pw * 0.2, top], ['L', x + pw * 0.75, top], ['L', x + pw * 0.75, bot], ['L', x + pw * 0.2, bot]], sw: t, cap: 'butt', join: 'miter' });
      } else if (ch === '|') {
        out.items.push({ k: 'r', x: x + pw * 0.5 - t / 2, y: top, w: t, h: bot - top });
      } else if (ch === '{' || ch === '}') {
        const dir = ch === '{' ? 1 : -1;
        const cx = x + pw * 0.5;
        out.items.push({ k: 'p', cmds: [
          ['M', cx + dir * pw * 0.35, top], ['Q', cx, top, cx, top + (mid - top) * 0.3], ['L', cx, mid - (mid - top) * 0.25],
          ['Q', cx, mid, cx - dir * pw * 0.35, mid], ['Q', cx, mid, cx, mid + (bot - mid) * 0.25], ['L', cx, bot - (bot - mid) * 0.3],
          ['Q', cx, bot, cx + dir * pw * 0.35, bot]], sw: t, cap: 'round', join: 'round' });
      }
    }

    function layOver(node, sz) {
      const B = lay(node.body, sz);
      const t = rule(sz);
      const clear = 0.1 * sz;
      const bodyA = Math.max(B.a, 0.55 * sz);
      const out = box(B.w, B.a, B.d);
      place(out, B, 0, 0);
      if (node.kind === 'line') {
        const y = -(bodyA + clear) - t;
        out.items.push({ k: 'r', x: 0.02 * sz, y, w: B.w - 0.04 * sz, h: t });
        out.a = -y;
      } else if (node.kind === 'arc') {
        const h = 0.2 * sz + 0.03 * B.w;
        const y0 = -(bodyA + clear);
        out.items.push({ k: 'p', cmds: [['M', 0.03 * sz, y0], ['Q', B.w / 2, y0 - 2 * h, B.w - 0.03 * sz, y0]], sw: t, cap: 'round' });
        out.a = -(y0 - h) + t;
      } else if (node.kind === 'arrow') {
        // في الكتابة العربية: السهم يتجه إلى اليسار
        const y = -(bodyA + clear) - 1.5 * t;
        const ah = 0.14 * sz;
        out.items.push({ k: 'p', cmds: [['M', B.w, y], ['L', 0, y]], sw: t, cap: 'round' });
        out.items.push({ k: 'p', cmds: [['M', ah, y - ah * 0.7], ['L', 0, y], ['L', ah, y + ah * 0.7]], sw: t, cap: 'round', join: 'round' });
        out.a = -y + ah;
      }
      return out;
    }

    const result = lay(ast, base);
    return result;
  }

  // ---------------------------------------------------------------- الرسم
  function pad(sz) { return Math.max(1, sz * 0.06); }

  function fmt(n) { return (Math.round(n * 1000) / 1000).toString(); }

  function cmdsToPath(cmds) {
    return cmds.map((c) => c[0] + (c.length > 1 ? ' ' + c.slice(1).map(fmt).join(' ') : '')).join(' ');
  }

  /** يعيد SVG كنص؛ الأبعاد بالبكسل (96 نقطة/بوصة) */
  function toSVG(b, opts) {
    const p = pad(opts.size);
    const W = Math.ceil((b.w + 2 * p) * 100) / 100;
    const H = Math.ceil((b.a + b.d + 2 * p) * 100) / 100;
    const ox = p, oy = p + b.a;
    const color = opts.color || '#000';
    let out = '';
    for (const it of b.items) {
      if (it.k === 't') {
        out += `<text x="${fmt(it.x + ox)}" y="${fmt(it.y + oy)}" font-size="${fmt(it.size)}" font-weight="${it.bold ? 700 : 400}" style="direction:ltr" text-anchor="start">${QText.escapeText(it.s)}</text>`;
      } else if (it.k === 'r') {
        out += `<rect x="${fmt(it.x + ox)}" y="${fmt(it.y + oy)}" width="${fmt(it.w)}" height="${fmt(it.h)}"/>`;
      } else if (it.k === 'p') {
        const d = cmdsToPath(it.cmds.map((c) => shiftCmd(c, ox, oy)));
        if (it.fill) out += `<path d="${d}" stroke="none"/>`;
        else out += `<path d="${d}" fill="none" stroke="${color}" stroke-width="${fmt(it.sw)}" stroke-linecap="${it.cap || 'round'}" stroke-linejoin="${it.join || 'round'}"/>`;
      }
    }
    const valign = -(b.d + p);
    return {
      svg: `<svg xmlns="http://www.w3.org/2000/svg" class="qmath" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="vertical-align:${fmt(valign)}px;direction:ltr;unicode-bidi:isolate;display:inline-block" fill="${color}" font-family='${opts.family.replace(/'/g, '"')}' overflow="visible">${out}</svg>`,
      width: W, height: H, descent: b.d + p, ascent: b.a + p,
    };
  }

  /** يرسم الصندوق على Canvas بدقة عالية ويعيد PNG (data URL) بالأبعاد نفسها */
  function toPNG(b, opts, scale) {
    scale = scale || 6;
    const p = pad(opts.size);
    const W = Math.ceil((b.w + 2 * p) * 100) / 100;
    const H = Math.ceil((b.a + b.d + 2 * p) * 100) / 100;
    const cv = document.createElement('canvas');
    cv.width = Math.ceil(W * scale);
    cv.height = Math.ceil(H * scale);
    const c = cv.getContext('2d');
    c.scale(scale, scale);
    const ox = p, oy = p + b.a;
    const color = opts.color || '#000';
    c.fillStyle = color; c.strokeStyle = color;
    c.textBaseline = 'alphabetic';
    c.textAlign = 'left';
    c.direction = 'ltr';
    for (const it of b.items) {
      if (it.k === 't') {
        c.font = fontString(it.size, it.bold, opts.family);
        c.fillText(it.s, it.x + ox, it.y + oy);
      } else if (it.k === 'r') {
        c.fillRect(it.x + ox, it.y + oy, it.w, it.h);
      } else if (it.k === 'p') {
        c.beginPath();
        for (const cmd of it.cmds) {
          const q = shiftCmd(cmd, ox, oy);
          if (q[0] === 'M') c.moveTo(q[1], q[2]);
          else if (q[0] === 'L') c.lineTo(q[1], q[2]);
          else if (q[0] === 'Q') c.quadraticCurveTo(q[1], q[2], q[3], q[4]);
          else if (q[0] === 'C') c.bezierCurveTo(q[1], q[2], q[3], q[4], q[5], q[6]);
          else if (q[0] === 'Z') c.closePath();
        }
        if (it.fill) c.fill();
        else { c.lineWidth = it.sw; c.lineCap = it.cap || 'round'; c.lineJoin = it.join || 'round'; c.stroke(); }
      }
    }
    return { dataUrl: cv.toDataURL('image/png'), width: W, height: H, descent: b.d + p, ascent: b.a + p, pxWidth: cv.width, pxHeight: cv.height };
  }

  /**
   * الواجهة الرئيسية: render(latex, opts) → {svg, width, height, descent, error}
   */
  function render(latex, opts) {
    try {
      const ast = parse(latex);
      const b = layout(ast, opts);
      const r = toSVG(b, opts);
      r.box = b;
      return r;
    } catch (e) {
      const msg = (e && e.message) || String(e);
      const safe = QText.escapeText(String(latex || ''));
      return {
        svg: `<span class="qmath-error" title="${QText.escapeText(msg)}">${safe}</span>`,
        error: msg, width: 0, height: 0, descent: 0,
      };
    }
  }

  function validate(latex) {
    try { parse(latex); return null; } catch (e) { return e.message || String(e); }
  }

  const api = { parse, layout, render, toSVG, toPNG, validate, clearCache, measureText };
  global.QMath = api;
})(typeof window !== 'undefined' ? window : globalThis);
