/*
 * textutil.js — أدوات النصوص المشتركة بين الواجهة ومحرك التصدير
 * - تحويل الأرقام (هندية/لاتينية) وعلامة النسبة المئوية والفاصلة العشرية عند العرض فقط
 * - تحليل وتسلسل "النص الغني" المخزن: نص عادي + <b>…</b> + <m>LaTeX</m> + <br>
 * المحتوى المخزن لا يتغير أبدًا؛ التحويلات للعرض والتصدير فقط.
 */
(function (global) {
  'use strict';

  const HINDI = '٠١٢٣٤٥٦٧٨٩';
  const PERSIAN = '۰۱۲۳۴۵۶۷۸۹';

  function normalizeDigitsToWestern(s) {
    return s.replace(/[٠-٩]/g, (c) => String(HINDI.indexOf(c)))
            .replace(/[۰-۹]/g, (c) => String(PERSIAN.indexOf(c)));
  }

  /**
   * تحويل نص للعرض حسب الإعدادات.
   * opts: { digits: 'hindi'|'western', percent: '⁒'|'٪'|'%', decimal: 'arabic'|'keep' }
   */
  function display(s, opts) {
    if (s == null) return '';
    s = String(s);
    opts = opts || {};
    const digits = opts.digits || 'hindi';
    const percent = opts.percent == null ? '⁒' : opts.percent;
    const decimal = opts.decimal || 'arabic';
    let out = normalizeDigitsToWestern(s);
    // الفاصلة العشرية بين رقمين: 3.5 -> ٣٫٥
    if (digits === 'hindi' && decimal === 'arabic') {
      out = out.replace(/(\d)\.(?=\d)/g, '$1٫');
    }
    if (digits === 'hindi') {
      out = out.replace(/[0-9]/g, (c) => HINDI[+c]);
    }
    if (percent) out = out.replace(/[%٪⁒]/g, percent);
    return out;
  }

  // ---------- النص الغني ----------
  const ENT = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ' };
  function decodeEntities(s) {
    return s.replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (m) => ENT[m] || m);
  }
  function escapeText(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /**
   * يحول النص الغني المخزن إلى قائمة مقاطع:
   * {t:'text', text, bold} | {t:'math', latex} | {t:'br'}
   */
  function parseRich(str) {
    const runs = [];
    if (!str) return runs;
    str = String(str);
    let bold = 0;
    let i = 0;
    let buf = '';
    const flush = () => {
      if (buf) {
        runs.push({ t: 'text', text: decodeEntities(buf), bold: bold > 0 });
        buf = '';
      }
    };
    while (i < str.length) {
      const ch = str[i];
      if (ch === '<') {
        const rest = str.slice(i);
        let m;
        if ((m = /^<b>/i.exec(rest)) || (m = /^<strong>/i.exec(rest))) { flush(); bold++; i += m[0].length; continue; }
        if ((m = /^<\/b>/i.exec(rest)) || (m = /^<\/strong>/i.exec(rest))) { flush(); bold = Math.max(0, bold - 1); i += m[0].length; continue; }
        if ((m = /^<br\s*\/?>/i.exec(rest))) { flush(); runs.push({ t: 'br' }); i += m[0].length; continue; }
        if ((m = /^<m>([\s\S]*?)<\/m>/i.exec(rest))) {
          flush();
          runs.push({ t: 'math', latex: decodeEntities(m[1]), bold: bold > 0 });
          i += m[0].length; continue;
        }
        // وسم غير معروف: يعامل كنص
        buf += ch; i++; continue;
      }
      buf += ch; i++;
    }
    flush();
    // دمج المقاطع النصية المتجاورة بنفس التنسيق
    const merged = [];
    for (const r of runs) {
      const last = merged[merged.length - 1];
      if (last && last.t === 'text' && r.t === 'text' && last.bold === r.bold) last.text += r.text;
      else merged.push(r);
    }
    return merged;
  }

  function serializeRich(runs) {
    let out = '';
    for (const r of runs) {
      if (r.t === 'text') out += r.bold ? '<b>' + escapeText(r.text) + '</b>' : escapeText(r.text);
      else if (r.t === 'math') out += '<m>' + escapeText(r.latex) + '</m>';
      else if (r.t === 'br') out += '<br>';
    }
    return out;
  }

  /** نص خام (بدون وسوم) — للبحث والعرض المختصر */
  function plainText(str) {
    return parseRich(str).map((r) => (r.t === 'text' ? r.text : r.t === 'math' ? ' [' + r.latex + '] ' : ' ')).join('').replace(/\s+/g, ' ').trim();
  }

  function isRichEmpty(str) {
    return parseRich(str).every((r) => (r.t === 'text' ? !r.text.trim() : r.t === 'br'));
  }

  const OPTION_LABELS = ['أ)', 'ب)', 'جـ)', 'د)'];
  const ANSWER_KEYS = ['a', 'b', 'c', 'd'];
  const ANSWER_LETTERS = { a: 'أ', b: 'ب', c: 'جـ', d: 'د' };

  function toHindiNumber(n, digits) {
    return display(String(n), { digits: digits || 'hindi' });
  }

  const api = {
    display, parseRich, serializeRich, plainText, isRichEmpty, escapeText,
    normalizeDigitsToWestern, toHindiNumber, OPTION_LABELS, ANSWER_KEYS, ANSWER_LETTERS,
  };
  global.QText = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
