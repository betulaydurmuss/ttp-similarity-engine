# Karar Kaydı (DECISIONS)

Bu dosya, projedeki **yöntem seçimlerinin, eşik değerlerinin ve terim kararlarının** gerekçesini tutar. Amaç, altı ay sonra "burada neden 0.70 yazıyor?" sorusuna cevap verebilmek ve üç kişilik ekibin aynı kararları iki farklı yerde tekrar tartışmasını önlemek.

**Kural:** `ttp_similarity/config.py` içindeki bir sabit değiştirildiğinde bu dosya da aynı commit'te güncellenir. Sabitin kendisi kodda, gerekçesi burada durur.

Durum etiketleri: **Kabul** (uygulanacak), **Açık** (henüz karar verilmedi), **Yeniden değerlendirilecek** (gerçek veri geldikten sonra ölçülüp karara bağlanacak).

---

## 1. Terim kararları

Ekip içinde ve çıktılarda tek dil kullanılması için:

| Terim | Anlamı | Kullanılmayacak karşılıklar |
|---|---|---|
| **Aktör (actor)** | ATT&CK `intrusion-set` nesnesine karşılık gelen, tek kimlik altında birleştirilmiş tehdit grubu | "APT", "grup", "düşman" (belirsiz) |
| **Teknik (technique)** | Ana seviye ATT&CK tekniği (`T1059`). Alt teknikler indirgenmiştir. | "TTP" (tekil nesne için) |
| **TTP seti** | Bir olaydan/sorgudan gelen teknik kimlikleri kümesi | "IOC listesi" (farklı şey) |
| **Benzerlik (similarity)** | İki ağırlıklı vektör arasındaki kosinüs değeri, `[0, 1]` | "eşleşme", "match" |
| **Aday (candidate)** | Sorgu sonucunda sıralanan aktör | "şüpheli", "fail" — **kesinlikle kullanılmaz** |
| **Güven (confidence)** | Sıralamanın ne kadar dayanaklı olduğunun ölçüsü | "olasılık", "probability" — istatistiksel olasılık değildir |
| **Kanıt (evidence)** | Bir adayın skorunu üreten teknikler ve katkı payları | "delil" (hukuki çağrışım) |
| **Attribution** | Faillik atfı. **Bu proje attribution yapmaz.** | — |

**Kabul.** Kullanıcıya görünen hiçbir metinde "fail", "sorumlu", "attribution" ifadesi bir sonuçla birlikte kullanılmaz. Sonuç ekranı hep `config.DISCLAIMER` ile birlikte gösterilir.

---

## 2. Veri normalizasyonu

### 2.1 Alt teknikler ana tekniğe indirgenir
`ROLL_UP_SUBTECHNIQUES = True` — **Kabul.**

`T1059.003` → `T1059`. Gerekçe: ATT&CK grup sayfalarında alt teknik detayı son derece dengesizdir. Hakkında çok yazılmış bir aktörün alt teknikleri tek tek listelenirken, az yazılmış bir aktörde yalnızca ana teknik geçer. Alt teknikler korunursa model, davranış farkını değil **raporlama derinliğini** ölçer.

Bedeli: `T1059.001 (PowerShell)` ile `T1059.004 (Unix Shell)` arasındaki gerçek fark kaybolur. Bu bilinçli bir kayıptır.

**Yeniden değerlendirilecek:** Gerçek veri geldikten sonra, alt teknik korunan bir varyantla `evaluation` karşılaştırması yapılıp top-1 farkı ölçülecek.

### 2.2 Aktör kimliği ve takma ad birleştirme
**Kabul.** Bir aktör = bir `actor_id`. Kimlik olarak ATT&CK grup kimliği (`G0016`) kullanılır — kalıcı, okunabilir ve MITRE tarafında kararlıdır. STIX UUID'si kullanılmaz (sürümler arası değişebilir ve okunamaz).

Birleştirme kuralı: iki kaydın `slugify` edilmiş ad/takma adlarından herhangi biri eşleşiyorsa aynı kimliktir; teknik kümeleri birleştirilir (union).

**Açık:** Genel takma adlar (`UNC`, `TA`, `Group`) üzerinden zincirleme yanlış birleşme riski var. `ALIAS_STOPLIST` gerekiyor. Her birleşme loglanacak ve gözden geçirilecek.

