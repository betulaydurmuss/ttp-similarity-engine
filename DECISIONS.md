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

Bu bölümdeki kararların tamamı `data/` modülünde **uygulandı**. Verilen sayılar ATT&CK Enterprise **v19.2** (indirme: 2026-09-07) üzerinde ölçülmüştür.

### 2.1 Kullanılan ATT&CK sürümü ve tekrarlanabilirlik
**Kabul.** Kaynak: `mitre-attack/attack-stix-data` deposundaki `enterprise-attack/enterprise-attack.json`. Sürüm referansı `config.ATTACK_RELEASE` ile seçilir ve şu an `"master"`, yani **hareketli bir referans**.

İndirilen her paketin yanına `data/raw/enterprise-attack.meta.json` yazılır: kaynak URL, indirme zaman damgası (UTC), sunucu ETag'i, dosya boyutu, SHA-256 özeti ve paketin kendi beyan ettiği `x_mitre_version`. Bu sayede bir rapor "ATT&CK v19.2, 2026-09-07 tarihinde indirildi, sha256 …" diyebilir.

İlk ölçüm: **v19.2**, 53.835.637 bayt, 26.086 STIX nesnesi.

**Yeniden değerlendirilecek — yayın öncesi zorunlu:** Sayı yayımlanmadan önce `ATTACK_RELEASE` sabit bir sürüm etiketine (`"v19.2"` gibi) çekilmelidir. `master` üzerinde iki hafta arayla alınan iki build farklı sonuç verir ve karşılaştırılamaz. Meta dosyası bu durumu tespit etmeyi sağlar ama engellemez.

### 2.2 Alt teknikler ana tekniğe indirgenir
`ROLL_UP_SUBTECHNIQUES = True` — **Kabul.**

`T1059.003` → `T1059`.

**Gerekçe.** ATT&CK grup sayfalarında alt teknik detayı son derece dengesizdir. Hakkında çok yazılmış bir aktörün alt teknikleri tek tek listelenirken, az yazılmış bir aktörde yalnızca ana teknik geçer. Alt teknikler korunursa model, davranış farkını değil **raporlama derinliğini** ölçer. Gerçek veri bunu doğruladı: pakette kalan 697 teknik nesnesinin **475'i (%68) alt tekniktir** ve bunların aktörlere dağılımı son derece düzensizdir.

**Ölçülen etki.** İndirgeme, 4.628 ham `uses` ilişkisini 3.726'ya düşürdü; **902 ilişki (%19,5) tekilleşti**. Yani her beş ilişkiden biri, aynı aktörün aynı ana tekniğin birden fazla alt tekniğini kullanmasından ibaretti. İndirgenmeseydi bu aktörler, yalnızca haklarında daha ayrıntılı yazıldığı için birbirine benzer görünecekti.

**Değerlendirilen alternatifler:**

| Alternatif | Neden seçilmedi |
|---|---|
| **Alt teknikleri koru** (indirgeme yok) | Sözlük 697 boyuta çıkar, vektörler aşırı seyrekleşir ve benzerlik, raporlama derinliğinin göstergesi hâline gelir. Ana neden bu. |
| **Hiyerarşik ağırlık** (alt teknik eşleşmesi tam puan, kardeş alt teknik kısmi puan) | Kavramsal olarak en doğrusu; ama kısmi puanın ne olacağı (0,3? 0,5?) veriden türetilemez, elle uydurulur. Ek karmaşıklığın karşılığı ölçülemez. |
| **İki seviyeyi birden vektöre koy** (hem `T1059` hem `T1059.001`) | Aynı bilgi iki kez sayılır, ana teknikler yapay olarak ağırlaşır. |

**Yeniden değerlendirilecek:** `evaluation` modülü çalışır hâle geldiğinde, alt teknik korunan bir varyantla top-1/top-3 farkı ölçülecek. Karar ancak o sayıdan sonra kesinleşir; şu anki gerekçe teoriktir ve %19,5'lik tekilleşme oranına dayanır.

### 2.3 Kimlik: `external_references`, STIX UUID değil
**Kabul.** `actor_id` = ATT&CK grup kimliği (`G0016`), `technique_id` = ATT&CK teknik kimliği (`T1059`). İkisi de `external_references` içinde `source_name == "mitre-attack"` olan girdiden okunur.

