# @author: Memba Co.
# Python'un hafif ve stabil bir sürümünü temel al
FROM python:3.11-slim

# Konteyner içindeki çalışma dizinini ayarla
WORKDIR /app

# Önce bağımlılıkları kopyala ve kur. Bu, Docker'ın katman önbellekleme
# mekanizmasından faydalanarak, kod değiştiğinde bağımlılıkların
# tekrar tekrar kurulmasını engeller.
COPY requirements.txt .

# pip'i güncelle ve requirements.txt içindeki kütüphaneleri kur
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Proje dosyalarının geri kalanını çalışma dizinine kopyala
COPY . .

# Konteyner başlatıldığında çalıştırılacak olan ana komut
# Bu komut, botu interaktif modda başlatır.
CMD ["python", "-u", "main.py"]
