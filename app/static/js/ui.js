/* ui.js — الحالة العامة ومكونات الواجهة المشتركة (نوافذ، تنبيهات، حقل النص الغني، محرر المعادلات، حقل الصورة) */
(function (global) {
  'use strict';
  const { reactive, ref, computed, watch, nextTick, h } = Vue;

  // ------------------------------------------------------------ الحالة العامة
  const Store = reactive({
    settings: null,
    system: null,
    media: {},        // id -> {w, h, url}
    sources: [],
  });

  async function loadSettings() {
    Store.settings = await API.get('/api/settings');
    return Store.settings;
  }
  async function loadSystem() {
    try { Store.system = await API.get('/api/system'); } catch (e) { /* ignore */ }
    return Store.system;
  }
  async function mediaInfo(id) {
    if (!id) return null;
    if (Store.media[id]) return Store.media[id];
    try {
      const m = await API.get('/api/media/' + id);
      Store.media[id] = { w: m.width, h: m.height, url: m.url };
    } catch (e) { Store.media[id] = { w: 4, h: 3, url: '/media/' + id, missing: true }; }
    return Store.media[id];
  }

  // ------------------------------------------------------------ التنبيهات والتأكيد
  const toasts = reactive([]);
  let toastSeq = 0;
  function toast(msg, type, ms) {
    const id = ++toastSeq;
    toasts.push({ id, msg, type: type || 'info' });
    setTimeout(() => { const k = toasts.findIndex((t) => t.id === id); if (k >= 0) toasts.splice(k, 1); }, ms || (type === 'error' ? 7000 : 3200));
  }
  const dialog = reactive({ open: false, title: '', message: '', okText: 'موافق', cancelText: 'إلغاء', danger: false, requireText: '', typed: '', resolve: null, details: null });
  function confirmBox(o) {
    return new Promise((resolve) => {
      Object.assign(dialog, { open: true, title: o.title || 'تأكيد', message: o.message || '', okText: o.okText || 'تأكيد', cancelText: o.cancelText || 'إلغاء',
        danger: !!o.danger, requireText: o.requireText || '', typed: '', details: o.details || null, resolve });
    });
  }
  function closeDialog(v) {
    const r = dialog.resolve;
    dialog.open = false; dialog.resolve = null;
    if (r) r(v);
  }
  async function guard(fn, okMsg) {
    try {
      const r = await fn();
      if (okMsg) toast(okMsg, 'ok');
      return r;
    } catch (e) {
      toast(e.message || String(e), 'error');
      return undefined;
    }
  }

  // ------------------------------------------------------------ معادلات
  function mathOpts(sizePx) {
    const s = Store.settings || {};
    return { size: sizePx || 20, family: QRender.fontStack(s), digits: s.digits || 'hindi', percent: s.percent_sign || '⁒', decimal: s.decimal_style || 'arabic', fracScale: Number(s.frac_scale) || 0.82 };
  }
  function mathSVG(latex, sizePx) {
    return QMath.render(latex, mathOpts(sizePx));
  }

  const mathState = reactive({ open: false, latex: '', original: '', editing: false, resolve: null });
  function openMath(latex) {
    return new Promise((resolve) => {
      Object.assign(mathState, { open: true, latex: latex || '', original: latex || '', editing: !!latex, resolve });
    });
  }

  const PALETTE = [
    { g: 'البُنى', items: [
      { l: 'كسر', t: '\\frac{□}{□}', title: 'كسر: البسط ثم المقام' },
      { l: 'جذر', t: '\\sqrt{□}', title: 'جذر تربيعي' },
      { l: 'جذر نوني', t: '\\sqrt[□]{□}', title: 'جذر بدرجة: الدرجة ثم ما تحت الجذر' },
      { l: 'أُس', t: '^{□}', title: 'أس (يوضع بعد الأساس)' },
      { l: 'دليل سفلي', t: '_{□}', title: 'دليل سفلي (يوضع بعد الرمز)' },
      { l: '( ) ممتد', t: '\\left( □ \\right)', title: 'قوسان يمتدان بحسب المحتوى' },
      { l: 'خط فوق', t: '\\overline{□}', title: 'قطعة مستقيمة: خط فوق الحروف' },
      { l: 'قوس فوق', t: '\\overarc{□}', title: 'قوس فوق الحروف' },
      { l: 'نص', t: '\\text{□}', title: 'نص عادي داخل المعادلة' },
    ] },
    { g: 'العمليات', items: [
      { l: '+', t: '+' }, { l: '−', t: '-' }, { l: '×', t: '\\times ' }, { l: '÷', t: '\\div ' }, { l: '=', t: '=' },
      { l: '≠', t: '\\ne ' }, { l: '<', t: '<' }, { l: '>', t: '>' }, { l: '≤', t: '\\le ' }, { l: '≥', t: '\\ge ' },
      { l: '≈', t: '\\approx ' }, { l: '±', t: '\\pm ' }, { l: '⋅', t: '\\cdot ' }, { l: '( )', t: '(□)' },
    ] },
    { g: 'رموز', items: [
      { l: '⁒', t: '\\%', title: 'نسبة مئوية' }, { l: 'ط', t: 'ط', title: 'ط (باي)' }, { l: 'π', t: '\\pi ' }, { l: '°', t: '\\degree ' },
      { l: '∠', t: '\\angle ' }, { l: '△', t: '\\triangle ' }, { l: '⊥', t: '\\perp ' }, { l: '∥', t: '\\parallel ' }, { l: '∞', t: '\\infty ' }, { l: '…', t: '\\ldots ' },
    ] },
    { g: 'متغيرات', items: ['س', 'ص', 'ع', 'ن', 'ل', 'م', 'ك', 'هـ', 'أ', 'ب', 'جـ', 'د'].map((x) => ({ l: x, t: x })) },
  ];

  const MathDialog = {
    setup() {
      const src = ref(null);
      const st = mathState;
      const preview = computed(() => mathSVG(st.latex, 36));
      const small = computed(() => mathSVG(st.latex, 17.3));
      function insert(tpl) {
        const ta = src.value;
        const s = st.latex;
        const a = ta ? ta.selectionStart : s.length;
        const b = ta ? ta.selectionEnd : s.length;
        let t = tpl;
        const selected = s.slice(a, b);
        if (selected && t.includes('□') && selected !== '□') t = t.replace('□', selected);
        st.latex = s.slice(0, a) + t + s.slice(b);
        nextTick(() => {
          if (!ta) return;
          ta.focus();
          const k = st.latex.indexOf('□', a);
          if (k >= 0 && k < a + t.length) ta.setSelectionRange(k, k + 1);
          else ta.setSelectionRange(a + t.length, a + t.length);
        });
      }
      function nextHole(e) {
        const ta = src.value;
        if (!ta) return;
        const k = st.latex.indexOf('□', ta.selectionEnd);
        const k2 = k >= 0 ? k : st.latex.indexOf('□');
        if (k2 >= 0) { e.preventDefault(); ta.setSelectionRange(k2, k2 + 1); }
      }
      function done(v) {
        const r = st.resolve;
        st.open = false; st.resolve = null;
        if (r) r(v);
      }
      function ok() {
        const v = (st.latex || '').trim();
        if (!v) { done(st.editing ? '__delete__' : null); return; }
        if (v.includes('□')) { toast('ما زالت في المعادلة خانات فارغة (□). املأها أو احذفها.', 'error'); return; }
        if (preview.value.error) { toast('في المعادلة خطأ: ' + preview.value.error, 'error'); return; }
        done(v);
      }
      watch(() => st.open, (o) => { if (o) nextTick(() => { if (src.value) { src.value.focus(); src.value.setSelectionRange(st.latex.length, st.latex.length); } }); });
      window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && st.open) { e.stopPropagation(); done(null); } }, true);
      window.addEventListener('hashchange', () => { if (st.open) done(null); });
      return { st, src, preview, small, PALETTE, insert, nextHole, ok, done };
    },
    template: `
    <div class="modal-back" v-if="st.open" @mousedown.self="done(null)">
      <div class="modal wide">
        <div class="modal-head"><h3>{{ st.editing ? 'تعديل معادلة' : 'إدراج معادلة' }}</h3><span class="spacer"></span>
          <span class="hint">اختر من الأزرار، ثم اكتب الأرقام والرموز في الخانات □ (زر Tab ينقلك للخانة التالية)</span></div>
        <div class="modal-body col">
          <div class="palette">
            <div class="grp" v-for="g in PALETTE" :key="g.g"><span class="gl">{{ g.g }}</span>
              <button v-for="it in g.items" :key="it.l+it.t" class="btn sm" :title="it.title || it.t" @mousedown.prevent="insert(it.t)">{{ it.l }}</button>
            </div>
          </div>
          <div class="field"><label>صيغة المعادلة (تُبنى بالأزرار ويمكن تعديلها يدويًا)</label>
            <textarea ref="src" class="input math-src" rows="2" v-model="st.latex" @keydown.tab="nextHole" @keydown.enter.exact.prevent="ok" spellcheck="false"></textarea>
          </div>
          <div class="lbl">المعاينة (كما ستظهر في الملف بالاتجاه العربي)</div>
          <div class="math-preview" :class="{err: preview.error}">
            <span v-if="!st.latex.trim()" class="muted small">اكتب المعادلة أو اختر من الأزرار</span>
            <span v-else-if="preview.error" class="small">⚠ {{ preview.error }}</span>
            <span v-else v-html="preview.svg"></span>
          </div>
          <div class="row small muted" v-if="st.latex.trim() && !preview.error">بالحجم الفعلي داخل جملة: <span style="font-size:17.3px;color:#000">إذا كان <span v-html="small.svg"></span> فما الناتج؟</span></div>
        </div>
        <div class="modal-foot">
          <button class="btn primary" @click="ok">{{ st.editing ? 'تحديث المعادلة' : 'إدراج' }}</button>
          <button class="btn" @click="done(null)">إلغاء</button>
          <span class="spacer"></span>
          <button v-if="st.editing" class="btn danger" @click="done('__delete__')">حذف المعادلة</button>
        </div>
      </div>
    </div>`,
  };

  // ------------------------------------------------------------ النص الغني (نص + غامق + معادلات + فراغات)
  function chipNode(latex) {
    const span = document.createElement('span');
    span.className = 'mchip';
    span.contentEditable = 'false';
    span.dataset.latex = latex;
    const r = mathSVG(latex, 19);
    if (r.error) { span.classList.add('err'); span.textContent = latex; span.title = 'خطأ في المعادلة: ' + r.error; }
    else { span.innerHTML = r.svg; span.title = 'انقر لتعديل المعادلة'; }
    return span;
  }

  function serializeArea(area, multiline) {
    const runs = [];
    function walk(node, bold) {
      for (const ch of node.childNodes) {
        if (ch.nodeType === 3) {
          const parts = ch.nodeValue.replace(/​/g, '').split('\n');
          parts.forEach((p, k) => {
            if (k > 0) runs.push({ t: 'br' });
            if (p) runs.push({ t: 'text', text: p, bold });
          });
        } else if (ch.nodeType === 1) {
          if (ch.classList && ch.classList.contains('mchip')) { runs.push({ t: 'math', latex: ch.dataset.latex || '' }); continue; }
          const tag = ch.tagName;
          if (tag === 'BR') { runs.push({ t: 'br' }); continue; }
          if (tag === 'DIV' || tag === 'P') {
            if (runs.length && runs[runs.length - 1].t !== 'br') runs.push({ t: 'br' });
            walk(ch, bold);
            continue;
          }
          const isBold = bold || tag === 'B' || tag === 'STRONG' || (ch.style && (ch.style.fontWeight === 'bold' || Number(ch.style.fontWeight) >= 600));
          walk(ch, isBold);
        }
      }
    }
    walk(area, false);
    while (runs.length && runs[runs.length - 1].t === 'br') runs.pop();
    let out = runs;
    if (!multiline) out = runs.map((r) => (r.t === 'br' ? { t: 'text', text: ' ', bold: false } : r));
    // دمج
    const merged = [];
    for (const r of out) {
      const l = merged[merged.length - 1];
      if (l && l.t === 'text' && r.t === 'text' && l.bold === r.bold) l.text += r.text;
      else merged.push(Object.assign({}, r));
    }
    return QText.serializeRich(merged);
  }

  // ------------------------------------------------------------ التنقل بين الحقول بمفتاح Enter
  // داخل أي حاوية تحمل الصنف .qnav: Enter ينقل إلى الحقل التالي (data-nav) بترتيبه في الصفحة،
  // وShift+Enter يُدرج سطرًا جديدًا في الحقول متعددة الأسطر.
  function navFields(root) {
    return Array.from(root.querySelectorAll('[data-nav]')).filter((x) => !x.disabled && x.offsetParent !== null);
  }
  function focusField(f) {
    f.focus();
    if (f.isContentEditable) {
      const r = document.createRange();
      r.selectNodeContents(f); r.collapse(false);
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
    } else if (typeof f.setSelectionRange === 'function') {
      const n = (f.value || '').length;
      try { f.setSelectionRange(n, n); } catch (_) { /* حقول لا تدعم التحديد */ }
    }
  }
  function onNavKey(e) {
    if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey || e.isComposing) return;
    const t = e.target;
    if (!t || !t.closest || !t.matches('[data-nav]')) return;
    const root = t.closest('.qnav');
    if (!root) return;
    e.preventDefault();
    const list = navFields(root);
    const k = list.indexOf(t);
    if (k >= 0 && k + 1 < list.length) focusField(list[k + 1]);
  }

  const RichInput = {
    props: {
      modelValue: { type: String, default: '' },
      multiline: { type: Boolean, default: false },
      placeholder: { type: String, default: '' },
      tools: { type: Array, default: () => ['bold', 'math'] },
      dense: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    data() { return { last: null, savedRange: null }; },
    mounted() { this.renderFrom(this.modelValue || ''); },
    watch: { modelValue(v) { if ((v || '') !== this.last) this.renderFrom(v || ''); } },
    methods: {
      has(t) { return this.tools.includes(t); },
      renderFrom(v) {
        const area = this.$refs.area;
        area.innerHTML = '';
        for (const r of QText.parseRich(v)) {
          if (r.t === 'text') {
            const tn = document.createTextNode(r.text);
            if (r.bold) { const b = document.createElement('b'); b.appendChild(tn); area.appendChild(b); } else area.appendChild(tn);
          } else if (r.t === 'br') area.appendChild(document.createElement('br'));
          else if (r.t === 'math') area.appendChild(chipNode(r.latex));
        }
        this.last = v;
      },
      emitNow() {
        const v = serializeArea(this.$refs.area, this.multiline);
        this.last = v;
        this.$emit('update:modelValue', v);
      },
      onInput() { this.emitNow(); },
      saveRange() {
        const sel = window.getSelection();
        if (sel.rangeCount && this.$refs.area.contains(sel.getRangeAt(0).commonAncestorContainer)) this.savedRange = sel.getRangeAt(0).cloneRange();
      },
      currentRange() {
        const area = this.$refs.area;
        const sel = window.getSelection();
        if (sel.rangeCount && area.contains(sel.getRangeAt(0).commonAncestorContainer)) return sel.getRangeAt(0);
        if (this.savedRange && area.contains(this.savedRange.commonAncestorContainer)) return this.savedRange;
        const r = document.createRange();
        r.selectNodeContents(area); r.collapse(false);
        return r;
      },
      insertNodes(nodes) {
        const area = this.$refs.area;
        const range = this.currentRange();
        range.deleteContents();
        let last = null;
        for (let k = nodes.length - 1; k >= 0; k--) { range.insertNode(nodes[k]); if (!last) last = nodes[k]; }
        const sel = window.getSelection();
        const r2 = document.createRange();
        r2.setStartAfter(last); r2.collapse(true);
        sel.removeAllRanges(); sel.addRange(r2);
        this.savedRange = r2.cloneRange();
        area.focus();
        this.emitNow();
      },
      insertBlank() {
        this.$refs.area.focus();
        const r = this.currentRange();
        const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
        document.execCommand('insertText', false, '........');
        this.emitNow();
      },
      bold() { this.$refs.area.focus(); document.execCommand('bold'); this.emitNow(); },
      async insertMath() {
        this.saveRange();
        const latex = await openMath('');
        if (latex && latex !== '__delete__') {
          this.insertNodes([chipNode(latex), document.createTextNode('​')]);
        }
      },
      async onClick(e) {
        const chip = e.target.closest && e.target.closest('.mchip');
        if (!chip || !this.$refs.area.contains(chip)) { this.saveRange(); return; }
        const latex = await openMath(chip.dataset.latex || '');
        if (latex === '__delete__') { chip.remove(); this.emitNow(); }
        else if (latex) { chip.replaceWith(chipNode(latex)); this.emitNow(); }
      },
      onKey(e) {
        if (e.key === 'Enter') {
          // داخل محرر السؤال: Enter للانتقال إلى الحقل التالي (يعالجه onNavKey)، وShift+Enter لسطر جديد
          if (!e.shiftKey && !e.isComposing && this.$refs.area.closest('.qnav')) return;
          e.preventDefault();
          if (this.multiline) { document.execCommand('insertLineBreak'); this.emitNow(); }
          return;
        }
        if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B' || e.key === 'ذ' || e.code === 'KeyB')) { e.preventDefault(); this.bold(); return; }
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === 'KeyM')) { e.preventDefault(); this.insertMath(); }
      },
      onPaste(e) {
        e.preventDefault();
        let text = (e.clipboardData || window.clipboardData).getData('text/plain') || '';
        if (!this.multiline) text = text.replace(/\s*\n\s*/g, ' ');
        document.execCommand('insertText', false, text);
        this.emitNow();
      },
    },
    template: `
    <div class="rich" :class="multiline ? 'multi' : 'single'">
      <div class="rich-tools" v-if="tools.length">
        <button v-if="has('bold')" type="button" class="btn ghost" title="خط عريض (Ctrl+B)" @mousedown.prevent="bold"><b>B</b> عريض</button>
        <button v-if="has('math')" type="button" class="btn ghost" title="إدراج معادلة رياضية (Ctrl+Shift+M)" @mousedown.prevent="insertMath">∑ معادلة</button>
        <button v-if="has('blank')" type="button" class="btn ghost" title="إدراج ثماني نقاط في موضع المؤشر" @mousedown.prevent="insertBlank">⋯ إضافة فراغ</button>
      </div>
      <div ref="area" class="rich-area" contenteditable="true" data-nav :data-placeholder="placeholder"
        @input="onInput" @keydown="onKey" @paste="onPaste" @click="onClick" @keyup="saveRange" @mouseup="saveRange" @blur="saveRange"></div>
    </div>`,
  };

  // ------------------------------------------------------------ حقل الصورة
  const ImageField = {
    props: { modelValue: { type: Object, default: null }, defaultWidth: { type: Number, default: 4.5 }, label: { type: String, default: 'الصورة' }, maxWidth: { type: Number, default: 8.3 } },
    emits: ['update:modelValue'],
    data() { return { busy: false, drag: false, info: null }; },
    watch: { 'modelValue.media_id': { immediate: true, async handler(id) { this.info = id ? await mediaInfo(id) : null; } } },
    computed: {
      width: {
        get() { return this.modelValue && this.modelValue.width_cm ? this.modelValue.width_cm : this.defaultWidth; },
        set(v) { this.$emit('update:modelValue', Object.assign({}, this.modelValue, { width_cm: Math.max(1, Math.min(Number(v) || this.defaultWidth, 20)) })); },
      },
      heightCm() { return this.info && this.info.w ? (Math.min(this.width, this.maxWidth) * this.info.h / this.info.w).toFixed(1) : null; },
    },
    methods: {
      pick() { this.$refs.file.click(); },
      async onFile(e) { const f = e.target.files && e.target.files[0]; e.target.value = ''; if (f) await this.upload(f); },
      async upload(f) {
        this.busy = true;
        try {
          const m = await API.upload('/api/media', f);
          Store.media[m.id] = { w: m.width, h: m.height, url: m.url };
          this.$emit('update:modelValue', { media_id: m.id, width_cm: (this.modelValue && this.modelValue.width_cm) || this.defaultWidth });
          toast('تم رفع الصورة', 'ok');
        } catch (err) { toast(err.message, 'error'); }
        this.busy = false;
      },
      async remove() {
        const yes = await confirmBox({ title: 'حذف الصورة', message: 'هل تريد إزالة هذه الصورة من السؤال؟ (يمكن رفعها مرة أخرى لاحقًا)', okText: 'نعم، أزل الصورة', danger: true });
        if (yes) this.$emit('update:modelValue', null);
      },
      onDrop(e) { this.drag = false; const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) this.upload(f); },
      onPaste(e) {
        const items = (e.clipboardData && e.clipboardData.items) || [];
        for (const it of items) { if (it.type && it.type.startsWith('image/')) { e.preventDefault(); this.upload(it.getAsFile()); return; } }
      },
    },
    template: `
    <div class="col" style="gap:6px">
      <div class="lbl">{{ label }}</div>
      <div class="img-field" :class="{drag}" tabindex="0" @dragover.prevent="drag=true" @dragleave="drag=false" @drop.prevent="onDrop" @paste="onPaste">
        <input ref="file" type="file" accept="image/*" class="hidden" @change="onFile">
        <template v-if="modelValue && modelValue.media_id">
          <img :src="'/media/' + modelValue.media_id" alt="">
          <div class="col" style="gap:8px">
            <div class="row"><button type="button" class="btn sm" @click="pick" :disabled="busy">استبدال الصورة</button>
              <button type="button" class="btn sm danger" @click="remove" :disabled="busy">حذف الصورة</button></div>
            <div class="row small"><label class="muted">العرض في الملف:</label>
              <input class="input sm" style="width:80px" type="number" step="0.1" min="1" :max="maxWidth" v-model.lazy="width"> سم
              <span class="muted" v-if="heightCm">(الارتفاع ≈ {{ heightCm }} سم)</span></div>
            <div class="hint" v-if="width > maxWidth">العرض أكبر من عرض العمود ({{ maxWidth.toFixed(1) }} سم)، سيُصغَّر تلقائيًا ليتسع.</div>
            <div class="hint" v-if="info && info.missing" style="color:#b42318">ملف الصورة غير موجود!</div>
          </div>
        </template>
        <template v-else>
          <div class="col" style="gap:6px">
            <button type="button" class="btn primary" @click="pick" :disabled="busy">{{ busy ? 'جارٍ الرفع…' : 'رفع صورة' }}</button>
            <span class="hint">أو اسحب الصورة وأفلتها هنا، أو انسخها والصقها (Ctrl+V) بعد النقر على هذا المربع.</span>
          </div>
        </template>
      </div>
    </div>`,
  };

  // ------------------------------------------------------------ نافذة عامة وقائمة منسدلة
  const QModal = {
    props: { title: String, wide: Boolean },
    emits: ['close'],
    mounted() { this._esc = (e) => { if (e.key === 'Escape' && !mathState.open && !dialog.open) this.$emit('close'); }; window.addEventListener('keydown', this._esc); },
    unmounted() { window.removeEventListener('keydown', this._esc); },
    template: `
    <div class="modal-back" @mousedown.self="$emit('close')">
      <div class="modal" :class="{wide}">
        <div class="modal-head"><h3>{{ title }}</h3><span class="spacer"></span><button class="btn ghost sm" @click="$emit('close')">✕</button></div>
        <div class="modal-body"><slot></slot></div>
        <div class="modal-foot" v-if="$slots.foot"><slot name="foot"></slot></div>
      </div>
    </div>`,
  };

  const QDropdown = {
    props: { label: String, btnClass: { type: String, default: 'btn sm' } },
    data() { return { open: false }; },
    mounted() { this._h = (e) => { if (!this.$el.contains(e.target)) this.open = false; }; document.addEventListener('mousedown', this._h); },
    unmounted() { document.removeEventListener('mousedown', this._h); },
    template: `
    <div class="dropdown">
      <button type="button" :class="btnClass" @click.stop="open=!open">{{ label }} ▾</button>
      <div class="dropdown-menu" v-if="open" @click="open=false"><slot></slot></div>
    </div>`,
  };

  const MathText = {
    // عرض نص غني (للمعاينات المختصرة)
    props: { value: String, size: { type: Number, default: 16 } },
    computed: {
      html() {
        let out = '';
        for (const r of QText.parseRich(this.value || '')) {
          const disp = QText.display(r.text || '', { digits: (Store.settings || {}).digits || 'hindi', percent: (Store.settings || {}).percent_sign });
          if (r.t === 'text') out += r.bold ? '<b>' + QText.escapeText(disp) + '</b>' : QText.escapeText(disp);
          else if (r.t === 'br') out += ' ';
          else if (r.t === 'math') out += mathSVG(r.latex, this.size * 1.0).svg;
        }
        return out;
      },
    },
    template: `<span v-html="html"></span>`,
  };

  function fmtDate(s) {
    if (!s) return '';
    try {
      const d = new Date(s);
      return QText.display(d.toLocaleDateString('ar-SA-u-ca-gregory-nu-arab', { year: 'numeric', month: 'short', day: 'numeric' }) + ' ' +
        d.toLocaleTimeString('ar-SA-u-nu-arab', { hour: '2-digit', minute: '2-digit' }), { digits: 'hindi' });
    } catch (e) { return s; }
  }
  function num(n) { return QText.display(String(n == null ? '' : n), { digits: 'hindi' }); }

  const KIND_LABEL = { quant: 'كمي', verbal: 'لفظي' };
  const STATUS_LABEL = { draft: 'مسودة', complete: 'مكتمل', review: 'يحتاج مراجعة' };
  const STATUS_CLASS = { draft: 'warn', complete: 'ok', review: 'danger' };

  global.UIX = {
    Store, loadSettings, loadSystem, mediaInfo, toasts, toast, dialog, confirmBox, closeDialog, guard, mathState, openMath, mathSVG,
    MathDialog, RichInput, ImageField, onNavKey, QModal, QDropdown, MathText, fmtDate, num, KIND_LABEL, STATUS_LABEL, STATUS_CLASS,
  };
})(window);