### 2.3 Kapsam dışı bırakılanlar
**Kabul.**
- `revoked` ve `x_mitre_deprecated` nesneler elenir (`DROP_REVOKED`, `DROP_DEPRECATED`).
- Yalnızca `intrusion-set → attack-pattern` yönündeki doğrudan `uses` ilişkileri alınır.

**Kabul (varsayılan hayır):** Dolaylı `aktör → malware → teknik` ilişkileri **dahil edilmez**. Gerekçe: bunlar aktörün davranışını değil, kullandığı aracın yeteneklerini ölçer; araçlar aktörler arasında paylaşılır ve bu, yapay benzerlik üretir. Değiştirilirse burada gerekçesiyle yazılır.

### 2.4 Seyrek aktör eşiği
`MIN_TECHNIQUES_PER_ACTOR = 5` — **Yeniden değerlendirilecek.**

5'ten az tekniği olan aktörün vektörü, hakkında anlamlı bir benzerlik cümlesi kurmak için fazla seyrektir; kosinüs benzerliği bu aktörleri rastgele biçimde bazı adaylara çok yakın gösterir. 5 şu an bir tahmindir; gerçek dağılım görüldükten sonra ATT&CK aktör teknik sayısı histogramına bakılarak kesinleştirilecek.

---

## 3. Ağırlıklandırma yöntemi

### 3.1 Şema
`WEIGHTING_SCHEME = "smooth_idf"` — **Kabul.**

```
w(t) = ln((N + s) / (df(t) + s)) + 1        s = IDF_SMOOTHING = 1.0
```

`N` = aktör sayısı, `df(t)` = tekniği kullanan aktör sayısı.

Gerekçe: Nadir teknikler ayırt edicidir, yaygın teknikler değildir — TF-IDF mantığının doğrudan karşılığı. Herkeste bulunan `T1059` iki aktörü benzer göstermemelidir; yalnızca iki aktörde geçen bir teknik ise güçlü bir sinyaldir.

`+ 1` tabanı neden var: `plain_idf` kullanılsaydı, bütün aktörlerde geçen bir teknik tam olarak 0 ağırlık alırdı. Bu durumda yalnızca yaygın tekniklerden oluşan bir sorgu **boş sonuç** döndürürdü. Oysa doğru davranış, sonuç döndürüp **güveni düşük** etiketlemektir. Taban, bu davranışı mümkün kılar.

Alternatifler kodda korunuyor:
- `plain_idf` — daha keskin ayrım, boş sonuç riski.
- `binary` — ablasyon temeli. `evaluation` bununla bir kez çalıştırılıp ağırlıklandırmanın kaç puan kazandırdığı raporlanacak. Bu, projenin en önemli tek ölçümüdür.

### 3.2 Terim frekansı ikilidir
`BINARY_TERM_FREQUENCY = True` — **Kabul.**

ATT&CK bir aktörün bir tekniği kaç kez kullandığını raporlamaz; yalnızca kullandığını söyler. Sayım uydurmak, olmayan bir sinyal üretmek olurdu.

### 3.3 Vektörler L2 normalize edilir
`NORMALIZE_VECTORS = True` — **Kabul.**

Aksi halde hakkında çok yazılmış (dolayısıyla uzun vektörlü) aktörler her sorguda üste çıkardı. Normalizasyon, "kaç teknik" yerine "hangi teknikler" sorusunu öne alır ve nokta çarpımı doğrudan kosinüs benzerliğine eşitler.

---

## 4. Benzerlik ve kümeleme

### 4.1 Metrik
`SIMILARITY_METRIC = "cosine"` — **Kabul.** Ağırlıklı vektörler üzerinde kosinüs; aktörün belgelenme hacminden bağımsız olarak davranışın **şeklini** karşılaştırır.

`jaccard` ağırlıksız kontrol olarak korunur. İki sıralama her yerde aynı çıkıyorsa ağırlıklandırma hiçbir şey kazandırmıyor demektir; bu bir hata sinyalidir.

### 4.2 Kümeleme
`CLUSTERING_METHOD = "agglomerative"`, `CLUSTERING_LINKAGE = "average"` — **Kabul.**

Gerekçe: küme sayısını önceden bilmiyoruz ve küme şekli hakkında varsayım yapmak istemiyoruz. Hiyerarşik kümeleme, önceden hesaplanmış kosinüs uzaklık matrisi üzerinde çalışır ve tahmin edilmiş bir `k` yerine bir uzaklık eşiğinden kesilebilir. `ward` bağlantısı önceden hesaplanmış uzaklık matrisiyle geçerli değildir, bu yüzden `average` seçildi.

