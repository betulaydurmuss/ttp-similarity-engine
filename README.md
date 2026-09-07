# ttp-similarity-engine

MITRE ATT&CK Enterprise verisini kullanarak tehdit aktörlerinin davranışsal parmak izini çıkaran, aktörler arası benzerliği ölçen ve verilen bir TTP setinin hangi aktörlere benzediğini güven seviyesiyle birlikte raporlayan bir CTI analiz aracı.

> **Bu araç attribution (faillik atfı) yapmaz.** Yalnızca davranışsal benzerlik ölçer. Bir sorgunun bir aktöre benzemesi, o aktörün sorumlu olduğu anlamına gelmez; yalnızca raporlanmış ATT&CK tekniklerinin örtüştüğünü gösterir. Sonuçlar, açık kaynak raporlamanın kapsam ve yanlılığından doğrudan etkilenir.

---

## Durum

Modüller arası arayüzler, veri formatları ve dosya sözleşmesi tamamlanmıştır. **Analiz motoru (`engine/`) tamamen implement edilmiştir** — IDF ağırlıklandırma, vektörize etme, cosine similarity, kümeleme, güven skoru ve sorgu modu çalışır durumdadır.

| Bileşen | Dosya | Durum |
|---|---|---|
| Ortak veri modeli | `ttp_similarity/schema.py` | ✅ Tamam |
| Dosya yolları / workspace | `ttp_similarity/paths.py` | ✅ Tamam |
| Ayarlar ve eşikler | `ttp_similarity/config.py` | ✅ Tamam |
| Disk okuma/yazma katmanı | `ttp_similarity/storage.py` | ✅ Tamam |
| 15 aktörlük sahte veri seti | `ttp_similarity/data/mock_dataset.py` | ✅ Tamam |
| Frekans tablosu üretimi | `ttp_similarity/data/frequency.py` | ✅ Tamam |
| Motor artefakt yükleyici | `ttp_similarity/engine/loading.py` | ✅ Tamam |
| IDF ağırlıklandırma | `ttp_similarity/engine/weighting.py` | ✅ Tamam |
| Vektör uzayı oluşturma | `ttp_similarity/engine/vectorize.py` | ✅ Tamam |
| Aktörler arası benzerlik matrisi | `ttp_similarity/engine/similarity.py` | ✅ Tamam |
| Davranışsal kümeleme | `ttp_similarity/engine/clustering.py` | ✅ Tamam |
| Güven skoru (rarity / margin / sufficiency) | `ttp_similarity/engine/confidence.py` | ✅ Tamam |
| TTP sorgu modu ve `rank_actors()` | `ttp_similarity/engine/query.py` | ✅ Tamam |
| Motor build pipeline | `ttp_similarity/engine/build.py` | ✅ Tamam |
| Örnekleme ve metrikler | `ttp_similarity/evaluation/{sampling,metrics}.py` | ✅ Tamam |
| Streamlit kabuğu | `ttp_similarity/app/streamlit_app.py` | Çalışır (ekranlar TODO) |
| STIX indirme / ayrıştırma / normalizasyon | `ttp_similarity/data/*` | **TODO** |
| Başarım testi döngüsü | `ttp_similarity/evaluation/benchmark.py` | **TODO** |
| Görselleştirme ve ekranlar | `ttp_similarity/app/{plots,views}.py` | **TODO** |

---

## Veri kaynağı

**MITRE ATT&CK Enterprise, STIX 2.1 paketi.**

- Kaynak: `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/<sürüm>/enterprise-attack/enterprise-attack.json`
- URL ve sürüm `ttp_similarity/config.py` içindeki `ATTACK_RELEASE` / `ATTACK_STIX_URL` ile yönetilir.
- Kullanılan nesneler:
  - `intrusion-set` → tehdit aktörü (ATT&CK grup kimliği, ör. `G0016`)
  - `attack-pattern` → teknik / alt teknik (ör. `T1059`, `T1059.003`)
  - `relationship` (`relationship_type == "uses"`) → aktör → teknik ilişkisi
