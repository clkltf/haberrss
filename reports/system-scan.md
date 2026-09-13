# HaberRSS Otomatik Sistem Taraması

- **Tarih:** 2026-09-13T19:03:24+03:00
- **Sunucu:** 109-236-48-134.diyovm.com
- **Git commit:** c576504
- **Branch:** main

## Özet

| Kontrol | Sonuç |
|---|---:|
| App | running |
| App health | healthy |
| PostgreSQL | true |
| Redis | true |
| News | 0 |
| Sources | 33 |
| Story clusters | 3072 |
| Cluster articles | 0 |
| Trends | 0 |
| News son 1 saat | 0 |
| News son 24 saat | 0 |
| GDELT hata sayısı (son 500 log) | 5 |
| App hata sayısı (son 500 log) | 15 |
| Restarting servis sayısı | 0 |
| Cluster P0 | false |

## P0 / Kritik

- **P1:** GDELT son loglarda 5 hata üretti.

## Container Durumu

```text
NAME                  IMAGE                COMMAND                  SERVICE    CREATED          STATUS                    PORTS
haberrss-app-1        haberrss-app         "python -m haberrss.…"   app        40 minutes ago   Up 40 minutes (healthy)   
haberrss-postgres-1   postgres:16-alpine   "docker-entrypoint.s…"   postgres   40 minutes ago   Up 40 minutes (healthy)   5432/tcp
haberrss-redis-1      redis:7-alpine       "docker-entrypoint.s…"   redis      40 minutes ago   Up 40 minutes (healthy)   6379/tcp
```

## Son Collector Kayıtları

```text
app-1  | 2026-09-13 16:01:29,957 INFO haberrss.collector source=Google News Galatasaray entries=100
app-1  | 2026-09-13 16:01:30,701 INFO haberrss.collector source=Google News Beşiktaş entries=100
app-1  | 2026-09-13 16:01:31,423 INFO haberrss.collector source=Google News Trabzonspor entries=100
app-1  | 2026-09-13 16:01:32,568 INFO haberrss.collector source=Google News Milli Takım entries=100
app-1  | 2026-09-13 16:01:33,271 INFO haberrss.collector source=Google News Yapay Zeka entries=100
app-1  | 2026-09-13 16:01:34,241 INFO haberrss.collector source=Google News Bitcoin entries=88
app-1  | 2026-09-13 16:01:35,414 INFO haberrss.collector source=Google News Borsa entries=100
app-1  | 2026-09-13 16:01:36,249 INFO haberrss.collector source=Google News Dolar entries=100
app-1  | 2026-09-13 16:01:37,551 INFO haberrss.collector source=Google News Akaryakıt entries=100
app-1  | 2026-09-13 16:01:38,707 INFO haberrss.collector source=Google News Zam entries=100
app-1  | 2026-09-13 16:01:39,807 INFO haberrss.collector source=Google News Mahkeme entries=89
app-1  | 2026-09-13 16:01:40,580 INFO haberrss.collector source=Google News Tutuklama entries=100
app-1  | 2026-09-13 16:01:41,859 INFO haberrss.collector source=Google News İstifa entries=100
app-1  | 2026-09-13 16:01:42,834 INFO haberrss.collector source=Google News Hava Durumu entries=76
app-1  | 2026-09-13 16:01:43,948 INFO haberrss.collector source=Google News Son Gelişme entries=100
app-1  | 2026-09-13 16:01:52,193 ERROR haberrss.realtime GDELT collector failed
app-1  |     r = client.get(GDELT_URL, params={"query": "Turkey", "mode": "artlist", "maxrecords": 100, "format": "json", "timespan": "15m"})
app-1  | 2026-09-13 16:03:22,648 INFO haberrss.trend trend processed clusters=3072
```

## Son Hatalar

```text
app-1  | 2026-09-13 15:55:43,837 ERROR haberrss.realtime GDELT collector failed
app-1  | Traceback (most recent call last):
app-1  | Traceback (most recent call last):
app-1  |     r = client.get(GDELT_URL, params={"query": "Turkey", "mode": "artlist", "maxrecords": 100, "format": "json", "timespan": "15m"})
app-1  | 2026-09-13 15:57:37,019 ERROR haberrss.realtime GDELT collector failed
app-1  | Traceback (most recent call last):
app-1  | Traceback (most recent call last):
app-1  |     r = client.get(GDELT_URL, params={"query": "Turkey", "mode": "artlist", "maxrecords": 100, "format": "json", "timespan": "15m"})
app-1  | 2026-09-13 16:01:25,171 INFO haberrss.collector source=GDELT Turkey 15m entries=0
app-1  | 2026-09-13 16:01:52,193 ERROR haberrss.realtime GDELT collector failed
app-1  | Traceback (most recent call last):
app-1  | Traceback (most recent call last):
app-1  |     r = client.get(GDELT_URL, params={"query": "Turkey", "mode": "artlist", "maxrecords": 100, "format": "json", "timespan": "15m"})
```

