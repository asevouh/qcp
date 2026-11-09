/*
 * layout.js — محرك التخطيط: يقيس كل كتلة بقياسها الفعلي ثم يوزع الكتل على نصفي الصفحة
 * بالترتيب: يمين الصفحة ١ ← يسار الصفحة ١ ← يمين الصفحة ٢ ← ...
 * القواعد:
 *  - السؤال وخياراته (وصورته وجدول مقارنته) وحدة واحدة لا تنقسم.
 *  - عنوان القسم وعنوان التصنيف وتعريفه يبقى مع أول ما يليه متى أمكن.
 *  - الرسم البياني يجوز فصله عن أسئلته، والنص الطويل يجوز تقسيمه بين الفقرات فقط.
 *  - خطة التوزيع نفسها تُستخدم لإنتاج Word حتى يتطابق الملفان.
 */
(function (global) {
  'use strict';
  const QText = global.QText;
  const QModel = global.QModel;
  const QRender = global.QRender;

  const CM2PT = 72 / 2.54;
  const PX2PT = 0.75;

  function geometry(s) {
    const pageW = 21.0, pageH = 29.7;
    const mt = Number(s.margin_top_cm), mb = Number(s.margin_bottom_cm);
    const mr = Number(s.margin_right_cm), ml = Number(s.margin_left_cm);
    const gap = Number(s.column_gap_cm);
    const bodyW = pageW - mr - ml;
    const colW = (bodyW - gap) / 2;
    const bodyH = pageH - mt - mb;
    return { pageW, pageH, mt, mb, mr, ml, gap, bodyW, colW, bodyH, colHpt: bodyH * CM2PT };
  }

  function el(tag, cls, parent) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (parent) parent.appendChild(e);
    return e;
  }
  function para(parent, sizePt, s, opts) {
    const p = el('div', 'p', parent);
    p.style.fontSize = sizePt + 'pt';
    p.style.lineHeight = QRender.lineHeightPt(sizePt, s) + 'pt';
    if (opts && opts.align) p.style.textAlign = opts.align;
    if (opts && opts.bold) p.style.fontWeight = '700';
    if (opts && opts.text != null) p.textContent = opts.text;
    return p;
  }
  function disp(t, s) { return QText.display(t == null ? '' : String(t), QModel.dispOpts(s)); }

  // ---------------------------------------------------------------- الترويسة والتذييل
  function renderHeader(page, s, g, info) {
    const hb = el('div', 'hdr', page);
    const top = Number(s.header_top_cm) || 0.6;
    const h = Number(s.header_height_cm) || 1.3;
    const gapBoxes = Number(s.header_box_gap_cm) || 0.3;
    hb.style.top = top + 'cm';
    hb.style.right = g.mr + 'cm';
    hb.style.width = g.bodyW + 'cm';
    hb.style.height = h + 'cm';
    hb.style.setProperty('--hdr-border', (Number(s.header_border_pt) || 1) + 'pt');
    const w = (g.bodyW - 2 * gapBoxes) / 3;
    const boxes = [
      { lab: s.header_quant_label || 'مصدر أسئلة الكمي:', val: info.quantSource, kind: 'src' },
      { title: info.headerTitle, kind: 'title' },
      { lab: s.header_verbal_label || 'مصدر أسئلة اللفظي:', val: info.verbalSource, kind: 'src' },
    ];
    for (const b of boxes) {
      const d = el('div', 'hbox', hb);
      d.style.width = w + 'cm';
      d.style.height = h + 'cm';
      if (b.kind === 'title') {
        para(d, Number(s.header_title_pt) || 18, s, { align: 'center', bold: true, text: disp(b.title, s) });
      } else {
        const sz = Number(s.header_source_pt) || 10;
        para(d, sz, s, { align: 'center', bold: true, text: disp(b.lab, s) });
        para(d, sz, s, { align: 'center', bold: true, text: disp(b.val || '—', s) });
      }
    }
    const rule = el('div', 'hdr-rule', page);
    rule.style.top = (top + h + (Number(s.header_rule_gap_cm) || 0.25)) + 'cm';
    rule.style.left = '0.4cm';
    rule.style.right = '0.4cm';
  }

  function renderFooter(page, s, g, num) {
    if (s.page_numbers === false || s.page_numbers === 'off') return;
    const f = el('div', 'ftr', page);
    const size = Number(s.page_number_box_cm) || 0.9;
    f.style.left = '0'; f.style.right = '0';
    f.style.bottom = (Number(s.footer_bottom_cm) || 0.6) + 'cm';
    const box = el('div', 'pnum', f);
    box.style.width = size + 'cm'; box.style.height = (size * 0.85) + 'cm';
    para(box, Number(s.page_number_pt) || 10, s, { align: 'center', text: disp(num, s) });
  }

  // ---------------------------------------------------------------- الغلاف
  /*
   * الغلاف — مأخوذ من قياسات غلاف «الاختبار الرابع» المرجعي:
   *  جدول علوي بعرض 16.93 سم في الوسط (4 صفوف × 0.75 سم)، ثم خمس مجموعات تتوزع رأسيًا بمسافات متساوية
   *  (المعلومات، العنوان الكبير، الملحوظات، خانتا الاسم والصف، صندوق التذكير المستدير) حتى تملأ الصفحة.
   *  النصوص تبدأ بإزاحة 1.15 سم داخل حافة الجدول (= هامش 3.17 سم كما في المرجع)، ونقاط الملحوظات بإزاحة قائمة Word.
   *  يعيد خطة بالقياسات نفسها ليبني منها كاتب Word الغلاف بالمواضع ذاتها.
   */
  const COVER = {
    top: 2.1, bottom: 3.4, tableW: 16.93, rowH: 0.75, inner: 1.15,
    bulletAt: 0.635, textAt: 1.27, infoAfter: 7, notesTitleAfter: 7, noteAfter: 2, nameAfter: 10,
    bigPt: 23.5, bigPadV: 0.127, bigPadH: 0.3, remindW: 13.0, remindPadH: 0.25, remindPadV: 0.35, remindMinH: 3.3,
    remindTitleAfter: 3, sizePt: 14, gridPt: 10, sidePt: 14, minGap: 0.35, maxGap: 2.4,
  };

  function renderCover(container, s, info) {
    const page = el('div', 'page cover', container);
    const c = s.cover || {};
    const K = COVER;
    const side = (21 - K.tableW) / 2;
    const tline = (sz) => QRender.lineHeightPt(sz, s);

    // ---- الجدول العلوي (جدول واحد بأربعة أعمدة كما في المرجع)
    const top = el('div', 'cv-top', page);
    top.style.top = K.top + 'cm'; top.style.right = side + 'cm'; top.style.width = K.tableW + 'cm';
    top.style.height = (4 * K.rowH) + 'cm';
    const t = el('table', 'cv-table', top);
    const widths = [0.3445, 0.1552, 0.1555, 0.3448];
    const cg = el('colgroup', null, t);
    for (const w of widths) { const col = el('col', null, cg); col.style.width = (w * K.tableW) + 'cm'; }
    const rows = [0, 1, 2, 3].map(() => { const r = el('tr', null, t); r.style.height = K.rowH + 'cm'; return r; });
    const sideCell = (txt) => { const td = el('td', 'cv-side', rows[0]); td.rowSpan = 4; para(td, K.sidePt, s, { align: 'center', bold: true, text: disp(txt || '', s) }); };
    sideCell(c.right_text);
    const h1 = el('td', null, rows[0]); h1.colSpan = 2;
    para(h1, K.gridPt, s, { align: 'center', text: disp(c.grade_label || 'الدرجة النهائية', s) });
    sideCell(c.left_text);
    para(el('td', null, rows[1]), K.gridPt, s, { align: 'center', text: disp(c.quant_label || 'كمي', s) });
    para(el('td', null, rows[1]), K.gridPt, s, { align: 'center', text: disp(c.verbal_label || 'لفظي', s) });
    el('td', null, rows[2]); el('td', null, rows[2]);
    para(el('td', null, rows[3]), K.gridPt, s, { align: 'center', text: disp(info.quantCount, s) });
    para(el('td', null, rows[3]), K.gridPt, s, { align: 'center', text: disp(info.verbalCount, s) });
    const tableBottom = K.top + 4 * K.rowH;

    // ---- المجموعات
    const groups = [];
    const group = (kind) => {
      const d = el('div', 'cv-group cvg-' + kind, page);
      d.style.right = side + 'cm'; d.style.width = K.tableW + 'cm';
      const gobj = { kind, el: d };
      groups.push(gobj);
      return gobj;
    };
    const spaced = (p, after) => { p.style.marginBottom = after + 'pt'; return p; };

    const gi = group('info');
    const infoLines = [
      { text: info.examTitle, bold: true },
      { text: (c.count_label || 'عدد الأسئلة:') + ' ' + info.totalCount + ' ' + (c.count_unit || 'سؤال') },
      { text: (c.duration_label || 'مدة الاختبار:') + ' ' + (info.duration || '') + ' ' + (c.duration_unit || 'دقيقة') },
    ];
    infoLines.forEach((ln, k) => spaced(para(gi.el, K.sizePt, s, { align: 'center', bold: ln.bold, text: disp(ln.text, s) }), k < infoLines.length - 1 ? K.infoAfter : 0));
    gi.lines = infoLines.map((ln) => ({ text: disp(ln.text, s), bold: !!ln.bold }));

    const gb = group('big');
    const big = el('div', 'cv-bigbox', gb.el);
    big.style.padding = K.bigPadV + 'cm ' + K.bigPadH + 'cm';
    big.style.maxWidth = K.tableW + 'cm';
    para(big, K.bigPt, s, { align: 'center', bold: true, text: disp(info.bigTitle, s) });
    gb.text = disp(info.bigTitle, s);

    const notes = (c.notes || []).filter((x) => x && String(x).trim());
    if (c.notes_title || notes.length) {
      const gn = group('notes');
      if (c.notes_title) spaced(para(gn.el, K.sizePt, s, { align: 'center', bold: true, text: disp(c.notes_title, s) }), notes.length ? K.notesTitleAfter : 0);
      notes.forEach((n, k) => {
        const p = spaced(para(gn.el, K.sizePt, s, { text: disp(n, s) }), k < notes.length - 1 ? K.noteAfter : 0);
        p.classList.add('cv-note');
        p.style.paddingRight = (K.inner + K.textAt) + 'cm';
        p.style.paddingLeft = K.inner + 'cm';
        const bul = el('span', 'cv-bullet', p);
        bul.textContent = '•';
        bul.style.right = (K.inner + K.bulletAt) + 'cm';
      });
      gn.title = c.notes_title ? disp(c.notes_title, s) : '';
      gn.notes = notes.map((n) => disp(n, s));
    }

    if (c.show_name_fields !== false) {
      const gm = group('names');
      const labels = [c.name_label || 'الاسم:', c.class_label || 'الصف والشعبة:'];
      labels.forEach((lab, k) => {
        const p = spaced(para(gm.el, K.sizePt, s, { bold: true }), k < labels.length - 1 ? K.nameAfter : 0);
        p.classList.add('cv-line');
        p.style.paddingRight = K.inner + 'cm'; p.style.paddingLeft = K.inner + 'cm';
        const l = el('span', 'cv-lab', p); l.textContent = disp(lab, s) + ' ';
        const dots = el('span', 'cv-dots', p);
        // عدد النقاط يُحسب بالقياس حتى يملأ السطر، ويُستعمل العدد نفسه في Word (نقاط حرفية كما في المرجع)
        const probe = el('span', null, p);
        probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;';
        probe.textContent = '.'.repeat(100);
        const dotW = probe.getBoundingClientRect().width / 100;
        probe.remove();
        const free = p.getBoundingClientRect().width - (2 * K.inner / 2.54 * 96) - l.getBoundingClientRect().width;
        const n = Math.max(10, Math.floor(free / dotW) - 2);
        dots.textContent = '.'.repeat(n);
        (gm.dots = gm.dots || []).push(n);
      });
      gm.labels = labels.map((x) => disp(x, s));
    }

    let remind = null;
    if (c.reminder_text && String(c.reminder_text).trim()) {
      const gr = group('remind');
      const rb = el('div', 'cv-remind', gr.el);
      rb.style.width = K.remindW + 'cm';
      rb.style.padding = K.remindPadV + 'cm ' + K.remindPadH + 'cm';
      if (c.reminder_title) spaced(para(rb, K.sizePt, s, { align: 'center', bold: true, text: disp(c.reminder_title, s) }), K.remindTitleAfter);
      para(rb, K.sizePt, s, { align: 'center', text: disp(c.reminder_text, s) });
      gr.title = c.reminder_title ? disp(c.reminder_title, s) : '';
      gr.text = disp(c.reminder_text, s);
      remind = { gr, rb };
    }

    // ---- القياس والتوزيع الرأسي بمسافات متساوية
    const PT_CM = 2.54 / 72;
    if (remind) {
      const natural = remind.rb.getBoundingClientRect().height * PX2PT * PT_CM;
      const h = Math.max(K.remindMinH, natural);
      remind.rb.style.height = h + 'cm';
      remind.rb.style.borderRadius = (0.16667 * Math.min(h, K.remindW)) + 'cm';
    }
    for (const gobj of groups) gobj.hCm = gobj.el.getBoundingClientRect().height * PX2PT * PT_CM;
    const avail = (29.7 - K.bottom) - tableBottom;
    const used = groups.reduce((a, gobj) => a + gobj.hCm, 0);
    const gap = Math.min(K.maxGap, Math.max(K.minGap, (avail - used) / Math.max(1, groups.length)));
    let y = tableBottom;
    for (const gobj of groups) {
      y += gap;
      gobj.topCm = y;
      gobj.el.style.top = y + 'cm';
      y += gobj.hCm;
    }
    const bigW = big.getBoundingClientRect().width * PX2PT * PT_CM;

    page._coverPlan = {
      K, side, tableBottom, gapCm: gap, bigWcm: bigW,
      lineSizePt: K.sizePt, lineHpt: tline(K.sizePt), bigLineHpt: tline(K.bigPt),
      sideLineHpt: tline(K.sidePt), gridLineHpt: tline(K.gridPt),
      top: { right: disp(c.right_text || '', s), left: disp(c.left_text || '', s), grade: disp(c.grade_label || 'الدرجة النهائية', s),
             quant: disp(c.quant_label || 'كمي', s), verbal: disp(c.verbal_label || 'لفظي', s),
             quantCount: disp(info.quantCount, s), verbalCount: disp(info.verbalCount, s) },
      groups: groups.map((gobj) => {
        const o = Object.assign({}, gobj); delete o.el; return o;
      }),
    };
    if (remind) {
      const rp = page._coverPlan.groups.find((x) => x.kind === 'remind');
      rp.boxHcm = remind.rb.getBoundingClientRect().height * PX2PT * PT_CM;
    }
    return page;
  }

  // ---------------------------------------------------------------- القياس والتوزيع
  function measureBlocks(blocks, ctx, g) {
    const meas = el('div', 'qdoc qdoc-measure', document.body);
    QRender.applyDocVars(meas, ctx.settings);
    const col = el('div', 'col-measure', meas);
    col.style.width = g.colW + 'cm';
    const els = [];
    for (const b of blocks) {
      const e = QRender.renderBlock(b, ctx);
      col.appendChild(e);
      els.push(e);
    }
    const heights = els.map((e) => e.getBoundingClientRect().height * PX2PT);
    return { meas, els, heights };
  }

  /**
   * توزيع الكتل على الأعمدة.
   * cap: سعة العمود بالنقطة. يعيد قائمة أعمدة، كل عمود: [{index, gap}]
   */
  function paginate(blocks, heights, cap) {
    const cols = [];
    let cur = [];
    let used = 0;
    const warnings = [];
    const newCol = () => { cols.push(cur); cur = []; used = 0; };
    let i = 0;
    let guard = 0;
    while (i < blocks.length) {
      if (++guard > blocks.length * 4 + 100) break;
      const b = blocks[i];
      const empty = cur.length === 0;
      const gap = empty ? 0 : (b.gapBefore || 0);
      const need = gap + heights[i];
      // سلسلة "ابقَ مع التالي": عنوان القسم ← عنوان التصنيف ← أول سؤال
      if (b.keepWithNext && i + 1 < blocks.length) {
        let total = need;
        let j = i;
        while (blocks[j].keepWithNext && j + 1 < blocks.length) {
          j++;
          total += (blocks[j].gapBefore || 0) + heights[j];
        }
        const chainFromTop = total - gap;
        if (!empty && used + total > cap && chainFromTop <= cap) { newCol(); continue; }
      }
      if (b.type === 'end_text' && !empty && used + need > cap) {
        // تقليص المسافة قبل عبارة النهاية لتجنب صفحة إضافية غير ضرورية
        const minGap = 2;
        if (used + minGap + heights[i] <= cap) {
          cur.push({ index: i, gap: minGap }); used += minGap + heights[i]; i++; continue;
        }
      }
      if (!empty && used + need > cap) { newCol(); continue; }
      if (heights[i] > cap + 0.5) warnings.push({ id: b.id, type: 'too_tall', height: heights[i], cap });
      cur.push({ index: i, gap });
      used += need;
      i++;
    }
    if (cur.length) cols.push(cur);
    return { cols, warnings };
  }

  function buildPages(container, blocks, els, plan, s, g, info, startPage) {
    const pages = [];
    const nPages = Math.ceil(plan.cols.length / 2);
    for (let p = 0; p < nPages; p++) {
      const page = el('div', 'page', container);
      renderHeader(page, s, g, info);
      const body = el('div', 'pbody', page);
      body.style.top = g.mt + 'cm'; body.style.right = g.mr + 'cm';
      body.style.width = g.bodyW + 'cm'; body.style.height = g.bodyH + 'cm';
      const colR = el('div', 'col col-right', body);
      colR.style.right = '0'; colR.style.width = g.colW + 'cm';
      const sep = el('div', 'col-sep', body);
      const sw = Number(s.separator_width_pt) || 0.75;
      sep.style.right = 'calc(' + (g.colW + g.gap / 2) + 'cm - ' + (sw / 2) + 'pt)';
      sep.style.width = sw + 'pt';
      sep.style.background = s.separator_color || '#404040';
      const colL = el('div', 'col col-left', body);
      colL.style.left = '0'; colL.style.width = g.colW + 'cm';
      const pageCols = [colR, colL];
      const pageInfo = { cols: [[], []] };
      for (let c = 0; c < 2; c++) {
        const colPlan = plan.cols[p * 2 + c];
        if (!colPlan) continue;
        for (const ent of colPlan) {
          const e = els[ent.index];
          e.style.marginTop = ent.gap + 'pt';
          pageCols[c].appendChild(e);
          pageInfo.cols[c].push({ id: blocks[ent.index].id, gap: ent.gap });
        }
      }
      renderFooter(page, s, g, (startPage || 1) + p);
      pages.push(pageInfo);
    }
    return pages;
  }

  function checkOverflow(container) {
    const problems = [];
    // تجاوز أفقي: معادلة أو صورة أعرض من العمود
    container.querySelectorAll('.col').forEach((col, k) => {
      const cr = col.getBoundingClientRect();
      col.querySelectorAll('.qm svg, img').forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.left < cr.left - 1.5 || r.right > cr.right + 1.5) {
          const blk = el.closest('.blk');
          problems.push({ col: k, horizontal: true, block: blk ? blk.dataset.id : null, overflowPt: Math.max(cr.left - r.left, r.right - cr.right) * PX2PT });
        }
      });
    });
    container.querySelectorAll('.col').forEach((col, k) => {
      const ch = col.getBoundingClientRect().height;
      let bottom = 0;
      const top = col.getBoundingClientRect().top;
      for (const child of col.children) {
        const r = child.getBoundingClientRect();
        bottom = Math.max(bottom, r.bottom - top);
      }
      if (bottom > ch + 0.5) problems.push({ col: k, overflowPt: (bottom - ch) * PX2PT });
    });
    return problems;
  }

  /**
   * run(input) — نقطة الدخول للتصدير والمعاينة.
   * input: { settings, sections, exam:{title, header_title, duration, ...}, variant, media, includeCover }
   */
  async function run(input, container) {
    const s = input.settings;
    const g = geometry(s);
    container = container || document.getElementById('doc');
    container.innerHTML = '';
    container.classList.add('qdoc');
    QRender.applyDocVars(container, s);
    global.QMath.clearCache();

    const doc = QModel.buildDocument({ settings: s, sections: input.sections, variant: input.variant, includeEndText: input.includeEndText });
    const ctx = { settings: s, media: input.media || {}, math: [], mathIndex: {} };
    const blocks = doc.blocks;
    const { meas, els, heights } = measureBlocks(blocks, ctx, g);
    const safety = Number(s.word_safety_pt) || 0;
    const cap = g.colHpt - safety;
    const plan = paginate(blocks, heights, cap);

    const quant = input.sections.find((x) => x && x.kind === 'quant');
    const verbal = input.sections.find((x) => x && x.kind === 'verbal');
    const countOf = (sec) => (sec ? doc.answerKey.filter((a) => a.section === sec.kind).length : 0);
    const exam = input.exam || {};
    const info = {
      quantSource: quant ? quant.source : '',
      verbalSource: verbal ? verbal.source : '',
      headerTitle: exam.header_title || exam.title || '',
      examTitle: exam.title || '',
      examNumber: exam.number || '',
      bigTitle: exam.big_title || ((exam.title || '') + (s.cover && s.cover.big_suffix != null ? s.cover.big_suffix : ': كمي ولفظي')),
      duration: exam.duration,
      quantCount: countOf(quant), verbalCount: countOf(verbal),
      totalCount: doc.answerKey.length,
    };
    let coverPlan = null;
    if (input.includeCover) coverPlan = renderCover(container, s, info)._coverPlan;
    const pages = buildPages(container, blocks, els, plan, s, g, info, 1);
    meas.remove();
    const overflow = checkOverflow(container);
    // انتظار تحميل الصور
    const imgs = Array.from(container.querySelectorAll('img'));
    await Promise.all(imgs.map((im) => (im.complete ? Promise.resolve() : new Promise((res) => { im.onload = im.onerror = res; }))));
    const brokenImages = imgs.filter((im) => !im.naturalWidth).map((im) => im.getAttribute('src'));
    return {
      blocks, answerKey: doc.answerKey, pages, heights,
      plan: plan.cols.map((c) => c.map((e) => ({ id: blocks[e.index].id, gap: e.gap }))),
      warnings: plan.warnings, overflow, brokenImages, info, cover: coverPlan,
      math: ctx.math.map((m) => ({ id: m.id, latex: m.latex, sizePt: m.sizePt, width: m.width, height: m.height, descent: m.descent })),
      mathCtx: ctx.math, geometry: g, colCapacityPt: cap,
    };
  }

  /** صور المعادلات (PNG عالية الدقة) لملف Word — بنفس أبعاد المعاينة تمامًا */
  function mathImages(mathCtx, scale) {
    return mathCtx.map((m) => {
      const r = global.QMath.toPNG(m.box, m.opts, scale || 6);
      return { id: m.id, dataUrl: r.dataUrl, width: r.width, height: r.height, descent: r.descent };
    });
  }

  // ---------------------------------------------------------------- مفتاح الإجابة
  function runAnswerKey(input, container) {
    const s = input.settings;
    container = container || document.getElementById('doc');
    container.innerHTML = '';
    container.classList.add('qdoc');
    QRender.applyDocVars(container, s);
    const doc = QModel.buildDocument({ settings: s, sections: input.sections, variant: 'student', includeEndText: false });
    const page = el('div', 'page', container);
    const body = el('div', 'pbody', page);
    body.style.top = '1.6cm'; body.style.right = '2cm'; body.style.left = '2cm';
    const exam = input.exam || {};
    para(body, 18, s, { align: 'center', bold: true, text: disp((s.answer_key_title || 'مفتاح الإجابة') + ' — ' + (exam.title || ''), s) });
    const sub = el('div', null, body); sub.style.height = '0.5cm';
    const groups = [];
    input.sections.forEach((sec, idx) => {
      if (!sec) return;
      const rows = doc.answerKey.filter((a) => a.sectionIndex === idx);
      groups.push({ sec, rows });
    });
    const wrap = el('div', null, body);
    wrap.style.display = 'flex'; wrap.style.gap = '1cm'; wrap.style.justifyContent = 'center'; wrap.style.alignItems = 'flex-start';
    for (const gr of groups) {
      const box = el('div', null, wrap);
      box.style.width = '7.5cm';
      const title = gr.sec.kind === 'quant' ? (s.quant_section_title || 'القسم الكمي') : (s.verbal_section_title || 'القسم اللفظي');
      para(box, 14, s, { align: 'center', bold: true, text: disp(title, s) });
      para(box, 10, s, { align: 'center', text: disp(gr.sec.source || '', s) });
      const t = el('table', 'key', box);
      t.style.marginTop = '4pt';
      const hr = el('tr', null, t);
      for (const h of ['رقم السؤال', 'الإجابة']) {
        const td = el('td', null, hr); td.style.border = '0.75pt solid #000'; td.style.background = '#E6E6E6'; td.style.textAlign = 'center';
        para(td, 12, s, { align: 'center', bold: true, text: h });
      }
      for (const r of gr.rows) {
        const tr = el('tr', null, t);
        const a = el('td', null, tr); a.style.border = '0.75pt solid #000';
        para(a, 12, s, { align: 'center', text: disp(r.number, s) });
        const b = el('td', null, tr); b.style.border = '0.75pt solid #000';
        para(b, 12, s, { align: 'center', bold: true, text: r.answer ? QText.ANSWER_LETTERS[r.answer] : '—' });
      }
    }
    return { answerKey: doc.answerKey, pages: 1 };
  }

  global.QLayout = { run, runAnswerKey, mathImages, geometry, paginate, renderCover };
})(typeof window !== 'undefined' ? window : globalThis);
