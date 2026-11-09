import email.utils, html, json, os, sys, time
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

SENT_FILE = Path(__file__).with_name("sent.json")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
KEYWORDS = [k.strip() for k in os.environ.get("KEYWORDS", "케이쓰리아이").split(",") if k.strip()]
MAX_PER_RUN = 10
MAX_AGE_HOURS = 24
UA = {"User-Agent": "Mozilla/5.0 (compatible; news-telegram-bot/1.0)"}


def load_sent():
    try:
        return json.loads(SENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def fetch_news(kw):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(kw) + "&hl=ko&gl=KR&ceid=KR:ko"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        except Exception:
            pub = None
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "source": (it.findtext("source") or "").strip(),
            "pub": pub, "kw": kw,
        })
    return [i for i in items if i["title"] and i["link"]]


def send(text):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=20).read()


def fmt(i):
    when = i["pub"].astimezone(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M") if i["pub"] else ""
    meta = " · ".join(x for x in [i["source"], when, "#" + i["kw"].replace(" ", "_")] if x)
    return f"📰 <b>{html.escape(i['title'])}</b>\n{html.escape(meta)}\n{i['link']}"


def main():
    if not BOT_TOKEN or not CHAT_ID:
        sys.exit("토큰/채팅ID 없음")
    sent = load_sent()
    done = set(sent)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    cands, titles = [], set()
    for kw in KEYWORDS:
        try:
            for i in fetch_news(kw):
                if i["link"] in done or i["title"] in titles:
                    continue
                if i["pub"] and i["pub"] < cutoff:
                    continue
                titles.add(i["title"])
                cands.append(i)
        except Exception as e:
            print("fetch fail", kw, e)
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    cands.sort(key=lambda x: x["pub"] or oldest, reverse=True)
    for i in reversed(cands[:MAX_PER_RUN]):
        try:
            send(fmt(i))
            time.sleep(1)
        except Exception as e:
            print("send fail", e)
    sent += [i["link"] for i in cands]
    SENT_FILE.write_text(json.dumps(sent[-1000:], ensure_ascii=False), encoding="utf-8")
    print("sent", min(len(cands), MAX_PER_RUN))


if __name__ == "__main__":
    main()
