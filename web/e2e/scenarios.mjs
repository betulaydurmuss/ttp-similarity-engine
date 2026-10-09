import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { launch } from './cdp.mjs';

const BASE = process.env.BASE_URL ?? 'http://localhost:8000/';
const out = fileURLToPath(new URL('./artifacts', import.meta.url));
mkdirSync(out, { recursive: true });
const results = [];
const b = await launch();

async function check(name, fn) {
  try {
    const detail = await fn();
    results.push({ ok: true, name, detail });
  } catch (error) {
    results.push({ ok: false, name, detail: String(error.message ?? error) });
  }
}

const q = (expr) => b.eval(expr);
const waitFor = async (expr, timeout = 4000) => {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await q(`Boolean(${expr})`)) return true;
    await b.sleep(100);
  }
  throw new Error(`zaman aşımı: ${expr}`);
};
const click = (selector, text = '') =>
  q(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.textContent.includes(${JSON.stringify(text)})); if (!el) throw new Error('yok: ' + ${JSON.stringify(selector + ' ' + text)}); el.click(); return true; })()`);

const brandVisible = (slot) =>
  q(`(() => { const el = document.querySelector('[data-brand-slot="${slot}"] [data-brand="emblem"]'); if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 20 && getComputedStyle(el).visibility === 'visible'; })()`);

await b.viewport(1440, 900, { reduced: false });
await b.goto('about:blank', 100);
await b.goto(BASE, 300);

await check('ilk açılışta logo sahnesi tam sürümle oynar', async () => {
  await waitFor(`document.querySelector('.ignition')`);
  const started = Date.now();
  await waitFor(`!document.querySelector('.ignition') && document.querySelector('.arrival')`, 9000);
  const ms = Date.now() - started;
  if (ms < 2500) throw new Error(`çok kısa: ${ms} ms`);
  return `${ms} ms`;
});
await check('logo giriş ekranındaki yerine görünür olarak iner', async () => {
  if (!(await brandVisible('arrival'))) throw new Error('giriş ekranında logo görünmüyor');
  return 'amblem ve yazı yerinde';
});
await check('yenilemede kısa imza sürümü oynar', async () => {
  await b.eval('location.reload(), true').catch(() => {});
  await b.sleep(250);
  await waitFor(`document.querySelector('.ignition')`);
  const started = Date.now();
  await waitFor(`!document.querySelector('.ignition') && document.querySelector('.arrival')`, 6000);
  const ms = Date.now() - started;
  if (ms > 3500 || ms < 900) throw new Error(`beklenmeyen süre: ${ms} ms`);
  return `${ms} ms`;
});
await check('Esc logo sahnesini anında atlar', async () => {
  await b.eval('location.reload(), true').catch(() => {});
  await b.sleep(350);
  await waitFor(`document.querySelector('.ignition')`);
  const started = Date.now();
  await b.key('Escape');
  await waitFor(`!document.querySelector('.ignition') && document.querySelector('.arrival')`, 3000);
  if (!(await brandVisible('arrival'))) throw new Error('atlamada logo kayboldu');
  return `${Date.now() - started} ms`;
});
await check('girişten çıkınca logo üst bara iner', async () => {
  await b.viewport(1440, 900);
  await b.key('Enter');
  await waitFor(`document.querySelector('aside.left') && !document.querySelector('.arrival')`);
  await b.sleep(1100);
  if (!(await brandVisible('bar'))) throw new Error('üst barda logo görünmüyor');
  return 'üst barda';
});
await check('gözleme geçince arama kutusu odaklanır', async () => {
  await waitFor(`document.activeElement?.id === 'technique-search'`);
  return 'odak arama kutusunda';
});
await check('yapıştırılan liste sorguya dönüşür ve sonuç gelir', async () => {
  await b.type('T1197 T1534 T1559 T1595 T1572 T1586 T1546 T1589');
  await b.key('Enter');
  await waitFor(`document.querySelectorAll('.tray li').length === 8`);
  await waitFor(`document.querySelector('.headline h3')`);
  return await q(`document.querySelector('.headline h3').textContent + ' · ' + document.querySelector('.lvl').textContent`);
});
await check('URL paylaşılabilir durumu taşır', async () => q(`location.hash`));
await check('ad ile arama öneri listesi verir', async () => {
  await q(`(() => { const i = document.getElementById('technique-search'); i.focus(); return true; })()`);
  await b.type('spearph');
  await waitFor(`document.querySelectorAll('#technique-results li').length > 0`);
  const first = await q(`document.querySelector('#technique-results li .id').textContent`);
  await b.key('Escape');
  return first;
});
await check('M matrisi açar; hücre seçimi sorguyu değiştirir; Esc kapatır', async () => {
  await q(`document.activeElement.blur(); true`);
  await b.key('m', 'KeyM');
  await waitFor(`document.querySelector('.matrix')`);
  const columns = await q(`document.querySelectorAll('.matrix .column').length`);
  await click('.matrix .cell', 'T1566');
  await waitFor(`document.querySelectorAll('.tray li').length === 9`);
  await b.key('Escape');
  await waitFor(`!document.querySelector('.matrix')`);
  return `${columns} taktik sütunu`;
});
await check('aday satırı aktör dosyasını açar', async () => {
  await click('.list li button', 'HEXANE');
  await waitFor(`document.querySelector('.drawer h2')`);
  return await q(`document.querySelector('.drawer h2').textContent`);
});
await check('dosyadan 1. adayla karşılaştırma açılır', async () => {
  await click('.drawer .btn', 'karşılaştır');
  await waitFor(`document.querySelector('.compare .big')`);
  const score = await q(`document.querySelector('.compare .big').textContent`);
  await b.shot(`${out}/e2e-compare.png`);
  await b.key('Escape');
  await waitFor(`!document.querySelector('.compare')`);
  return `benzerlik ${score}`;
});
await check('Esc dosyayı kapatır, sonuç paneli döner', async () => {
  await b.key('Escape');
  await waitFor(`!document.querySelector('.drawer') && document.querySelector('.headline')`);
  return 'tamam';
});
await check('F odak modunda paneller gizlenir, tekrar F geri getirir', async () => {
  await b.key('f', 'KeyF');
  await waitFor(`!document.querySelector('aside.left') && !document.querySelector('aside.right')`);
  await b.shot(`${out}/e2e-focus.png`);
  await b.key('f', 'KeyF');
  await waitFor(`document.querySelector('aside.left') && document.querySelector('aside.right')`);
  return 'tamam';
});
await check('Harita sekmesi: aktör araması ve dosya', async () => {
  await click('.modes button', 'Harita');
  await waitFor(`document.getElementById('actor-search')`);
  await q(`document.getElementById('actor-search').focus(); true`);
  await b.type('cozy bear');
  await waitFor(`document.querySelectorAll('.found button').length > 0`);
  const hit = await q(`document.querySelector('.found button').textContent.replace(/\\s+/g, ' ').trim()`);
  await click('.found button');
  await waitFor(`document.querySelector('.drawer h2')`);
  return hit;
});
await check('takımyıldız odağı haritayı süzer', async () => {
  await b.key('Escape');
  await click('.constellations button');
  await waitFor(`document.querySelectorAll('.star.faded').length > 100`);
  return await q(`document.querySelectorAll('.star.faded').length + ' yıldız soluklaştı'`);
});
await check('Güven sekmesi ölçümleri gösterir', async () => {
  await click('.modes button', 'Güven');
  await waitFor(`document.querySelectorAll('.regimes article').length === 3`);
  await b.shot(`${out}/e2e-trust.png`);
  return await q(`[...document.querySelectorAll('.regimes .value')].map(e => e.textContent).join(' / ')`);
});
await check('kör test: gizli aktör ve cevabın açılması', async () => {
  await click('.trust .btn', 'kör test');
  await waitFor(`document.querySelector('.blind button') && document.querySelector('.headline')`);
  await click('.blind button', 'Cevabı göster');
  await waitFor(`document.querySelector('.reveal strong')`);
  return await q(`document.querySelector('.reveal strong').textContent.replace(/\\s+/g, ' ') + ' — ' + document.querySelector('.reveal p').textContent.trim()`);
});
await check('gürültü enjeksiyonu kesikli tepsiye ekler', async () => {
  const before = await q(`document.querySelectorAll('.tray li').length`);
  await click('.tools .btn', 'Gürültü enjekte');
  await waitFor(`document.querySelectorAll('.tray li.injected').length > 0`);
  return `${before} → ${await q(`document.querySelectorAll('.tray li').length`)}`;
});
await check('masaüstünde konsol hatası yok', async () => {
  if (b.errors.length) throw new Error(b.errors.join(' | '));
  return 'temiz';
});

await b.viewport(390, 844, { mobile: true });
await b.goto('about:blank', 100);
await b.goto(`${BASE}#q=T1566,T1078,T1047,T1003,T1021,T1560,T1114,T1074`, 2200);
await check('telefonda sonuç hapı görünür ve sonuca kaydırır', async () => {
  await waitFor(`document.querySelector('.pill')`);
  await click('.pill');
  await waitFor(`!document.querySelector('.pill')`, 3000);
  return await q(`Math.round(document.querySelector('aside.right').getBoundingClientRect().top) + 'px'`);
});
await check('telefonda alt gezinti ekranın altında', async () => {
  const r = await q(`(() => { const r = document.querySelector('.modes').getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom), innerHeight]; })()`);
  if (Math.abs(r[1] - r[2]) > 1) throw new Error(JSON.stringify(r));
  return JSON.stringify(r);
});
await check('telefonda dosya açılınca görünür alana kayar', async () => {
  await q(`window.scrollTo(0, 0); true`);
  await click('.list li button', 'FIN');
  await waitFor(`document.querySelector('.drawer h2')`);
  await b.sleep(600);
  const top = await q(`Math.round(document.querySelector('aside.right').getBoundingClientRect().top)`);
  await b.shot(`${out}/e2e-phone-dossier.png`);
  if (top > 300) throw new Error(`dosya görünmüyor: top=${top}`);
  return `top=${top}`;
});
await check('telefonda matris kullanılabilir', async () => {
  await click('.modes button', 'Gözlem');
  await b.key('Escape');
  await click('.tools .btn', 'Matristen');
  await waitFor(`document.querySelector('.matrix')`);
  await b.shot(`${out}/e2e-phone-matrix.png`);
  const scrollable = await q(`(() => { const g = document.querySelector('.matrix .grid'); return g.scrollWidth > g.clientWidth; })()`);
  await b.key('Escape');
  return scrollable ? 'yatay kaydırılabilir' : 'sığıyor';
});
await check('telefonda konsol hatası yok', async () => {
  if (b.errors.length) throw new Error(b.errors.join(' | '));
  return 'temiz';
});

await b.close();
const failed = results.filter((r) => !r.ok);
for (const r of results) console.log(`${r.ok ? 'GEÇTİ' : 'KALDI'}  ${r.name}  →  ${r.detail}`);
console.log(`\n${results.length - failed.length}/${results.length} senaryo geçti`);
process.exit(failed.length ? 1 : 0);