**Gerekçe.** STIX UUID'si (`intrusion-set--<uuid>`) MITRE'nin iç tanımlayıcısıdır: sürümler arasında değişebilir, bir analiste hiçbir şey ifade etmez ve ATT&CK web sitesinde görünmez. `G0016` ise kalıcıdır, okunabilirdir ve doğrudan `attack.mitre.org/groups/G0016` adresine karşılık gelir — elle doğrulama ancak böyle mümkün olur.

ATT&CK referansı olmayan nesneler atlanır (pakette birkaç tane içe aktarılmış nesne bulunuyor).

### 2.4 Revoked / deprecated filtreleme politikası
`DROP_REVOKED = True`, `DROP_DEPRECATED = True` — **Kabul.**

**Politika.** Eleme `stix_parse.parse_bundle` içinde, ilişkiler çözülmeden **önce** yapılır. Sıralama önemlidir: eleme sonra yapılsaydı, elenmiş bir tekniğe işaret eden ilişkiler ortada kalırdı. İlişkiler yalnızca **kalan** nesneler arasında çözüldüğü için, revoked bir tekniğe giden kenar o teknikle birlikte kendiliğinden yok olur.

**Ayrım.** MITRE'nin iki farklı işareti aynı anlama gelmez ve ikisi de ayrı sayılır:

- `revoked` — nesne başka bir nesneyle **değiştirildi** (ör. bir grup başka bir grubun aynısı çıktı, bir teknik yeniden numaralandı). Tutulursa aynı gerçeklik iki kez sayılır.
- `x_mitre_deprecated` — nesne **kullanımdan kaldırıldı**, yerine bir şey konmadı. Tutulursa artık ATT&CK'in savunmadığı bir modelleme kararı taşınır.

Her iki durumda da veri, güncel ATT&CK'i temsil etmediği için elenir.

**Ölçülen etki (v19.2):**

| Nesne | Toplam | revoked | deprecated | Elenen | Kalan |
|---|---:|---:|---:|---:|---:|
| `intrusion-set` | 191 | 6 | 9 | 15 | 176 |
| `attack-pattern` | 858 | 149 | 12 | 161 | 697 |

Teknik tarafındaki 149 `revoked` nesnenin çoğu, ATT&CK'in 2020'de yaptığı alt teknik yeniden numaralandırmasının kalıntısıdır.

**İlişki kapsamı.** Yalnızca doğrudan `intrusion-set → attack-pattern` yönündeki `uses` ilişkileri alınır. Dolaylı `aktör → malware → teknik` yolu **izlenmez**: bu, aktörün davranışını değil kullandığı aracın yeteneklerini ölçer; araçlar aktörler arasında paylaşıldığı için yapay benzerlik üretir. `uses` dışındaki ilişki türleri (`attributed-to`, `mitigates` …) de alınmaz.

### 2.5 Takma ad birleştirme yöntemi
**Kabul.** Bir aktör = bir `actor_id`.

**Yöntem.** Takma adlar üzerinde **union-find (birleşim-bulma)**:

1. Her `intrusion-set` için ad ve tüm takma adlar `slugify` edilir (`"APT 29"` ve `"APT-29"` aynı anahtara iner).
2. Elenen anahtarlar: `ALIAS_STOPLIST` içindekiler (`apt`, `ta`, `unc`, `group`, `team`, `crew`, `campaign` …) ve `MIN_ALIAS_LENGTH = 3`'ten kısa olanlar.
3. Aynı anahtarı paylaşan kayıtlar birleştirilir; teknik kümeleri birleşim (union) alınır, tüm adlar takma ad olarak korunur.
4. Kanonik kimlik: gruptaki **en küçük ATT&CK grup kimliği**. Deterministiktir, giriş sırasından ve parse sırasından bağımsızdır.

**Stoplist neden zorunlu.** Onsuz, `"APT"` takma adını taşıyan her kayıt tek bir kimliğe zincirlenir — düzinelerce ilgisiz aktör birleşir. Kısa anahtar eşiği de aynı işi görür: iki harfli bir token'ın kazara çakışma ihtimali, grup kimliği olma ihtimalinden yüksektir. Bu kural birim testiyle korunuyor (`test_alias_merge_joins_shared_tokens_but_not_generic_ones`).

**Ölçülen sonuç (v19.2): 176 → 174, iki birleşme. İkisi de doğru.**

| Kanonik | Birleşen | Ortak takma ad | Doğrulama |
|---|---|---|---|
| `G0030` Lotus Blossom | `G0076` Thrip | `thrip` | G0030'un kendi ATT&CK takma ad listesinde "Thrip" var |
| `G1003` Ember Bear | `G1031` Saint Bear | `uac-0056` | Her iki kayıt da "UAC-0056" takma adını listeliyor |

