/* app.js — الهيكل العام والتنقل */
(function () {
  'use strict';
  const { createApp, reactive, computed, markRaw } = Vue;
  const { Store, toasts, dialog, closeDialog, MathDialog, toast, confirmBox, num } = UIX;
  const P = QPages;

  const ROUTES = [
    { re: /^\/?$/, comp: P.Home, nav: 'home' },
    { re: /^\/sections\/new$/, comp: P.SectionNew, nav: 'new-section' },
    { re: /^\/sections\/(\d+)$/, comp: QSectionEditor, nav: 'sections', params: ['id'] },
    { re: /^\/sections$/, comp: P.SectionsList, nav: 'sections' },
    { re: /^\/exams\/new$/, comp: P.ExamBuilder, nav: 'new-exam' },
    { re: /^\/exams\/(\d+)$/, comp: P.ExamBuilder, nav: 'exams', params: ['id'] },
    { re: /^\/exams$/, comp: P.ExamsList, nav: 'exams' },
    { re: /^\/settings$/, comp: P.Settings, nav: 'settings' },
    { re: /^\/backup$/, comp: P.Backup, nav: 'backup' },
  ];

  function parse(hash) {
    const raw = (hash || '').replace(/^#/, '') || '/';
    const qi = raw.indexOf('?');
    const path = qi >= 0 ? raw.slice(0, qi) : raw;
    const query = new URLSearchParams(qi >= 0 ? raw.slice(qi + 1) : '');
    for (const r of ROUTES) {
      const m = r.re.exec(path);
      if (m) {
        const params = {};
        (r.params || []).forEach((p, i) => { params[p] = m[i + 1]; });
        const back = query.get('back');
        if (back && /^#\/[\w\/]+$/.test(back) && r.comp === QSectionEditor) params.back = back;
        return { comp: markRaw(r.comp), nav: r.nav, params, path };
      }
    }
    return { comp: markRaw(P.Home), nav: 'home', params: {}, path };
  }

  // ------------------------------------------------------------ شاشة الترخيص (أول تشغيل)
  const LicenseGate = {
    props: { lic: Object },
    emits: ['accepted'],
    data() { return { reached: false, ack: false, busy: false, declined: false, error: '' }; },
    computed: {
      // للعرض فقط: إخفاء أسطر الفواصل (=====) دون أي تغيير في نص الترخيص نفسه
      shown() { return (this.lic.text || '').split('\n').filter((l) => !/^=+$/.test(l.trim())).join('\n').replace(/\n{3,}/g, '\n\n'); },
    },
    mounted() { this.$nextTick(() => this.onScroll()); },
    methods: {
      onScroll() {
        const b = this.$refs.box;
        if (b && b.scrollTop + b.clientHeight >= b.scrollHeight - 8) this.reached = true;
      },
      async accept() {
        if (!this.ack || !this.reached) return;
        this.busy = true; this.error = '';
        try { await API.post('/api/license/accept', { acknowledged: true }); this.$emit('accepted'); }
        catch (e) { this.error = e.message; }
        finally { this.busy = false; }
      },
      async decline() {
        this.declined = true;
        try { await API.post('/api/shutdown'); } catch (e) { /* ignore */ }
      },
    },
    template: `
    <div class="lic-wrap">
      <div class="lic-card" v-if="declined">
        <h2>لم يُقبل الترخيص</h2>
        <p>لا يمكن استخدام البرنامج دون قبول ترخيصه. توقف البرنامج، ويمكنك إغلاق هذه الصفحة.</p>
      </div>
      <div class="lic-card" v-else-if="lic.state !== 'ok'">
        <h2>تعذر تشغيل البرنامج</h2>
        <p>ملف الترخيص (LICENSE.txt) {{ lic.state === 'missing' ? 'مفقود' : 'معدَّل أو غير مطابق للنسخة الأصلية' }}.
          لا يعمل البرنامج إلا مع نص الترخيص الأصلي كاملًا دون تعديل.</p>
        <p>احصل على النسخة الأصلية من البرنامج والترخيص بالتواصل مع صانع البرنامج.</p>
      </div>
      <div class="lic-card" v-else>
        <h2>ترخيص الاستخدام وسياسات البرنامج</h2>
        <p class="hint">يجب قراءة بنود الترخيص كاملةً والإقرار بقبولها قبل استخدام البرنامج.</p>
        <div ref="box" class="lic-text" @scroll="onScroll" tabindex="0">{{ shown }}</div>
        <div class="hint" v-if="!reached">مرّر النص حتى نهايته لتفعيل الإقرار.</div>
        <label class="check lic-ack" :class="{dim: !reached}">
          <input type="checkbox" v-model="ack" :disabled="!reached">
          أقرّ بأنني قرأت بنود الترخيص وسياسات الاستخدام كاملةً وفهمتها، وأوافق على الالتزام بها.
        </label>
        <div class="alert error" v-if="error">{{ error }}</div>
        <div class="row">
          <button class="btn primary big" :disabled="!(ack && reached) || busy" @click="accept">{{ busy ? 'جارٍ الحفظ…' : 'أوافق — متابعة إلى البرنامج' }}</button>
          <button class="btn" @click="decline">لا أوافق — إغلاق البرنامج</button>
        </div>
      </div>
    </div>`,
  };

  const App = {
    setup() {
      const state = reactive({ route: parse(location.hash), key: 1, ready: false, lic: null });
      let current = location.hash;
      window.addEventListener('hashchange', async () => {
        if (location.hash === current) return;
        if (UIX.leaveGuard) {
          try { await UIX.leaveGuard(); } catch (e) { /* ignore */ }
        }
        current = location.hash;
        state.route = parse(location.hash);
        state.key++;
      });
      async function boot() {
        try { await UIX.loadSettings(); } catch (e) { toast(e.message, 'error'); }
        await UIX.loadSystem();
        state.ready = true;
      }
      (async () => {
        try { state.lic = await API.get('/api/license'); } catch (e) { state.lic = { state: 'missing', accepted: false }; }
        if (state.lic.state === 'ok' && state.lic.accepted) await boot();
      })();
      async function onAccepted() { state.lic = Object.assign({}, state.lic, { accepted: true }); await boot(); }
      async function stop() {
        const yes = await confirmBox({ title: 'إيقاف البرنامج', message: 'سيتوقف البرنامج وتُغلق نافذته. كل البيانات محفوظة. لتشغيله مرة أخرى استخدم ملف التشغيل.', okText: 'إيقاف' });
        if (!yes) return;
        if (UIX.leaveGuard) await UIX.leaveGuard();
        try { await API.post('/api/shutdown'); } catch (e) { /* ignore */ }
        document.body.innerHTML = '<div style="padding:60px;text-align:center;font-size:20px;font-family:sans-serif">توقف البرنامج. يمكنك إغلاق هذه الصفحة.</div>';
      }
      const nav = [
        { id: 'home', href: '#/', l: 'الرئيسية', i: '⌂' },
        { id: 'sections', href: '#/sections', l: 'الأقسام', i: '☰' },
        { id: 'new-section', href: '#/sections/new', l: 'إنشاء قسم', i: '＋' },
        { id: 'new-exam', href: '#/exams/new', l: 'إنشاء اختبار', i: '✎' },
        { id: 'exams', href: '#/exams', l: 'الاختبارات السابقة', i: '🗂' },
        { id: 'settings', href: '#/settings', l: 'الإعدادات', i: '⚙' },
        { id: 'backup', href: '#/backup', l: 'النسخ الاحتياطي', i: '⛁' },
      ];
      window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && dialog.open) closeDialog(false); });
      window.addEventListener('hashchange', () => { if (dialog.open) closeDialog(false); });
      const fontOk = computed(() => !Store.system || !Store.system.font || Store.system.font.found);
      return { state, nav, toasts, dialog, closeDialog, stop, Store, fontOk, num, onAccepted };
    },
    components: { MathDialog, LicenseGate },
    template: `
    <div v-if="!state.lic" class="lic-wrap"><div class="empty">جارٍ التحميل…</div></div>
    <LicenseGate v-else-if="!(state.lic.state==='ok' && state.lic.accepted)" :lic="state.lic" @accepted="onAccepted"/>
    <div class="shell" v-else>
      <aside class="sidebar">
        <div class="brand"><div class="t1">مُنشئ اختبارات القدرات</div><div class="t2">اختبارات ورقية محاكية — كمي ولفظي</div></div>
        <nav class="nav"><a v-for="n in nav" :key="n.id" :href="n.href" :class="{active: state.route.nav===n.id}"><span class="ico">{{ n.i }}</span>{{ n.l }}</a>
          <a href="/static/guide.html" target="_blank"><span class="ico">📖</span>دليل الاستخدام</a>
          <a href="/license.txt" target="_blank"><span class="ico">§</span>الترخيص</a></nav>
        <div class="side-foot">
          <div class="status" v-if="Store.system"><span>{{ fontOk ? '●' : '▲' }}</span>
            <span>الخط: {{ Store.system.font.family }} {{ fontOk ? '(متوفر)' : '(غير متوفر — يُستخدم بديل في PDF)' }}</span></div>
          <div class="status" v-if="Store.system"><span>●</span><span>الإصدار {{ Store.system.version }}</span></div>
          <div class="status"><span>●</span><span>البرنامج الأصلي من تصميم وبناء علي برغله</span></div>
          <button @click="stop">إيقاف البرنامج</button>
        </div>
      </aside>
      <main class="main">
        <component v-if="state.ready" :is="state.route.comp" :key="state.key" v-bind="state.route.params"></component>
        <div v-else class="page"><div class="empty">جارٍ التحميل…</div></div>
      </main>
    </div>
    <MathDialog/>
    <div class="modal-back" v-if="dialog.open" @mousedown.self="closeDialog(false)">
      <div class="modal">
        <div class="modal-head"><h3>{{ dialog.title }}</h3></div>
        <div class="modal-body col">
          <div style="line-height:1.8">{{ dialog.message }}</div>
          <ul v-if="dialog.details" style="margin:0;padding-inline-start:20px;line-height:1.8"><li v-for="d in dialog.details" :key="d">{{ d }}</li></ul>
          <input v-if="dialog.requireText" class="input" v-model="dialog.typed" :placeholder="'اكتب: ' + dialog.requireText" @keydown.enter="dialog.typed.trim()===dialog.requireText && closeDialog(true)">
        </div>
        <div class="modal-foot">
          <button class="btn" :class="dialog.danger ? 'danger solid' : 'primary'" :disabled="!!dialog.requireText && dialog.typed.trim()!==dialog.requireText" @click="closeDialog(true)">{{ dialog.okText }}</button>
          <button class="btn" @click="closeDialog(false)">{{ dialog.cancelText }}</button>
        </div>
      </div>
    </div>
    <div class="toasts"><div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">{{ t.msg }}</div></div>`,
  };

  const app = createApp(App);
  app.config.errorHandler = (err) => { console.error(err); toast('خطأ في الواجهة: ' + (err && err.message), 'error'); };
  app.mount('#app');
})();
