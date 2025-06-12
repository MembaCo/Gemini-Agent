# Değişiklik Günlüğü (Changelog)

Bu projede yapılan tüm önemli değişiklikler bu dosyada belgelenmektedir.
Format, [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardına dayanmaktadır.

# Değişiklik Günlüğü (Changelog)

Bu projede yapılan tüm önemli değişiklikler bu dosyada belgelenmektedir.
Format, [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardına dayanmaktadır.

Değişiklik Günlüğü (Changelog)

Bu projede yapılan tüm önemli değişiklikler bu dosyada belgelenmektedir. Format, Keep a Changelog standardına dayanmaktadır.

[1.5.0] - 2025-06-12

Bu sürüm, proaktif tarama (Fırsat Avcısı) modülünü temelden yenileyerek çok daha stabil, akıllı ve yapılandırılabilir hale getirmeye odaklanmıştır. Artık tarayıcı, hatalara karşı daha dirençli, piyasa gürültüsünü daha iyi filtreliyor ve Çoklu Zaman Aralığı (MTA) analizi ile daha kaliteli sinyaller üretiyor.

Eklendi (Added)

API Hatalarına Karşı Direnç: tenacity kütüphanesi entegre edildi. tools.py içindeki tüm borsa API çağrıları (teknik gösterge, fiyat, bakiye alma vb.), geçici ağ veya API limit hatalarında programın çökmesini önlemek için artık otomatik olarak birkaç kez yeniden deneme yapmaktadır.

Hacim ve Likidite Filtresi: Proaktif tarayıcıya, düşük hacimli ve riskli koinleri elemek için PROACTIVE_SCAN_MIN_VOLUME_USDT ayarı eklendi. Tarayıcı artık sadece belirlenen 24 saatlik işlem hacminin üzerindeki koinleri dikkate alır.

Gelişmiş Sembol Liste Yönetimi: config.py dosyasına PROACTIVE_SCAN_WHITELIST (her zaman tara) ve PROACTIVE_SCAN_BLACKLIST (asla tarama) seçenekleri eklendi. Bu, taranacak koinler üzerinde tam kontrol sağlar.

Dinamik Kara Liste Mekanizması: Analiz sırasında sürekli NaN gibi hatalar veren veya kritik bir hataya neden olan semboller, bot tarafından otomatik olarak geçici bir süre (30-60 dk) kara listeye alınır. Bu, gereksiz kaynak tüketimini ve tekrarlayan hataları önler.

Değiştirildi (Changed)

MİMARİ DEĞİŞİKLİK (Proaktif Tarama Mantığı): _execute_single_scan_cycle fonksiyonu tamamen yeniden yazıldı.

Toplu Analizden Bireysel Analize Geçiş: Tarayıcı artık tüm sembolleri tek bir prompt ile toplu olarak analiz etmek yerine, filtrelenmiş listedeki her bir sembolü tek tek ve sırayla analiz eder.

MTA Entegrasyonu: Tarayıcı, PROACTIVE_SCAN_MTA_ENABLED ayarı True ise, her bir potansiyel fırsatı manuel analizde olduğu gibi Çoklu Zaman Aralığı (giriş + trend) mantığıyla değerlendirir. Bu, sinyal kalitesini ve isabet oranını önemli ölçüde artırır.

Akıllı Filtreleme Sırası: Tarama listesi artık önce whitelist, sonra gainer/loser listesi alınarak oluşturulur ve ardından blacklist, dinamik kara liste ve mevcut açık pozisyonlara göre filtrelenir.

[1.4.0] - 2025-06-12

(Bu versiyon bir önceki geliştirme döngüsünde ara versiyon olarak kullanılmıştır)

[1.3.1] - 2025-06-12

(Kritik hata düzeltmeleri)

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