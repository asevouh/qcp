/* section_editor.js — صفحة تحرير القسم: قائمة الأسئلة المرتبة (سحب وإفلات/أزرار) + محرر السؤال المحدد مع حفظ تلقائي */
(function (global) {
  'use strict';
  const { Store, toast, confirmBox, guard, num, QModal, QDropdown, MathText, KIND_LABEL, STATUS_LABEL, STATUS_CLASS } = UIX;
  const { QuestionEditor, GroupEditor, CAT_LABEL, defaultData, ensureShape } = QEditors;

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function itemPreviewText(it) {
    const d = it.data || {};
    if (it.type === 'group') {
      if (d.title) return d.title;
      if (it.group_kind === 'reading') return QText.plainText((d.paragraphs || [])[0] || '') || 'نص استيعاب';
      return 'رسم بياني';
    }
    switch (it.category) {
      case 'analogy': return ((d.pair && d.pair.a) || '…') + ' : ' + ((d.pair && d.pair.b) || '…');
      case 'context': return d.sentence || '';
      case 'odd': return (d.options || []).map((o) => QText.plainText(o)).filter(Boolean).join('، ');
      default: return QText.plainText(d.stem || '') || (d.options_type === 'compare' ? 'قارن بين' : '');
    }
  }

  function richHtml(rich) {
    const st = Store.settings || {};
    let out = '';
    for (const r of QText.parseRich(rich || '')) {
      if (r.t === 'text') { const t = QText.escapeText(QText.display(r.text, { digits: st.digits || 'hindi', percent: st.percent_sign })); out += r.bold ? '<b>' + t + '</b>' : t; }
      else if (r.t === 'br') out += ' ';
      else if (r.t === 'math') out += UIX.mathSVG(r.latex, 14).svg;
    }
    return out;
  }
  function itemPreviewHtml(it) {
    const d = it.data || {};
    if (it.type === 'question' && !['analogy', 'context', 'odd'].includes(it.category) && d.stem && /<m>/.test(d.stem)) return richHtml(d.stem);
    const t = itemPreviewText(it);
    return t ? QText.escapeText(t) : '<span class="muted">— فارغ —</span>';
  }

  const ADD_TOP = {
    quant: [
      { cat: 'regular', l: 'سؤال اعتيادي' },
      { cat: 'geometry', l: 'سؤال رسم هندسي' },
      { group: 'chart', l: 'رسم بياني مع أسئلته' },
    ],
    verbal: [
      { cat: 'analogy', l: 'تناظر لفظي' },
      { cat: 'completion', l: 'إكمال جمل' },
      { cat: 'odd', l: 'مفردة شاذة' },
      { cat: 'context', l: 'خطأ سياقي' },
      { group: 'reading', l: 'نص استيعاب مع أسئلته' },
    ],
  };

  const SectionEditor = {
    components: { QuestionEditor, GroupEditor, QModal, QDropdown, MathText },
    props: { id: [String, Number], back: String },
    data() {
      return {
        section: null, tree: [], selectedId: null, draft: null, loadingDraft: false,
        saveState: 'idle', saveError: '', saveTimer: null, savePromise: null, dirty: false,
        listKey: 1, previewTimer: null, statusKey: 1,
        showMeta: false, meta: {}, sources: [],
        pdf: null, pdfBusy: false, itemPreview: null,
        insertCtx: null,
      };
    },
    setup() { return { Store, num, KIND_LABEL, STATUS_LABEL, STATUS_CLASS, CAT_LABEL, ADD_TOP }; },
    computed: {
      kind() { return this.section ? this.section.kind : 'quant'; },
      numbers() {
        const map = {}; const ranges = {}; let n = 0;
        for (const it of this.tree) {
          if (it.type === 'group') {
            const from = n + 1;
            for (const ch of it.children || []) map[ch.id] = ++n;
            ranges[it.id] = (it.children || []).length ? [from, n] : null;
          } else map[it.id] = ++n;
        }
        return { map, ranges, total: n };
      },
      completeCount() {
        let c = 0;
        for (const it of this.tree) {
          if (it.type === 'group') { for (const ch of it.children || []) if (ch.status === 'complete') c++; }
          else if (it.status === 'complete') c++;
        }
        return c;
      },
      selected() { return this.findItem(this.selectedId); },
      selectedParent() {
        for (const it of this.tree) if (it.type === 'group' && (it.children || []).some((c) => c.id === this.selectedId)) return it;
        return null;
      },
      rangeOk() {
        const s = Store.settings || { min_questions: 11, max_questions: 13 };
        return this.numbers.total >= s.min_questions && this.numbers.total <= s.max_questions;
      },
    },
    watch: {
      draft: { deep: true, handler() { if (this.loadingDraft) return; this.dirty = true; this.scheduleSave(); this.schedulePreview(); } },
      tree() { this.$nextTick(() => this.setupSortables()); },
    },
    async mounted() {
      UIX.leaveGuard = () => this.flushSave();
      this._keys = (e) => { if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'س')) { e.preventDefault(); this.flushSave(true); } };
      window.addEventListener('keydown', this._keys);
      this._unload = (e) => { if (this.dirty) { e.preventDefault(); e.returnValue = ''; } };
      window.addEventListener('beforeunload', this._unload);
      await this.load();
    },
    unmounted() {
      if (UIX.leaveGuard) UIX.leaveGuard = null;
      window.removeEventListener('keydown', this._keys);
      window.removeEventListener('beforeunload', this._unload);
      (this._sortables || []).forEach((s) => s.destroy());
    },
    methods: {
      async load() {
        const sec = await guard(() => API.get('/api/sections/' + this.id));
        if (!sec) return;
        this.section = sec;
        this.tree = sec.items || [];
        this.listKey++;
        const first = this.tree[0];
        if (!this.selectedId && first) this.select(first.type === 'group' && (first.children || []).length ? first.id : first.id);
      },
      findItem(id) {
        for (const it of this.tree) {
          if (it.id === id) return it;
          for (const ch of it.children || []) if (ch.id === id) return ch;
        }
        return null;
      },
      // -------------------------------------------------- التحديد والحفظ التلقائي
      async select(id) {
        if (id === this.selectedId && this.draft) return;
        await this.flushSave();
        if (this.dirty) {
          const go = await confirmBox({ title: 'تعديلات لم تُحفظ', message: 'تعذر حفظ آخر تعديلات هذا السؤال (' + (this.saveError || '') + '). إن انتقلت الآن ستُفقد هذه التعديلات. هل تريد الانتقال؟', okText: 'انتقال دون حفظ', danger: true });
          if (!go) return;
          this.dirty = false;
        }
        this.selectedId = id;
        const it = this.findItem(id);
        this.loadingDraft = true;
        this.draft = it ? (it.type === 'question' ? ensureShape(clone(it)) : this.groupDraft(clone(it))) : null;
        this.$nextTick(() => { this.loadingDraft = false; this.dirty = false; this.renderPreview(); });
        this.saveState = 'idle';
      },
      groupDraft(g) {
        g.data = g.data || {};
        if (g.group_kind === 'reading') {
          if (!Array.isArray(g.data.paragraphs) || !g.data.paragraphs.length) g.data.paragraphs = [''];
          if (g.data.numbered === undefined) g.data.numbered = true;
          if (!g.data.passage_type) g.data.passage_type = 'short';
        }
        if (g.data.title === undefined) g.data.title = '';
        return g;
      },
      scheduleSave() {
        this.saveState = 'pending';
        clearTimeout(this.saveTimer);
        this.saveTimer = setTimeout(() => this.doSave(), 700);
      },
      async flushSave(announce) {
        clearTimeout(this.saveTimer);
        if (this.savePromise) await this.savePromise;
        if (this.dirty) await this.doSave();
        if (announce && !this.dirty) toast('كل التعديلات محفوظة', 'ok');
      },
      async doSave() {
        if (!this.draft) return;
        if (this.savePromise) { await this.savePromise; if (!this.dirty) return; }
        const d = this.draft;
        const payload = d.type === 'question' ? { category: d.category, data: clone(d.data), answer: d.answer || null } : { data: clone(d.data) };
        this.dirty = false;
        this.saveState = 'saving';
        this.savePromise = (async () => {
          try {
            const res = await API.put('/api/items/' + d.id, payload);
            const it = this.findItem(d.id);
            if (it) { it.data = res.data; it.answer = res.answer; it.status = res.status; it.issues = res.issues || []; it.category = res.category; }
            if (this.draft && this.draft.id === d.id) { this.loadingDraft = true; this.draft.issues = res.issues || []; this.draft.status = res.status; this.$nextTick(() => { this.loadingDraft = false; }); }
            this.saveState = this.dirty ? 'pending' : 'saved';
          } catch (e) {
            this.dirty = true;
            this.saveState = 'error';
            this.saveError = e.message;
            toast('لم يُحفظ التعديل: ' + e.message, 'error');
          } finally { this.savePromise = null; }
        })();
        await this.savePromise;
      },
      // -------------------------------------------------- المعاينة
      schedulePreview() { clearTimeout(this.previewTimer); this.previewTimer = setTimeout(() => this.renderPreview(), 280); },
      async renderPreview() {
        const box = this.$refs.preview;
        if (!box || !this.draft || !Store.settings) return;
        let node = this.draft;
        if (node.type === 'group') {
          const orig = this.findItem(node.id);
          node = Object.assign({}, node, { children: (orig && orig.children) || [] });
        }
        const ids = [];
        const collect = (n) => { const img = (n.data || {}).image; if (img && img.media_id) ids.push(img.media_id); (n.children || []).forEach(collect); };
        collect(node);
        await Promise.all(ids.map((m) => UIX.mediaInfo(m)));
        box.innerHTML = '';
        try {
          box.appendChild(QRender.previewQuestion(node, Store.settings, this.kind, this.numbers.map[node.id] || (this.numbers.ranges[node.id] || [1])[0], Store.media));
        } catch (e) { box.textContent = 'تعذرت المعاينة: ' + e.message; }
      },
      // -------------------------------------------------- الإضافة والحذف والترتيب
      async addItem(spec, parentId, position) {
        await this.flushSave();
        let item;
        if (spec.group) {
          const data = spec.group === 'chart' ? { title: '', image: null } : { title: '', passage_type: 'short', paragraphs: [''], numbered: true };
          const childCat = spec.group === 'chart' ? 'chart' : 'reading';
          item = { type: 'group', group_kind: spec.group, data, children: [{ type: 'question', category: childCat, data: defaultData(childCat) }] };
        } else {
          item = { type: 'question', category: spec.cat, data: defaultData(spec.cat) };
        }
        const res = await guard(() => API.post('/api/sections/' + this.id + '/items', { item, parent_id: parentId || null, position: position == null ? null : position }));
        if (!res) return;
        this.tree = res.items; this.listKey++;
        await this.select(res.id);
        toast(spec.group ? 'أُنشئت المجموعة مع سؤالها الأول' : 'أُضيف سؤال جديد', 'ok');
      },
      addToGroup(g) { return this.addItem({ cat: g.group_kind === 'chart' ? 'chart' : 'reading' }, g.id, null); },
      openInsert(it, parent) {
        const pos = parent ? parent.children.indexOf(it) + 1 : this.tree.indexOf(it) + 1;
        if (parent) { this.addItem({ cat: parent.group_kind === 'chart' ? 'chart' : 'reading' }, parent.id, pos); return; }
        this.insertCtx = { position: pos, after: it };
      },
      async doInsert(spec) {
        const ctx = this.insertCtx; this.insertCtx = null;
        await this.addItem(spec, null, ctx.position);
      },
      async remove(it, parent) {
        const isGroup = it.type === 'group';
        const n = isGroup ? (it.children || []).length : 0;
        const msg = isGroup ? ('سيتم حذف هذه المجموعة' + (n ? ' مع أسئلتها (' + num(n) + ')' : '') + ' نهائيًا. لا يمكن التراجع.')
          : ('سيتم حذف السؤال رقم ' + num(this.numbers.map[it.id]) + ' نهائيًا، ويُعاد ترقيم ما بعده تلقائيًا دون تغيير ترتيبها.' + (parent ? ' (يبقى ' + (parent.group_kind === 'chart' ? 'الرسم البياني' : 'نص القراءة') + ' المشترك لبقية الأسئلة.)' : ''));
        const yes = await confirmBox({ title: isGroup ? 'حذف مجموعة' : 'حذف سؤال', message: msg, okText: 'نعم، احذف', danger: true });
        if (!yes) return;
        await this.flushSave();
        const res = await guard(() => API.del('/api/items/' + it.id));
        if (!res) return;
        const wasSel = this.selectedId === it.id || (isGroup && (it.children || []).some((c) => c.id === this.selectedId));
        this.tree = res.items; this.listKey++;
        if (wasSel) { this.selectedId = null; this.draft = null; const f = this.tree[0]; if (f) this.select(f.id); }
        toast('تم الحذف', 'ok');
      },
      async duplicate(it) {
        await this.flushSave();
        const res = await guard(() => API.post('/api/items/' + it.id + '/duplicate'));
        if (!res) return;
        this.tree = res.items; this.listKey++;
        await this.select(res.id);
        toast('أُنشئت نسخة بعد العنصر مباشرة', 'ok');
      },
      async move(it, dir) {
        await this.flushSave();
        const res = await guard(() => API.post('/api/items/' + it.id + '/move', { direction: dir }));
        if (res) { this.tree = res; this.listKey++; this.$nextTick(() => this.renderPreview()); }
      },
      orderPayload() {
        return this.tree.map((t) => ({ id: t.id, children: t.type === 'group' ? (t.children || []).map((c) => c.id) : null }));
      },
      async persistOrder() {
        const res = await guard(() => API.post('/api/sections/' + this.id + '/reorder', { order: this.orderPayload() }));
        if (res) { this.tree = res; this.listKey++; toast('حُفظ الترتيب الجديد', 'ok'); this.$nextTick(() => this.renderPreview()); }
        else await this.load();
      },
      setupSortables() {
        (this._sortables || []).forEach((s) => s.destroy());
        this._sortables = [];
        if (!global.Sortable) return;
        const top = this.$refs.toplist;
        if (top) {
          this._sortables.push(Sortable.create(top, {
            handle: '.handle', draggable: '.qitem.top', animation: 140, group: 'top',
            onEnd: (e) => {
              const a = e.oldDraggableIndex, b = e.newDraggableIndex;
              if (a == null || b == null || a === b) { this.listKey++; return; }
              const [m] = this.tree.splice(a, 1);
              this.tree.splice(b, 0, m);
              this.listKey++;
              this.persistOrder();
            },
          }));
        }
        document.querySelectorAll('.qchildren[data-gid]').forEach((el) => {
          const gid = Number(el.dataset.gid);
          this._sortables.push(Sortable.create(el, {
            handle: '.handle', draggable: '.qitem', animation: 140, group: 'g' + gid,
            onEnd: (e) => {
              const g = this.tree.find((t) => t.id === gid);
              const a = e.oldDraggableIndex, b = e.newDraggableIndex;
              if (!g || a == null || b == null || a === b) { this.listKey++; return; }
              const [m] = g.children.splice(a, 1);
              g.children.splice(b, 0, m);
              this.listKey++;
              this.persistOrder();
            },
          }));
        });
      },
      // -------------------------------------------------- تغيير التصنيف
      async changeCategory(v) {
        const d = this.draft;
        if (!d) return;
        if (v === 'chart' || v === 'reading') {
          const yes = await confirmBox({ title: v === 'chart' ? 'تحويل إلى مجموعة رسم بياني' : 'تحويل إلى نص استيعاب',
            message: v === 'chart' ? 'أسئلة الرسوم البيانية تتبع رسمًا مشتركًا. سيُنشأ في هذا الموضع رسم بياني (مجموعة) ويُنقل هذا السؤال إليه ليكون أول أسئلته، ثم ترفع صورة الرسم.'
              : 'أسئلة الاستيعاب تتبع نصًا مشتركًا. سيُنشأ في هذا الموضع نص استيعاب (مجموعة) ويُنقل هذا السؤال إليه ليكون أول أسئلته.', okText: 'متابعة' });
          if (!yes) return;
          await this.flushSave();
          const res = await guard(() => API.post('/api/items/' + d.id + '/wrap', { group_kind: v }));
          if (!res) return;
          this.tree = res.items; this.listKey++;
          await this.select(res.group_id);
          return;
        }
        const from = d.category;
        const data = d.data || {};
        const has = (x) => (typeof x === 'string' ? !QText.isRichEmpty(x) : !!x);
        let loses = false;
        if (from === 'analogy') loses = has(data.pair && data.pair.a) || has(data.pair && data.pair.b) || (data.option_pairs || []).some((p) => has(p.a) || has(p.b));
        else if (from === 'context') loses = has(data.sentence);
        else if (v === 'analogy' || v === 'context') loses = has(data.stem) || (data.options || []).some(has);
        else if (v === 'odd') loses = has(data.stem);
        if (loses) {
          const yes = await confirmBox({ title: 'تغيير التصنيف', message: 'شكل هذا التصنيف مختلف، وقد يُفقد جزء من المحتوى الحالي للسؤال (مثل نص السؤال أو الأطراف). هل تريد المتابعة؟', okText: 'تغيير التصنيف', danger: true });
          if (!yes) return;
        }
        d.category = v;
        ensureShape(d);
        if (v !== 'geometry' && d.data.image === undefined) d.data.image = null;
      },
      // -------------------------------------------------- بيانات القسم والمعاينات
      async openMeta() {
        this.meta = { title: this.section.title, source: this.section.source, status: this.section.status, notes: this.section.notes || '' };
        this.sources = (await guard(() => API.get('/api/sources'))) || [];
        this.showMeta = true;
      },
      async saveMeta() {
        const res = await guard(() => API.put('/api/sections/' + this.id, this.meta), 'حُفظت بيانات القسم');
        if (res) { this.section = res; this.showMeta = false; }
      },
      async setStatus(st) {
        await this.flushSave();
        const res = await guard(() => API.put('/api/sections/' + this.id, { status: st }), 'تم تحديث حالة القسم');
        if (res) this.section = res;
        this.statusKey++;
      },
      async previewSection() {
        await this.flushSave();
        this.pdfBusy = true;
        const res = await guard(() => API.post('/api/sections/' + this.id + '/preview'));
        this.pdfBusy = false;
        if (res) this.pdf = res;
      },
      async previewItem(it) {
        await this.flushSave();
        this.itemPreview = it;
        this.$nextTick(async () => {
          const box = this.$refs.itemPrev;
          if (!box) return;
          const ids = [];
          const collect = (n) => { const img = (n.data || {}).image; if (img && img.media_id) ids.push(img.media_id); (n.children || []).forEach(collect); };
          collect(it);
          await Promise.all(ids.map((m) => UIX.mediaInfo(m)));
          box.innerHTML = '';
          box.appendChild(QRender.previewQuestion(it, Store.settings, this.kind, this.numbers.map[it.id] || (this.numbers.ranges[it.id] || [1])[0], Store.media));
        });
      },
      label(it) { return it.type === 'group' ? (it.group_kind === 'chart' ? 'رسم بياني' : 'نص استيعاب') : (CAT_LABEL[it.category] || it.category); },
      preview(it) { return itemPreviewText(it); },
      previewHtml(it) { return itemPreviewHtml(it); },
      rangeText(it) { const r = this.numbers.ranges[it.id]; return r ? (r[0] === r[1] ? num(r[0]) : num(r[0]) + '–' + num(r[1])) : '—'; },
    },
    template: `
    <div class="page" v-if="section">
      <div class="sec-top">
        <a v-if="back" :href="back" class="btn primary sm">↩ العودة إلى الاختبار</a>
        <a href="#/sections" class="btn ghost sm">→ الأقسام</a>
        <span class="title">{{ section.title }}</span>
        <span class="badge" :class="section.kind">{{ KIND_LABEL[section.kind] }}</span>
        <span class="muted small">المصدر: <b>{{ section.source }}</b></span>
        <span class="spacer"></span>
        <span class="badge" :class="rangeOk ? 'ok' : 'warn'" :title="'المطلوب ' + num(Store.settings && Store.settings.min_questions) + '–' + num(Store.settings && Store.settings.max_questions)">{{ num(numbers.total) }} سؤالًا ({{ num(completeCount) }} مكتمل)</span>
        <select class="select sm" style="width:auto" :key="statusKey" :value="section.status" @change="setStatus($event.target.value)">
          <option value="draft">الحالة: مسودة</option><option value="review">الحالة: يحتاج مراجعة</option><option value="complete">الحالة: مكتمل</option>
        </select>
        <button class="btn sm" @click="openMeta">بيانات القسم</button>
        <button class="btn sm primary" @click="previewSection" :disabled="pdfBusy">{{ pdfBusy ? 'جارٍ التجهيز…' : 'معاينة القسم (PDF)' }}</button>
      </div>

      <div class="split">
        <!-- قائمة الأسئلة -->
        <div class="card">
          <div class="card-head"><h3>الأسئلة بالترتيب</h3><span class="spacer"></span><span class="hint">اسحب ⋮⋮ لتغيير الترتيب</span></div>
          <div class="qlist" ref="toplist" :key="listKey">
            <div v-if="!tree.length" class="empty">لا توجد أسئلة بعد. أضف أول سؤال من الأزرار في الأسفل.</div>
            <div v-for="(it, idx) in tree" :key="it.id" class="qitem top" :class="{qgroup: it.type==='group', selected: selectedId===it.id}">
              <div class="qrow" @click="select(it.id)">
                <span class="handle" title="اسحب لتغيير الموضع" @click.stop>⋮⋮</span>
                <span class="num">{{ it.type==='group' ? rangeText(it) : num(numbers.map[it.id]) }}</span>
                <div class="grow col" style="gap:0">
                  <span class="cat">{{ label(it) }}</span>
                  <span class="txt" v-html="previewHtml(it)"></span>
                </div>
                <span class="st" :title="(it.issues||[]).join('، ') || 'مكتمل'">{{ (it.issues||[]).length ? '⚠️' : '✅' }}</span>
                <span class="acts" @click.stop>
                  <button class="btn xs ghost" title="للأعلى" @click="move(it,'up')" :disabled="idx===0">▲</button>
                  <button class="btn xs ghost" title="للأسفل" @click="move(it,'down')" :disabled="idx===tree.length-1">▼</button>
                  <QDropdown label="⋯" btn-class="btn xs ghost">
                    <button @click="openInsert(it, null)">＋ إدراج عنصر بعد هذا</button>
                    <button @click="previewItem(it)">👁 معاينة</button>
                    <button @click="duplicate(it)">⧉ نسخ</button>
                    <div class="sep"></div>
                    <button @click="remove(it, null)" style="color:#b42318">🗑 حذف</button>
                  </QDropdown>
                </span>
              </div>
              <div v-if="it.type==='group'" class="qchildren" :data-gid="it.id">
                <div v-for="(ch, cidx) in it.children" :key="ch.id" class="qitem" :class="{selected: selectedId===ch.id}">
                  <div class="qrow" @click="select(ch.id)">
                    <span class="handle" @click.stop>⋮⋮</span>
                    <span class="num">{{ num(numbers.map[ch.id]) }}</span>
                    <span class="txt grow" v-html="previewHtml(ch)"></span>
                    <span class="st" :title="(ch.issues||[]).join('، ') || 'مكتمل'">{{ (ch.issues||[]).length ? '⚠️' : '✅' }}</span>
                    <span class="acts" @click.stop>
                      <button class="btn xs ghost" @click="move(ch,'up')" :disabled="cidx===0">▲</button>
                      <button class="btn xs ghost" @click="move(ch,'down')" :disabled="cidx===it.children.length-1">▼</button>
                      <QDropdown label="⋯" btn-class="btn xs ghost">
                        <button @click="openInsert(ch, it)">＋ إدراج سؤال بعده</button>
                        <button @click="previewItem(ch)">👁 معاينة</button>
                        <button @click="duplicate(ch)">⧉ نسخ</button>
                        <div class="sep"></div>
                        <button @click="remove(ch, it)" style="color:#b42318">🗑 حذف</button>
                      </QDropdown>
                    </span>
                  </div>
                </div>
                <div><button class="btn xs" @click.stop="addToGroup(it)">＋ سؤال لهذه المجموعة</button></div>
              </div>
            </div>
          </div>
          <div class="add-bar">
            <span class="lbl" style="align-self:center">إضافة في النهاية:</span>
            <button v-for="a in ADD_TOP[kind]" :key="a.l" class="btn sm" :class="{primary: !a.group}" @click="addItem(a, null, null)">＋ {{ a.l }}</button>
          </div>
        </div>

        <!-- المحرر -->
        <div class="card editor-pane" v-if="draft">
          <div class="card-head">
            <h3 v-if="draft.type==='question'">السؤال {{ num(numbers.map[draft.id]) }}</h3>
            <h3 v-else>{{ draft.group_kind==='chart' ? 'رسم بياني مشترك' : 'نص استيعاب مقروء' }} <span class="muted small">(الأسئلة {{ rangeText(findItem(draft.id) || draft) }})</span></h3>
            <span class="spacer"></span>
            <span class="save-state" :class="saveState">{{ {idle:'', pending:'تعديلات لم تُحفظ بعد…', saving:'جارٍ الحفظ…', saved:'✓ تم الحفظ', error:'✗ لم يُحفظ'}[saveState] }}</span>
            <button class="btn sm" @click="flushSave(true)">حفظ</button>
          </div>
          <div class="card-body col" style="gap:14px">
            <div v-if="(draft.issues||[]).length" class="alert warn issues"><b>{{ draft.type==='question' ? 'السؤال محفوظ كمسودة' : 'ملاحظة' }}:</b>
              <ul><li v-for="x in draft.issues" :key="x">{{ x }}</li></ul></div>
            <QuestionEditor v-if="draft.type==='question'" :key="'q' + draft.id" :q="draft" :section-kind="kind" :group-kind="selectedParent ? selectedParent.group_kind : null" :number="numbers.map[draft.id]" @change-category="changeCategory"/>
            <template v-else>
              <GroupEditor :key="'g' + draft.id" :g="draft" :section-kind="kind"/>
              <div class="sec-pick col" style="gap:6px">
                <div class="row"><b>أسئلة المجموعة</b><span class="spacer"></span><button class="btn sm primary" @click="addToGroup(findItem(draft.id))">＋ إضافة سؤال</button></div>
                <div v-for="ch in (findItem(draft.id)||{}).children || []" :key="ch.id" class="row qrow" style="background:#fff" @click="select(ch.id)">
                  <span class="num">{{ num(numbers.map[ch.id]) }}</span><span class="txt grow">{{ preview(ch) || '— فارغ —' }}</span><span class="btn xs">تحرير</span></div>
                <div class="hint">يمكن إعادة ترتيب أسئلة المجموعة بالسحب داخلها في القائمة.</div>
              </div>
            </template>
            <div>
              <div class="lbl" style="margin-bottom:6px">معاينة تقريبية بعرض عمود الورقة الحقيقي</div>
              <div class="qpreview"><div ref="preview"></div></div>
              <div class="preview-note">هذه معاينة سريعة للسؤال وحده. المعاينة الدقيقة للطباعة: زر «معاينة القسم (PDF)» أو معاينة الاختبار.</div>
            </div>
          </div>
        </div>
        <div class="card empty" v-else>اختر سؤالًا من القائمة لتحريره، أو أضف سؤالًا جديدًا.</div>
      </div>

      <QModal v-if="insertCtx" title="إدراج عنصر في هذا الموضع" @close="insertCtx=null">
        <div class="col">
          <div class="hint">سيُدرج العنصر الجديد بعد «{{ preview(insertCtx.after) || label(insertCtx.after) }}»، ويُعاد الترقيم تلقائيًا دون تغيير ترتيب بقية الأسئلة.</div>
          <div class="row wrap"><button v-for="a in ADD_TOP[kind]" :key="a.l" class="btn" :class="{primary: !a.group}" @click="doInsert(a)">＋ {{ a.l }}</button></div>
        </div>
      </QModal>

      <QModal v-if="showMeta" title="بيانات القسم" @close="showMeta=false">
        <div class="col">
          <div class="field"><label>عنوان القسم</label><input class="input" v-model="meta.title"></div>
          <div class="field"><label>مصدر القسم (يظهر في ترويسة الاختبار)</label><input class="input" v-model="meta.source" list="srcs"><datalist id="srcs"><option v-for="s in sources" :key="s" :value="s"></option></datalist></div>
          <div class="field"><label>الحالة</label><select class="select" v-model="meta.status"><option value="draft">مسودة</option><option value="review">يحتاج مراجعة</option><option value="complete">مكتمل</option></select></div>
          <div class="field"><label>ملاحظات (اختياري)</label><textarea class="input" v-model="meta.notes" rows="2"></textarea></div>
          <div class="hint">نوع القسم ({{ KIND_LABEL[section.kind] }}) ثابت بعد الإنشاء.</div>
        </div>
        <template #foot><button class="btn primary" @click="saveMeta">حفظ</button><button class="btn" @click="showMeta=false">إلغاء</button></template>
      </QModal>

      <QModal v-if="itemPreview" title="معاينة" @close="itemPreview=null"><div class="qpreview"><div ref="itemPrev"></div></div></QModal>

      <QModal v-if="pdf" title="معاينة القسم (PDF — مطابقة للطباعة)" wide @close="pdf=null">
        <div v-if="pdf.report && pdf.report.primaryFontLoaded===false" class="alert warn" style="margin-bottom:8px">خط {{ Store.settings && Store.settings.font_family }} غير موجود على هذا الجهاز؛ استُخدم خط بديل في هذه المعاينة.</div>
        <iframe class="pdf-frame" :src="pdf.url" style="height:75vh"></iframe>
      </QModal>
    </div>
    <div class="page" v-else><div class="empty">جارٍ التحميل…</div></div>`,
  };

  global.QSectionEditor = SectionEditor;
})(window);
