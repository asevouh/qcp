/* api.js — الاتصال بالخادم المحلي */
(function (global) {
  'use strict';
  async function req(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      throw new Error('تعذر الاتصال بالبرنامج. تأكد أن نافذة البرنامج ما زالت مفتوحة ثم أعد المحاولة.');
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (!res.ok || !data || data.ok === false) {
      throw new Error((data && data.error) || ('خطأ في الخادم (' + res.status + ')'));
    }
    return data.data;
  }
  async function upload(url, file, fields) {
    const fd = new FormData();
    fd.append('file', file);
    for (const k in (fields || {})) fd.append(k, fields[k]);
    let res;
    try { res = await fetch(url, { method: 'POST', body: fd }); } catch (e) { throw new Error('تعذر الاتصال بالبرنامج.'); }
    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (!res.ok || !data || data.ok === false) throw new Error((data && data.error) || ('خطأ في الرفع (' + res.status + ')'));
    return data.data;
  }
  global.API = {
    get: (u) => req('GET', u),
    post: (u, b) => req('POST', u, b === undefined ? {} : b),
    put: (u, b) => req('PUT', u, b),
    del: (u) => req('DELETE', u),
    upload,
  };
})(window);
