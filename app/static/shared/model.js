/*
 * model.js — بناء "نموذج المستند" الموحد من بيانات الأقسام والإعدادات.
 * هذا النموذج هو المصدر الوحيد الذي يُبنى منه كل من: المعاينة، وملف PDF، وملف Word.
 * لا يغيّر النموذج نصوص الأسئلة ولا ترتيبها؛ يضيف فقط عناصر العرض (الترقيم، العناوين، التعريفات...).
 */
(function (global) {
  'use strict';
  const QText = global.QText;

  const QUANT_CATEGORIES = {
    regular: 'اعتيادي',
    chart: 'رسوم بيانية',
    geometry: 'رسم هندسي',
  };
  const VERBAL_CATEGORIES = {
    analogy: 'تناظر لفظي',
    completion: 'إكمال جمل',
    odd: 'مفردة شاذة',
    context: 'خطأ سياقي',
    reading: 'استيعاب المقروء',
  };

  function dispOpts(settings) {
    return { digits: settings.digits || 'hindi', percent: settings.percent_sign || '⁒', decimal: settings.decimal_style || 'arabic' };
  }

  /** يحول النص الغني المخزن إلى مقاطع جاهزة للعرض (مع تحويل الأرقام في النصوص) */
  function runsOf(rich, settings, extra) {
    const o = dispOpts(settings);
    return QText.parseRich(rich).map((r) => {
      if (r.t === 'text') return { t: 'text', text: QText.display(r.text, o), bold: r.bold || !!(extra && extra.bold) };
      if (r.t === 'math') return { t: 'math', latex: r.latex, bold: r.bold || !!(extra && extra.bold) };
      return r;
    });
  }
  function textRuns(plain, settings, bold) {
    return [{ t: 'text', text: QText.display(plain || '', dispOpts(settings)), bold: !!bold }];
  }

  function numberLabel(n, settings) {
    const fmt = settings.number_format || '{n}:';
    return QText.display(fmt.replace('{n}', String(n)), dispOpts(settings));
  }

  /** التحقق من تحديدات الخطأ السياقي وإعادة ترتيبها حسب موضعها في الجملة */
  function contextSelections(q) {
    const sentence = (q.data && q.data.sentence) || '';
    const sels = ((q.data && q.data.selections) || []).filter((s) => s && s.end > s.start && s.start >= 0 && s.end <= sentence.length);
    return sels.slice().sort((a, b) => a.start - b.start);
  }

  function optionTexts(q, settings) {
    const d = q.data || {};
    if (q.category === 'context') {
      return contextSelections(q).map((s) => (q.data.sentence || '').slice(s.start, s.end));
    }
    if (q.category === 'analogy') {
      return (d.option_pairs || []).map((p) => (p ? [p.a || '', p.b || ''] : ['', '']));
    }
    if (d.options_type === 'compare') return settings.compare_options || [];
    return d.options || [];
  }

  /** يبني كتلة سؤال */
  function buildQuestion(q, number, settings, variant, sectionKind) {
    const d = q.data || {};
    const block = {
      id: 'q' + q.id, type: 'question', qid: q.id, category: q.category,
      number, numberLabel: numberLabel(number, settings), answer: q.answer || null,
      stem: [], options: null, compare: null, figure: null,
    };
    const sz = settings;
    // نص السؤال
    if (q.category === 'analogy') {
      const a = (d.pair && d.pair.a) || '';
      const b = (d.pair && d.pair.b) || '';
      block.stem = textRuns(a + ' : ' + b, sz, sz.analogy_stem_bold !== false);
    } else if (q.category === 'odd') {
      block.stem = textRuns(sz.odd_stem_text || 'أي الآتي مختلف؟', sz, false);
    } else if (q.category === 'context') {
      const sentence = d.sentence || '';
      const sels = contextSelections(q);
      const runs = [];
      let pos = 0;
      const o = dispOpts(sz);
      for (const s of sels) {
        if (s.start < pos) continue;
        if (s.start > pos) runs.push({ t: 'text', text: QText.display(sentence.slice(pos, s.start), o), bold: false });
        runs.push({ t: 'text', text: QText.display(sentence.slice(s.start, s.end), o), bold: true });
        pos = s.end;
      }
      if (pos < sentence.length) runs.push({ t: 'text', text: QText.display(sentence.slice(pos), o), bold: false });
      block.stem = runs;
    } else {
      block.stem = runsOf(d.stem || '', sz);
    }
    // الشكل الهندسي
    if (q.category === 'geometry' && d.image && d.image.media_id) {
      block.figure = {
        media: d.image.media_id,
        widthCm: Math.max(1, Number(d.image.width_cm) || sz.geometry_width_cm || 4.5),
        placement: d.image_placement || 'below',
        caption: sz.geometry_caption || '(الرسم ليس على القياس)',
        aspect: d.image.aspect || null,
      };
    }
    // المقارنة
    const type = d.options_type || 'short';
    if (sectionKind === 'quant' && type === 'compare') {
      block.compare = {
        label1: sz.compare_label_1 || '- القيمة الأولى:',
        label2: sz.compare_label_2 || '- القيمة الثانية:',
        v1: runsOf((d.compare && d.compare.v1) || '', sz),
        v2: runsOf((d.compare && d.compare.v2) || '', sz),
      };
    }
    // الخيارات
    const labels = sz.option_labels || QText.OPTION_LABELS;
    let texts = optionTexts(q, sz);
    const items = [];
    for (let k = 0; k < 4; k++) {
      let runs;
      if (q.category === 'analogy') {
        const pr = texts[k] || ['', ''];
        runs = textRuns((pr[0] || '') + ' : ' + (pr[1] || ''), sz, false);
      } else if (q.category === 'context' || type === 'compare') {
        runs = textRuns(texts[k] || '', sz, false);
      } else {
        runs = runsOf(texts[k] || '', sz);
      }
      items.push({ label: labels[k], key: QText.ANSWER_KEYS[k], runs, correct: variant === 'teacher' && q.answer === QText.ANSWER_KEYS[k] });
    }
    block.options = { layout: type === 'long' ? 'list' : 'grid', items };
    return block;
  }

  /**
   * buildDocument({settings, exam, sections:[{kind,title,source,items}], variant})
   * يعيد { blocks, questions:[{section, number, answer, qid}] }
   */
  function buildDocument(input) {
    const settings = input.settings;
    const variant = input.variant || 'student';
    const blocks = [];
    const answerKey = [];
    let counter = 0;
    let blockSeq = 0;
    const nid = (p) => p + (++blockSeq);

    input.sections.forEach((section, sIdx) => {
      if (!section) return;
      if (settings.numbering === 'per_section' || !settings.numbering) counter = 0;
      const kind = section.kind;
      const titleText = kind === 'quant' ? (settings.quant_section_title || 'القسم الكمي') : (settings.verbal_section_title || 'القسم اللفظي');
      blocks.push({ id: nid('st'), type: 'section_title', text: QText.display(titleText, dispOpts(settings)), keepWithNext: true, sectionIndex: sIdx });
      let prevCategory = null;
      for (const node of section.items || []) {
        if (node.type === 'group') {
          const gd = node.data || {};
          const children = node.children || [];
          if (node.group_kind === 'reading') {
            if (kind === 'verbal' && prevCategory !== 'reading') {
              blocks.push(categoryHeader('reading', settings, nid));
            }
            prevCategory = 'reading';
            const paras = (gd.paragraphs || []).filter((p) => !QText.isRichEmpty(p));
            const longText = gd.passage_type === 'long';
            const align = gd.align || (longText ? 'justify' : 'center');
            paras.forEach((p, pi) => {
              let runs = runsOf(p, settings);
              if (longText && gd.numbered !== false && paras.length > 1) {
                runs = textRuns('(' + (pi + 1) + ') ', settings, false).concat(runs);
              }
              blocks.push({ id: nid('pp'), type: 'passage', groupId: node.id, runs, align, index: pi, count: paras.length, long: longText });
            });
          } else if (node.group_kind === 'chart') {
            if (kind === 'verbal') prevCategory = null;
            if (gd.image && gd.image.media_id) {
              blocks.push({ id: nid('ch'), type: 'chart', groupId: node.id, media: gd.image.media_id,
                widthCm: Math.max(1, Number(gd.image.width_cm) || settings.chart_width_cm || 7.5), aspect: gd.image.aspect || null });
            }
          }
          for (const child of children) {
            counter++;
            const qb = buildQuestion(child, counter, settings, variant, kind);
            qb.id = nid('q');
            qb.groupId = node.id;
            blocks.push(qb);
            answerKey.push({ section: kind, sectionIndex: sIdx, number: counter, numberLabel: qb.numberLabel, answer: child.answer || null, qid: child.id });
          }
          continue;
        }
        // سؤال منفرد
        if (kind === 'verbal') {
          const cat = node.category;
          if (cat !== prevCategory) blocks.push(categoryHeader(cat, settings, nid));
          prevCategory = cat;
        }
        counter++;
        const qb = buildQuestion(node, counter, settings, variant, kind);
        qb.id = nid('q');
        blocks.push(qb);
        answerKey.push({ section: kind, sectionIndex: sIdx, number: counter, numberLabel: qb.numberLabel, answer: node.answer || null, qid: node.id });
      }
    });
    if (settings.end_text && input.includeEndText !== false) {
      blocks.push({ id: nid('end'), type: 'end_text', text: QText.display(settings.end_text, dispOpts(settings)) });
    }
    // ربط الكتل: هل الكتلة التالية تابعة (للتفضيل في التوزيع)
    for (let k = 0; k < blocks.length; k++) {
      const b = blocks[k];
      const next = blocks[k + 1];
      b.gapBefore = gapBefore(blocks[k - 1], b, settings);
      if (b.type === 'category_header' || b.type === 'section_title') b.keepWithNext = true;
      if (b.type === 'passage' && next && next.type === 'passage' && next.groupId === b.groupId) b.samePassageNext = true;
    }
    return { blocks, answerKey };
  }

  function categoryHeader(cat, settings, nid) {
    const defs = settings.category_definitions || {};
    const titles = settings.category_titles || {};
    return {
      id: nid('h'), type: 'category_header', category: cat,
      title: QText.display(titles[cat] || VERBAL_CATEGORIES[cat] || cat, dispOpts(settings)),
      definition: QText.display(defs[cat] || '', dispOpts(settings)),
      keepWithNext: true,
    };
  }

  function gapBefore(prev, b, s) {
    if (!prev) return 0;
    const pt = (v, d) => (v == null ? d : Number(v));
    if (b.type === 'end_text') return pt(s.end_text_gap_pt, 18);
    if (prev.type === 'section_title') return pt(s.after_title_gap_pt, 6);
    if (prev.type === 'category_header') return pt(s.after_header_gap_pt, 6);
    if (b.type === 'section_title') return pt(s.section_gap_pt, 16);
    if (b.type === 'category_header') return pt(s.question_gap_pt, 10);
    if (prev.type === 'chart' && b.type === 'question') return pt(s.after_chart_gap_pt, 6);
    if (prev.type === 'passage' && b.type === 'passage' && prev.groupId === b.groupId) return pt(s.paragraph_gap_pt, 4);
    if (prev.type === 'passage' && b.type === 'question') return pt(s.after_passage_gap_pt, 8);
    return pt(s.question_gap_pt, 10);
  }

  global.QModel = { buildDocument, buildQuestion, runsOf, QUANT_CATEGORIES, VERBAL_CATEGORIES, contextSelections, dispOpts };
})(typeof window !== 'undefined' ? window : globalThis);
