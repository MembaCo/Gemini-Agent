# Dockerfile
# @author: Memba Co.

# 1. Temel imaj olarak Python 3.11'in hafif (slim) bir versiyonunu kullan.
FROM python:3.11-slim

# 2. Çalışma dizinini /app olarak ayarla. Sonraki tüm komutlar bu dizin içinde çalışır.
WORKDIR /app

# 3. Bağımlılıkları kurmak için requirements.txt dosyasını konteynere kopyala.
# Not: Sadece bu dosyayı önce kopyalamak, Docker'ın katman önbellekleme özelliğinden faydalanır.
# requirements.txt değişmediği sürece, bu adımlar tekrar çalıştırılmaz ve imaj daha hızlı oluşur.
COPY requirements.txt .

# 4. Gerekli kütüphaneleri pip ile kur.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Projenin geri kalan tüm dosyalarını (.py, .db, .md, /dashboard klasörü vb.) /app dizinine kopyala.
COPY . .

# 6. Web arayüzünün çalıştığı 5001 portunu dışarıya aç.
EXPOSE 5001

# 7. Konteyner başladığında çalıştırılacak olan varsayılan komut.
# Bu, botun tüm bileşenlerini (arka plan görevleri, web sunucusu, telegram botu) başlatır.
CMD ["python", "main.py"]