Yanlış birleşme (false positive) gözlenmedi. Her birleşme `build_stats.json` → `alias_merges` altına, hangi takma adın tetiklediğiyle birlikte yazılır; yeni bir ATT&CK sürümünde bu liste gözden geçirilmelidir.

**Bilinen sınır.** Yöntem yalnızca ATT&CK'in **kendi** takma ad listelerine bakar. İki grup gerçekte aynı olup ATT&CK bunu henüz kaydetmemişse birleşmezler. Bu kabul edilen bir sınırdır: dış kaynaklı takma ad eşlemesi getirmek, projenin "attribution yapmaz" duruşuyla çelişir.

### 2.6 Seyrek aktör eşiği
`MIN_TECHNIQUES_PER_ACTOR = 5` — **Yeniden değerlendirilecek.**

5'ten az tekniği olan aktörün vektörü, hakkında anlamlı bir benzerlik cümlesi kurmak için fazla seyrektir.

**Ölçülen etki (v19.2):** 174 aktörün **25'i** elendi, **149** kaldı. Kalanların dağılımı: min 5, medyan 21, maks 87 teknik.

Eşiğin çalışma anında okunması gerekiyordu; `filter_sparse_actors` ve `normalize_bundle` artık `config` değerini **çağrı anında** okuyor (varsayılan argüman olsaydı import anında donardı ve config değişikliği etkisiz kalırdı). Bu bir birim testiyle korunuyor.

**Açık:** 5 hâlâ bir tahmin. Medyanın 21 olduğu bir dağılımda 5, oldukça düşük bir taban. `evaluation` çalıştığında, eşiği 5/8/10 alan üç varyantın top-1 doğruluğu karşılaştırılıp karara bağlanacak.

---

## 3. Ağırlıklandırma yöntemi

`engine/` modülünde **uygulandı**. Sayılar ATT&CK Enterprise v19.2, 149 aktör, 203 teknik üzerinde ölçülmüştür.

### 3.1 Şema: `smooth_idf`
`WEIGHTING_SCHEME = "smooth_idf"` — **Kabul, ölçümle doğrulandı.**

```
w(t) = ln((N + s) / (df(t) + s)) + 1        s = IDF_SMOOTHING = 1.0
```

`N` = aktör sayısı, `df(t)` = tekniği kullanan aktör sayısı.

**Neden bu varyant.** Üç aday vardı ve seçim, iki uç arasındaki ayrımı bozmadan uç değerlerin ölçeği patlatmamasına dayandı:

| Varyant | En yaygın (T1059, 120/149) | En nadir (1/149) | Sorun |
|---|---:|---:|---|
| `plain_idf` — `ln(N/df)` | 0,217 | 5,004 | Tüm aktörlerde geçen bir teknik **tam 0** alır; yalnızca yaygın tekniklerden oluşan bir sorgu boş sonuç döner. Oran 23× — tek nadir eşleşme her şeyi ezer. |
| **`smooth_idf`** ✔ | **1,215** | **5,317** | Taban 1, tavan `ln(N+1)+1 = 6,011`. Oran **4,38×**: iki uç net ayrışıyor ama tek bir nadir teknik skoru domine edemiyor. |
| `binary` | 1,0 | 1,0 | Ablasyon temeli, ayrım yok. |

**Ölçülen dağılım:** min **1,215** · medyan **3,813** · maks **5,317**.

**Uç değer kontrolü — asıl mesele buydu.** Tekniklerin %15,8'i (32 teknik) tek aktörde geçiyor ve hepsi aynı tavan ağırlığı (5,317) alıyor. `plain_idf` ile bu grup 5,004 alırken en yaygın teknik 0,217'ye düşerdi; 23 katlık bir uçurum, tek bir nadir eşleşmenin geniş bir davranışsal örtüşmeyi ezmesi demekti. `+1` tabanı ve `s=1` yumuşatması bu oranı 4,38×'e indiriyor. Tavan `ln(N+1)+1` ile analitik olarak sınırlı — hiç kullanılmayan bir teknik bile 6,011'i geçemez. Bu, birim testiyle korunuyor (`test_singleton_technique_does_not_blow_up_the_scale`).

### 3.2 Terim frekansı ikilidir
`BINARY_TERM_FREQUENCY = True` — **Kabul.**