## Veritabanı Kontrolleri

```text
news_by_source
```

## Kaynaklar

```text
1|Google News Türkiye|https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr|genel
2|Google News Son Dakika|https://news.google.com/rss/search?q=son%20dakika&hl=tr&gl=TR&ceid=TR:tr|son-dakika
3|Google News Gündem|https://news.google.com/rss/search?q=Türkiye%20gündem&hl=tr&gl=TR&ceid=TR:tr|gundem
4|Google News Siyaset|https://news.google.com/rss/search?q=siyaset%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|siyaset
5|Google News Ekonomi|https://news.google.com/rss/search?q=Türkiye%20ekonomi&hl=tr&gl=TR&ceid=TR:tr|ekonomi
6|Google News Spor|https://news.google.com/rss/search?q=spor%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|spor
7|Google News Teknoloji|https://news.google.com/rss/search?q=teknoloji%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|teknoloji
8|Google News Magazin|https://news.google.com/rss/search?q=magazin%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|magazin
9|Google News Dünya|https://news.google.com/rss/search?q=dünya%20gündem&hl=tr&gl=TR&ceid=TR:tr|dunya
10|Google News Deprem|https://news.google.com/rss/search?q=deprem%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|afet
11|Google News Yangın|https://news.google.com/rss/search?q=yangın%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|afet
12|Google News Kaza|https://news.google.com/rss/search?q=kaza%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|afet
13|Google News Patlama|https://news.google.com/rss/search?q=patlama%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|afet
14|Google News Hava Durumu|https://news.google.com/rss/search?q=sel%20fırtına%20kar%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|hava
15|Google News Son Gelişme|https://news.google.com/rss/search?q=son%20gelişme%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|breaking
16|Google News Flaş|https://news.google.com/rss/search?q=flaş%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|breaking
17|Google News Önemli|https://news.google.com/rss/search?q=önemli%20gelişme%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|breaking
18|Google News Fenerbahçe|https://news.google.com/rss/search?q=Fenerbahçe&hl=tr&gl=TR&ceid=TR:tr|spor
19|Google News Galatasaray|https://news.google.com/rss/search?q=Galatasaray&hl=tr&gl=TR&ceid=TR:tr|spor
20|Google News Beşiktaş|https://news.google.com/rss/search?q=Beşiktaş&hl=tr&gl=TR&ceid=TR:tr|spor
21|Google News Trabzonspor|https://news.google.com/rss/search?q=Trabzonspor&hl=tr&gl=TR&ceid=TR:tr|spor
22|Google News Milli Takım|https://news.google.com/rss/search?q=Milli%20Takım%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|spor
23|Google News Yapay Zeka|https://news.google.com/rss/search?q=yapay%20zeka&hl=tr&gl=TR&ceid=TR:tr|teknoloji
24|Google News Bitcoin|https://news.google.com/rss/search?q=Bitcoin%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|finans
25|Google News Borsa|https://news.google.com/rss/search?q=Borsa%20İstanbul&hl=tr&gl=TR&ceid=TR:tr|finans
26|Google News Dolar|https://news.google.com/rss/search?q=dolar%20TL&hl=tr&gl=TR&ceid=TR:tr|finans
27|Google News Akaryakıt|https://news.google.com/rss/search?q=akaryakıt%20zam%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|ekonomi
28|Google News Zam|https://news.google.com/rss/search?q=zam%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|ekonomi
29|Google News Mahkeme|https://news.google.com/rss/search?q=mahkeme%20karar%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|gundem
30|Google News Tutuklama|https://news.google.com/rss/search?q=tutuklandı%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|gundem
31|Google News İstifa|https://news.google.com/rss/search?q=istifa%20Türkiye&hl=tr&gl=TR&ceid=TR:tr|gundem
33|Google Trends Türkiye|https://trends.google.com/trendingsearches/daily/rss?geo=TR|trend-signal
1118|GDELT Turkey 15m|https://api.gdeltproject.org/api/v2/doc/doc?query=Turkey&mode=artlist&maxrecords=100&format=json&timespan=15m|gdelt
```

## Son Haberler

```text

```

## Git Durumu

```text
 M reports/system-scan.md
 M scripts/haberrss-doctor.sh
 M scripts/haberrss-scan-push.sh
?? docker-compose.simple.yml
```
