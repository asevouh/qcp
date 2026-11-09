/*
 * render.js — تحويل كتل نموذج المستند إلى عناصر HTML بالقياسات نفسها التي يستخدمها ملف Word.
 * جميع الأبعاد بالنقطة (pt) أو السنتيمتر حتى يتطابق التخطيط مع Word.
 */
(function (global) {
  'use strict';
  const QText = global.QText;
  const QMath = global.QMath;

  const PT2PX = 96 / 72;

  function fontStack(settings) {
    return '"QSymbols", "QPrimary", "QLatinFallback", "QArabicFallback", sans-serif';
  }

  /** ارتفاع السطر بالنقطة لحجم خط معين (مطابق لحساب Word: مضاعف × مقاييس الخط) */
  function lineHeightPt(sizePt, settings) {
    const factor = Number(settings.font_metrics_factor) || 1.2207;
    const mult = Math.max(1.0, Number(settings.line_spacing) || 1.15); // أقل من ١ يجعل Word يكبّر الأسطر فيختل التطابق
    return Math.round(sizePt * factor * mult * 20) / 20; // تقريب لأقرب 1/20 نقطة (وحدة Word)
  }

  function el(tag, cls, parent) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (parent) parent.appendChild(e);
    return e;
  }

  /** مقاطع النص → عقد HTML. ctx.math: سجل المعادلات (لتصديرها صورًا إلى Word) */
  function renderRuns(runs, parent, sizePt, ctx) {
    for (const r of runs || []) {
      if (r.t === 'text') {
        if (!r.text) continue;
        const s = document.createElement(r.bold ? 'b' : 'span');
        s.textContent = r.text;
        parent.appendChild(s);
      } else if (r.t === 'br') {
        parent.appendChild(document.createElement('br'));
      } else if (r.t === 'math') {
        const opts = {
          size: sizePt * PT2PX, family: fontStack(ctx.settings),
          digits: ctx.settings.digits || 'hindi', percent: ctx.settings.percent_sign || '⁒',
          decimal: ctx.settings.decimal_style || 'arabic', fracScale: Number(ctx.settings.frac_scale) || 0.82,
          bold: false,
        };
        const res = QMath.render(r.latex, opts);
        const wrap = document.createElement('span');
        wrap.className = 'qm';
        wrap.innerHTML = res.svg;
        if (ctx.math && !res.error) {
          const key = sizePt + '|' + r.latex;
          let id = ctx.mathIndex[key];
          if (id == null) {
            id = 'm' + ctx.math.length;
            ctx.mathIndex[key] = id;
            ctx.math.push({ id, latex: r.latex, sizePt, opts, box: res.box, width: res.width, height: res.height, descent: res.descent });
          }
          r.mathId = id;
          wrap.dataset.mid = id;
        }
        if (res.error) r.error = res.error;
        parent.appendChild(wrap);
      }
    }
  }

  function para(cls, parent, sizePt, ctx, opts) {
    const p = el('div', 'p ' + (cls || ''), parent);
    p.style.fontSize = sizePt + 'pt';
    p.style.lineHeight = lineHeightPt(sizePt, ctx.settings) + 'pt';
    if (opts && opts.align) p.style.textAlign = opts.align;
    if (opts && opts.bold) p.style.fontWeight = '700';
    return p;
  }

  function cm(v) { return v + 'cm'; }

  function mediaSize(media, widthCm, ctx, maxWidthCm) {
    const info = (ctx.media && ctx.media[media]) || null;
    let w = Math.min(widthCm, maxWidthCm || widthCm);
    let aspect = info && info.w ? info.h / info.w : 0.75;
    return { wCm: w, hCm: w * aspect, url: info ? info.url : ('/media/' + media) };
  }

  function renderImage(media, widthCm, parent, ctx, maxW) {
    const sz = mediaSize(media, widthCm, ctx, maxW);
    const p = el('div', 'imgp', parent);
    const img = el('img', null, p);
    img.src = sz.url;
    img.style.width = cm(sz.wCm.toFixed(3));
    img.style.height = cm(sz.hCm.toFixed(3));
    img.alt = '';
    return { p, sz };
  }

  function colWidthCm(s) {
    const pageW = 21.0;
    return (pageW - Number(s.margin_right_cm) - Number(s.margin_left_cm) - Number(s.column_gap_cm)) / 2;
  }

  function renderOptions(block, parent, ctx) {
    const s = ctx.settings;
    const size = Number(s.option_font_pt) || 13;
    const t = el('table', 'opts ' + block.options.layout, parent);
    const lab = Number(s.option_label_width_cm) || 0.9;
    const cg = el('colgroup', null, t);
    if (block.options.layout === 'grid') {
      for (let k = 0; k < 2; k++) {
        el('col', null, cg).style.width = cm(lab);
        el('col', null, cg).style.width = 'calc((100% - ' + (2 * lab) + 'cm) / 2)';
      }
      for (let r = 0; r < 2; r++) {
        const tr = el('tr', null, t);
        for (let c = 0; c < 2; c++) {
          const it = block.options.items[r * 2 + c];
          addOptionCells(tr, it, size, ctx);
        }
      }
    } else {
      el('col', null, cg).style.width = cm(lab);
      el('col', null, cg);
      for (const it of block.options.items) {
        const tr = el('tr', null, t);
        addOptionCells(tr, it, size, ctx);
      }
    }
    return t;
  }

  function addOptionCells(tr, it, size, ctx) {
    const lh = lineHeightPt(size, ctx.settings) + 'pt';
    const td1 = el('td', 'lab' + (it.correct ? ' correct' : ''), tr);
    td1.style.fontSize = size + 'pt'; td1.style.lineHeight = lh;
    td1.textContent = it.label;
    const td2 = el('td', 'txt' + (it.correct ? ' correct' : ''), tr);
    td2.style.fontSize = size + 'pt'; td2.style.lineHeight = lh;
    renderRuns(it.runs, td2, size, ctx);
  }

  function renderStem(block, parent, ctx) {
    const s = ctx.settings;
    const size = Number(s.question_font_pt) || 13;
    const p = para('stem', parent, size, ctx);
    const num = el('span', 'num', p);
    num.textContent = block.numberLabel + ' ';
    if (s.number_bold) num.style.fontWeight = '700';
    renderRuns(block.stem, p, size, ctx);
    return p;
  }

  function renderBlock(block, ctx) {
    const s = ctx.settings;
    const root = document.createElement('div');
    root.className = 'blk blk-' + block.type;
    root.dataset.id = block.id;
    const colW = colWidthCm(s);
    switch (block.type) {
      case 'section_title': {
        const box = el('div', 'box title-box', root);
        const p = para('', box, Number(s.title_font_pt) || 16, ctx, { align: 'center', bold: true });
        p.textContent = block.text;
        break;
      }
      case 'category_header': {
        const box = el('div', 'box cat-box', root);
        const p1 = para('cat-title', box, Number(s.category_title_pt) || 13, ctx, { align: 'center', bold: true });
        p1.textContent = block.title;
        if (block.definition) {
          const p2 = para('cat-def', box, Number(s.category_def_pt) || 12, ctx, { align: 'center' });
          p2.textContent = block.definition;
        }
        break;
      }
      case 'question': {
        const fig = block.figure;
        if (fig && fig.placement === 'side') {
          const t = el('table', 'side', root);
          const cg = el('colgroup', null, t);
          const figW = Math.min(fig.widthCm, colW * 0.55);
          el('col', null, cg);
          el('col', null, cg).style.width = cm((figW + 0.2).toFixed(3));
          const tr = el('tr', null, t);
          const tdText = el('td', 'side-text', tr);
          renderStem(block, tdText, ctx).style.marginBottom = '0';
          const tdFig = el('td', 'side-fig', tr);
          renderImage(fig.media, figW, tdFig, ctx, figW);
          const cap = para('cap', tdFig, Number(s.caption_font_pt) || 9, ctx, { align: 'center' });
          cap.textContent = fig.caption;
          const sp = el('div', 'stem-gap', root); sp.style.height = (Number(s.stem_options_gap_pt) || 4) + 'pt';
        } else {
          if (fig && fig.placement === 'above') {
            renderImage(fig.media, fig.widthCm, root, ctx, colW);
            const cap = para('cap', root, Number(s.caption_font_pt) || 9, ctx, { align: 'center' });
            cap.textContent = fig.caption;
          }
          const stem = renderStem(block, root, ctx);
          stem.style.marginBottom = (Number(s.stem_options_gap_pt) || 4) + 'pt';
          if (fig && fig.placement !== 'above') {
            renderImage(fig.media, fig.widthCm, root, ctx, colW);
            const cap = para('cap', root, Number(s.caption_font_pt) || 9, ctx, { align: 'center' });
            cap.textContent = fig.caption;
            cap.style.marginBottom = (Number(s.stem_options_gap_pt) || 4) + 'pt';
          }
        }
        if (block.compare) {
          const size = Number(s.option_font_pt) || 13;
          const t = el('table', 'cmp', root);
          const tr = el('tr', null, t);
          for (const [lab, val] of [[block.compare.label1, block.compare.v1], [block.compare.label2, block.compare.v2]]) {
            const td = el('td', null, tr);
            const p1 = para('cmp-lab', td, Number(s.compare_label_pt) || 12, ctx);
            p1.textContent = QText.display(lab, { digits: s.digits });
            const p2 = para('cmp-val', td, size, ctx, { align: 'center' });
            renderRuns(val, p2, size, ctx);
          }
          const gap = el('div', 'cmp-gap', root); gap.style.height = (Number(s.compare_gap_pt) || 4) + 'pt';
        }
        renderOptions(block, root, ctx);
        break;
      }
      case 'chart': {
        const r = renderImage(block.media, block.widthCm, root, ctx, colW);
        r.p.classList.add('chart');
        break;
      }
      case 'passage': {
        const size = Number(s.passage_font_pt) || 13;
        const p = para('passage', root, size, ctx, { align: block.align === 'justify' ? 'justify' : block.align });
        renderRuns(block.runs, p, size, ctx);
        break;
      }
      case 'end_text': {
        const p = para('end', root, Number(s.end_text_pt) || 13, ctx, { align: 'center', bold: true });
        p.textContent = block.text;
        break;
      }
    }
    return root;
  }

  /** معاينة سؤال واحد داخل الواجهة (بعرض عمود حقيقي) */
  function previewQuestion(question, settings, sectionKind, number, media) {
    const ctx = { settings, media: media || {}, math: null, mathIndex: {} };
    const blocks = [];
    if (question.type === 'group') {
      const doc = global.QModel.buildDocument({ settings, sections: [{ kind: sectionKind, items: [question] }], includeEndText: false });
      for (const b of doc.blocks) if (b.type !== 'section_title' && b.type !== 'category_header') blocks.push(b);
    } else {
      blocks.push(global.QModel.buildQuestion(question, number || 1, settings, 'teacher', sectionKind));
    }
    const wrap = document.createElement('div');
    wrap.className = 'qdoc preview-col';
    wrap.style.width = colWidthCm(settings) + 'cm';
    applyDocVars(wrap, settings);
    for (const b of blocks) {
      const e = renderBlock(b, ctx);
      e.style.marginTop = (blocks.indexOf(b) ? (b.gapBefore || 8) : 0) + 'pt';
      wrap.appendChild(e);
    }
    return wrap;
  }

  function applyDocVars(node, s) {
    node.style.setProperty('--doc-font', fontStack(s));
    node.style.setProperty('--rule', (Number(s.border_width_pt) || 0.75) + 'pt');
    node.style.setProperty('--rule-color', s.border_color || '#000000');
    node.style.setProperty('--title-fill', s.title_fill || '#E6E6E6');
    node.style.setProperty('--correct-fill', s.correct_fill || '#D9D9D9');
    node.style.setProperty('--cell-pad', (Number(s.cell_padding_pt) || 2) + 'pt');
    node.style.setProperty('--box-pad-v', (Number(s.box_padding_v_pt) || 3) + 'pt');
    node.style.setProperty('--box-pad-h', (Number(s.box_padding_h_pt) || 5) + 'pt');
    node.style.fontFamily = fontStack(s);
  }

  global.QRender = { renderBlock, renderRuns, previewQuestion, lineHeightPt, fontStack, colWidthCm, applyDocVars, PT2PX, mediaSize };
})(typeof window !== 'undefined' ? window : globalThis);