ATT&CK bir aktörün bir tekniği kaç kez kullandığını raporlamaz; yalnızca kullandığını söyler. Sayım uydurmak, olmayan bir sinyal üretmek olurdu.

### 3.3 L2 normalizasyonu — kısmi çözüm, sorun tamamen çözülmedi
`NORMALIZE_VECTORS = True` — **Kabul, ama yetersiz. Yeniden değerlendirilecek.**

**Ne yapıyor.** Her aktör satırı birim uzunluğa indiriliyor, böylece nokta çarpımı doğrudan kosinüs benzerliğine eşitleniyor ve **vektör uzunluğu** avantajı ortadan kalkıyor. Normalizasyonsuz hâlde 87 teknikli Kimsuky'nin vektör normu 5 teknikli bir aktörünkinin katları oluyordu; bu birim testiyle gösteriliyor.

**Ne yapmıyor — ölçülen sonuç.** Normalizasyon, iyi belgelenmiş aktörlerin avantajını **kaldırmıyor, yalnızca hafifletiyor.** 200 rastgele 8-teknikli sorgu üzerinde, aktörün teknik sayısı ile aldığı ortalama skor arasındaki Spearman korelasyonu:

| Kurulum | ρ (teknik sayısı ↔ ortalama sorgu skoru) |
|---|---:|
| Normalizasyon **kapalı** | +0,806 |
| Normalizasyon **açık** (mevcut) | **+0,747** |

Aktör-aktör benzerliğinde de aynı tablo: ρ = +0,777. Somut olarak: ≤10 teknikli aktörler ortalama 0,085, ≥40 teknikli aktörler ortalama 0,150 skor alıyor — **yaklaşık 1,8 kat**.

**Neden.** L2 normalizasyonu vektör *uzunluğu* avantajını siliyor ama *kapsam* avantajını silemiyor: 87 tekniği belgelenmiş bir aktörün herhangi bir sorguyla kesişme ihtimali, 5 tekniği belgelenmiş bir aktörünkinden yapısal olarak yüksektir. Bu, modelin değil **verinin** özelliği — ATT&CK'te aktör başına teknik sayısı 5 ile 87 arasında değişiyor (medyan 21) ve bu fark davranış farkından çok raporlama yoğunluğu farkı.

**Ters yöndeki etki de var.** Küçük aktörler sorgu modunda şişebiliyor: örnek sorguda Elderwood (6 teknik) 8 tekniğin yalnızca 2'siyle eşleşmesine rağmen 0,409 skor aldı ve 8/8 eşleşen doğru aktörle (0,412) neredeyse başa baş çıktı. Az sayıda tekniği olan bir aktörün normu küçük olduğu için birkaç ağır eşleşme kosinüsü orantısız yükseltiyor.

**Açık — öncelikli.** Değerlendirilecek seçenekler:
1. **Kapsam (coverage) düzeltmesi:** skoru `|eşleşen| / |sorgu|` ile birleştirmek. Elderwood örneğini doğrudan çözer.
2. **Aktör başına teknik sayısına göre skor kalibrasyonu** (boyut sınıfı içinde z-skoru).
3. **Değişiklik yok**, ama sınırlılık raporda açıkça belirtilir ve arayüzde aktörün teknik sayısı her adayın yanında gösterilir.

Karar `evaluation` modülünün top-1/top-3 sayıları görülmeden verilmemeli: düzeltme doğruluğu artırıyor mu, yoksa yalnızca skorları mı yeniden dağıtıyor, ölçülmeli. Şu anki durum **3. seçenek** ile aynı: sınır biliniyor ve burada kayıtlı.

### 3.4 Ağırlıklandırma gerçekten fark yaratıyor mu
**Evet, ama sanıldığı kadar değil.** Ağırlıklı kosinüs ile ağırlıksız Jaccard'ın en benzer 15 çifti karşılaştırıldığında:

- Kesişim: **8/15 çift** — yani listenin yarısından biraz fazlası ortak.
- Tüm çiftlerde Spearman sıra korelasyonu: **ρ = 0,901**.

Ayrım en çok, **ortak teknikleri nadir olan** çiftlerde ortaya çıkıyor. En uç örnek: `IndigoZebra ↔ TA577` ağırlıklı kosinüste **1. sırada** (0,713) ama Jaccard'da **200. sırada** (0,375) — ikisi de az sayıda ama nadir teknik paylaşıyor. Ters yönde `Gallmaker ↔ TA577` Jaccard'da 2. sırada ama kosinüste 423. sırada: paylaştıkları teknikler emtia.

