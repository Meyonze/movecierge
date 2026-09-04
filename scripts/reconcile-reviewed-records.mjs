import fs from 'node:fs';

const publicPath = new URL('../data/city_data.json', import.meta.url);
const reviewPath = new URL('../data/city_data_review.json', import.meta.url);

// Official links were checked on 2026-09-04.  These are the 90 records added
// to the existing 10-record batch, for a total reconciliation batch of 100.
const targetIds = [
  'toyohashishi', 'kasugaishi', 'hirakatashi', 'akashishi', 'tomakomaishi',
  'iwakishi', 'hirosakishi', 'numazushi', 'oyamashi', 'nobeokashi',
  'kawanishishi', 'kashiharashi', 'izumishi', 'matsubarashi', 'handashi',
  'kirishimashi', 'ebetsushi', 'chitoseshi', 'tsuchiurashi', 'kisarazushi',
  'sakurashi_chib', 'hatanoshi', 'koganeishi', 'kunitachishi', 'fussashi',
  'higashiyamatoshi', 'hamurashi', 'tondabayashishi', 'kawachinaganoshi',
  'ishinomakishi', 'tochigishi', 'takahamashi', 'chiryuushi', 'iwakurashi',
  'izumisanoshi', 'kashiwabarashi', 'onoshi', 'sumotoshi', 'miharashi',
  'onomichishi', 'hatsukaichishi', 'sanoshi', 'okegawashi', 'kitamotoshi',
  'fujimishi', 'satteshi', 'shiraokashi', 'zushishi', 'chitashi',
  'shijounawateshi', 'aioishi', 'goshoshi', 'kanoyashi', 'satsumasendaishi',
  'airashi', 'inzaishi', 'shibetsushi', 'sunagawashi', 'eniwashi', 'irumashi',
  'ootawarashi', 'chikuseishi', 'kimitsushi', 'yachimatashi', 'asahishi',
  'tomiokashi', 'shiroishishi', 'iwanumashi', 'kuriharashi',
  'higashimatsushimashi', 'kuroishishi', 'goshogawarashi', 'ichinosekishi',
  'oushuushi', 'oofunatoshi', 'tendoushi', 'shirakawashi', 'sukagawashi',
  'nirasakishi', 'fujiyoshidashi', 'okayashi', 'minokamoshi', 'tokishi',
  'itomanshi', 'tomigusukushi', 'shussuishi', 'ibusukishi',
  'ichikikushikinoshi', 'minamisatsumashi', 'amamishi'
];

if (targetIds.length !== 90 || new Set(targetIds).size !== targetIds.length) {
  throw new Error('The reconciliation target list must contain exactly 90 unique IDs.');
}

const publicData = JSON.parse(fs.readFileSync(publicPath, 'utf8'));
const reviewData = JSON.parse(fs.readFileSync(reviewPath, 'utf8'));
let newlyReconciled = 0;
const alreadyReconciled = [];

for (const id of targetIds) {
  const current = publicData[id];
  const reviewed = reviewData[id];
  if (!current || current.confidence !== 'high') {
    throw new Error(`${id}: expected a high-confidence public record`);
  }
  if (!reviewed) {
    alreadyReconciled.push(id);
    continue;
  }
  if (!reviewed || reviewed.confidence !== 'low' || !reviewed.office || !reviewed.links?.out || !reviewed.links?.in) {
    throw new Error(`${id}: expected a complete low-confidence review record`);
  }

  current.office = reviewed.office;
  current.links.out = reviewed.links.out;
  current.links.in = reviewed.links.in;
  current.links.mail = reviewed.links.mail ?? current.links.mail ?? null;
  delete reviewData[id];
  newlyReconciled += 1;
}

const result = {
  reconciled: targetIds.length,
  newlyReconciled,
  alreadyReconciled: alreadyReconciled.length,
  skipped: ['kishiwadashi (official URL returned 404)', 'higashimurayamashi (official site returned 403)'],
  remainingReviewRecords: Object.keys(reviewData).length
};

if (process.argv.includes('--write')) {
  fs.writeFileSync(publicPath, `${JSON.stringify(publicData, null, 2)}\n`);
  fs.writeFileSync(reviewPath, `${JSON.stringify(reviewData, null, 2)}\n`);
}

console.log(JSON.stringify(result, null, 2));