`CLUSTERING_DISTANCE_THRESHOLD = 0.65` — **Yeniden değerlendirilecek.** Yani kosinüs benzerliği 0.35'in üzerinde kalan aktörler birleşir. Şu an tahmindir; sahte veri setinde 5 aileyi geri bulup bulmadığına bakılarak, ardından gerçek veride dendrogram incelenerek kesinleştirilecek. Doğrulama ölçütü: `data/mock/mock_ground_truth.csv` içindeki aile etiketlerine karşı ARI (adjusted Rand index).

`MIN_CLUSTER_SIZE = 2` — tek üyeli kümeler `-1` (atanmamış) olarak etiketlenir; tek başına duran bir aktör için "küme" demek yanıltıcıdır.

**Açık:** `kmeans` vektörler üzerinde çalışır, uzaklık matrisi üzerinde değil. Uygulanacaksa `cluster_actors` imzasının `VectorSpace` de alması gerekir. Karar verilene kadar `agglomerative` tek desteklenen yoldur.

---

## 5. Güven skoru

**Kabul.** Üç bileşenli ağırlıklı ortalama. Tek bir benzerlik sayısı yanıltıcıdır: en iyi aday her zaman vardır, sorgu üç yaygın teknikten ibaret olsa bile.

```
score = 0.40 * rarity + 0.35 * margin + 0.25 * sufficiency
```

`CONFIDENCE_COMPONENT_WEIGHTS` — **Yeniden değerlendirilecek** (kalibrasyon sonrası).

### 5.1 Nadirlik (rarity) — 0.40
Eşleşen tekniklerin **ortalama** ağırlığı, veri setindeki maksimum ağırlığa bölünür.

Neden ortalama, maksimum değil: maksimum kullanılsaydı, tek bir nadir tekniği bir sürü yaygın teknikle doldurmak güveni yüksek tutardı. Ortalama bu doldurmayı cezalandırır — istenen davranış budur.

En yüksek ağırlığa sahip bileşendir, çünkü ayırt edicilik olmadan sıralama zaten anlamsızdır.

### 5.2 Fark (margin) — 0.35
```
margin = min(1, ((skor_1 - skor_2) / skor_1) / MARGIN_SATURATION)
```
`MARGIN_SATURATION = 0.15` — **Yeniden değerlendirilecek.**

Yani 1. ve 2. aday arasında %15 göreli fark varsa bileşen doyuma ulaşır. Pratikte kosinüs farkları küçüktür, bu yüzden tavan düşük tutuldu; gerçek veride skor dağılımı görüldükten sonra ölçülüp güncellenecek.

Tek aday varsa bileşen 1.0'dır — karışacak bir şey yoktur. Berabere kalan iki aday, "bunlardan biri" demektir, "bu" değil; sonuç bu şekilde okunmalıdır.

### 5.3 Yeterlilik (sufficiency) — 0.25
```
sufficiency = clip((n - MIN_QUERY_TECHNIQUES) / (SUFFICIENCY_SATURATION - MIN_QUERY_TECHNIQUES), 0, 1)
```
`MIN_QUERY_TECHNIQUES = 3`, `SUFFICIENCY_SATURATION = 12` — **Yeniden değerlendirilecek.**

Yalnızca veri setinin sözlüğünde bulunan teknikler sayılır; tanınmayan kimlikler yeterliliğe katkı yapmaz.

12 sayısı, `evaluation` modülünün sorgu boyutu eğrisinden belirlenecek: top-1 doğruluğun platoya girdiği nokta doyum noktasıdır. Şu anki değer bir başlangıç tahminidir.

### 5.4 Eşikler
`CONFIDENCE_HIGH_THRESHOLD = 0.70`, `CONFIDENCE_MEDIUM_THRESHOLD = 0.45` — **Yeniden değerlendirilecek.**

Kalibrasyon ölçütü `evaluation.metrics.breakdown_by_confidence` tablosudur: `yüksek` etiketli sorguların top-1 doğruluğu `düşük` etiketlilerden **belirgin biçimde** yüksek olmalıdır. Değilse eşikler ya da bileşen ağırlıkları yanlıştır. Hedef: `yüksek` için top-1 ≥ 0.80, `düşük` için ≤ 0.40. Bu hedefler gerçek veri sonrası gözden geçirilecek.