ρ = 0,901 yüksek bir korelasyon; ağırlıklandırma sıralamayı baştan aşağı değiştirmiyor, **uçları** düzeltiyor. `binary` şemasıyla `evaluation` çalıştırılıp top-1 farkının kaç puan olduğu ölçülmeden, ağırlıklandırmanın maliyetini hak edip etmediği kesinleşmiş sayılmaz. Bu ölçüm hâlâ projenin en önemli tek testidir.

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

`evaluation/` modülünde **uygulandı**. Sayılar ATT&CK v19.2, 149 aktör üzerinde.

### 7.1 Ölçüm tasarımı (sabit)
**Kabul.** Her aktörün tekniklerinin **%50'si** rastgele sorgu olarak seçilir, kalanı gizlenir. Aktör başına **20 tekrar**, tek tohumdan (`EVAL_RANDOM_SEED = 1337`) — bir koşu birebir tekrarlanabilir. Hedef, sorgunun çekildiği aktördür (kendini bulma testi).

Sorgusu **3 tekniğin altına** düşen tekrar **atlanır ve sayılır**, tamamlanmaz: tamamlama gizlenen teknikleri sorguya geri koyar ve cevabı sızdırır. Gerçek veride 7 aktör (≤5 teknikli) tamamen elendi → 140 atlanan tekrar, 2.840 geçerli deneme.

