# RFP ve Sözleşme Asistanı

RFP ve Sözleşme Asistanı, yapay zeka destekli bir belge analiz ve hazırlama sistemidir. Bu sistem, RFP (Request for Proposal) ve sözleşme hazırlama süreçlerini otomatikleştirerek, belgelerin kalitesini artırır ve risk yönetimini iyileştirir.

## Özellikler

- **Doküman Analizi**: RFP ve sözleşmelerin içerik analizi, eksik bölümlerin tespiti
- **Risk Değerlendirmesi**: Yasal ve ticari risklerin otomatik tespiti
- **Şablon Oluşturma**: Sektöre özel RFP ve sözleşme şablonları
- **Karşılaştırma**: Doküman versiyonları arasındaki farkların analizi
- **OCR İşleme**: PDF ve Word belgelerinden metin çıkarımı

## Mimari

Sistem, aşağıdaki Azure servislerini kullanmaktadır:

- **Azure OpenAI Service**: GPT-4o ile içerik analizi ve risk değerlendirmesi
- **Azure Blob Storage**: Doküman depolama
- **Azure Form Recognizer**: OCR ve belge yapısı çıkarımı
- **Azure App Service**: Backend API barındırma
- **Azure Cosmos DB**: Veritabanı
- **Azure AD B2C**: Kimlik doğrulama
- **Azure Application Insights**: Loglama ve izleme

## Kurulum

### Gereksinimler

- Python 3.8+
- Azure hesabı
- Azure CLI

### Yerel Geliştirme Ortamı

1. Depoyu klonlayın:
```
git clone https://github.com/kullanici/raporlama.git
cd raporlama
```

2. Sanal ortam oluşturun ve bağımlılıkları yükleyin:
```
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Çevre değişkenlerini ayarlayın:
```
cp .env.example .env
# .env dosyasını düzenleyerek gerekli API anahtarlarını ekleyin
```

4. Uygulamayı çalıştırın:
```
python backend/api/main.py
```

## API Kullanımı

### Doküman Yükleme

```
POST /documents/upload
```

Örnek istek:
```json
{
  "file": "(binary file)",
  "document_type": "rfp",
  "description": "Yazılım Projesi RFP"
}
```

### Doküman Analizi

```
POST /analysis/rfp
```

Örnek istek:
```json
{
  "document_id": "1234",
  "analysis_type": ["completeness", "clarity", "risks"]
}
```

### Şablon Oluşturma

```
POST /templates/
```

Örnek istek:
```json
{
  "name": "Yazılım Geliştirme RFP",
  "template_type": "rfp",
  "description": "Yazılım projeleri için RFP şablonu",
  "sections": [...]
}
```

## Katkıda Bulunma

1. Bu depoyu forklayın
2. Yeni bir branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır - detaylar için LICENSE dosyasına bakın. 