**Açık:** Sert kural gerekli mi — `MIN_QUERY_TECHNIQUES`'ten az tanınan teknik girildiğinde, teknikler ne kadar nadir olursa olsun sonuç asla `düşük`ün üstüne çıkamasın mı? Eğilim: evet. Karara bağlanınca `confidence.score_confidence` içinde uygulanacak ve buraya yazılacak.

### 5.5 Kanıt döndürülmesi
**Kabul.** Her aday için, skoru üreten teknikler ve katkı payları (`evidence`) ile **aday aktörde görülmeyen sorgu teknikleri** (`missing_technique_ids`) döndürülür. Gerekçe: analiste "bu aktör 9 tekniğinizin 6'sıyla eşleşiyor, bunlar da eşleşmiyor" denebilmelidir. Açıklanamayan bir sıralama, denetlenemeyeceği için kullanılabilir istihbarat değildir.

`MAX_EVIDENCE_TECHNIQUES = 8` — arayüzde okunabilirlik sınırı, yöntemsel bir karar değil.

---

## 6. Sorgu modu

`QUERY_TOP_K = 10` — **Kabul.** Arayüzde bir ekrana sığar, `evaluation` için top-1/top-3 hesaplamaya fazlasıyla yeter.

`MIN_CANDIDATE_SCORE = 0.05` — **Kabul.** Bunun altındaki adaylar listeden düşer; sıfıra yakın skorlu 10 aday göstermek, olmayan bir bilgi varmış izlenimi verir.

**Kabul.** Tanınmayan teknik kimlikleri sessizce atılmaz, `unknown_technique_ids` içinde geri döndürülür. Analiste "12 tekniğinizden 3'ü bu veri setinde yok" denmelidir; aksi halde sorulmayan bir soru cevaplanmış olur.

**Kabul.** Eşitlik durumunda sıralama `actor_id`'ye göre deterministik olarak bozulur, aksi halde `evaluation` sonuçları tekrarlanabilir olmaz.

---

## 7. Başarım testi

**Kabul.** Bilinen aktörün tekniklerinden rastgele `k` tanesi çekilir, sorgu moduna verilir, doğru aktörün sırasına bakılır. Ölçüler: top-1, top-3, MRR; sorgu boyutuna ve güven seviyesine göre kırılımlar.

`EVAL_SAMPLE_SIZES = (3, 5, 8, 12)`, `EVAL_TRIALS_PER_ACTOR = 10`, `EVAL_RANDOM_SEED = 1337` — **Kabul** (tekrarlanabilirlik için tohum sabit).

**Kabul.** Sorgu boyutundan az tekniği olan aktör o boyut için **atlanır**, tamamlanmaz. Tamamlama bilgi sızdırır.

**Kabul (sınırlılık olarak yazılacak).** Alt küme, motorun indekslediği aynı kayıtlardan çekildiği için ölçülen şey **erişim tutarlılığıdır**, gerçek dünya doğruluğu değil. Gerçek olay verisi gürültülüdür, eksiktir ve aktöre atfedilmemiş teknikler içerir. Bu, raporda açıkça belirtilecek.

**Açık:** Gürültülü örnekleme modu (`sample_with_noise`) — aktöre ait olmayan `k` teknik enjekte edilir. Gerçek dünyaya en yakın ölçüm budur ve eklenmesi güçlü biçimde öneriliyor. Temel test çalıştıktan sonra karara bağlanacak.

---

## 8. Mimari kararlar

**Kabul — modüller arası veri diskten geçer.** Hiçbir modül diğerinin bellekteki nesnesine dokunmaz. Gerekçe: üç kişi paralel çalışıyor; dosya sözleşmesi, sınıf sözleşmesinden daha zor bozulur ve her aşama tek başına yeniden çalıştırılabilir olur. Bedeli: bir miktar serileştirme maliyeti. Bu veri boyutunda (yüzlerce aktör, yüzlerce teknik) önemsizdir.

**Kabul — ortak veri modeli tek dosyada.** `ttp_similarity/schema.py`. Modül sınırını geçen her şey oradadır; kendi modülü içinde paralel bir sözlük yapısı uydurmak yasaktır.

**Kabul — dosya formatları.** CSV (tablolar, `utf-8`, indekssiz), JSON (kayıtlar ve raporlar), NPZ (matrisler + etiketleri tek dosyada). Parquet kullanılmadı: ek bağımlılık getirir ve bu boyutta kazancı yok; CSV ise gözle okunabilir ve diff'lenebilir.