- Alt teknikler ana tekniğe indirgenir (`T1059.003` → `T1059`). Gerekçesi `DECISIONS.md` içinde.
- İndirilen paket `data/raw/` altında önbelleğe alınır; sonraki tüm aşamalar diskten okur, yani boru hattı çevrimdışı tekrarlanabilir.

MITRE ATT&CK içeriği MITRE tarafından [ATT&CK Terms of Use](https://attack.mitre.org/resources/legal-and-branding/terms-of-use/) kapsamında sağlanır.

---

## Kurulum

> **Python 3.11 zorunludur.** "3.11 ve üstü" değil, tam olarak **3.11.x**. 

Aşağıdaki komutlar **depo kökünde** çalıştırılır. Herkes birebir aynı komutları çalıştırmalıdır.

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python check_setup.py
```

> PowerShell "execution policy" hatası verirse, aynı oturum için:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
> Alternatif olarak `cmd.exe` kullanılıyorsa aktivasyon komutu: `.venv\Scripts\activate.bat`

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python check_setup.py
```

### Kurulumu doğrulama

Her iki platformda da tek komut:

```bash
python check_setup.py
```

Bu betik sırasıyla şunları kontrol eder ve özet basar:

1. **Python sürümü** — `.python-version` içindeki sabitle karşılaştırır, sanal ortamın aktif olup olmadığını söyler.
2. **Bağımlılıklar** — `requirements.txt` içindeki her paketi kurulu sürümüyle karşılaştırır (beklenen / bulunan / durum tablosu).
3. **Kritik importlar** — paket kurulu görünse bile gerçekten import edilebiliyor mu (bozuk wheel, yanlış mimari).
4. **Proje paketi** — `ttp_similarity` import ediliyor mu, mock veri seti ve motor artefaktları üretilmiş mi.

Her şey yolundaysa çıkış kodu `0`, bir sorun varsa `1` döner ve **ne yapılması gerektiğini** numaralı liste hâlinde yazar. Betik yalnızca standart kütüphaneyi kullanır ve **yanlış Python sürümünde de çalışır** — zaten ilk bulgusu bu olur.

### Python 3.11 kurulu değilse

**Windows**
[python.org/downloads/windows](https://www.python.org/downloads/windows/) adresinden **Python 3.11** serisinin son sürümünü indirin (64-bit installer). Kurulumda **"Add python.exe to PATH"** ve **"py launcher"** seçeneklerini işaretleyin. Kurulum sonrası doğrulama:

```powershell
py -0p          # kurulu tüm sürümleri listeler, 3.11 görünmeli
py -3.11 -V
```

**Ubuntu / Debian**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
python3.11 -V
```
Depoda 3.11 yoksa: `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update` ardından yukarıdaki kurulum.

**Fedora / RHEL**
```bash
sudo dnf install python3.11
```

**macOS (Homebrew)**
```bash
brew install python@3.11
python3.11 -V
```

**pyenv (her platform)** — depoda `.python-version` dosyası bulunduğu için dizine girildiğinde sürüm otomatik seçilir:
```bash
pyenv install 3.11
pyenv local 3.11     # .python-version zaten mevcut, doğrulamak için
python -V
```

### Notlar

- Ek altyapı yoktur: veritabanı, Docker veya servis gerekmez. Tüm ara çıktılar diske dosya olarak yazılır.
- `requirements.txt` içindeki sürümler `==` ile sabitlenmiştir ve **Python 3.11'e karşı çözülmüştür**. Daha yeni bir Python'da kurulu olan sürümleri buraya kopyalamayın: örneğin `numpy 2.5.x` ve `scipy 1.18.x` için Python 3.11 wheel'i yoktur.
- Sanal ortam klasörü (`.venv/`) ve üretilen tüm veri dosyaları `.gitignore` içindedir; `.python-version` ise **bilerek versiyonlanır**.

---

## Çalıştırma

Komutlar depo kökünden, **sanal ortam aktifken** çalıştırılır.

```bash
# 0) Kurulum doğru mu? (her zaman önce bunu çalıştırın)
python check_setup.py

# 1) Sahte veri seti (gerçek ATT&CK verisi olmadan denemek için)
python -m ttp_similarity.data.mock_dataset

# 1b) Gerçek veri seti (data modülü tamamlandığında)
python -m ttp_similarity.data.build --dataset mitre

# 2) Motor artefaktları: ağırlıklar, vektörler, benzerlik matrisi, kümeler ✅
python -m ttp_similarity.engine.build --dataset mock

# 3) Komut satırından sorgu ✅
python -m ttp_similarity.engine.query T1566 T1078 T1047 T1003 --dataset mock

# 3b) JSON çıktı ✅
python -m ttp_similarity.engine.query T1566 T1078 T1047 T1003 --dataset mock --json

# 4) Başarım testi (evaluation modülü tamamlandığında)
python -m ttp_similarity.evaluation.benchmark --dataset mock

# 5) Arayüz
streamlit run ttp_similarity/app/streamlit_app.py

# Testler ✅
pytest
```

### Python API ile kullanım

```python
from ttp_similarity.engine import rank_actors

# Gözlemlenen teknikleri sorgula
results = rank_actors(["T1566", "T1059", "T1078", "T1003"], top_k=5)

for r in results:
    print(f"{r['actor_name']:<24} "
          f"score={r['similarity_score']:.3f}  "
          f"confidence={r['confidence_level']}  "
          f"matched={r['match_count']}")
    for ev in r["evidence"][:3]:
        print(f"  ↳ {ev['technique_id']} ({ev['technique_name']}): {ev['contribution']:.1%}")
```

`--dataset` her komutta aynı anlama gelir: `mock` (sahte veri) veya `mitre` (gerçek ATT&CK). İki veri seti aynı dosya sözleşmesini ürettiği için tüm alt modüller ikisiyle de ayrım gözetmeden çalışır.

---

## Dizin yapısı

```
ttp-similarity-engine/
├── ttp_similarity/              # kod
│   ├── schema.py                # ORTAK VERİ MODELİ - önce burayı okuyun
│   ├── pyversion.py             # Python sürüm koruması (import anında çalışır)
│   ├── paths.py                 # tüm dosya yolları (Workspace)
│   ├── config.py                # eşikler, ağırlıklar, ayarlar
│   ├── storage.py               # diske okuma/yazma
│   ├── data/                    # aşama 1: ATT&CK -> temiz tablo
│   ├── engine/                  # aşama 2: ağırlık, vektör, benzerlik, sorgu
│   ├── evaluation/              # aşama 3: başarım testi
│   └── app/                     # aşama 4: Streamlit arayüzü
├── data/                        # üretilen veri dosyaları (git'e girmez)
│   ├── raw/                     # indirilen STIX paketi
│   ├── interim/                 # ara çıktılar
│   ├── processed/<veri-seti>/   # MODÜL SÖZLEŞMESİ burada
│   └── mock/                    # sahte veri setinin ground-truth dosyaları
├── outputs/
│   ├── figures/<veri-seti>/     # üretilen grafikler
│   └── reports/<veri-seti>/     # başarım raporları
├── tests/
│   ├── test_contract.py         # modüller arası sözleşme testleri
│   ├── test_engine.py           # motor modülü birim testleri
│   ├── test_mock_dataset.py     # sahte veri seti testleri
│   └── test_python_pin.py       # Python sürüm sabiti testleri
├── check_setup.py               # tek komutla kurulum doğrulama
├── .python-version              # 3.11 (pyenv sürüm sabiti, versiyonlanır)
├── pyproject.toml               # requires-python = ">=3.11,<3.12"
├── requirements.txt             # sürümleri sabitlenmiş bağımlılıklar
├── README.md
└── DECISIONS.md                 # yöntem, eşik ve terim kararları
```

---

## Modüller

Dört modül **paralel geliştirilebilecek** şekilde tasarlandı. Her modülün girdisi ve çıktısı diskteki dosyalardır; hiçbir modül diğerinin bellekteki nesnesine dokunmaz. Bir modül, girdi dosyası henüz üretilmemişse hangi komutun çalıştırılması gerektiğini söyleyen bir hata verir (`storage.require`).

### `data/` — ATT&CK'ten temiz aktör-teknik tablosuna

Yaptığı iş:
1. ATT&CK Enterprise STIX paketini indirir ve `data/raw/` altında önbelleğe alır.
2. `intrusion-set`, `attack-pattern` nesnelerini ve aralarındaki `uses` ilişkilerini ayrıştırır.
3. Alt teknikleri ana tekniklere indirger (`T1059.003` → `T1059`).
4. Aktör takma adlarını tek kimlik altında birleştirir (bir aktör = bir `actor_id`).
5. Revoked/deprecated nesneleri ve çok seyrek aktörleri eler.
6. Temiz aktör-teknik tablosunu ve **her tekniğin kaç aktörde geçtiğini gösteren frekans tablosunu** diske yazar.

Çıktıları (`data/processed/<veri-seti>/`):

| Dosya | İçerik |
|---|---|
| `actors.json` | `actor_id`, `name`, `aliases[]`, `technique_ids[]`, `source`, `metadata` |
| `actor_technique.csv` | `actor_id, actor_name, technique_id, technique_name` (uzun format) |
| `techniques.csv` | `technique_id, technique_name, tactics` |
| `technique_frequency.csv` | `technique_id, technique_name, actor_count, actor_ratio` |
| `manifest.json` | Kaynak, ATT&CK sürümü, üretim zamanı, sayımlar |

### `engine/` — ağırlıklandırma, benzerlik, kümeleme, sorgu

> **Bu modül tamamen implement edilmiştir.**

Temel fikir: **nadir teknikler ayırt edicidir, yaygın teknikler değildir.** Aktör = doküman, teknik = terim kabul edilir; ATT&CK sayım değil varlık bilgisi verdiği için terim frekansı ikilidir ve tüm sinyal IDF tarafındadır.

#### Pipeline

| Adım | Dosya | Çıktı | Açıklama |
|---|---|---|---|
| 1 | `weighting.py` | `weights.csv` | Her tekniğin kaç aktörde geçtiğinden IDF ağırlığı hesaplanır |
| 2 | `vectorize.py` | `vector_space.npz` | Her aktör, kullandığı tekniklerin IDF ağırlıklarıyla bir vektör olarak temsil edilir |
| 3 | `similarity.py` | `similarity.npz` | Aktörler arası cosine similarity matrisi üretilir |
| 4 | `clustering.py` | `clusters.csv` | Agglomerative clustering ile davranışsal kümeler oluşturulur |
| 5 | `query.py` | — | Kullanıcının verdiği teknik listesi aynı vektör uzayına yansıtılıp aktörlerle karşılaştırılır |
| 6 | `confidence.py` | — | Sorgu sonucunun güvenilirliği üç bileşenden hesaplanır |

#### IDF formülü

Yaygın tekniklerin etkisini azaltmak, nadir olanların etkisini artırmak için smoothed IDF kullanılır:

```
idf(t) = ln((N + 1) / (df(t) + 1)) + 1
```

- `N` = toplam aktör sayısı
- `df(t)` = tekniği kullanan aktör sayısı
- `+1` zemin, evrensel bir tekniğin ağırlığını sıfır yerine 1'de tutar

Alternatif şemalar (`plain_idf`, `binary`) `config.WEIGHTING_SCHEME` ile seçilebilir.

#### `rank_actors()` — yüksek seviyeli sorgu API'si

Motor modülü, kullanıcının doğrudan çağırabileceği bir convenience fonksiyonu sunar:

```python
from ttp_similarity.engine import rank_actors

results = rank_actors(["T1566", "T1059", "T1078", "T1003"], top_k=5)

for r in results:
    print(f"{r['actor_name']:<24} score={r['similarity_score']:.3f}  "
          f"confidence={r['confidence_level']}  "
          f"matched={r['match_count']}/{len(r['matched_techniques'])}")
```

Her aday için dönen alanlar:

| Alan | Açıklama |
|---|---|
| `actor_id` / `actor_name` | Aktör kimliği ve adı |
| `similarity_score` | Cosine similarity (0–1) |
| `confidence_score` / `confidence_level` | Güven skoru (0–1) ve etiketi (`high` / `medium` / `low`) |
| `matched_techniques` | Aktörle eşleşen teknik ID'leri |
| `match_count` | Eşleşen teknik sayısı |
| `technique_coverage` | Eşleşen / sorgulanan teknik oranı |
| `evidence` | Sonucu en fazla etkileyen yüksek-IDF teknikler (contribution payıyla) |

#### Edge case'ler

| Durum | Davranış |
|---|---|
| Boş teknik listesi | Boş sonuç, `LOW` confidence |
| Duplicate teknik ID'leri | Otomatik de-duplicate edilir |
| Bilinmeyen teknik ID'leri | `unknown_technique_ids` olarak raporlanır, sessizce atılmaz |
| Tek teknikle sorgu | Çalışır, `sufficiency` düşük olacağından confidence düşer |
| Hiçbir aktörle eşleşmeyen sorgu | Boş aday listesi, `LOW` confidence |
| Top-1 ve top-2 çok yakın | `margin` bileşeni düşer → confidence düşer |

#### Güven skoru (confidence)

**Güven skoru üç bileşenden oluşur** (ayrıntı ve eşikler `DECISIONS.md`):

| Bileşen | Sorduğu soru | Ağırlık |
|---|---|---|
| **Nadirlik (rarity)** | Eşleşen teknikler ayırt edici mi, yoksa herkeste var mı? | 0.40 |
| **Fark (margin)** | 1. aday 2. adaydan gerçekten ayrışıyor mu? | 0.35 |
| **Yeterlilik (sufficiency)** | Karar vermeye yetecek kadar teknik girildi mi? | 0.25 |

Sonuç **yüksek / orta / düşük** olarak etiketlenir. Sorgu çıktısı ayrıca **hangi tekniklerin sonucu belirlediğini** (`evidence`) ve **aday aktörde görülmeyen sorgu tekniklerini** (`missing_technique_ids`) döndürür — açıklanamayan bir sıralama kullanılabilir istihbarat değildir.

> **Güven skoru bir olasılık değildir** ve kesin attribution (faillik atfı) izlenimi vermez. Sistem `"Bu APT29'dur"` değil, `"Gözlemlenen davranış en çok APT29 ile benzerlik gösteriyor"` mantığında çalışır.

### `evaluation/` — başarım testi

Bilinen bir aktörün tekniklerinden rastgele `k` tanesi seçilir, sanki yeni bir olaydan gelmiş gibi sorgu moduna verilir ve doğru aktörün sıralamada nerede çıktığına bakılır. Ölçülenler:

- **top-1 doğruluk** — doğru aktörün ilk sırada çıkma oranı
- **top-3 doğruluk** — ilk üçte çıkma oranı
- **MRR** (ortalama karşılıklı sıra)
- Sorgu boyutuna göre kırılım — "kaç teknik gerekiyor?" sorusunun cevabı
- **Güven seviyesine göre kırılım** — kalibrasyon kontrolü: `yüksek` etiketli sonuçlar `düşük` etiketlilerden belirgin biçimde daha doğru olmalıdır, aksi halde güven skoru süstür.

Çıktı: `outputs/reports/<veri-seti>/evaluation.json` ve `evaluation_trials.csv`.

> Not: Alt küme, motorun indekslediği aynı ATT&CK kayıtlarından çekilir. Bu nedenle ölçülen şey **erişim tutarlılığıdır**, gerçek dünya attribution doğruluğu değildir.

### `app/` — Streamlit arayüzü

- **Benzerlik ısı haritası** — kümeleme sırasına göre dizilmiş aktör-aktör benzerlik matrisi, seçilen aktörün en yakın komşuları, küme profilleri.
- **TTP sorgu ekranı** — teknik listesi girilir; aday aktörler, güven seviyesi ve üç bileşeni, eşleşen teknikler ve katkı payları görüntülenir.
- **Veri seti ekranı** — aktör listesi, teknik frekans dağılımı, ağırlık dağılımı.

Arayüzde puanlama mantığı yoktur; her hesap motorda yapılır, böylece CLI ile arayüz aynı sonucu verir.

---

## Sahte veri seti

`python -m ttp_similarity.data.mock_dataset` komutu, gerçek veri hazır olmadan engine ve app modüllerinin geliştirilebilmesi için **15 aktörlük sentetik bir veri seti** üretir.

- Teknik kimlikleri ve adları **gerçek** ATT&CK teknikleridir, böylece motorun bugün gördüğü sözlük ile ileride göreceği sözlük aynıdır.
- Aktör adları **uydurmadır** (`SILENT HERON`, `IRON TIDE`, ...). Hiçbir gerçek tehdit grubuna karşılık gelmez ve istihbarat olarak kullanılamaz.
- 15 aktör, 3'erli 5 davranışsal aileye yerleştirilmiştir; her aktör ailesinin çekirdek tekniklerinin çoğunu, neredeyse herkeste bulunan yaygın teknikleri ve birkaç rastgele tekniği alır. Bu, gerçekçi bir frekans eğrisi, kümelemenin bulması gereken bir yapı ve güven skorunun `margin` bileşenini zorlayan yakın çiftler üretir.
- Üretim tohumlanmıştır (`seed`), yani her makinede aynı sonucu verir.
- Ailelerin ground-truth eşlemesi `data/mock/mock_ground_truth.csv` dosyasına yazılır.

---

## Ekip için: modüller arası sözleşme

1. **Önce `ttp_similarity/schema.py` okunur.** Modül sınırını geçen her şey orada tanımlıdır. Yeni bir alan gerekiyorsa önce orası değiştirilir ve diğer iki sahibe haber verilir.
2. **Dosya yolları elle yazılmaz.** `paths.Workspace.get("mock").weights` kullanılır.
3. **Dosyalar elle açılmaz.** `storage.*` kullanılır; eksik girdi durumunda kullanıcıya doğru komutu söyleyen hata otomatik gelir.
4. **Eşik ve sabitler kod içine gömülmez.** Hepsi `config.py` içindedir; değiştirildiğinde `DECISIONS.md` de güncellenir.
5. `TODO` yorumları sahibiyle etiketlenmiştir: `TODO(data)`, `TODO(engine)`, `TODO(eval)`, `TODO(app)`.

---

## Sınırlılıklar

- ATT&CK grup kayıtları **açık kaynak raporlamaya** dayanır. Çok yazılmış bir aktörün teknik listesi uzundur; az yazılmış bir aktörünki kısadır. Benzerlik bir ölçüde raporlama yoğunluğunu ölçer.
- Aktörler zaman içinde davranış değiştirir; ATT&CK kayıtları bu değişimi tarihlendirmez. Model zamansızdır.
- Farklı aktörlerin aynı sızma araçlarını ve tekniklerini kullanması yaygındır; yüksek benzerlik ortak araç setinden de kaynaklanabilir.
- Bu araç bir tespit sistemi değildir ve olay müdahale kararlarının tek dayanağı olarak kullanılmamalıdır.
