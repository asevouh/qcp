/* pages.js — صفحات البرنامج: الرئيسية، الأقسام، إنشاء قسم، إنشاء اختبار، الاختبارات السابقة، الإعدادات، النسخ الاحتياطي */
(function (global) {
  'use strict';
  const { Store, toast, confirmBox, guard, num, fmtDate, QModal, QDropdown, KIND_LABEL, STATUS_LABEL, STATUS_CLASS } = UIX;

  function go(hash) { location.hash = hash; }

  // ================================================================ الرئيسية
  const Home = {
    data() { return { sys: null, sections: [], exams: [], busy: false }; },
    setup() { return { Store, num, fmtDate, KIND_LABEL, STATUS_LABEL, STATUS_CLASS }; },
    async mounted() { await this.load(); },
    methods: {
      async load() {
        this.sys = await UIX.loadSystem();
        this.sections = ((await guard(() => API.get('/api/sections?sort=updated'))) || []).slice(0, 6);
        this.exams = ((await guard(() => API.get('/api/exams'))) || []).slice(0, 6);
      },
      async demo() {
        this.busy = true;
        const r = await guard(() => API.post('/api/demo'), 'أُنشئ قسمان تجريبيان واختبار تجريبي');
        this.busy = false;
        if (r) this.load();
      },
    },
    template: `
    <div class="page">
      <div class="page-head"><h1>مرحبًا بك في مُنشئ اختبارات القدرات</h1></div>
      <div v-if="sys && sys.font && !sys.font.found" class="alert warn" style="margin-bottom:14px">
        لم يُعثر على خط <b>{{ sys.font.family }}</b> في هذا الجهاز؛ سيُستخدم في ملفات PDF والمعاينة خط بديل مشابه. ملف Word سيبقى بخط {{ sys.font.family }} ويظهر به على أي جهاز يحتوي الخط.
        يمكنك نسخ ملفات الخط (calibri.ttf و calibrib.ttf) إلى مجلد <span class="mono">data/fonts</span> داخل مجلد البرنامج ثم إعادة تشغيله.
      </div>
      <div class="grid c4" v-if="sys">
        <div class="card stat"><div class="n">{{ num(sys.stats.quant_sections) }}</div><div class="l">أقسام كمية</div></div>
        <div class="card stat"><div class="n">{{ num(sys.stats.verbal_sections) }}</div><div class="l">أقسام لفظية</div></div>
        <div class="card stat"><div class="n">{{ num(sys.stats.questions) }}</div><div class="l">سؤالًا محفوظًا</div></div>
        <div class="card stat"><div class="n">{{ num(sys.stats.exams) }}</div><div class="l">اختبارًا</div></div>
      </div>
      <div class="row wrap" style="margin:18px 0">
        <a class="btn primary big" href="#/sections/new">＋ إنشاء قسم</a>
        <a class="btn primary big" href="#/exams/new">＋ إنشاء اختبار</a>
        <a class="btn big" href="#/sections">الأقسام</a>
        <a class="btn big" href="#/exams">الاختبارات السابقة</a>
        <button v-if="sys && sys.stats.sections===0" class="btn big" @click="demo" :disabled="busy">تحميل بيانات تجريبية للتجربة</button>
      </div>
      <div class="grid c2">
        <div class="card"><div class="card-head"><h3>آخر الأقسام المعدّلة</h3><span class="spacer"></span><a href="#/sections" class="small">عرض الكل</a></div>
          <table class="list" v-if="sections.length"><tr v-for="s in sections" :key="s.id" style="cursor:pointer" @click="go('#/sections/'+s.id)">
            <td><b>{{ s.title }}</b><div class="small muted">{{ s.source }}</div></td>
            <td><span class="badge" :class="s.kind">{{ KIND_LABEL[s.kind] }}</span></td>
            <td class="nowrap">{{ num(s.question_count) }} سؤالًا</td>
            <td><span class="badge" :class="STATUS_CLASS[s.status]">{{ STATUS_LABEL[s.status] }}</span></td></tr></table>
          <div v-else class="empty">لا توجد أقسام بعد.</div></div>
        <div class="card"><div class="card-head"><h3>آخر الاختبارات</h3><span class="spacer"></span><a href="#/exams" class="small">عرض الكل</a></div>
          <table class="list" v-if="exams.length"><tr v-for="e in exams" :key="e.id" style="cursor:pointer" @click="go('#/exams/'+e.id)">
            <td><b>{{ e.title }}</b><div class="small muted">{{ fmtDate(e.updated_at) }}</div></td>
            <td class="small">{{ e.quant_section ? e.quant_section.title : '—' }}<br>{{ e.verbal_section ? e.verbal_section.title : '—' }}</td>
            <td><span v-if="e.frozen" class="badge info">معتمد</span></td></tr></table>
          <div v-else class="empty">لا توجد اختبارات بعد.</div></div>
      </div>
    </div>`,
  };
  Home.methods.go = go;

  // ================================================================ الأقسام
  const SectionsList = {
    components: { QModal, QDropdown },
    data() { return { list: [], q: '', kind: '', status: '', sort: 'updated', loading: true, edit: null, sources: [], importing: false }; },
    setup() { return { num, fmtDate, KIND_LABEL, STATUS_LABEL, STATUS_CLASS }; },
    async mounted() { await this.load(); },
    watch: { kind() { this.load(); }, status() { this.load(); }, sort() { this.load(); } },
    methods: {
      async load() {
        const p = new URLSearchParams({ q: this.q, kind: this.kind, status: this.status, sort: this.sort });
        this.list = (await guard(() => API.get('/api/sections?' + p.toString()))) || [];
        this.loading = false;
      },
      onSearch() { clearTimeout(this._t); this._t = setTimeout(() => this.load(), 250); },
      async openEdit(s) { this.edit = { id: s.id, title: s.title, source: s.source, status: s.status, notes: s.notes || '' }; this.sources = (await guard(() => API.get('/api/sources'))) || []; },
      async saveEdit() {
        const e = this.edit;
        const r = await guard(() => API.put('/api/sections/' + e.id, { title: e.title, source: e.source, status: e.status, notes: e.notes }), 'حُفظت بيانات القسم');
        if (r) { this.edit = null; this.load(); }
      },
      async dup(s) {
        const r = await guard(() => API.post('/api/sections/' + s.id + '/duplicate'), 'أُنشئت نسخة من القسم');
        if (r) this.load();
      },
      async del(s) {
        const yes = await confirmBox({ title: 'حذف قسم', danger: true, okText: 'حذف نهائي',
          message: 'سيتم حذف القسم «' + s.title + '» وجميع أسئلته (' + num(s.question_count) + ') نهائيًا. الاختبارات المعتمدة (المثبتة) تحتفظ بنسختها، أما غير المعتمدة فستفقد هذا القسم. للتأكيد اكتب كلمة: حذف',
          requireText: 'حذف' });
        if (!yes) return;
        const r = await guard(() => API.del('/api/sections/' + s.id), 'حُذف القسم');
        if (r) this.load();
      },
      pickImport() { this.$refs.imp.click(); },
      async onImport(e) {
        const f = e.target.files && e.target.files[0]; e.target.value = '';
        if (!f) return;
        this.importing = true;
        const r = await guard(() => API.upload('/api/restore', f, { mode: 'merge' }));
        this.importing = false;
        if (r) { toast('تم استيراد ' + num(r.sections) + ' قسم', 'ok'); this.load(); }
      },
    },
    template: `
    <div class="page">
      <div class="page-head"><h1>الأقسام</h1><span class="sub">كل قسم وحدة مستقلة بمصدر واحد وأسئلة مرتبة</span><span class="spacer"></span>
        <input ref="imp" type="file" accept=".zip,.json" class="hidden" @change="onImport">
        <button class="btn" @click="pickImport" :disabled="importing">استيراد قسم من ملف</button>
        <a class="btn primary" href="#/sections/new">＋ إنشاء قسم</a></div>
      <div class="card">
        <div class="card-head row wrap">
          <input class="input sm" style="max-width:280px" v-model="q" @input="onSearch" placeholder="بحث في العنوان أو المصدر…">
          <select class="select sm" style="width:auto" v-model="kind"><option value="">كل الأنواع</option><option value="quant">كمي</option><option value="verbal">لفظي</option></select>
          <select class="select sm" style="width:auto" v-model="status"><option value="">كل الحالات</option><option value="draft">مسودة</option><option value="review">يحتاج مراجعة</option><option value="complete">مكتمل</option></select>
          <span class="spacer"></span>
          <label class="small muted">الفرز:</label>
          <select class="select sm" style="width:auto" v-model="sort"><option value="updated">آخر تعديل</option><option value="created">تاريخ الإنشاء (الأحدث)</option><option value="created_asc">تاريخ الإنشاء (الأقدم)</option><option value="kind">النوع</option><option value="title">العنوان</option></select>
        </div>
        <table class="list" v-if="list.length">
          <tr><th>العنوان</th><th>النوع</th><th>المصدر</th><th>الأسئلة</th><th>الحالة</th><th>آخر تعديل</th><th></th></tr>
          <tr v-for="s in list" :key="s.id">
            <td><a :href="'#/sections/'+s.id"><b>{{ s.title }}</b></a></td>
            <td><span class="badge" :class="s.kind">{{ KIND_LABEL[s.kind] }}</span></td>
            <td class="small">{{ s.source }}</td>
            <td class="nowrap">{{ num(s.question_count) }} <span class="muted small" v-if="s.complete_count < s.question_count">({{ num(s.question_count - s.complete_count) }} مسودة)</span></td>
            <td><span class="badge" :class="STATUS_CLASS[s.status]">{{ STATUS_LABEL[s.status] }}</span></td>
            <td class="small muted nowrap">{{ fmtDate(s.updated_at) }}</td>
            <td class="nowrap"><a class="btn sm primary" :href="'#/sections/'+s.id">فتح</a>
              <QDropdown label="المزيد" btn-class="btn sm">
                <button @click="openEdit(s)">تعديل العنوان والمصدر والحالة</button>
                <button @click="dup(s)">نسخ القسم</button>
                <button @click="download('/api/sections/'+s.id+'/export-file')">تصدير القسم إلى ملف</button>
                <div class="sep"></div>
                <button @click="del(s)" style="color:#b42318">حذف القسم</button>
              </QDropdown></td>
          </tr>
        </table>
        <div v-else-if="!loading" class="empty">لا توجد أقسام مطابقة. <a href="#/sections/new">أنشئ قسمًا جديدًا</a></div>
      </div>
      <QModal v-if="edit" title="تعديل بيانات القسم" @close="edit=null">
        <div class="col">
          <div class="field"><label>العنوان</label><input class="input" v-model="edit.title"></div>
          <div class="field"><label>المصدر</label><input class="input" v-model="edit.source" list="srcs2"><datalist id="srcs2"><option v-for="x in sources" :key="x" :value="x"></option></datalist></div>
          <div class="field"><label>الحالة</label><select class="select" v-model="edit.status"><option value="draft">مسودة</option><option value="review">يحتاج مراجعة</option><option value="complete">مكتمل</option></select></div>
          <div class="field"><label>ملاحظات</label><textarea class="input" rows="2" v-model="edit.notes"></textarea></div>
        </div>
        <template #foot><button class="btn primary" @click="saveEdit">حفظ</button><button class="btn" @click="edit=null">إلغاء</button></template>
      </QModal>
    </div>`,
  };
  SectionsList.methods.download = (u) => { const a = document.createElement('a'); a.href = u; a.download = ''; document.body.appendChild(a); a.click(); a.remove(); };

  const SectionNew = {
    data() { return { title: '', kind: '', source: '', notes: '', sources: [], busy: false }; },
    async mounted() { this.sources = (await guard(() => API.get('/api/sources'))) || []; this.$nextTick(() => this.$refs.t && this.$refs.t.focus()); },
    methods: {
      async create() {
        if (!this.title.trim()) return toast('اكتب عنوان القسم', 'error');
        if (!this.kind) return toast('اختر نوع القسم: كمي أو لفظي', 'error');
        if (!this.source.trim()) return toast('اكتب مصدر القسم', 'error');
        this.busy = true;
        const r = await guard(() => API.post('/api/sections', { title: this.title, kind: this.kind, source: this.source, notes: this.notes }));
        this.busy = false;
        if (r) { toast('أُنشئ القسم، أضف أسئلته الآن', 'ok'); go('#/sections/' + r.id); }
      },
    },
    template: `
    <div class="page" style="max-width:760px">
      <div class="page-head"><h1>إنشاء قسم جديد</h1></div>
      <div class="card"><div class="card-body col" style="gap:16px">
        <div class="field"><label>عنوان القسم</label><input ref="t" class="input" v-model="title" placeholder="مثال: القسم الكمي ٧ — المنصف"></div>
        <div class="field"><label>نوع القسم</label>
          <div class="choice-cards">
            <div class="choice" :class="{on: kind==='quant'}" @click="kind='quant'"><div class="big">كمي</div><div class="small muted">اعتيادي، رسوم بيانية، رسم هندسي، مقارنة</div></div>
            <div class="choice" :class="{on: kind==='verbal'}" @click="kind='verbal'"><div class="big">لفظي</div><div class="small muted">تناظر، إكمال، مفردة شاذة، خطأ سياقي، استيعاب</div></div>
          </div></div>
        <div class="field"><label>مصدر القسم (يُحفظ للقسم كله ويظهر في ترويسة الاختبار)</label>
          <input class="input" v-model="source" list="srcs3" placeholder="مثال: أقسام دورة أ. محمود المنصف تدريب">
          <datalist id="srcs3"><option v-for="s in sources" :key="s" :value="s"></option></datalist></div>
        <div class="field"><label>ملاحظات (اختياري)</label><textarea class="input" rows="2" v-model="notes"></textarea></div>
        <div><button class="btn primary big" @click="create" :disabled="busy">إنشاء القسم والمتابعة إلى الأسئلة ←</button></div>
      </div></div>
    </div>`,
  };

  // ================================================================ إنشاء/تحرير اختبار
  const ExamBuilder = {
    components: { QModal },
    props: { id: [String, Number] },
    data() {
      return {
        exam: { title: '', number: '', header_title: '', quant_section_id: null, verbal_section_id: null, duration: null, options: { section_order: 'quant_first', include_cover: true, big_title: '' } },
        quants: [], verbals: [], problems: [], busy: '', results: null, pdf: null, saved: true, loaded: false,
      };
    },
    setup() { return { Store, num, fmtDate, STATUS_LABEL, STATUS_CLASS }; },
    computed: {
      isNew() { return !this.exam.id; },
      qsec() { return this.quants.find((s) => s.id === Number(this.exam.quant_section_id)) || (this.exam.frozen ? this.exam.quant_section : null); },
      vsec() { return this.verbals.find((s) => s.id === Number(this.exam.verbal_section_id)) || (this.exam.frozen ? this.exam.verbal_section : null); },
      total() { return (this.qsec ? this.qsec.question_count : 0) + (this.vsec ? this.vsec.question_count : 0); },
      range() { const s = Store.settings || {}; return [s.min_questions || 11, s.max_questions || 13]; },
    },
    watch: {
      exam: { deep: true, handler() { if (this.loaded) this.saved = false; } },
      total(n) { if (this.loaded && !this.exam.duration && n) this.exam.duration = n + 2; },
    },
    async mounted() {
      const all = (await guard(() => API.get('/api/sections?sort=updated'))) || [];
      this.quants = all.filter((s) => s.kind === 'quant');
      this.verbals = all.filter((s) => s.kind === 'verbal');
      if (this.id && this.id !== 'new') {
        const e = await guard(() => API.get('/api/exams/' + this.id));
        if (e) { e.options = Object.assign({ section_order: 'quant_first', include_cover: true, big_title: '' }, e.options || {}); this.exam = e; await this.loadProblems(); }
      }
      this.$nextTick(() => { this.loaded = true; this.saved = !!this.exam.id; });
    },
    methods: {
      async loadProblems() { if (this.exam.id) this.problems = (await guard(() => API.get('/api/exams/' + this.exam.id + '/problems'))) || []; },
      payload() {
        const e = this.exam;
        return { title: e.title, number: e.number, header_title: e.header_title, quant_section_id: e.quant_section_id || null, verbal_section_id: e.verbal_section_id || null, duration: e.duration || null, options: e.options };
      },
      async save(silent) {
        if (!this.exam.title.trim()) { toast('اكتب عنوان الاختبار', 'error'); return false; }
        let r;
        if (!this.exam.id) r = await guard(() => API.post('/api/exams', this.payload()));
        else r = await guard(() => API.put('/api/exams/' + this.exam.id, this.payload()));
        if (!r) return false;
        if (!silent) toast('حُفظ الاختبار', 'ok');
        this.loaded = false;
        r.options = Object.assign({ section_order: 'quant_first', include_cover: true, big_title: '' }, r.options || {});
        this.exam = r;
        this.$nextTick(() => { this.loaded = true; this.saved = true; });
        if (location.hash !== '#/exams/' + r.id) history.replaceState(null, '', '#/exams/' + r.id);
        await this.loadProblemsFor(r.id);
        return r;
      },
      async loadProblemsFor(id) { this.problems = (await guard(() => API.get('/api/exams/' + id + '/problems'))) || []; },
      examId() { return this.exam.id; },
      async ensureSaved() {
        if (!this.saved || !this.exam.id) { const r = await this.save(true); if (!r) return false; }
        return true;
      },
      async checkProblems(action) {
        await this.loadProblemsFor(this.examId());
        if (!this.problems.length) return true;
        return confirmBox({ title: 'تنبيه قبل ' + action, message: 'توجد ملاحظات على هذا الاختبار:', details: this.problems, okText: 'متابعة رغم ذلك' });
      },
      async preview() {
        if (!(await this.ensureSaved())) return;
        this.busy = 'preview';
        const r = await guard(() => API.post('/api/exams/' + this.examId() + '/preview'));
        this.busy = '';
        if (r) this.pdf = r;
      },
      async exportFiles(formats, variant) {
        if (!(await this.ensureSaved())) return;
        if (!(await this.checkProblems('التصدير'))) return;
        this.busy = variant + formats.join();
        const r = await guard(() => API.post('/api/exams/' + this.examId() + '/export', { formats, variant }));
        this.busy = '';
        if (r) {
          this.results = Object.assign({ variant }, r);
          toast('اكتمل التصدير', 'ok');
          for (const k of formats) if (r.files[k]) this.download(r.files[k]);
        }
      },
      download(url) { const a = document.createElement('a'); a.href = url; a.download = ''; document.body.appendChild(a); a.click(); a.remove(); },
      async freeze() {
        if (!(await this.ensureSaved())) return;
        const yes = await confirmBox({ title: 'اعتماد الاختبار', message: 'سيُثبَّت محتوى القسمين الحاليين داخل هذا الاختبار، فلا يتأثر لاحقًا إذا عدّلت الأقسام الأصلية. يمكنك إلغاء الاعتماد في أي وقت.', okText: 'اعتماد وتثبيت' });
        if (!yes) return;
        const r = await guard(() => API.post('/api/exams/' + this.examId() + '/freeze'), 'اعتُمد الاختبار وثُبّتت نسخة من أقسامه');
        if (r) { this.loaded = false; r.options = Object.assign({ section_order: 'quant_first', include_cover: true }, r.options || {}); this.exam = r; this.$nextTick(() => { this.loaded = true; this.saved = true; }); this.loadProblemsFor(r.id); }
      },
      async unfreeze() {
        const yes = await confirmBox({ title: 'إلغاء الاعتماد', message: 'سيعود الاختبار لاستخدام المحتوى الحالي للأقسام الأصلية (وتُحذف النسخة المثبتة). هل تريد المتابعة؟', okText: 'إلغاء الاعتماد', danger: true });
        if (!yes) return;
        const r = await guard(() => API.post('/api/exams/' + this.examId() + '/unfreeze'), 'أُلغي الاعتماد');
        if (r) { this.loaded = false; r.options = Object.assign({ section_order: 'quant_first', include_cover: true }, r.options || {}); this.exam = r; this.$nextTick(() => { this.loaded = true; this.saved = true; }); this.loadProblemsFor(r.id); }
      },
      async editSection(sid) {
        if (!(await this.ensureSaved())) return;
        go('#/sections/' + sid + '?back=' + encodeURIComponent('#/exams/' + this.exam.id));
      },
      reportItems(rep) {
        const out = [];
        if (!rep) return out;
        if (rep.primaryFontLoaded === false) out.push({ t: 'warn', m: 'خط ' + ((Store.settings || {}).font_family || '') + ' غير موجود على هذا الجهاز؛ استُخدم خط بديل في PDF. (ملف Word بالخط الأصلي)' });
        for (const w of rep.warnings || []) if (w.type === 'too_tall') out.push({ t: 'danger', m: 'عنصر أطول من نصف الصفحة ولا يتسع كاملًا (غالبًا صورة كبيرة) — صغّر عرض الصورة.' });
        for (const o of rep.overflow || []) out.push({ t: 'danger', m: o.horizontal ? ('معادلة أو صورة أعرض من نصف الصفحة بمقدار ' + o.overflowPt.toFixed(1) + ' نقطة — قسّمها أو صغّرها.') : ('تجاوز في أحد الأعمدة بمقدار ' + o.overflowPt.toFixed(1) + ' نقطة.') });
        for (const b of rep.brokenImages || []) out.push({ t: 'danger', m: 'صورة مفقودة: ' + b });
        for (const m of rep.mathErrors || []) out.push({ t: 'danger', m: 'خطأ في معادلة (السؤال ' + m.where + '): ' + m.error });
        return out;
      },
    },
    template: `
    <div class="page">
      <div class="page-head"><h1>{{ isNew ? 'إنشاء اختبار' : 'الاختبار: ' + exam.title }}</h1>
        <span v-if="exam.frozen" class="badge info">معتمد — محتوى مثبَّت</span>
        <span v-if="!saved" class="badge warn">تعديلات غير محفوظة</span>
        <span class="spacer"></span><a href="#/exams" class="btn ghost">→ الاختبارات السابقة</a></div>
      <div class="grid" style="grid-template-columns: minmax(0,1.25fr) minmax(0,1fr); align-items:start">
        <div class="col" style="gap:14px">
          <div class="card"><div class="card-head"><h3>بيانات الاختبار</h3></div><div class="card-body col">
            <div class="grid c2">
              <div class="field"><label>عنوان الاختبار</label><input class="input" v-model="exam.title" placeholder="مثال: الاختبار الخامس"></div>
              <div class="field"><label>رقم الاختبار</label><input class="input" v-model="exam.number" placeholder="مثال: ٥"></div>
              <div class="field"><label>نص وسط الترويسة (اختياري؛ الافتراضي العنوان)</label><input class="input" v-model="exam.header_title" :placeholder="exam.title"></div>
              <div class="field"><label>مدة الاختبار (بالدقائق)</label><input class="input" type="number" min="1" v-model.number="exam.duration"></div>
            </div>
            <div class="row wrap">
              <label class="check"><input type="checkbox" v-model="exam.options.include_cover"> إضافة صفحة الغلاف</label>
              <span class="spacer"></span><span class="lbl">ترتيب القسمين:</span>
              <div class="btn-group"><button class="btn sm" :class="{on: exam.options.section_order!=='verbal_first'}" @click="exam.options.section_order='quant_first'">الكمي أولًا</button>
                <button class="btn sm" :class="{on: exam.options.section_order==='verbal_first'}" @click="exam.options.section_order='verbal_first'">اللفظي أولًا</button></div>
            </div>
            <div class="field"><label>العنوان الكبير في الغلاف (اختياري؛ الافتراضي: العنوان + «: كمي ولفظي»)</label><input class="input" v-model="exam.options.big_title" :placeholder="(exam.title||'') + ': كمي ولفظي'"></div>
          </div></div>

          <div class="card"><div class="card-head"><h3>القسمان</h3><span class="spacer"></span>
            <span class="badge" :class="total>=range[0]*2 && total<=range[1]*2 ? 'ok' : 'warn'">إجمالي الأسئلة: {{ num(total) }}</span></div>
            <div class="card-body col">
              <div v-if="exam.frozen" class="alert info">الاختبار معتمد: يُصدَّر من النسخة المثبتة. لتغيير القسمين ألغِ الاعتماد أولًا.</div>
              <div class="grid c2">
                <div class="sec-pick col">
                  <div class="field"><label>القسم الكمي</label>
                    <select class="select" v-model.number="exam.quant_section_id" :disabled="exam.frozen"><option :value="null">— اختر قسمًا كميًا —</option>
                      <option v-for="s in quants" :key="s.id" :value="s.id">{{ s.title }} ({{ num(s.question_count) }})</option></select></div>
                  <div v-if="qsec" class="kv small">
                    <span class="k">العنوان</span><span>{{ qsec.title }}</span>
                    <span class="k">المصدر</span><span>{{ qsec.source }}</span>
                    <span class="k">عدد الأسئلة</span><span :style="{color: (qsec.question_count<range[0]||qsec.question_count>range[1]) ? '#b42318' : ''}">{{ num(qsec.question_count) }}</span>
                    <span class="k" v-if="qsec.status">الحالة</span><span v-if="qsec.status"><span class="badge" :class="STATUS_CLASS[qsec.status]">{{ STATUS_LABEL[qsec.status] }}</span></span>
                  </div>
                  <button v-if="qsec && !exam.frozen" class="btn sm" @click="editSection(qsec.id)">تعديل هذا القسم</button>
                </div>
                <div class="sec-pick col">
                  <div class="field"><label>القسم اللفظي</label>
                    <select class="select" v-model.number="exam.verbal_section_id" :disabled="exam.frozen"><option :value="null">— اختر قسمًا لفظيًا —</option>
                      <option v-for="s in verbals" :key="s.id" :value="s.id">{{ s.title }} ({{ num(s.question_count) }})</option></select></div>
                  <div v-if="vsec" class="kv small">
                    <span class="k">العنوان</span><span>{{ vsec.title }}</span>
                    <span class="k">المصدر</span><span>{{ vsec.source }}</span>
                    <span class="k">عدد الأسئلة</span><span :style="{color: (vsec.question_count<range[0]||vsec.question_count>range[1]) ? '#b42318' : ''}">{{ num(vsec.question_count) }}</span>
                    <span class="k" v-if="vsec.status">الحالة</span><span v-if="vsec.status"><span class="badge" :class="STATUS_CLASS[vsec.status]">{{ STATUS_LABEL[vsec.status] }}</span></span>
                  </div>
                  <button v-if="vsec && !exam.frozen" class="btn sm" @click="editSection(vsec.id)">تعديل هذا القسم</button>
                </div>
              </div>
              <div class="hint">تُعرض في القوائم الأقسام الكمية في خانة الكمي واللفظية في خانة اللفظي فقط. لا يُغيَّر ترتيب الأسئلة عند إنشاء الاختبار.</div>
            </div></div>
          <div class="row wrap"><button class="btn primary big" @click="save(false)">حفظ الاختبار</button>
            <button v-if="!isNew && !exam.frozen" class="btn" @click="freeze">اعتماد وتثبيت المحتوى</button>
            <button v-if="exam.frozen" class="btn danger" @click="unfreeze">إلغاء الاعتماد</button></div>
        </div>

        <div class="col" style="gap:14px">
          <div v-if="problems.length" class="alert warn"><b>ملاحظات قبل الطباعة:</b><ul><li v-for="p in problems" :key="p">{{ p }}</li></ul></div>
          <div class="card"><div class="card-head"><h3>المعاينة والتصدير</h3></div><div class="card-body col">
            <button class="btn big" @click="preview" :disabled="!!busy">{{ busy==='preview' ? 'جارٍ تجهيز المعاينة…' : '👁 معاينة المستند (مطابقة للطباعة)' }}</button>
            <div class="lbl">نسخة الطالب</div>
            <div class="row wrap">
              <button class="btn primary" @click="exportFiles(['docx'],'student')" :disabled="!!busy">{{ busy==='studentdocx' ? 'جارٍ…' : 'تصدير Word' }}</button>
              <button class="btn primary" @click="exportFiles(['pdf'],'student')" :disabled="!!busy">{{ busy==='studentpdf' ? 'جارٍ…' : 'تصدير PDF' }}</button>
              <button class="btn" @click="exportFiles(['pdf','docx'],'student')" :disabled="!!busy">{{ busy==='studentpdf,docx' ? 'جارٍ…' : 'الاثنان معًا' }}</button>
            </div>
            <div class="lbl">مفتاح الإجابة (مستقل عن توزيع الصفحات)</div>
            <div class="row wrap">
              <button class="btn" @click="exportFiles(['docx'],'key')" :disabled="!!busy">Word</button>
              <button class="btn" @click="exportFiles(['pdf'],'key')" :disabled="!!busy">PDF</button>
            </div>
            <div class="lbl">نسخة المعلم (الإجابات الصحيحة مظللة)</div>
            <div class="row wrap">
              <button class="btn" @click="exportFiles(['docx'],'teacher')" :disabled="!!busy">Word</button>
              <button class="btn" @click="exportFiles(['pdf'],'teacher')" :disabled="!!busy">PDF</button>
            </div>
            <div class="hint" v-if="busy && busy!=='preview'">جارٍ إنشاء الملفات… (ثوانٍ قليلة)</div>
          </div></div>
          <div class="card" v-if="results"><div class="card-head"><h3>آخر تصدير</h3><span class="spacer"></span><span class="badge ok">تم</span></div>
            <div class="card-body col">
              <div class="files-out">
                <a v-for="(u,k) in results.files" :key="k" class="btn" :href="u" download>⬇ تنزيل ملف {{ k==='pdf' ? 'PDF' : 'Word' }}</a>
              </div>
              <div class="hint">تُحفظ الملفات أيضًا في مجلد البرنامج: <span class="mono small">{{ results.folder }}</span></div>
              <template v-if="results.report">
                <div v-if="results.report.pages" class="small">عدد صفحات المستند: {{ num(results.report.pages) }}</div>
                <div v-for="(r,i) in reportItems(results.report)" :key="i" class="alert" :class="r.t">{{ r.m }}</div>
                <div v-if="results.variant!=='key' && !reportItems(results.report).length" class="alert ok">فُحص التخطيط: لا تداخل، ولا أسئلة مقسومة، والصور والمعادلات سليمة.</div>
              </template>
            </div></div>
        </div>
      </div>
      <QModal v-if="pdf" title="معاينة المستند (هذا هو ملف PDF الفعلي)" wide @close="pdf=null">
        <div v-for="(r,i) in reportItems(pdf.report)" :key="i" class="alert" :class="r.t" style="margin-bottom:6px">{{ r.m }}</div>
        <iframe class="pdf-frame" :src="pdf.url" style="height:76vh"></iframe>
      </QModal>
    </div>`,
  };

  // ================================================================ الاختبارات السابقة
  const ExamsList = {
    components: { QDropdown },
    data() { return { list: [], q: '', busy: null }; },
    setup() { return { num, fmtDate }; },
    async mounted() { await this.load(); },
    methods: {
      async load() { this.list = (await guard(() => API.get('/api/exams?q=' + encodeURIComponent(this.q)))) || []; },
      onSearch() { clearTimeout(this._t); this._t = setTimeout(() => this.load(), 250); },
      total(e) { return (e.quant_section ? e.quant_section.question_count : 0) + (e.verbal_section ? e.verbal_section.question_count : 0); },
      async dup(e) { const r = await guard(() => API.post('/api/exams/' + e.id + '/duplicate'), 'أُنشئت نسخة'); if (r) this.load(); },
      async del(e) {
        const yes = await confirmBox({ title: 'حذف اختبار', message: 'سيُحذف الاختبار «' + e.title + '» وإعداداته. الأقسام لا تُحذف.', okText: 'حذف', danger: true });
        if (!yes) return;
        const r = await guard(() => API.del('/api/exams/' + e.id), 'حُذف الاختبار');
        if (r !== undefined) this.load();
      },
      async quick(e, formats) {
        this.busy = e.id;
        const r = await guard(() => API.post('/api/exams/' + e.id + '/export', { formats, variant: 'student' }));
        this.busy = null;
        if (r) { for (const k of formats) { const a = document.createElement('a'); a.href = r.files[k]; a.download = ''; document.body.appendChild(a); a.click(); a.remove(); } toast('اكتمل التصدير', 'ok'); this.load(); }
      },
    },
    template: `
    <div class="page">
      <div class="page-head"><h1>الاختبارات السابقة</h1><span class="spacer"></span>
        <input class="input sm" style="max-width:260px" v-model="q" @input="onSearch" placeholder="بحث…">
        <a class="btn primary" href="#/exams/new">＋ إنشاء اختبار</a></div>
      <div class="card">
        <table class="list" v-if="list.length">
          <tr><th>الاختبار</th><th>القسم الكمي</th><th>القسم اللفظي</th><th>الأسئلة</th><th>المدة</th><th>آخر تصدير</th><th></th></tr>
          <tr v-for="e in list" :key="e.id">
            <td><a :href="'#/exams/'+e.id"><b>{{ e.title }}</b></a> <span v-if="e.frozen" class="badge info">معتمد</span><div class="small muted">{{ fmtDate(e.updated_at) }}</div></td>
            <td class="small">{{ e.quant_section ? e.quant_section.title : '—' }}<div class="muted" v-if="e.quant_section">{{ e.quant_section.source }}</div></td>
            <td class="small">{{ e.verbal_section ? e.verbal_section.title : '—' }}<div class="muted" v-if="e.verbal_section">{{ e.verbal_section.source }}</div></td>
            <td>{{ num(total(e)) }}</td>
            <td class="nowrap">{{ e.duration ? num(e.duration) + ' دقيقة' : '—' }}</td>
            <td class="small muted nowrap">{{ e.last_export_at ? fmtDate(e.last_export_at) : 'لم يُصدَّر' }}</td>
            <td class="nowrap"><a class="btn sm primary" :href="'#/exams/'+e.id">فتح</a>
              <button class="btn sm" @click="quick(e,['pdf','docx'])" :disabled="busy===e.id">{{ busy===e.id ? 'جارٍ…' : 'تصدير Word وPDF' }}</button>
              <QDropdown label="المزيد" btn-class="btn sm"><button @click="dup(e)">نسخ الاختبار</button><div class="sep"></div><button @click="del(e)" style="color:#b42318">حذف</button></QDropdown></td>
          </tr>
        </table>
        <div v-else class="empty">لا توجد اختبارات بعد. <a href="#/exams/new">أنشئ اختبارًا</a></div>
      </div>
    </div>`,
  };

  // ================================================================ الإعدادات
  const F = (k, l, t, extra) => Object.assign({ k, l, t: t || 'text' }, extra || {});
  const CATS5 = [['analogy', 'التناظر اللفظي'], ['completion', 'إكمال الجمل'], ['odd', 'المفردة الشاذة'], ['context', 'الخطأ السياقي'], ['reading', 'استيعاب المقروء']];
  const TABS = [
    { id: 'org', l: 'الجهة والغلاف', fields: [
      F('cover.right_text', 'النص في المربع الأيمن أعلى الغلاف', 'textarea'),
      F('cover.left_text', 'اسم المدرسة / الجهة المُعِدّة (المربع الأيسر)', 'textarea'),
      F('organization_name', 'اسم المدرسة أو الجهة (للمرجع)'),
      F('cover.grade_label', 'عنوان جدول الدرجة'), F('cover.quant_label', 'تسمية عمود الكمي'), F('cover.verbal_label', 'تسمية عمود اللفظي'),
      F('cover.count_label', 'عبارة عدد الأسئلة'), F('cover.count_unit', 'وحدة العدد'), F('cover.duration_label', 'عبارة المدة'), F('cover.duration_unit', 'وحدة المدة'),
      F('cover.big_suffix', 'لاحقة العنوان الكبير (بعد عنوان الاختبار)'),
      F('cover.notes_title', 'عنوان التعليمات'), F('cover.notes', 'تعليمات الاختبار (سطر لكل تعليمة)', 'list'),
      F('cover.show_name_fields', 'إظهار خانتي اسم الطالب والصف والشعبة', 'bool'), F('cover.name_label', 'تسمية خانة الاسم'), F('cover.class_label', 'تسمية خانة الصف والشعبة'),
      F('cover.reminder_title', 'عنوان صندوق التنبيه'), F('cover.reminder_text', 'رسالة التنبيه أو التحفيز (اتركها فارغة لإخفاء الصندوق)', 'textarea'),
    ] },
    { id: 'texts', l: 'النصوص الثابتة', fields: [
      F('end_text', 'عبارة نهاية الاختبار'), F('quant_section_title', 'عنوان القسم الكمي'), F('verbal_section_title', 'عنوان القسم اللفظي'),
      F('header_quant_label', 'تسمية مصدر الكمي في الترويسة'), F('header_verbal_label', 'تسمية مصدر اللفظي في الترويسة'),
      F('odd_stem_text', 'نص سؤال المفردة الشاذة'), F('geometry_caption', 'العبارة تحت الرسم الهندسي'),
      F('compare_label_1', 'تسمية القيمة الأولى'), F('compare_label_2', 'تسمية القيمة الثانية'),
      F('compare_options', 'خيارات المقارنة الثابتة (أربعة بالترتيب)', 'list4'), F('option_labels', 'رموز الخيارات (أربعة)', 'list4'),
      F('answer_key_title', 'عنوان مفتاح الإجابة'),
    ] },
    { id: 'cats', l: 'تعريفات التصنيفات', fields: CATS5.flatMap(([k, l]) => [F('category_titles.' + k, 'عنوان: ' + l), F('category_definitions.' + k, 'تعريف: ' + l, 'textarea')]) },
    { id: 'fonts', l: 'الخطوط', fields: [
      F('font_family', 'نوع الخط (الافتراضي Calibri)', 'font'),
      F('question_font_pt', 'حجم خط السؤال', 'num', { u: 'نقطة', step: 0.5 }), F('option_font_pt', 'حجم خط الخيارات', 'num', { u: 'نقطة', step: 0.5 }),
      F('passage_font_pt', 'حجم خط نصوص القراءة', 'num', { u: 'نقطة', step: 0.5 }), F('title_font_pt', 'حجم عنوان القسم', 'num', { u: 'نقطة', step: 0.5 }),
      F('category_title_pt', 'حجم عنوان التصنيف', 'num', { u: 'نقطة', step: 0.5 }), F('category_def_pt', 'حجم تعريف التصنيف', 'num', { u: 'نقطة', step: 0.5 }),
      F('compare_label_pt', 'حجم تسميات المقارنة', 'num', { u: 'نقطة', step: 0.5 }), F('caption_font_pt', 'حجم عبارة «الرسم ليس على القياس»', 'num', { u: 'نقطة', step: 0.5 }),
      F('end_text_pt', 'حجم عبارة النهاية', 'num', { u: 'نقطة', step: 0.5 }), F('header_title_pt', 'حجم عنوان الترويسة', 'num', { u: 'نقطة', step: 0.5 }),
      F('header_source_pt', 'حجم مصادر الترويسة', 'num', { u: 'نقطة', step: 0.5 }), F('page_number_pt', 'حجم رقم الصفحة', 'num', { u: 'نقطة', step: 0.5 }),
      F('line_spacing', 'تباعد الأسطر (مضاعف)', 'num', { step: 0.05 }), F('number_bold', 'رقم السؤال بخط عريض', 'bool'), F('analogy_stem_bold', 'سؤال التناظر بخط عريض', 'bool'),
    ] },
    { id: 'page', l: 'الصفحة والمسافات', fields: [
      F('margin_top_cm', 'الهامش العلوي (بداية الأسئلة)', 'num', { u: 'سم', step: 0.1 }), F('margin_bottom_cm', 'الهامش السفلي', 'num', { u: 'سم', step: 0.1 }),
      F('margin_right_cm', 'الهامش الأيمن', 'num', { u: 'سم', step: 0.1 }), F('margin_left_cm', 'الهامش الأيسر', 'num', { u: 'سم', step: 0.1 }),
      F('column_gap_cm', 'المسافة بين نصفي الصفحة', 'num', { u: 'سم', step: 0.1 }), F('separator_width_pt', 'سُمك الخط الفاصل', 'num', { u: 'نقطة', step: 0.25 }),
      F('header_top_cm', 'بُعد الترويسة عن أعلى الورقة', 'num', { u: 'سم', step: 0.1 }), F('header_height_cm', 'ارتفاع مربعات الترويسة', 'num', { u: 'سم', step: 0.05 }),
      F('footer_bottom_cm', 'بُعد رقم الصفحة عن أسفل الورقة', 'num', { u: 'سم', step: 0.1 }), F('page_numbers', 'ترقيم الصفحات', 'bool'),
      F('question_gap_pt', 'المسافة بين الأسئلة', 'num', { u: 'نقطة', step: 1 }), F('stem_options_gap_pt', 'المسافة بين السؤال وخياراته', 'num', { u: 'نقطة', step: 1 }),
      F('paragraph_gap_pt', 'المسافة بين فقرات النص', 'num', { u: 'نقطة', step: 1 }), F('after_passage_gap_pt', 'المسافة بعد نص القراءة', 'num', { u: 'نقطة', step: 1 }),
      F('section_gap_pt', 'المسافة قبل عنوان القسم الثاني', 'num', { u: 'نقطة', step: 1 }), F('end_text_gap_pt', 'المسافة قبل عبارة النهاية', 'num', { u: 'نقطة', step: 1 }),
      F('option_label_width_cm', 'عرض عمود رمز الخيار (أ، ب…)', 'num', { u: 'سم', step: 0.05 }), F('border_width_pt', 'سُمك حدود الصناديق', 'num', { u: 'نقطة', step: 0.25 }),
    ] },
    { id: 'colors', l: 'تدرجات الرمادي', fields: [
      F('separator_color', 'لون الخط الفاصل بين النصفين', 'gray'), F('title_fill', 'خلفية عنوان القسم', 'gray'),
      F('correct_fill', 'تظليل الإجابة الصحيحة (نسخة المعلم)', 'gray'), F('border_color', 'لون الحدود', 'gray'),
    ] },
    { id: 'numbers', l: 'الأرقام والترقيم', fields: [
      F('digits', 'نمط الأرقام في المستند', 'select', { opts: [['hindi', 'هندية عربية ٠١٢٣'], ['western', 'لاتينية 0123']] }),
      F('percent_sign', 'شكل علامة النسبة المئوية', 'select', { opts: [['⁒', '⁒  (الافتراضي)'], ['٪', '٪'], ['%', '%']] }),
      F('decimal_style', 'الفاصلة العشرية', 'select', { opts: [['arabic', 'عربية ٣٫٥'], ['keep', 'كما كُتبت']] }),
      F('numbering', 'ترقيم الأسئلة', 'select', { opts: [['per_section', 'يبدأ من ١ في كل قسم'], ['continuous', 'متصل عبر القسمين']] }),
      F('number_format', 'صيغة رقم السؤال ({n} مكان الرقم)'), F('frac_scale', 'حجم أرقام الكسر نسبةً للنص', 'num', { step: 0.02 }),
    ] },
    { id: 'images', l: 'الصور', fields: [
      F('geometry_width_cm', 'العرض الافتراضي للرسم الهندسي', 'num', { u: 'سم', step: 0.1 }), F('chart_width_cm', 'العرض الافتراضي للرسم البياني', 'num', { u: 'سم', step: 0.1 }),
    ] },
    { id: 'export', l: 'التصدير والتحقق', fields: [
      F('word_layout_mode', 'توزيع ملف Word', 'select', { opts: [['match', 'مطابق لتوزيع PDF (فواصل أعمدة محسوبة) — موصى به'], ['flow', 'تدفق تلقائي داخل Word (أسهل للتعديل الحر)']] }),
      F('word_safety_pt', 'هامش أمان لكل عمود في Word', 'num', { u: 'نقطة', step: 1 }),
      F('min_questions', 'أقل عدد أسئلة للقسم', 'num', { step: 1 }), F('max_questions', 'أكثر عدد أسئلة للقسم', 'num', { step: 1 }),
    ] },
  ];

  function getPath(o, p) { return p.split('.').reduce((a, k) => (a == null ? a : a[k]), o); }
  function setPath(o, p, v) { const ks = p.split('.'); let a = o; for (let i = 0; i < ks.length - 1; i++) a = a[ks[i]]; a[ks[ks.length - 1]] = v; }
  function grayToHex(v) { const h = Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0').toUpperCase(); return '#' + h + h + h; }
  function hexToGray(hex) { const m = /^#?([0-9a-f]{2})/i.exec(hex || '#000000'); return m ? parseInt(m[1], 16) : 0; }

  const Settings = {
    data() { return { s: null, tab: 'org', presets: {}, dirty: false, sys: null }; },
    setup() { return { TABS, getPath, grayToHex, hexToGray }; },
    async mounted() {
      this.s = JSON.parse(JSON.stringify(await UIX.loadSettings()));
      this.presets = (await guard(() => API.get('/api/presets'))) || {};
      this.sys = await UIX.loadSystem();
      this.$watch('s', () => { this.dirty = true; }, { deep: true });
    },
    computed: { fields() { return (TABS.find((t) => t.id === this.tab) || TABS[0]).fields; } },
    methods: {
      val(f) { return getPath(this.s, f.k); },
      set(f, v) { setPath(this.s, f.k, v); },
      listText(f) { return (getPath(this.s, f.k) || []).join('\n'); },
      setList(f, text) { setPath(this.s, f.k, text.split('\n').map((x) => x.trim()).filter(Boolean)); },
      async save() {
        const r = await guard(() => API.put('/api/settings', this.s), 'حُفظت الإعدادات — ستُطبَّق على كل ملف تصدّره من الآن');
        if (r) { UIX.Store.settings = r; this.s = JSON.parse(JSON.stringify(r)); this.$nextTick(() => { this.dirty = false; }); this.sys = await UIX.loadSystem(); }
      },
      async preset(name) {
        const yes = await confirmBox({ title: 'تطبيق قالب تنسيق', message: 'سيُغيّر القالب أحجام الخطوط والمسافات والهوامش فقط، ولا يمس النصوص الثابتة. متابعة؟', okText: 'تطبيق' });
        if (!yes) return;
        const r = await guard(() => API.post('/api/settings/preset', { name }), 'طُبّق القالب');
        if (r) { UIX.Store.settings = r; this.s = JSON.parse(JSON.stringify(r)); this.$nextTick(() => { this.dirty = false; }); }
      },
      async reset() {
        const yes = await confirmBox({ title: 'استعادة الإعدادات الافتراضية', message: 'ستعود كل الإعدادات (النصوص والخطوط والمسافات) إلى القيم الافتراضية. لا تتأثر الأقسام والأسئلة.', okText: 'استعادة الافتراضي', danger: true });
        if (!yes) return;
        const r = await guard(() => API.post('/api/settings/reset'), 'استُعيدت الإعدادات الافتراضية');
        if (r) { UIX.Store.settings = r; this.s = JSON.parse(JSON.stringify(r)); this.$nextTick(() => { this.dirty = false; }); }
      },
    },
    template: `
    <div class="page" v-if="s">
      <div class="page-head"><h1>الإعدادات</h1><span class="sub">تؤثر في جميع ملفات Word وPDF المصدَّرة</span><span class="spacer"></span>
        <span v-if="dirty" class="badge warn">تعديلات غير محفوظة</span>
        <span class="lbl">قوالب جاهزة:</span>
        <button v-for="(n,k) in presets" :key="k" class="btn sm" @click="preset(k)">{{ n }}</button>
        <button class="btn sm danger" @click="reset">الافتراضي</button>
        <button class="btn primary" @click="save">حفظ الإعدادات</button></div>
      <div class="tabs"><button v-for="t in TABS" :key="t.id" :class="{on: tab===t.id}" @click="tab=t.id">{{ t.l }}</button></div>
      <div class="card"><div class="card-body">
        <div class="grid c2">
          <div v-for="f in fields" :key="f.k" class="field" :style="(f.t==='textarea'||f.t==='list'||f.t==='list4') ? 'grid-column: 1 / -1' : ''">
            <label>{{ f.l }}</label>
            <input v-if="f.t==='text'" class="input" :value="val(f)" @input="set(f, $event.target.value)">
            <textarea v-else-if="f.t==='textarea'" class="input" rows="2" :value="val(f)" @input="set(f, $event.target.value)"></textarea>
            <textarea v-else-if="f.t==='list'" class="input" rows="4" :value="listText(f)" @change="setList(f, $event.target.value)"></textarea>
            <div v-else-if="f.t==='list4'" class="grid c4"><input v-for="i in 4" :key="i" class="input" :value="(val(f)||[])[i-1]" @input="val(f)[i-1] = $event.target.value"></div>
            <div v-else-if="f.t==='num'" class="row"><input class="input" style="max-width:140px" type="number" :step="f.step||1" :value="val(f)" @input="set(f, Number($event.target.value))"><span class="muted small">{{ f.u }}</span></div>
            <label v-else-if="f.t==='bool'" class="check"><input type="checkbox" :checked="val(f)" @change="set(f, $event.target.checked)"> مفعّل</label>
            <select v-else-if="f.t==='select'" class="select" :value="val(f)" @change="set(f, $event.target.value)"><option v-for="o in f.opts" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
            <div v-else-if="f.t==='gray'" class="row"><input type="range" min="0" max="255" :value="hexToGray(val(f))" @input="set(f, grayToHex(Number($event.target.value)))" style="flex:1">
              <span class="gray-swatch" :style="{background: val(f)}"></span><span class="mono small">{{ val(f) }}</span></div>
            <div v-else-if="f.t==='font'" class="col" style="gap:6px"><input class="input" :value="val(f)" @input="set(f, $event.target.value)" list="fontlist">
              <datalist id="fontlist"><option value="Calibri"></option><option value="Arial"></option><option value="Tahoma"></option><option value="Sakkal Majalla"></option><option value="Traditional Arabic"></option><option value="Simplified Arabic"></option></datalist>
              <span v-if="sys && sys.font" class="hint">{{ sys.font.found ? ('✓ الخط «' + sys.font.family + '» موجود على هذا الجهاز' + (sys.font.has_arabic===false ? ' لكنه لا يحتوي حروفًا عربية' : '')) : ('✗ الخط «' + sys.font.family + '» غير موجود على هذا الجهاز (يُستخدم بديل في PDF فقط)') }}</span></div>
          </div>
        </div>
        <div v-if="tab==='cats'" class="hint" style="margin-top:12px">يظهر العنوان والتعريف مرة واحدة عند بداية كل مجموعة متتالية من التصنيف نفسه في القسم اللفظي.</div>
        <div v-if="tab==='export'" class="hint" style="margin-top:12px">في وضع «مطابق لـ PDF» يحسب البرنامج توزيع الأسئلة بقياساتها الفعلية ويضع فواصل الأعمدة في Word في المواضع نفسها؛ وهامش الأمان يمنع فيضان العمود إن اختلف عرض Word قليلًا.</div>
      </div></div>
    </div>`,
  };

  // ================================================================ النسخ الاحتياطي
  const Backup = {
    data() { return { mode: 'merge', busy: false, autos: [], sys: null }; },
    setup() { return { num }; },
    async mounted() { this.autos = (await guard(() => API.get('/api/backups'))) || []; this.sys = await UIX.loadSystem(); },
    methods: {
      pick() { this.$refs.f.click(); },
      async onFile(e) {
        const f = e.target.files && e.target.files[0]; e.target.value = '';
        if (!f) return;
        const msg = this.mode === 'replace'
          ? 'ستُستبدل جميع الأقسام والاختبارات والإعدادات الحالية بمحتوى النسخة الاحتياطية. (تُحفظ نسخة تلقائية من الوضع الحالي قبل الاستعادة.) للتأكيد اكتب: استبدال'
          : 'ستُضاف الأقسام والاختبارات من الملف بجانب الموجود حاليًا دون حذف شيء.';
        const yes = await confirmBox({ title: 'استعادة نسخة احتياطية', message: msg, okText: 'استعادة', danger: this.mode === 'replace', requireText: this.mode === 'replace' ? 'استبدال' : '' });
        if (!yes) return;
        this.busy = true;
        const r = await guard(() => API.upload('/api/restore', f, { mode: this.mode }));
        this.busy = false;
        if (r) { toast('تمت الاستعادة: ' + num(r.sections) + ' قسم، ' + num(r.exams) + ' اختبار، ' + num(r.media) + ' صورة', 'ok'); await UIX.loadSettings(); this.autos = (await guard(() => API.get('/api/backups'))) || []; }
      },
    },
    template: `
    <div class="page" style="max-width:900px">
      <div class="page-head"><h1>النسخ الاحتياطي</h1></div>
      <div class="col" style="gap:14px">
        <div class="card"><div class="card-head"><h3>إنشاء نسخة احتياطية كاملة</h3></div><div class="card-body col">
          <div class="hint">ملف واحد (zip) يحوي كل الأقسام والأسئلة بترتيبها، والصور، والاختبارات، والإعدادات — بصيغة JSON منظمة. احفظه في مكان آمن (فلاشة أو سحابة).</div>
          <div><a class="btn primary big" href="/api/backup">⬇ تنزيل نسخة احتياطية الآن</a></div>
        </div></div>
        <div class="card"><div class="card-head"><h3>استعادة من نسخة احتياطية</h3></div><div class="card-body col">
          <div class="row wrap">
            <label class="check"><input type="radio" value="merge" v-model="mode"> دمج مع البيانات الحالية (آمن)</label>
            <label class="check"><input type="radio" value="replace" v-model="mode"> استبدال كل البيانات الحالية</label>
          </div>
          <input ref="f" type="file" accept=".zip,.json" class="hidden" @change="onFile">
          <div><button class="btn" @click="pick" :disabled="busy">{{ busy ? 'جارٍ الاستعادة…' : 'اختيار ملف النسخة الاحتياطية…' }}</button></div>
          <div class="hint">يقبل أيضًا ملفات الأقسام المصدَّرة من صفحة الأقسام.</div>
        </div></div>
        <div class="card"><div class="card-head"><h3>النسخ التلقائية</h3></div><div class="card-body col">
          <div class="hint">يحفظ البرنامج نسخة تلقائية من قاعدة البيانات عند كل تشغيل وقبل كل استعادة (آخر ١٥ نسخة). مكان البيانات: <span class="mono small">{{ sys && sys.data_dir }}</span></div>
          <table class="list" v-if="autos.length"><tr v-for="a in autos" :key="a.name"><td class="mono small">{{ a.name }}</td><td class="small muted">{{ num(Math.round(a.size/1024)) }} ك.ب</td><td><a class="btn sm" :href="'/api/backups/'+a.name">تنزيل</a></td></tr></table>
          <div class="hint">لاستعادة نسخة تلقائية: أغلق البرنامج، ثم انسخ الملف إلى مجلد data وسمِّه exams.db بدل الملف الحالي.</div>
        </div></div>
      </div>
    </div>`,
  };

  global.QPages = { Home, SectionsList, SectionNew, ExamBuilder, ExamsList, Settings, Backup };
})(window);
