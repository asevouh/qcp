/* editors.js — محررات الأسئلة الديناميكية بحسب التصنيف، ومحررات المجموعات (رسم بياني / نص استيعاب) */
(function (global) {
  'use strict';
  const { RichInput, ImageField, Store, toast, confirmBox, num } = UIX;
  const KEYS = ['a', 'b', 'c', 'd'];
  const LABELS = ['أ', 'ب', 'جـ', 'د'];

  const CAT = {
    quant: [
      { v: 'regular', l: 'اعتيادي' },
      { v: 'chart', l: 'رسوم بيانية' },
      { v: 'geometry', l: 'رسم هندسي' },
    ],
    verbal: [
      { v: 'analogy', l: 'تناظر لفظي' },
      { v: 'completion', l: 'إكمال جمل' },
      { v: 'odd', l: 'مفردة شاذة' },
      { v: 'context', l: 'خطأ سياقي' },
      { v: 'reading', l: 'استيعاب المقروء' },
    ],
  };
  const CAT_LABEL = {};
  for (const k in CAT) for (const c of CAT[k]) CAT_LABEL[c.v] = c.l;

  function defaultData(cat) {
    const four = () => ['', '', '', ''];
    switch (cat) {
      case 'analogy': return { pair: { a: '', b: '' }, options_type: 'short', option_pairs: [0, 1, 2, 3].map(() => ({ a: '', b: '' })) };
      case 'odd': return { options_type: 'short', options: four() };
      case 'context': return { sentence: '', selections: [], options_type: 'short' };
      case 'geometry': return { stem: '', options_type: 'short', options: four(), compare: { v1: '', v2: '' }, image: null, image_placement: 'side' };
      default: return { stem: '', options_type: 'short', options: four(), compare: { v1: '', v2: '' } };
    }
  }
  function ensureShape(q) {
    const d = q.data || (q.data = {});
    const def = defaultData(q.category);
    for (const k in def) if (d[k] === undefined || d[k] === null && k !== 'image') d[k] = def[k];
    if (Array.isArray(d.options)) while (d.options.length < 4) d.options.push('');
    if (Array.isArray(d.option_pairs)) while (d.option_pairs.length < 4) d.option_pairs.push({ a: '', b: '' });
    if (!d.compare) d.compare = { v1: '', v2: '' };
    return q;
  }

  // ------------------------------------------------------------ اختيار الإجابة
  const AnswerPick = {
    props: { q: Object, k: String },
    template: `<span class="ans-pick" :class="{on: q.answer===k}" @click="q.answer = k" :title="q.answer===k ? 'الإجابة الصحيحة' : 'اجعلها الإجابة الصحيحة'">{{ q.answer===k ? '✓ الصحيحة' : 'صحيحة؟' }}</span>`,
  };

  // ------------------------------------------------------------ نوع الخيارات + الخيارات
  const OptionsEditor = {
    components: { RichInput, AnswerPick },
    props: { q: Object, sectionKind: String, allowCompare: Boolean },
    setup() { return { KEYS, LABELS, Store }; },
    computed: {
      types() {
        const t = [{ v: 'short', l: 'خيارات قصيرة (عمودان)' }, { v: 'long', l: 'خيارات طويلة (عمود واحد)' }];
        if (this.allowCompare) t.push({ v: 'compare', l: 'مقارنة بين قيمتين' });
        return t;
      },
      cmpOptions() { return (Store.settings && Store.settings.compare_options) || []; },
    },
    template: `
    <div class="col">
      <div class="field"><label>نوع الخيارات</label>
        <div class="btn-group"><button v-for="t in types" :key="t.v" type="button" class="btn sm" :class="{on: q.data.options_type===t.v}" @click="q.data.options_type=t.v">{{ t.l }}</button></div>
      </div>
      <template v-if="q.data.options_type==='compare'">
        <div class="grid c2">
          <div class="field"><label>القيمة الأولى (الخلية اليمنى)</label><RichInput v-model="q.data.compare.v1" placeholder="مثال: ٤٠٪ من ٦٠"/></div>
          <div class="field"><label>القيمة الثانية (الخلية اليسرى)</label><RichInput v-model="q.data.compare.v2" placeholder="مثال: ٦٠٪ من ٤٠"/></div>
        </div>
        <div class="lbl">الخيارات ثابتة — اختر الصحيح منها</div>
        <div class="col" style="gap:6px">
          <div class="opt-row" v-for="(o, i) in cmpOptions" :key="i"><span class="lab">{{ LABELS[i] }}</span><span>{{ o }}</span><AnswerPick :q="q" :k="KEYS[i]"/></div>
        </div>
      </template>
      <template v-else>
        <div class="lbl">الخيارات وتحديد الإجابة الصحيحة</div>
        <div class="col" style="gap:6px">
          <div class="opt-row" v-for="i in 4" :key="i"><span class="lab">{{ LABELS[i-1] }}</span>
            <RichInput v-model="q.data.options[i-1]" :placeholder="'الخيار ' + LABELS[i-1]" :tools="['bold','math']"/>
            <AnswerPick :q="q" :k="KEYS[i-1]"/></div>
        </div>
      </template>
    </div>`,
  };

  // ------------------------------------------------------------ التناظر اللفظي
  const AnalogyEditor = {
    components: { AnswerPick },
    props: { q: Object },
    setup() { return { KEYS, LABELS }; },
    template: `
    <div class="col">
      <div class="lbl">السؤال (الطرفان بالترتيب، وتُوضع ":" بينهما تلقائيًا)</div>
      <div class="pair-row" style="grid-template-columns: 1fr 16px 1fr">
        <input class="input" data-nav v-model="q.data.pair.a" placeholder="الطرف الأول">
        <span class="colon">:</span>
        <input class="input" data-nav v-model="q.data.pair.b" placeholder="الطرف الثاني">
      </div>
      <div class="field"><label>نوع الخيارات</label>
        <div class="btn-group"><button type="button" class="btn sm" :class="{on:q.data.options_type!=='long'}" @click="q.data.options_type='short'">قصيرة (عمودان)</button>
        <button type="button" class="btn sm" :class="{on:q.data.options_type==='long'}" @click="q.data.options_type='long'">طويلة (عمود واحد)</button></div></div>
      <div class="lbl">الخيارات (كل خيار طرفان)</div>
      <div class="col" style="gap:6px">
        <div class="pair-row" v-for="i in 4" :key="i"><span class="lab" style="font-weight:700;text-align:center;background:#eef1f3;border-radius:7px;padding:6px 0">{{ LABELS[i-1] }}</span>
          <input class="input" data-nav v-model="q.data.option_pairs[i-1].a" placeholder="الطرف الأول">
          <span class="colon">:</span>
          <input class="input" data-nav v-model="q.data.option_pairs[i-1].b" placeholder="الطرف الثاني">
          <AnswerPick :q="q" :k="KEYS[i-1]"/></div>
      </div>
    </div>`,
  };

  // ------------------------------------------------------------ الخطأ السياقي
  const ContextEditor = {
    components: { AnswerPick },
    props: { q: Object },
    data() { return { prevSentence: null }; },
    setup() { return { KEYS, LABELS, num }; },
    created() { this.prevSentence = this.q.data.sentence || ''; },
    computed: {
      sorted() { return (this.q.data.selections || []).slice().sort((a, b) => a.start - b.start); },
      viewHtml() {
        const s = this.q.data.sentence || '';
        let out = '', pos = 0;
        for (const sel of this.sorted) {
          if (sel.bad || sel.start < pos) continue;
          out += QText.escapeText(s.slice(pos, sel.start)) + '<b>' + QText.escapeText(s.slice(sel.start, sel.end)) + '</b>';
          pos = sel.end;
        }
        return out + QText.escapeText(s.slice(pos));
      },
    },
    watch: {
      'q.data.sentence'(nv) {
        // إعادة ربط التحديدات بمواضعها بعد تعديل الجملة
        const old = this.prevSentence || '';
        this.prevSentence = nv || '';
        if (old === nv) return;
        const sels = this.q.data.selections || [];
        const out = [];
        for (const sel of sels) {
          const text = sel.text || old.slice(sel.start, sel.end);
          if (nv.slice(sel.start, sel.end) === text) { out.push({ start: sel.start, end: sel.end, text }); continue; }
          let best = -1, bestD = 1e9, k = nv.indexOf(text);
          while (k >= 0) {
            const d = Math.abs(k - sel.start);
            const clash = out.some((o) => k < o.end && k + text.length > o.start);
            if (!clash && d < bestD) { best = k; bestD = d; }
            k = nv.indexOf(text, k + 1);
          }
          if (best >= 0) out.push({ start: best, end: best + text.length, text });
          else toast('أُزيلت الكلمة «' + text + '» من الخيارات لأنها لم تعد موجودة في الجملة. حدّدها من جديد.', 'error');
        }
        this.q.data.selections = out.sort((a, b) => a.start - b.start);
      },
    },
    methods: {
      addSelection() {
        const ta = this.$refs.ta;
        let a = ta.selectionStart, b = ta.selectionEnd;
        const s = this.q.data.sentence || '';
        while (a < b && /\s/.test(s[a])) a++;
        while (b > a && /[\s.,،؛:!؟?]/.test(s[b - 1])) b--;
        if (b <= a) { toast('حدّد كلمة أو عبارة من الجملة بالفأرة أولًا، ثم اضغط الزر.', 'error'); return; }
        const sels = this.q.data.selections || (this.q.data.selections = []);
        if (sels.length >= 4) { toast('يوجد أربع كلمات محددة بالفعل. احذف واحدة أولًا.', 'error'); return; }
        if (sels.some((x) => a < x.end && b > x.start)) { toast('هذا التحديد يتداخل مع كلمة محددة سابقًا.', 'error'); return; }
        sels.push({ start: a, end: b, text: s.slice(a, b) });
        sels.sort((x, y) => x.start - y.start);
      },
      remove(sel) {
        const k = this.q.data.selections.indexOf(sel);
        if (k >= 0) this.q.data.selections.splice(k, 1);
      },
    },
    template: `
    <div class="col">
      <div class="field"><label>الجملة كاملة</label>
        <textarea ref="ta" class="input" data-nav rows="2" v-model="q.data.sentence" placeholder="اكتب الجملة هنا، ثم حدّد بالفأرة كل كلمة تريدها خيارًا واضغط «إضافة إلى الخيارات»"></textarea></div>
      <div class="row"><button type="button" class="btn primary sm" @mousedown.prevent="addSelection">＋ إضافة الكلمة المحددة إلى الخيارات</button>
        <span class="hint">المحدد: {{ (q.data.selections||[]).length }} من ٤ — تُرتب الخيارات تلقائيًا حسب موضعها في الجملة.</span></div>
      <div class="lbl">كيف ستظهر الجملة (الكلمات المحددة بخط عريض)</div>
      <div class="ctx-view" v-html="viewHtml || '<span class=muted>—</span>'"></div>
      <div class="lbl">الخيارات</div>
      <div class="col" style="gap:6px">
        <div class="opt-row" v-for="(sel, i) in sorted" :key="sel.start + '-' + sel.end"><span class="lab">{{ LABELS[i] }}</span>
          <div class="ctx-sel"><span class="grow">{{ sel.text }}</span><span class="muted small">الموضع {{ num(sel.start) }}</span><button type="button" class="btn xs danger" @click="remove(sel)">إزالة</button></div>
          <AnswerPick :q="q" :k="KEYS[i]"/></div>
        <div v-if="!sorted.length" class="hint">لم تُحدد كلمات بعد.</div>
      </div>
      <div class="field"><label>نوع الخيارات</label>
        <div class="btn-group"><button type="button" class="btn sm" :class="{on:q.data.options_type!=='long'}" @click="q.data.options_type='short'">قصيرة (عمودان)</button>
        <button type="button" class="btn sm" :class="{on:q.data.options_type==='long'}" @click="q.data.options_type='long'">طويلة (عمود واحد)</button></div></div>
    </div>`,
  };

  // ------------------------------------------------------------ محرر السؤال الرئيسي
  const QuestionEditor = {
    components: { RichInput, ImageField, OptionsEditor, AnalogyEditor, ContextEditor },
    props: { q: Object, sectionKind: String, groupKind: String, number: Number },
    emits: ['change-category'],
    setup() { return { Store, CAT, num, onNavKey: UIX.onNavKey }; },
    computed: {
      cats() { return CAT[this.sectionKind] || []; },
      fixedCat() { return !!this.groupKind; },
      colWidth() { return Store.settings ? QRender.colWidthCm(Store.settings) : 8.3; },
      oddStem() { return (Store.settings && Store.settings.odd_stem_text) || 'أي الآتي مختلف؟'; },
    },
    methods: {
      onCat(v) { if (v !== this.q.category) this.$emit('change-category', v); },
    },
    template: `
    <div class="col qnav" style="gap:14px" @keydown="onNavKey">
      <div class="alert info small" style="padding:6px 10px">اضغط <b>Enter</b> للانتقال إلى الحقل التالي، و<b>Shift+Enter</b> لسطر جديد داخل نص السؤال.</div>
      <div class="field"><label>تصنيف السؤال</label>
        <div class="btn-group" v-if="!fixedCat">
          <button v-for="c in cats" :key="c.v" type="button" class="btn sm" :class="{on: q.category===c.v}" @click="onCat(c.v)">{{ c.l }}</button>
        </div>
        <div v-else class="row"><span class="badge info">{{ groupKind==='chart' ? 'رسوم بيانية' : 'استيعاب المقروء' }}</span><span class="hint">هذا السؤال ضمن مجموعة؛ يظهر بعد {{ groupKind==='chart' ? 'الرسم البياني' : 'نص القراءة' }} في الملف.</span></div>
      </div>

      <template v-if="q.category==='analogy'"><AnalogyEditor :q="q"/></template>
      <template v-else-if="q.category==='context'"><ContextEditor :q="q"/></template>
      <template v-else>
        <div v-if="q.category==='odd'" class="alert info">نص السؤال ثابت ويُكتب تلقائيًا: <b>{{ oddStem }}</b></div>
        <div v-else class="field"><label>{{ q.data.options_type==='compare' ? 'نص السؤال (مثل: قارن بين:)' : 'نص السؤال' }}</label>
          <RichInput v-model="q.data.stem" multiline :tools="q.category==='completion' ? ['bold','blank','math'] : ['bold','math']"
            :placeholder="q.category==='completion' ? 'اكتب الجملة، واضغط «إضافة فراغ» في موضع كل فراغ' : 'اكتب نص السؤال'"/>
          <span class="hint" v-if="q.category==='completion'">زر «إضافة فراغ» يُدرج ثماني نقاط ........ في موضع المؤشر، ويمكن إضافة أكثر من فراغ.</span>
        </div>
        <template v-if="q.category==='geometry'">
          <ImageField v-model="q.data.image" label="صورة الرسم الهندسي" :default-width="Number(Store.settings && Store.settings.geometry_width_cm) || 4.5" :max-width="colWidth"/>
          <div class="field"><label>موضع الرسم</label>
            <div class="btn-group">
              <button type="button" class="btn sm" :class="{on: q.data.image_placement==='side'}" @click="q.data.image_placement='side'">بجانب النص (يسارًا)</button>
              <button type="button" class="btn sm" :class="{on: q.data.image_placement==='below' || !q.data.image_placement}" @click="q.data.image_placement='below'">تحت النص</button>
              <button type="button" class="btn sm" :class="{on: q.data.image_placement==='above'}" @click="q.data.image_placement='above'">فوق النص</button>
            </div>
            <span class="hint">تُكتب تحت الرسم تلقائيًا عبارة: {{ Store.settings && Store.settings.geometry_caption }}</span>
          </div>
        </template>
        <OptionsEditor :q="q" :section-kind="sectionKind" :allow-compare="sectionKind==='quant'"/>
      </template>
    </div>`,
  };

  // ------------------------------------------------------------ محرر الفقرات
  const PassageEditor = {
    components: { RichInput },
    props: { g: Object },
    setup() { return { num }; },
    methods: {
      add() { this.g.data.paragraphs.push(''); },
      move(i, d) { const p = this.g.data.paragraphs; const j = i + d; if (j < 0 || j >= p.length) return; const t = p[i]; p[i] = p[j]; p[j] = t; },
      async del(i) {
        const p = this.g.data.paragraphs;
        if (!QText.isRichEmpty(p[i])) {
          const yes = await confirmBox({ title: 'حذف فقرة', message: 'هل تريد حذف الفقرة رقم ' + num(i + 1) + '؟', okText: 'حذف', danger: true });
          if (!yes) return;
        }
        p.splice(i, 1);
        if (!p.length) p.push('');
      },
    },
    template: `
    <div class="col">
      <div class="field"><label>نوع النص</label>
        <div class="btn-group">
          <button type="button" class="btn sm" :class="{on: g.data.passage_type!=='long'}" @click="g.data.passage_type='short'">نص قصير (عبارة أو فقرة)</button>
          <button type="button" class="btn sm" :class="{on: g.data.passage_type==='long'}" @click="g.data.passage_type='long'">نص طويل (عدة فقرات)</button>
        </div>
      </div>
      <div class="row wrap" v-if="g.data.passage_type==='long'">
        <label class="check"><input type="checkbox" v-model="g.data.numbered"> ترقيم الفقرات تلقائيًا (١) (٢) …</label>
      </div>
      <div class="row wrap"><span class="lbl">محاذاة النص:</span>
        <div class="btn-group">
          <button type="button" class="btn xs" :class="{on:(g.data.align|| (g.data.passage_type==='long'?'justify':'center'))==='justify'}" @click="g.data.align='justify'">ضبط</button>
          <button type="button" class="btn xs" :class="{on:(g.data.align|| (g.data.passage_type==='long'?'justify':'center'))==='center'}" @click="g.data.align='center'">توسيط</button>
          <button type="button" class="btn xs" :class="{on:g.data.align==='right'}" @click="g.data.align='right'">يمين</button>
        </div></div>
      <div class="col" style="gap:8px">
        <div class="para-card" v-for="(p, i) in g.data.paragraphs" :key="i">
          <div class="ph"><span class="badge">الفقرة {{ num(i+1) }}</span><span class="spacer"></span>
            <button type="button" class="btn xs" @click="move(i,-1)" :disabled="i===0" title="نقل للأعلى">▲</button>
            <button type="button" class="btn xs" @click="move(i,1)" :disabled="i===g.data.paragraphs.length-1" title="نقل للأسفل">▼</button>
            <button type="button" class="btn xs danger" @click="del(i)">حذف</button></div>
          <RichInput v-model="g.data.paragraphs[i]" multiline placeholder="نص الفقرة"/>
        </div>
      </div>
      <div><button type="button" class="btn sm" @click="add">＋ إضافة فقرة</button>
        <span class="hint" v-if="g.data.passage_type==='long'"> — يجوز أن يتوزع النص الطويل بين نصفي الصفحة عند حدود الفقرات فقط، ولا تُقسم الفقرة الواحدة.</span></div>
    </div>`,
  };

  const GroupEditor = {
    components: { ImageField, PassageEditor },
    props: { g: Object, sectionKind: String },
    setup() { return { Store }; },
    computed: { colWidth() { return Store.settings ? QRender.colWidthCm(Store.settings) : 8.3; } },
    template: `
    <div class="col" style="gap:14px">
      <div class="field"><label>عنوان داخلي للمجموعة (يظهر في البرنامج فقط ولا يُطبع)</label>
        <input class="input" v-model="g.data.title" :placeholder="g.group_kind==='chart' ? 'مثال: رسم توزيع الفئات العمرية' : 'مثال: نص الإمام مالك'"></div>
      <template v-if="g.group_kind==='chart'">
        <ImageField v-model="g.data.image" label="صورة الرسم البياني (تظهر مرة واحدة قبل أسئلتها)" :default-width="Number(Store.settings && Store.settings.chart_width_cm) || 7.5" :max-width="colWidth"/>
        <div class="hint">يجوز أن يقع الرسم في نصف صفحة وأسئلته في النصف التالي عند ضيق المساحة، ولا تظهر أسئلته قبله أبدًا.</div>
      </template>
      <template v-else><PassageEditor :g="g"/></template>
    </div>`,
  };

  global.QEditors = { QuestionEditor, GroupEditor, PassageEditor, CAT, CAT_LABEL, defaultData, ensureShape };
})(window);
