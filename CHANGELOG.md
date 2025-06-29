# Değişiklik Günlüğü (Changelog)
Bu projede yapılan tüm önemli değişiklikler bu dosyada belgelenmektedir.
Format, [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardına dayanmaktadır.

## [2.2.0] - 2025-06-18
### Eklendi (Added)
- **Gelişmiş Pozisyon Yönetimi:** Arka planda çalışan `check_and_manage_positions` fonksiyonuna, `config.py`'da etkinleştirilebilen **İz Süren Zarar Durdurma (Trailing Stop-Loss)** ve **Kısmi Kâr Alma (Partial Take-Profit)** stratejileri eklendi.
- **İnteraktif Web Analizi:** Web arayüzündeki "Açık Pozisyonlar" tablosuna, her pozisyon için anlık yeniden analiz yapmayı sağlayan bir "Analiz" butonu ve sonuçları gösteren bir modal pencere eklendi.
- **Tam Entegre Telegram Botu:** `telegram_bot.py` modülü, projenin `core` ve `database` modülleriyle doğrudan iletişim kuracak, `asyncio` uyumluluk sorunları giderilmiş, modern ve stabil bir yapıya kavuşturuldu.

### Değiştirildi (Changed)
- **Daha Esnek Analiz:** `get_technical_indicators` aracı, hesaplama sırasında `NaN` değeriyle karşılaştığında hata vermek yerine bu değeri `None` olarak kabul edip analizin devam etmesini sağlayacak şekilde güncellendi. `create_mta_analysis_prompt` fonksiyonu da bu `None` değerlerini işleyebilecek şekilde iyileştirildi.
- **Modernleştirilmiş Araç Çağrıları:** `LangChain`'in yeni versiyonlarıyla uyumluluk ve `Pydantic` doğrulama hatalarını gidermek için, `@tool` ile işaretlenmiş tüm fonksiyonların (`get_technical_indicators`, `execute_trade_order` vb.) `.invoke()` metoduyla çağrılması sağlandı.

### Düzeltildi (Fixed)
- **Telegram `RuntimeError` Hatası:** `telegram_bot.py`'ın ayrı bir `thread` içinde çalışırken `RuntimeError: There is no current event loop` ve `Cannot close a running event loop` hataları vermesine neden olan `asyncio` olay döngüsü çakışması, kütüphanenin temel asenkron fonksiyonları kullanılarak tamamen giderildi.
- **LangChain `ValidationError` Hatası:** Ajanın veya programın, girdi olarak sözlük bekleyen araçlara metin (`string`) veya yanlış formatta sözlük göndermesinden kaynaklanan tüm `pydantic.ValidationError` hataları, araçların girdi işleme mantığı ve çağırma yöntemleri iyileştirilerek düzeltildi.
- **Telegram Bildirim Formatı:** Düşük değerli coin'lerde (`1000WHY/USDT` gibi) fiyatların bildirimde `0.0000` olarak görünmesine neden olan ondalık basamak yuvarlama sorunu, `notifications.py` dosyasında formatlayıcı hassasiyeti artırılarak (`.8f`) çözüldü.
- **`get_top_gainers_losers` Hatası:** Bu aracın doğrudan çağrılmasının neden olduğu `'int' object has no attribute 'parent_run_id'` hatası, aracın `.invoke()` metoduyla çağrılması sağlanarak giderildi.
- **`NameError` Hatası:** `dashboard/app.py` dosyasında `database` modülünün import edilmemesinden kaynaklanan `NameError` hatası, eksik olan `import database` satırı eklenerek düzeltildi.

[1.9.1] - 2025-06-17
Bu, botun stabilitesini ve verimliliğini artıran bir bakım sürümüdür. Özellikle proaktif tarama modülündeki tekrarlayan hatalar hedeflenmiştir.

Eklendi (Added)
Dinamik Kara Liste: Proaktif tarama sırasında, teknik analiz verisi alınamayan veya sürekli NaN hatası veren coin'ler artık dinamik olarak 1 saatliğine bir kara listeye alınmaktadır. Bu, botun aynı hatalı coin'leri tekrar tekrar analiz ederek zaman ve kaynak israf etmesini önler.

Değiştirildi (Changed)
get_technical_indicators Sağlamlığı: tools.py içerisindeki bu fonksiyon, borsadan gelen bozuk veya eksik verileri (NaN değerleri) hesaplama yapmadan önce otomatik olarak temizleyecek şekilde iyileştirildi. Bu, NaN hatalarının büyük bir kısmını kaynağında çözer.

Haber API'si Hata Mesajları: get_latest_news aracı, 403 Forbidden gibi API anahtarı veya izinleriyle ilgili hatalarda artık daha açıklayıcı bir mesaj döndürerek sorunun teşhisini kolaylaştırır.

[1.9.0] - 2025-06-17
Bu sürüm, bota yapay zeka kararları üzerinde manuel kontrol yeteneği kazandırarak, kullanıcı etkileşimini ve güvenliği önemli ölçüde artırmaktadır.

Eklendi (Added)
Ajan Kararları için Onay Mekanizması: config.py dosyasına AGENT_CLOSE_AUTO_CONFIRM ayarı eklendi. Bu ayar varsayılan olarak False'tur.

Eğer bu ayar False ise, yapay zeka bir pozisyonu kapatmayı tavsiye ettiğinde (Yeniden Analiz Et menüsünde), bot terminalde kullanıcıdan "evet/hayır" şeklinde onay ister.

Bu özellik, kullanıcılara ajanın kararlarını geçersiz kılma ve son sözü söyleme imkanı tanır.

Değiştirildi (Changed)
handle_reanalyze_position Mantığı: Bu fonksiyon, yeni AGENT_CLOSE_AUTO_CONFIRM ayarını kontrol edecek ve buna göre ya otomatik olarak pozisyonu kapatacak ya da kullanıcıdan onay isteyecek şekilde yeniden yapılandırıldı.

[1.8.0] - 2025-06-17
Bu sürüm, projenin temel mimarisinde önemli bir iyileştirme yaparak modüller arası döngüsel bağımlılık (circular dependency) sorununu ortadan kaldırmıştır. Ayrıca, botun Telegram üzerinden daha interaktif yönetilmesini sağlayan yeni özellikler eklenmiştir.

Değiştirildi (Changed)
MİMARİ DEĞİŞİKLİK (Circular Import Refactoring): main.py ve telegram_bot.py arasındaki döngüsel içe aktarma hatası, ana uygulama fonksiyonlarının (analiz, tara, pozisyon kapatma vb.) Telegram botuna argüman olarak geçirilmesiyle tamamen giderildi.

handle_manual_close Fonksiyonu: Bu fonksiyon, işlemin sonucunu belirten bir metin (string) döndürecek şekilde yeniden düzenlendi.

Eklendi (Added)
Telegram Üzerinden Pozisyon Kapatma: Kullanıcılar artık /pozisyonlar komutuyla listeledikleri aktif pozisyonları, "❌ Kapat" butonuna basarak doğrudan Telegram arayüzünden kapatabilirler.

Düzeltildi (Fixed)
Asenkron Bloklama Sorunları: Telegram botundaki tüm senkron (bloklayıcı) fonksiyon çağrıları asyncio.to_thread kullanılarak ayrı bir iş parçacığında çalıştırılmaktadır.
[1.8.0] - 2025-06-17
Bu sürüm, projenin temel mimarisinde önemli bir iyileştirme yaparak modüller arası döngüsel bağımlılık (circular dependency) sorununu ortadan kaldırmıştır. Ayrıca, botun Telegram üzerinden daha interaktif yönetilmesini sağlayan yeni özellikler eklenmiştir.

Değiştirildi (Changed)
MİMARİ DEĞİŞİKLİK (Circular Import Refactoring): main.py ve telegram_bot.py arasındaki döngüsel içe aktarma hatası, ana uygulama fonksiyonlarının (analiz, tara, pozisyon kapatma vb.) Telegram botuna argüman olarak geçirilmesiyle tamamen giderildi. Bu, daha modüler ve bakımı kolay bir kod yapısı sağlar.

handle_manual_close Fonksiyonu: Bu fonksiyon artık sadece konsola çıktı basmak yerine, işlemin sonucunu belirten bir metin (string) döndürecek şekilde yeniden düzenlendi. Bu, Telegram gibi arayüzlerin işlem sonucunu kullanıcıya doğru bir şekilde bildirmesini sağlar.

Eklendi (Added)
Telegram Üzerinden Pozisyon Kapatma: Kullanıcılar artık /pozisyonlar komutuyla listeledikleri aktif pozisyonları, "❌ Kapat" butonuna basarak doğrudan Telegram arayüzünden kapatabilirler. Bu işlem için ek bir onay adımı da bulunmaktadır.

Düzeltildi (Fixed)
Asenkron Bloklama Sorunları: Telegram botundaki tüm senkron (bloklayıcı) fonksiyon çağrıları (analiz, tarama, pozisyon durumu sorgulama vb.) artık asyncio.to_thread kullanılarak ayrı bir iş parçacığında çalıştırılmaktadır. Bu, botun kullanıcı komutlarına her zaman anında yanıt vermesini sağlar.

[1.7.0] - 2025-06-16
Bu sürüm, bota temel analiz yeteneği kazandırarak karar mekanizmasını çok daha sofistike hale getirmeye odaklanmıştır. Artık bot, sadece teknik göstergelere değil, piyasayı etkileyebilecek en güncel haberlere de bakarak işlem yapmaktadır. Ayrıca, önceki sürümlerde tespit edilen kritik hatalar giderilmiştir.

Eklendi (Added)
Haber Analizi (Temel Analiz) Entegrasyonu: Bot artık bir işlem kararı vermeden önce, ilgili kripto para hakkındaki en son haberleri analiz etme yeteneğine sahiptir.

CryptoPanic API Entegrasyonu: tools.py içine, CryptoPanic API'sini kullanarak haber başlıklarını ve duyarlılık oylarını çeken yeni bir get_latest_news aracı eklendi.

Güvenlik Odaklı Karar Verme: Yapay zeka prompt'ları, analize başlamadan önce haberleri kontrol edecek şekilde güncellendi. Eğer piyasayı olumsuz etkileyebilecek (FUD, hack, regülasyon vb.) bir haber varsa, bot diğer tüm sinyaller olumlu olsa bile işlemi açmayarak "BEKLE" kararı verir.

Değiştirildi (Changed)
Yapay Zeka Prompt'ları: main.py içerisindeki create_mta_analysis_prompt, create_final_analysis_prompt ve create_reanalysis_prompt fonksiyonları, yeni haber verilerini işleyecek ve analiz sürecine dahil edecek şekilde tamamen yeniden yapılandırıldı.

Ajan Yetenekleri: LangChain ajanının araç seti (agent_tools), yeni get_latest_news aracını içerecek şekilde genişletildi. Ajanın maksimum iterasyon sayısı, daha karmaşık analizler için artırıldı.

Düzeltildi (Fixed)
Veritabanı Kayıt Hatası (TypeError): Pozisyon kapatıldıktan sonra işlem geçmişine kayıt yapılırken, calculate_pnl yardımcı fonksiyonunun yanlışlıkla @tool olarak etiketlenmesinden kaynaklanan TypeError hatası, ilgili dekoratör kaldırılarak giderildi.

Ajan Girdi Ayrıştırma Hatası: Ajanın get_technical_indicators aracına SEMBOL@ZAMAN_DİLİMİ formatında girdi göndermesi durumunda oluşan sembol ayrıştırma hatası düzeltildi. _parse_symbol_timeframe_input fonksiyonu artık @ karakterini de geçerli bir ayırıcı olarak tanımaktadır.

[1.6.1] - 2025-06-13
Düzeltildi (Fixed)
KRİTİK HATA (AttributeError): config.py dosyasından yanlışlıkla silinen ATR_MULTIPLIER_SL parametresi geri eklendi. Bu hata, botun yeni bir pozisyon açmaya çalışırken Stop-Loss mesafesini hesaplayamamasına ve programın çökmesine neden oluyordu.


## [1.6.0] - 2025-06-13
Bu sürüm, botun kâr alma stratejilerine profesyonel bir yaklaşım getirerek, "Kısmi Kâr Alma" (Partial Take-Profit) özelliğini eklemiştir. Ayrıca, web arayüzündeki ve senkronizasyon mantığındaki önemli hatalar giderilmiştir.

### Eklendi (Added)
- **Kısmi Kâr Alma Stratejisi:** Bot artık `config.py` üzerinden etkinleştirilebilen yeni bir kâr alma mekanizmasına sahip.
  - **İlk Kâr Hedefi (1R):** Fiyat, ilk risk mesafesi (1R) kadar kâr ettiğinde, bot pozisyonun belirlenen bir yüzdesini (`PARTIAL_TP_CLOSE_PERCENT`) otomatik olarak kapatır.
  - **Riski Sıfırlama (Breakeven):** İlk kâr alındıktan sonra, kalan pozisyonun Stop-Loss seviyesi otomatik olarak giriş fiyatına çekilir.
  - **Özel Telegram Bildirimi:** Kısmi kâr alma işlemi başarıyla tamamlandığında yeni bir Telegram bildirimi gönderilir.
- **Web Arayüzü (Dashboard):** Botun performansını, aktif pozisyonlarını ve işlem geçmişini canlı olarak görselleştiren bir web panosu eklendi. Flask ile oluşturulmuştur ve `D` menü seçeneği ile başlatılabilir.

### Değiştirildi (Changed)
- **Senkronizasyon Mantığı:** `sync_and_display_positions` fonksiyonu, bot tarafından yönetilmeyen ve manuel olarak kapatılan pozisyonları artık işlem geçmişine kaydetmeyecek şekilde güncellendi. Bu, web arayüzündeki PNL istatistiklerinin doğruluğunu artırır.
- **Sembol Standardizasyonu:** `_get_unified_symbol` fonksiyonu, `HMSTRUSDT/USDT` gibi hatalı formatları önlemek için daha sağlam bir mantıkla tamamen yeniden yazıldı.

### Düzeltildi (Fixed)
- **Web Arayüzü Grafik Hatası:** `index.html` dosyasındaki P&L zaman çizelgesinin sürekli aşağı kaymasına neden olan boyutlandırma hatası, grafiğin sabit yükseklikte bir konteynere alınması ve chart.js ayarlarının iyileştirilmesiyle giderildi.


## [1.5.0] - 2025-06-12
Bu sürüm, proaktif tarama (Fırsat Avcısı) modülünü temelden yenileyerek çok daha stabil, akıllı ve yapılandırılabilir hale getirmeye odaklanmıştır.

Eklendi (Added)
API Hatalarına Karşı Direnç: tenacity kütüphanesi entegre edildi.

Hacim ve Likidite Filtresi: Proaktif tarayıcıya PROACTIVE_SCAN_MIN_VOLUME_USDT ayarı eklendi.

Gelişmiş Sembol Liste Yönetimi: PROACTIVE_SCAN_WHITELIST ve PROACTIVE_SCAN_BLACKLIST seçenekleri eklendi.

Dinamik Kara Liste Mekanizması: Sürekli hata veren semboller geçici olarak kara listeye alınır.

Değiştirildi (Changed)
MİMARİ DEĞİŞİKLİK (Proaktif Tarama Mantığı): _execute_single_scan_cycle fonksiyonu tamamen yeniden yazıldı. Toplu analizden bireysel ve MTA tabanlı analize geçildi.

## [1.4.0] - 2025-06-12

(Bu versiyon bir önceki geliştirme döngüsünde ara versiyon olarak kullanılmıştır)

## [1.3.1] - 2025-06-12

- **(Kritik hata düzeltmeleri)**

Bu sürüm, önceki sürümde tespit edilen ve botun temel işlevselliğini (analiz, senkronizasyon) etkileyen kritik hataları gidermeye odaklanan bir bakım sürümüdür. Ajan-araç etkileşimi daha sağlam hale getirilmiştir.

### Düzeltildi (Fixed)
- **KRİTİK ÇEKİRDEK HATA (Sembol Ayrıştırma):** Projenin farklı modüllerinde (`Yeni Analiz`, `Proaktif Tarama`, `Senkronizasyon`) `binance does not have market symbol ...USDT,/USDT` gibi hatalara yol açan temel sembol ayrıştırma (`parsing`) mantığı tamamen yeniden yazılarak düzeltildi. Artık bot, `BTC/USDT,15m` veya `BTC/USDT_15m` gibi farklı formatları doğru bir şekilde işleyebilmektedir.
- **KRİTİK SENKRONİZASYON HATASI (Ekle/Sil Döngüsü):** Manuel olarak yönetime eklenen bir pozisyonun (`HMSTRUSDT/USDT`), hatalı sembol standardizasyonu nedeniyle anında "borsada bulunamadı" olarak algılanıp veritabanından silinmesi sorunu giderildi.
- **Proaktif Tarama `NaN` Hatası:** Proaktif tarama modunda, bazı coinler için teknik göstergelerin sürekli `NaN` (geçersiz sayı) dönmesine neden olan ve gereksiz olan `volume` (hacim) verisini işleme mantığı kaldırıldı. Bu düzeltme ile tarama özelliği tekrar işlevsel hale getirildi.
- **API Bağlantı Hatası Loglaması:** `get_top_gainers_losers` fonksiyonunda olası ağ veya borsa hatalarının daha açıklayıcı bir şekilde loglanması için `try-except` blokları iyileştirildi.

### Değiştirildi (Changed)
- **Ajan Mantığı (Yeniden Analiz):** "Pozisyonu Yeniden Analiz Et" özelliğinde, ajanın doğrudan pozisyon kapatma emri vermesi yerine, sadece "TUT" veya "KAPAT" tavsiyesi vermesi sağlandı. Pozisyonu kapatma eylemi, ajanın tavsiyesine göre doğrudan Python kodu tarafından daha güvenilir bir şekilde gerçekleştirilmektedir. Bu değişiklik, ajanın görev aşımını ve karmaşık emirlerde hata yapmasını önler.

## [1.3.0] - 2025-06-11

Bu sürüm, projenin temel mimarisini `JSON` tabanlı durum yönetiminden, kalıcı ve sağlam bir `SQLite` veritabanına taşıyarak büyük bir adım atmaktadır. Ayrıca gelişmiş risk yönetimi özellikleri eklenmiş ve önceki sürümlerdeki kritik hatalar giderilmiştir.

### Eklendi (Added)
- **Dinamik Pozisyon Büyüklüğü:** Bot artık sabit bir marjin kullanmak yerine, toplam portföy bakiyesinin belirli bir yüzdesini (`RISK_PER_TRADE_PERCENT`) riske atarak pozisyon büyüklüğünü dinamik olarak hesaplamaktadır.
- **İz Süren Zarar Durdur (Trailing Stop-Loss):** Kâra geçen pozisyonlarda, kârı kilitlemek amacıyla stop-loss seviyesini otomatik olarak yukarı taşıyan `USE_TRAILING_STOP_LOSS` özelliği eklendi.
- **İşlem Geçmişi (Trade History):** Kapanan tüm işlemler (TP, SL veya manuel), PNL bilgisiyle birlikte analiz ve takip için veritabanındaki `trade_history` tablosuna kaydedilmektedir.
- **Yeni Araçlar:** Dinamik pozisyon büyüklüğü için `get_wallet_balance` ve Trailing SL için `update_stop_loss_order` araçları `tools.py` dosyasına eklendi.

### Değiştirildi (Changed)
- **MİMARİ DEĞİŞİKLİK (JSON -> SQLite):** Projenin en temel değişikliği olarak, tüm pozisyon yönetimi `managed_positions.json` dosyasından `trades.db` adlı bir SQLite veritabanına taşındı. Bu değişiklik için yeni bir `database.py` modülü oluşturuldu.
- **Kod Yeniden Yapılandırması (Refactoring):** `main.py` içerisindeki tüm pozisyon okuma, yazma, güncelleme ve silme işlemleri, yeni `database.py` modülündeki fonksiyonları kullanacak şekilde tamamen yeniden yazıldı.

### Düzeltildi (Fixed)
- **Kritik Senkronizasyon Hatası:** Botun kendi açtığı pozisyonları (`BTC/USDT`) borsadan gelen formatla (`BTC/USDT:USDT`) eşleştirememesi sorunu, sembol isimleri standartlaştırılarak kalıcı olarak çözüldü.
- **Veri Kaybı Hatası:** Senkronizasyon hatası sonrası manuel olarak yönetime eklenen pozisyonların SL/TP bilgilerinin kaydedilmemesi ve bu nedenle pozisyonun anında kapanmasına neden olan kritik hata, senkronizasyon mantığının düzeltilmesiyle giderildi.
- **Python 3.12+ Uyumluluğu:** `distutils` kütüphanesinin kaldırılmasıyla oluşan program çökmesi, özel bir `str_to_bool` fonksiyonu yazılarak düzeltildi.
- **Loglama Hatası:** Pozisyon kapatma emirleri için yanıltıcı olan "Giriş Emri" log mesajı, daha genel bir ifade olan "İşlem Emri" olarak güncellendi.
- **NameError Hataları:** Önceki sürümlerde, kodun eksik sunulmasından kaynaklanan `handle_new_analysis` ve diğer fonksiyonların tanımlanmamış olması hataları giderildi.

Bu sürüm, projenin temel mimarisini `JSON` tabanlı durum yönetiminden, kalıcı ve sağlam bir `SQLite` veritabanına taşıyarak büyük bir adım atmaktadır. Ayrıca gelişmiş risk yönetimi özellikleri eklenmiş ve önceki sürümlerdeki kritik hatalar giderilmiştir.

### Eklendi (Added)
- **Dinamik Pozisyon Büyüklüğü:** Bot artık sabit bir marjin kullanmak yerine, toplam portföy bakiyesinin belirli bir yüzdesini (`RISK_PER_TRADE_PERCENT`) riske atarak pozisyon büyüklüğünü dinamik olarak hesaplamaktadır.
- **İz Süren Zarar Durdur (Trailing Stop-Loss):** Kâra geçen pozisyonlarda, kârı kilitlemek amacıyla stop-loss seviyesini otomatik olarak yukarı taşıyan `USE_TRAILING_STOP_LOSS` özelliği eklendi.
- **İşlem Geçmişi (Trade History):** Kapanan tüm işlemler (TP, SL veya manuel), PNL bilgisiyle birlikte analiz ve takip için veritabanındaki `trade_history` tablosuna kaydedilmektedir.
- **Yeni Araçlar:** Dinamik pozisyon büyüklüğü için `get_wallet_balance` ve Trailing SL için `update_stop_loss_order` araçları `tools.py` dosyasına eklendi.

### Değiştirildi (Changed)
- **MİMARİ DEĞİŞİKLİK (JSON -> SQLite):** Projenin en temel değişikliği olarak, tüm pozisyon yönetimi `managed_positions.json` dosyasından `trades.db` adlı bir SQLite veritabanına taşındı. Bu değişiklik için yeni bir `database.py` modülü oluşturuldu.
- **Kod Yeniden Yapılandırması (Refactoring):** `main.py` içerisindeki tüm pozisyon okuma, yazma, güncelleme ve silme işlemleri, yeni `database.py` modülündeki fonksiyonları kullanacak şekilde tamamen yeniden yazıldı.

### Düzeltildi (Fixed)
- **Kritik Senkronizasyon Hatası:** Botun kendi açtığı pozisyonları (`BTC/USDT`) borsadan gelen formatla (`BTC/USDT:USDT`) eşleştirememesi sorunu, sembol isimleri standartlaştırılarak kalıcı olarak çözüldü.
- **Veri Kaybı Hatası:** Senkronizasyon hatası sonrası manuel olarak yönetime eklenen pozisyonların SL/TP bilgilerinin kaydedilmemesi ve bu nedenle pozisyonun anında kapanmasına neden olan kritik hata, senkronizasyon mantığının düzeltilmesiyle giderildi.
- **Python 3.12+ Uyumluluğu:** `distutils` kütüphanesinin kaldırılmasıyla oluşan program çökmesi, özel bir `str_to_bool` fonksiyonu yazılarak düzeltildi.
- **Loglama Hatası:** Pozisyon kapatma emirleri için yanıltıcı olan "Giriş Emri" log mesajı, daha genel bir ifade olan "İşlem Emri" olarak güncellendi.
- **NameError Hataları:** Önceki sürümlerde, kodun eksik sunulmasından kaynaklanan `handle_new_analysis` ve diğer fonksiyonların tanımlanmamış olması hataları giderildi.

## [1.2.0] - 2025-06-11
(Bu versiyon bir önceki geliştirme döngüsünde ara versiyon olarak kullanılmış ve 1.3.0 ile birleştirilmiştir)

## [1.1.0] - 2025-06-11

Bu sürüm, botun analiz yeteneklerini önemli ölçüde artıran Çoklu Zaman Aralığı (MTA) özelliğini ve kritik bir performans iyileştirmesini içermektedir.

### Eklendi (Added)
- **Çoklu Zaman Aralığı Analizi (MTA):** Botun analiz yeteneği, kısa vadeli giriş sinyallerini daha yüksek bir zaman dilimindeki ana trend ile teyit ederek daha isabetli kararlar almasını sağlayan MTA özelliği ile geliştirildi.
- **MTA Konfigürasyonu:** `config.py` dosyasına `USE_MTA_ANALYSIS` ve `MTA_TREND_TIMEFRAME` seçenekleri eklenerek yeni MTA özelliğinin kontrolü sağlandı.

### Değiştirildi (Changed)
- **Kritik Performans İyileştirmesi:** Proaktif tarama modunda kullanılan `get_top_gainers_losers` fonksiyonu, tüm piyasayı taramak yerine tek bir verimli API çağrısı kullanacak şekilde tamamen yeniden yazıldı.

## [1.0.0] - 2025-06-11
(İlk sürümün değişiklikleri)s