**Kabul — eksik girdi hatası komut önerir.** `storage.require`, eksik bir artefaktla karşılaşınca onu üreten komutu söyler. Paralel geliştirmede en sık karşılaşılan sürtünme budur.

**Kabul — ek altyapı yok.** Veritabanı, Docker, servis yok. Tüm ara çıktılar diskte dosyadır.

**Kabul — sahte veri setinde gerçek teknik kimlikleri, uydurma aktör adları.** Sözlük gerçek olmalı ki motorun bugün gördüğü uzay ileride göreceğiyle aynı olsun; aktör adları uydurma olmalı ki sentetik veri hiçbir koşulda istihbarat sanılmasın.

---

## 9. Açık kararlar özeti

| # | Konu | Nerede |
|---|---|---|
| 1 | `ALIAS_STOPLIST` içeriği ve yanlış birleşme koruması | `data/normalize.py` |
| 2 | Dolaylı `aktör → malware → teknik` ilişkileri dahil edilecek mi | `data/stix_parse.py` |
| 3 | `MIN_TECHNIQUES_PER_ACTOR` gerçek dağılıma göre kesinleştirilecek | `config.py` |
| 4 | Kümeleme eşiği ARI ile doğrulanacak; `kmeans` desteklenecek mi | `engine/clustering.py` |
| 5 | Yetersiz teknik sayısında sert `düşük` kuralı | `engine/confidence.py` |
| 6 | Güven eşiklerinin kalibrasyonu | `config.py` + `evaluation/` |
| 7 | Gürültülü örnekleme modu | `evaluation/sampling.py` |
| 8 | Alt teknik korunan varyantın karşılaştırması | `config.py` |
| 9 | Geçişli bağımlılıklar için lock dosyası (3.11 kurulumundan sonra) | `requirements.txt` |

---

## 10. Python sürümü ve bağımlılık sabitleme

### 10.1 Tek sürüme sabitleme: Python 3.11
**Kabul.** `pyproject.toml` → `requires-python = ">=3.11,<3.12"`, `.python-version` → `3.11`.

**Neden `>=3.11` değil de `>=3.11,<3.12`:** Amaç "yeterince yeni bir Python" değil, **üç makinede aynı yorumlayıcı**. Üst sınır olmadan biri 3.11, biri 3.12, biri 3.13 kurar ve fark ancak birinin makinesinde çıkan bir hatayla anlaşılır. `>=3.11,<3.12` ile `==3.11.*` aynı kümeyi ifade eder; okunabilirliği ve pip/PEP 440 araçlarındaki yaygınlığı nedeniyle aralık biçimi seçildi.

**Neden yama sürümü (3.11.9 gibi) sabitlenmedi:** Yama sürümleri yalnızca hata ve güvenlik düzeltmesi içerir; davranış farkı yaratmazlar. Sabitlenseydi, herkesin tam olarak aynı yama sürümünü bulup kurması gerekirdi — kurulum maliyeti gerçek bir faydaya karşılık gelmeden artardı. Sınır minor sürümdedir, çünkü Python'da uyumluluğu bozan değişiklikler minor sürümlerde gelir.

### 10.2 Neden 3.13 değil de 3.11
**Kabul.** Geliştirme makinelerinden birinde 3.13, birinde 3.10 kurulu olduğu için sürüm zaten seçilmek zorundaydı. 3.11 seçildi:

- **Bağımlılık uyumu.** Bilimsel Python yığını en yeni Python sürümünü aylar sonra destekler ve eski sürümleri hızla düşürür. Bu proje sabitlenirken `numpy 2.5.x` ve `scipy 1.18.x` için **Python 3.11 wheel'i bulunmadığı**, buna karşılık 3.11 için `numpy 2.4.6` / `scipy 1.17.1`'in sorunsuz çözüldüğü ölçülerek doğrulandı. Ters yönde bir engel çıkmadı: 3.11'de kurulamayan başka bir bağımlılık yok.
- **Dağıtım yaygınlığı.** 3.11 tüm güncel Linux dağıtımlarının depolarında, Homebrew'da ve python.org installer'larında mevcut. 3.13 bazı LTS dağıtımlarında hâlâ ek depo gerektiriyor.
- **Proje ihtiyacı.** 3.12/3.13'ün getirdiği hiçbir özellik bu projede kullanılmıyor. Kod `from __future__ import annotations` ile yazıldığı için tip sözdizimi açısından da yeni sürüme ihtiyaç yok.
- **Destek süresi.** 3.11 güvenlik desteği projenin ömrünü fazlasıyla kapsıyor.

