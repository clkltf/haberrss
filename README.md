# HaberRSS — Ne Konuşuluyor?

Türkiye odaklı gerçek zamanlı haber ve trend istihbarat motoru.

## Hedef
- Çoklu RSS/news feed toplama
- GDELT destekli keşif
- URL + başlık normalize/dedup
- Aynı olayı story cluster olarak birleştirme
- Hız, kaynak çeşitliliği, tazelik ve aciliyet ile trend/viral skorları
- AI editör kuyruğu
- Telegram onay akışı
- X yayınlayıcı katmanı
- PostgreSQL + Redis
- Docker Compose
- Health-check ve gözlemlenebilirlik

## Kurulum

```bash
git clone https://github.com/clkltf/haberrss.git
cd haberrss
cp .env.example .env
# .env değerlerini doldur
docker compose up -d --build
```

## Güvenlik

API anahtarlarını GitHub'a koymayın. `.env` sadece sunucuda tutulur. İlk aşamada X otomatik yayın kapalıdır.

## Mimari

collector → normalizer/dedup → story clustering → trend engine → editor queue → AI editor → Telegram → X publisher
