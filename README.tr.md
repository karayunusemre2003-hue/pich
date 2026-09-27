<p align="center"><img src="docs/hero.png" alt="Jarvis Video Studio — ham konuşma videosundan bitmiş Reel'e, otomatik kalite kontrolüyle" width="100%" /></p>

# <img src="assets/brand/logo-64.png" alt="" width="40" align="top" /> Jarvis Video Studio

**Ham bir konuşma videosunu, kurguyu yapay zekâ ajanının yaptığı ve otomatik kalite kontrolünün insanın gözden
kaçırdıklarını yakaladığı, bitmiş dikey bir Reel'e dönüştürür.** Bir [Claude Code](https://docs.claude.com/en/docs/claude-code)
skill'i (shell komutu çalıştırabilen her ajanla çalışır) ve sade Python/FFmpeg script'leri.

[English README](README.md)

## Neler yapıyor

Tek bir `plan.json`'dan, tek FFmpeg geçişinde:

- **Konuşmaya güvenli kesim** — duraklamalar çıkar, hece kırpılmaz (her kesim kenarı ölçülür).
- **Doğrulanmış altyazı** — iki Whisper modeli ve öbek bazlı izole geçiş, yanlış duyulan kelimeleri altyazıya girmeden işaretler.
- **Kare 0'da hook kartı**, bilgi kartları, **ikonlar** (Iconify üzerinden 200 bin+ açık kaynak), doğrulanmış **marka logoları**.
- **Canlı PiP'li adım slaytı** ya da konuşan kişi ekranda kalırken **brag tarzı [Hyperframes](https://github.com/heygen-com/hyperframes)
  motion bölümü** (animasyonlu sayaçlar, grafikler).
- Pexels'ten **stok B-roll**: tam ekran ara plan ya da kameranın üstünde video kartı.
- **Sesin altında kısılan müzik**, efektler, yayın seviyesinde ses (-14 LUFS).
- **Hook A/B önizlemesi**: birkaç hook'un ilk 3 saniyesini yan yana gör, birini seç.

Ardından `qa_reel.py` sonucu kontrol eder: gözü veya ağzı kapatan katman (temiz kaynak karede macOS Vision), kişinin
aslında söylemediği altyazı, bir kelimeyi bastıran müzik, segment bazında ses-görüntü kayması, ses seviyesi, siyah
son kare, tahmini Instagram arayüzü çakışması. Bozuk render yüksek sesle hata verir; yanlışlıkla paylaşılmaz.

## Gereksinimler

- macOS veya Linux, Python 3.11+, `ffmpeg`/`ffprobe`, `pip install pillow`
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (`whisper-cli` PATH'te) + modeller: `scripts/setup_models.sh` (~2 GB)
- İsteğe bağlı: Hyperframes motion bölümleri için Node 20+ (`npx hyperframes`), Linux'ta ikon/logo için `librsvg` (`rsvg-convert`)
- İsteğe bağlı ücretsiz key'ler: stok için `PEXELS_API_KEY`, Simple Icons'ta olmayan logolar için `BRANDFETCH_API_KEY`
- Yüz kontrolü macOS Vision kullanır; Linux'ta uyarıyla atlanır

## Claude Code skill'i olarak kurulum

```bash
git clone https://github.com/<sen>/jarvis-video-studio ~/.claude/skills/jarvis-video-studio
~/.claude/skills/jarvis-video-studio/scripts/setup_models.sh
```

Sonra Claude'a bir video ver: *"~/Movies/cekim3.mov'dan bir Reel yap"*. `SKILL.md` ajanı adım adım götürür:
konuşma haritası → transkript kontrolü → kesim → katmanlar → önizleme → final → QA.

## Kendi videon olmadan dene

```bash
python3 examples/demo/make_demo.py                     # sentetik 12 sn kaynak + B-roll + plan.json
python3 scripts/render_reel.py examples/demo/plan.json demo.mp4 --preview
python3 scripts/qa_reel.py demo.mp4 --plan examples/demo/plan.json --no-asr
```

`examples/motion-template/` kendi rakamlarına uyarlayabileceğin hazır bir Hyperframes bölümü ("Ne zaman kâra geçer?":
kurulum saati → günlük kazanılan dakika → amorti günü → kâr).

## Haklar ve gizlilik

- Müzik ve marka logosu gelmez. Müzik için `"rights_checked": true` (ya da üretilen pad) gerekir; logolar kaynak URL
  ve doğrulama tarihi ister. Markalar sahiplerinindir — logo yalnız marka anıldığında gösterilir.
- Stok ve ikonların yazar ve lisans bilgisi render manifest'ine yazılır.
- Key'ler yalnız ortam değişkenlerinden okunur.

## Testler

```bash
python3 -m unittest discover -s tests -v
```

## Lisans

MIT — bkz. [LICENSE](LICENSE). Üçüncü taraf bileşenler: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