**Yeniden değerlendirilecek:** Gerçek ATT&CK verisiyle performans sorunu çıkarsa 3.12+ derleyici iyileştirmeleri gündeme alınabilir; ancak bu karar tüm ekipte aynı anda uygulanmalıdır.

### 10.3 Sürüm kontrolü import anında yapılır
**Kabul.** `ttp_similarity/pyversion.py`, `ttp_similarity/__init__.py` içinden import anında çağrılır ve yanlış sürümde `UnsupportedPythonError` fırlatır.

Gerekçe: Tüm giriş noktaları (`python -m ttp_similarity...`, Streamlit uygulaması, `pytest`) paketi import eder; kontrolü buraya koymak, her giriş noktasına ayrı ayrı eklemekten daha güvenilirdir ve unutulamaz. Hata mesajı beklenen sürümü, bulunan sürümü, yorumlayıcı yolunu, sanal ortam durumunu ve platforma göre düzeltme komutlarını birlikte verir — "sessizce yanlış sürümde çalışmama" gereksinimi budur.

`pyversion.py` bilerek eski Python sözdizimiyle yazıldı (eşleştirme ifadesi yok, çalışma zamanı `X | Y` birleşimi yok, yalnızca standart kütüphane). Aksi halde 3.8 gibi bir sürümde "yanlış sürümdesiniz" demek yerine `SyntaxError` verirdi.

**Kaçış kapısı:** `TTP_SIMILARITY_ALLOW_ANY_PYTHON=1` ortam değişkeni hatayı uyarıya indirir. Tek seferlik denemeler ve CI matris koşuları için vardır; **desteklenen bir yapılandırma değildir** ve uyarı bunu açıkça söyler. Kapıyı tamamen kapatmamanın gerekçesi: kontrolün kendisi bir hata yaptığında projenin tamamen kullanılamaz hâle gelmemesi.

### 10.4 Bağımlılıklar `==` ile sabitlenir
**Kabul.** `requirements.txt` içindeki dokuz doğrudan bağımlılığın tamamı tam sürüme sabitlendi.

Gerekçe: Aralık (`>=2.2,<3.0`) kullanıldığında iki kişi iki hafta arayla kurulum yaptığında farklı sürümler alır. Bu projede özellikle `numpy`/`scikit-learn` sürüm farkları benzerlik skorlarında küçük sayısal sapmalar yaratabilir; başarım testi sonuçlarının makineler arası karşılaştırılabilir olması buna bağlıdır.

**Sürümler 3.11'e karşı çözüldü, kurulu ortamdan kopyalanmadı.** Bu ayrım kritiktir: sabitleme sırasında geliştirme sanal ortamı 3.13 üzerindeydi ve orada `numpy 2.5.3` / `scipy 1.18.1` kuruluydu. Bu sürümlerin 3.11 wheel'i olmadığı için, kurulu sürümler doğrudan kopyalansaydı `requirements.txt` **3.11'de kurulamazdı** — yani sürüm sabitlemenin çözmesi gereken sorunun ta kendisi üretilirdi. Doğru sürümler şu komutla belirlendi:

```bash
pip install --dry-run --python-version 3.11 --only-binary=:all:     --target <geçici-dizin> -r requirements.txt --report report.json
```

Sürüm yükseltilirken aynı komut tekrar çalıştırılmalı, ardından `python check_setup.py && pytest` ile doğrulanmalıdır.

**Açık:** Geçişli (transitive) bağımlılıklar sabitlenmedi; yalnızca doğrudan olanlar sabit. Tam yeniden üretilebilirlik isteniyorsa 3.11 kurulumundan sonra `pip freeze > requirements.lock.txt` üretilip versiyonlanabilir. Şu an eklenmedi, çünkü 3.13 ortamından üretilecek bir lock dosyası yanıltıcı olurdu.

### 10.5 Kurulum doğrulaması tek komut
**Kabul.** `python check_setup.py` — sürüm, sanal ortam, sabitlenmiş bağımlılıklar, kritik importlar ve proje paketi kontrol edilir; hata varsa çıkış kodu `1` ve numaralı yapılacaklar listesi.

Yalnızca standart kütüphane kullanır ve paketi import etmeden önce sürümü kontrol eder, böylece **yanlış yorumlayıcıda da çalışır** ve sorunu teşhis edebilir. Depo kökünde durur (paketin içinde değil), çünkü paket import edilemediğinde de çalışabilmesi gerekir.
