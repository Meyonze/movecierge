import fs from 'node:fs';

const publicPath = new URL('../data/city_data.json', import.meta.url);
const reviewPath = new URL('../data/city_data_review.json', import.meta.url);

// Each official URL below returned a successful response on 2026-09-04.
const targetIds = [
  'rumoishi', 'ashibetsushi', 'akabirashi', 'mikasashi', 'dateshi',
  'hokutoshi', 'noshiroshi', 'ogashi', 'kazunoshi', 'yurihonjoushi',
  'kitaakitashi', 'nikahoshi', 'senbokushi', 'ishiokashi', 'hitachiootashi',
  'takahagishi', 'kitaibaragishi', 'kasamashi', 'hitachioomiyashi', 'nakashi',
  'bandoushi', 'inashikishi', 'kasumigaurashi', 'sakuragawashi', 'namegatashi',
  'hokotashi', 'tsukubamiraishi', 'omitamashi', 'isumishi', 'kanishi',
  'motosushi', 'nodashi', 'sodegaurashi', 'minamibousoushi', 'itoushi',
  'shimadashi', 'susonoshi', 'kosaishi', 'izushi', 'tsushimashi',
  'owariasahishi', 'nisshinshi', 'nagakuteshi', 'murotoshi', 'nangokushi',
  'tosashi', 'susakishi', 'kounanshi_kouc', 'kamishi', 'sakatashi',
  'ueyamashi', 'higashineshi', 'suzakashi', 'iiyamashi', 'chikumashi',
  'toumishi', 'ikedashi', 'moriguchishi', 'sennanshi', 'tonegunkatashinamura',
  'tonegunkawabamura', 'tonegunminakamimachi', 'ouragunmeiwamachi',
  'ouragunchiyodamachi', 'ouragunooizumichou', 'ouragunyuurakumachi',
  'ikomagunhegurimachi', 'ikomagunikarugamachi', 'shikigunkawanishimachi',
  'shikigunmiyakemachi', 'shikiguntawaramotomachi', 'udagunmitsuemura',
  'kitakatsuragigujoumakimachi', 'yoshinogunooyodomachi',
  'yoshinogunkurotakimura', 'yoshinogunamakawamura',
  'yoshinoguntotsugawamura', 'yoshinogunshimokitayamamura',
  'yoshinogunkawakamimura', 'kimotsukigunminamioosumimachi',
  'kumagegunchuushushimachi', 'kumagegunyakushimamachi',
  'ooshimaguntatsugoumachi', 'ooshimagunkikaimachi',
  'ooshimagunnoriyukishimamachi', 'ooshimagunamagimachi',
  'ooshimagunisenmachi', 'kitagunmagunshintoumura',
  'kitagunmagunyoshiokamachi', 'tanogunkannamachi', 'kanragunshimonitamachi',
  'kanragunkanramachi', 'azumagunchuuyukijoumachi', 'azumaguntsumagoimura',
  'azumagunkusatsumachi', 'kunigamigunkunigamimura', 'kamaketanishi',
  'uryuugunchippubetsumachi'
];

if (targetIds.length !== 98 || new Set(targetIds).size !== targetIds.length) {
  throw new Error('The reconciliation target list must contain exactly 98 unique IDs.');
}

const publicData = JSON.parse(fs.readFileSync(publicPath, 'utf8'));
const reviewData = JSON.parse(fs.readFileSync(reviewPath, 'utf8'));
let newlyReconciled = 0;
let alreadyReconciled = 0;

for (const id of targetIds) {
  const current = publicData[id];
  const reviewed = reviewData[id];
  if (!current || current.confidence !== 'high') {
    throw new Error(`${id}: expected a high-confidence public record`);
  }
  if (!reviewed) {
    alreadyReconciled += 1;
    continue;
  }
  if (reviewed.confidence !== 'low' || !reviewed.office || !reviewed.links?.out || !reviewed.links?.in) {
    throw new Error(`${id}: expected a complete low-confidence review record`);
  }

  current.office = reviewed.office;
  current.links.out = reviewed.links.out;
  current.links.in = reviewed.links.in;
  current.links.mail = reviewed.links.mail ?? current.links.mail ?? null;
  delete reviewData[id];
  newlyReconciled += 1;
}

if (process.argv.includes('--write')) {
  fs.writeFileSync(publicPath, `${JSON.stringify(publicData, null, 2)}\n`);
  fs.writeFileSync(reviewPath, `${JSON.stringify(reviewData, null, 2)}\n`);
}

console.log(JSON.stringify({
  reconciled: targetIds.length,
  newlyReconciled,
  alreadyReconciled,
  skipped: 14,
  remainingReviewRecords: Object.keys(reviewData).length
}, null, 2));
