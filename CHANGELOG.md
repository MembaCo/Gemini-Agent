# Değişiklik Günlüğü (Changelog)

Bu projede yapılan tüm önemli değişiklikler bu dosyada belgelenmektedir.
Format, [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardına dayanmaktadır.

## [1.1.0] - 2025-06-11

Bu sürüm, botun analiz yeteneklerini önemli ölçüde artıran Çoklu Zaman Aralığı (MTA) özelliğini ve kritik bir performans iyileştirmesini içermektedir.

### Eklendi (Added)
- **Çoklu Zaman Aralığı Analizi (MTA):** Botun analiz yeteneği, kısa vadeli giriş sinyallerini daha yüksek bir zaman dilimindeki ana trend ile teyit ederek daha isabetli kararlar almasını sağlayan MTA özelliği ile geliştirildi.
- **MTA Konfigürasyonu:** `config.py` dosyasına `USE_MTA_ANALYSIS` ve `MTA_TREND_TIMEFRAME` seçenekleri eklenerek yeni MTA özelliğinin kontrolü sağlandı.

### Değiştirildi (Changed)
- **Kritik Performans İyileştirmesi:** Proaktif tarama modunda kullanılan `get_top_gainers_losers` fonksiyonu, tüm piyasayı taramak yerine tek bir verimli API çağrısı kullanacak şekilde tamamen yeniden yazıldı. Bu değişiklik, API limit kullanımını büyük ölçüde azaltmış ve tarama hızını onlarca kat artırmıştır.
- **Prompt Mühendisliği:** Manuel analiz (`handle_new_analysis`) fonksiyonundaki prompt'lar, MTA verilerini (trend ve giriş sinyali) işleyebilecek ve buna göre karar verebilecek şekilde daha gelişmiş hale getirildi.
- **Simülasyon Modu:** Pozisyonları gösterirken yaklaşık PNL (Kâr/Zarar) hesaplaması, daha sağlam ve hatasız çalışması için metin ayrıştırmak yerine doğrudan dahili bir fonksiyonla fiyatı alacak şekilde iyileştirildi.

### Düzeltildi (Fixed)
- **Kritik Hata:** `main.py` dosyasında eksik olan `load_positions_from_file` ve `save_positions_to_file` fonksiyon tanımları nedeniyle programın başlangıçta çökmesine neden olan `NameError` hatası giderildi.
- **Arayüz:** Program başlangıcında tekrar eden konsol karşılama mesajları kaldırılarak daha temiz bir başlangıç sağlandı.

## [1.0.2] - 2025-06-11:
**Mimari İyileştirme:** Simülasyon modu ve pozisyon listeleme mantığı düzeltildi.

## [1.0.0] - 2025-06-11

Bu, projenin ilk kararlı sürümüdür. Çekirdek özellikler tamamlanmış ve bilinen kritik hatalar giderilmiştir.

### Eklendi (Added)
- `config.py`, `main.py`, `tools.py` ve `managed_positions.json` dosyaları ile temel proje yapısı oluşturuldu.
- Manuel (`Yeni Analiz Yap`) ve otomatik (`Proaktif Tarama`) analiz modları eklendi.
- Google Gemini ve LangChain kullanılarak yapay zeka destekli karar verme mekanizması entegre edildi.
- ATR'ye dayalı dinamik Stop-Loss ve Take-Profit hesaplama özelliği eklendi.
- Borsadaki açık pozisyonları listeleme ve botun hafızasıyla senkronize etme özelliği (`Pozisyonları Göster`) eklendi.
- `README.md` ile proje dokümantasyonu ve `requirements.txt` ile kurulum kolaylığı sağlandı.
- Merkezi versiyon takibi için `config.py` dosyasına `APP_VERSION` eklendi.

### Değiştirildi (Changed)
- **Mimari İyileştirme:** Manuel analiz (`handle_new_analysis`) fonksiyonu, Agent döngülerini engellemek için yeniden yapılandırıldı. Artık veri toplama sıralı olarak kod tarafından yapılıyor ve analiz için LLM'e tek seferde sunuluyor.
- **Performans:** `tools.py` içerisindeki `get_technical_indicators` fonksiyonunun daha fazla geçmiş veri (`limit=200`) çekmesi sağlanarak `NaN` hataları azaltıldı.
- **Sağlamlık:** Kod içindeki tüm `@tool` çağrıları, LangChain'in modern ve doğru yöntemi olan `.invoke()` kullanacak şekilde güncellendi.
- **Prompt Mühendisliği:** LLM'e verilen direktifler (prompt'lar), daha net ve kararlı JSON çıktıları üretmesi için iyileştirildi.

### Düzeltildi (Fixed)
- **Kritik Hata:** Agent'in `Action: None` üreterek veya aynı aracı tekrar tekrar çağırarak sonsuz döngüye girmesi ve API kotasını tüketmesi sorunu çözüldü.
- **Mantık Hatası:** Başarılı bir işlem sonrası dönen `"başarıyla"` mesajının `"başarılı"` olarak kontrol edilmesi nedeniyle işlemin başarısız sanılması hatası düzeltildi.
- **Veri Tipi Hatası:** Borsa senkronizasyonu sırasında `leverage` değerinin `None` gelmesi durumunda programın çökmesine neden olan `TypeError` hatası giderildi.
- **Kurulum Hatası:** `@tool` ile işaretlenen fonksiyonlarda `docstring` eksikliği nedeniyle programın başlamamasına neden olan `ValueError` hatası düzeltildi.