Metrikler: top-1 / top-3 / top-5, MRR, doğru cevabın ortalama sırası (ıskalar ortalamaya katılmaz, ayrı sayılır — sentinel ortalaması `top_k`'ya bağlı anlamsız bir sayı üretirdi).

### 7.2 Ölçüm tavana vurdu — sonuçların okunma biçimi
**Bu bölümdeki tüm karşılaştırmalar için geçerli uyarı.** Tasarım, sekiz konfigürasyonun tamamında top-1'i **0,97–0,997** aralığına oturttu. Bir aktörün tekniklerinin yarısı verildiğinde onu bulmak neredeyse hiç zorlanmıyor; konfigürasyonlar arası farklar bu tavan yüzünden 1–2 puanla sınırlı kalıyor ve ayırt edici değil.

Bu, kararların bu sayılara dayandırılamayacağı anlamına gelir. Ayrıştırıcı bir ölçüm için tasarımın zorlaştırılması gerekir (daha küçük sorgu oranı, gürültü enjeksiyonu, veya aktöre ait olmayan teknik ekleme). Tasarım şu an bilinçli olarak sabit tutulduğu için bu bir **açık madde**.

### 7.3 Ağırlıklandırma ablasyonu
**Sonuç: ayrım yok.** `smooth_idf` 0,9754 · `binary` 0,9778 · `jaccard` 0,9715 (top-1). Aradaki fark 0,6 puan ve ağırlıksız `binary` marjinal olarak **önde**.

Bu, "ağırlıklandırma işe yaramıyor" demek **değildir** — 7.2'deki tavan etkisi nedeniyle bu ölçüm soruyu cevaplayamıyor. §3.4'te ölçülen sıra korelasyonu (ρ=0,901) ve uç örnekler (IndigoZebra↔TA577: kosinüste 1., Jaccard'da 200.) ağırlıklandırmanın sıralamayı gerçekten değiştirdiğini gösteriyor; değiştirdiği yerlerin bu görevde **önemli olmadığı** anlaşılıyor. Karar, daha zor bir ölçüm tasarımı olmadan verilemez.

### 7.4 Seyrek aktör eşiği
**Ölçülen:** eşik 5 → 149 aktör, top-1 0,9754 · eşik 8 → 128 aktör, 0,9926 · eşik 10 → 117 aktör, 0,9970.

Metrikler monoton olarak iyileşiyor, ama bu bir kazanç değil **tanım gereği**: eşik yükseldikçe zor vakalar (az teknikli aktörler) popülasyondan çıkarılıyor. 5→10 arasında 32 aktör (%21) kaybediliyor. Eşik seçimi bir başarım kararı değil, **kapsam kararı**dır: kaç aktör hakkında konuşmak istediğinizle ilgilidir.

### 7.5 Kapsam (coverage) düzeltmesi
`COVERAGE_CORRECTION = False` — **varsayılan kapalı, açık madde.**

`score * (eşleşen / |sorgu|) ** COVERAGE_CORRECTION_EXPONENT`.

**Ölçülen:** top-1 0,9754 → **0,9873**, MRR 0,9856 → 0,9924, ortalama sıra 1,041 → 1,020.

Asıl etki, §3.3'te tarif edilen az teknikli aktör şişmesinde: hedef olmadığı hâlde 1. sırada tahmin edilen **5–10 teknikli** aktör sayısı **64 → 30** düştü. Toplam yanlış top-1: 70 → 36. Boyut yanlılığı korelasyonu ρ=+0,523'ten +0,462'ye indi — azaldı ama kalkmadı.

Yani düzeltme, tasarlandığı sorunu (Elderwood etkisi) fiilen çözüyor. Varsayılan kapalı bırakıldı çünkü karar kullanıcıya ait ve tavana vurmuş bir ölçümde 1,2 puanlık kazanç tek başına yeterli gerekçe değil.

### 7.6 Teknik sayısı ile başarı ilişkisi
**Ölçülen (kapsam düzeltmesi kapalı):**

| Teknik sayısı | Aktör | top-1 |
|---|---:|---:|
| 5–10 | 30 | 0,933 |
| 11–20 | 37 | 0,965 |
| 21–35 | 39 | 0,995 |
| 36–50 | 23 | 1,000 |
| 51+ | 13 | 1,000 |

Aktör başına top-1 ile teknik sayısı arasında Spearman **ρ = +0,523**. §3.3'teki skor düzeyindeki yanlılığın (ρ=+0,747) başarım tarafındaki karşılığı: iyi belgelenmiş aktörler hem daha yüksek skor alıyor hem de daha kolay bulunuyor. Sistemin başarısı kısmen raporlama derinliğini ölçüyor.

### 7.7 Güven kalibrasyonu
**Sonuç: kalibrasyon çalışıyor.** `smooth_idf` koşusunda HIGH etiketli 1.586 sorguda top-1 **1,000**, MEDIUM'da 0,979, LOW'da **0,603**. Yani güven skoru düşük dediğinde gerçekten daha sık yanılıyor — DECISIONS §5.4'teki hedefler (HIGH ≥0,80, LOW ≤0,40) HIGH tarafında fazlasıyla, LOW tarafında **tutmuyor** (0,603 > 0,40).

**Açık:** LOW etiketi fazla iyimser. Ayrıca `binary` ve `jaccard` koşularında sorguların %96'sı HIGH etiketleniyor — ağırlıksız skorlarda `margin` bileşeni büyüdüğü için güven şişiyor. Eşiklerin şema başına ayarlanması mı gerekiyor, yoksa `margin` doygunluğu mu yeniden ayarlanmalı, ölçülmeli.

### 7.8 Sınırlılık
**Kabul (raporda açıkça yazılacak).** Alt küme, motorun indekslediği aynı kayıtlardan çekiliyor; ölçülen şey **erişim tutarlılığıdır**, gerçek dünya doğruluğu değil. Gerçek olay verisi gürültülüdür, eksiktir ve aktöre atfedilmemiş teknikler içerir. Gürültülü örnekleme modu hâlâ açık (§9, madde 7) ve 7.2'deki tavan sorunu göz önüne alındığında artık yalnızca "iyi olur" değil, **gerekli**.

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
| 1 | ~~`ALIAS_STOPLIST` ve yanlış birleşme koruması~~ — **kapandı** (§2.5) | `data/normalize.py` |
| 2 | ~~Dolaylı `aktör → malware → teknik` ilişkileri~~ — **kapandı: hayır** (§2.4) | `data/stix_parse.py` |
| 3 | `MIN_TECHNIQUES_PER_ACTOR`: dağılım ölçüldü (medyan 21), eşik hâlâ açık (§2.6) | `config.py` |
| 4 | Kümeleme eşiği ARI ile doğrulanacak; `kmeans` desteklenecek mi | `engine/clustering.py` |
| 5 | Yetersiz teknik sayısında sert `düşük` kuralı | `engine/confidence.py` |
| 6 | Güven eşiklerinin kalibrasyonu | `config.py` + `evaluation/` |
| 7 | Gürültülü örnekleme modu | `evaluation/sampling.py` |
| 8 | Alt teknik korunan varyantın karşılaştırması (§2.2) | `config.py` |
| 10 | `ATTACK_RELEASE` yayın öncesi sabit sürüme çekilmeli (§2.1) | `config.py` |
| 11 | ~~Kapsam düzeltmesi açılsın mı~~ — **kapandı: AÇIK** (§11.1) | `config.py` |
| 12 | ~~Ölçüm tavana vurdu~~ — **kapandı: rejim B/C eklendi** (§11.2) | `evaluation/` |
| 13 | Güven eşikleri hangi rejime göre kalibre edilecek? (§11.7) | `config.py` |
| 14 | **Ağırlıklı Jaccard denenmedi — C'de düz Jaccard ikisini de geçiyor (§11.5)** | `engine/query.py` |
| 15 | Boyut yanlılığı zorlukla büyüyor (ρ: 0,46→0,77); raporda zaaf olarak yazılmalı (§11.6) | — |
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

---

## 11. Zorlaştırılmış ölçüm ve verilen kararlar

### 11.1 Uygulanan üç karar
**Karar 1 — `COVERAGE_CORRECTION = True` (varsayılan AÇIK).** Gerekçe: yanlış top-1 tahminleri 70 → 36 düştü, düşüşün tamamı 5–10 teknikli gruptan geldi ve 11+ gruplarında hiçbir bozulma olmadı (§7.5). Kapalı seçeneği config'de duruyor, karşılaştırma `outputs/reports/attck/comparison_summary.csv` içinde saklı.

**Karar 2 — `MIN_TECHNIQUES_PER_ACTOR = 5` sabit kalıyor.** Eşiği yükseltmek her manşet metriği iyileştiriyor ama bunu yalnızca **zor vakaları popülasyondan silerek** yapıyor: 8 → 128 aktör, 10 → 117 aktör, 149'un 32'si (%21) kayboluyor. Bu, kapsam kararının başarım kazancı gibi sunulmasıdır. Az teknikli aktör sorunu bunun yerine **skorlama tarafında** çözüldü (Karar 1). Gerekçe `config.py` içindeki sabitin yanına da yazıldı.

**Karar 3 — güven eşikleri (0,70 / 0,45) değiştirilmedi.** Kalibrasyon, aşağıdaki zor rejim sonuçlarına göre yapılacak.

### 11.2 Neden yeni rejimler gerekti
Önceki ölçüm (§7.2) tavana vurmuştu: sekiz konfigürasyonun tamamı top-1'de 0,97–0,997 aralığındaydı ve şemalar arası fark ayırt edilemiyordu. Ölçüm tasarımının geri kalanı (aktör başına 20 tekrar, sabit seed, 3 tekniğin altındaki tekrarların atlanıp sayılması, hedefin aktörün kendisi olması) aynı tutularak **zorluk ekseni** eklendi:

| Rejim | Sorgu oranı | Gürültü | Deneme | Atlanan |
|---|---:|---:|---:|---:|
| A (referans) | %50 | — | 2.840 | 140 (7 aktör) |
| B (seyrek) | %25 | — | 2.100 | 880 (44 aktör) |
| C (gürültülü) | %25 | %30 | 2.100 | 880 (44 aktör) |

**Gürültü seçimi yaygınlığa orantılı, rastgele değil.** Gerçek bir analistin elindeki listede emtia teknikler baskındır; düzgün (uniform) gürültü çoğunlukla nadir teknik enjekte ederdi, ağırlıklandırma bunları kolayca eleyeceği için görev yapay olarak kolaylaşırdı. Enjeksiyon oranı `config.EVAL_NOISE_RATIO` ile ayarlanır ve **opt-in**'dir: sıradan bir koşu gürültü enjekte etmez, aksi hâlde `--dataset attck` sessizce zorlaştırılmış olurdu.

Atlanan tekrar sayısındaki sıçrama (140 → 880) tasarımın doğal sonucu: %25 oranında 3 tekniğe ulaşmak için aktörün ≥12 tekniği olması gerekiyor, 44 aktör bu eşiğin altında. B ve C rejimleri dolayısıyla **105 aktör** üzerinde ölçülüyor, A ise 142.

### 11.3 Rejim tavanı kırdı
top-1: A 0,987 → B 0,939 → C 0,684. Rejim C ayrıştırıcı: şemalar arası fark 10 puana kadar açılıyor ve ıskalar (top-10 dışı) 29'a çıkıyor.

### 11.4 Ağırlıklandırma sorusunun cevabı
**Kolay rejimlerde fark yok, zor rejimde ağırlıklandırma kazanıyor.** Aktör bazında eşleştirilmiş Wilcoxon işaretli sıra testi (her iki şema birebir aynı seed'li sorgu planını gördüğü için eşleştirme tam):

| Rejim | Δ top-1 (smooth_idf − binary) | smooth iyi | binary iyi | berabere | p |
|---|---:|---:|---:|---:|---:|
| A | −0,0028 | 1 | 4 | 137 | 0,225 |
| B | −0,0057 | 10 | 20 | 75 | 0,095 |
| **C** | **+0,0510** | **63** | **20** | 22 | **1,7×10⁻⁵** |

A ve B'de binary marjinal olarak önde ama fark anlamlı değil. C'de smooth_idf **+5,1 puan** önde ve fark güçlü biçimde anlamlı.

**Yorum:** ağırlıklandırmanın değeri, sorgu temiz olduğunda görünmüyor; devreye girdiği yer, sorguda **aktöre ait olmayan emtia teknikler** bulunduğunda. IDF bu emtia gürültüyü hafif ağırlıkla bastırıyor, `binary` ise onları gerçek eşleşmelerle aynı ağırlıkta sayıyor. Bu, §3.1'de teorik olarak savunulan davranışın ilk ampirik doğrulaması.

### 11.5 Beklenmeyen sonuç: Jaccard, gürültüde her ikisini de geçiyor
Rejim C'de düz Jaccard top-1 **0,739** — smooth_idf (0,684) ve binary'nin (0,633) ikisinden de yüksek, ıska sayısı 7 (smooth_idf'te 29).

Nedeni yapısal: Jaccard'ın paydası birleşim kümesi, enjekte edilen her gürültü tekniği paydayı **tüm adaylar için** büyütüyor, dolayısıyla gürültü sıralamayı bozmuyor. Kosinüs tarafında ise gürültü, kapsam düzeltmesiyle birlikte skorları asimetrik biçimde eziyor.

Bu sonuç ağırlıklandırma kararını karmaşıklaştırıyor: ağırlıklandırma `binary` kosinüsü geçiyor (§11.4), ama **hiçbir ağırlık kullanmayan** Jaccard ikisini birden geçiyor. **Açık madde:** ağırlıklı Jaccard (kesişim ve birleşimi IDF ile ağırlıklandırmak) denenmedi; iki etkinin birleşimi olabilir.

### 11.6 Boyut yanlılığı zorlukla birlikte büyüyor
Aktör başına top-1 ile teknik sayısı arasındaki Spearman ρ (smooth_idf):

| Rejim | ρ |
|---|---:|
| A | +0,462 |
| B | +0,660 |
| C | **+0,770** |

Görev zorlaştıkça iyi belgelenmiş aktörleri bulmak göreli olarak daha da kolaylaşıyor. Rejim C'de 11–20 teknikli aktörlerde top-1 0,452 iken 51+ teknikte 0,935. Kapsam düzeltmesi A rejiminde yanlılığı 0,523 → 0,462'ye indirmişti; zor rejimlerde bu kazanç erimiş durumda.

**Açık:** Bu, sistemin gerçek olay verisindeki en büyük zaafı olarak raporda yer almalı. Az belgelenmiş bir aktör, gürültülü bir sorguda bulunamıyor.

### 11.7 Güven kalibrasyonu zor rejimde anlam kazanıyor
Rejim C, smooth_idf:

| Seviye | n | pay | top-1 |
|---|---:|---:|---:|
| HIGH | 782 | %37 | 0,950 |
| MEDIUM | 956 | %46 | 0,611 |
| LOW | 362 | %17 | 0,304 |

A rejiminde HIGH %56 pay ve 1,000 top-1 ile neredeyse anlamsızdı (her şey HIGH'dı). C'de dağılım gerçek bir bilgi taşıyor ve §5.4'teki hedefler (HIGH ≥0,80, LOW ≤0,40) **ilk kez ikisi birden tutuyor**.

Buna karşılık `binary` ve `jaccard` şemalarında sorguların %72–84'ü hâlâ HIGH etiketleniyor ve HIGH'ın top-1'i 0,74–0,80'e düşüyor — yani ağırlıksız skorlarda güven şişiyor. Güven eşikleri **şemadan bağımsız değil**.

**Açık (Karar 3'ün devamı):** Eşikler mevcut hâlleriyle smooth_idf + rejim C kombinasyonunda doğru çalışıyor. Kalibrasyonun hangi rejime göre yapılacağı — kolay (A) mı, gerçekçi (C) mi — bir ürün kararıdır ve verilmedi.

---

