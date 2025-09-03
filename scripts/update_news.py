\
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup  # optional for future use
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import nltk

# Ensure required tokenizers are available (matches your previous approach)
for pkg in ["punkt", "punkt_tab"]:
    try:
        nltk.data.find(f"tokenizers/{pkg}")
    except LookupError:
        nltk.download(pkg)

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
CURRENTS_KEY = os.getenv("CURRENTS_KEY", "")
GUARDIAN_KEY = os.getenv("GUARDIAN_KEY", "")

IMAGE_PROVIDERS = ["unsplash"]  # simple default

def fetch_newsapi():
    if not NEWSAPI_KEY:
        return []
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=5&apiKey={NEWSAPI_KEY}"
    try:
        r = requests.get(url, timeout=10)
        return r.json().get("articles", [])
    except Exception:
        return []

def fetch_currents():
    if not CURRENTS_KEY:
        return []
    url = f"https://api.currentsapi.services/v1/latest-news?apiKey={CURRENTS_KEY}"
    try:
        r = requests.get(url, timeout=10)
        return r.json().get("articles", [])
    except Exception:
        return []

def fetch_guardian():
    if not GUARDIAN_KEY:
        return []
    url = f"https://content.guardianapis.com/search?api-key={GUARDIAN_KEY}&show-fields=trailText,thumbnail"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        return data.get("response",{}).get("results", [])
    except Exception:
        return []

def fetch_image_for_query(query):
    # Simple unsplash source
    return f"https://source.unsplash.com/600x400/?{query.replace(' ', ',')}"

def aggregate():
    articles = []
    # NewsAPI
    for art in fetch_newsapi():
        articles.append({
            "title": art.get("title"),
            "content": art.get("content") or art.get("description") or "",
            "url": art.get("url"),
            "image": art.get("urlToImage") or fetch_image_for_query(art.get("title","news"))
        })
    # Currents
    for art in fetch_currents():
        articles.append({
            "title": art.get("title"),
            "content": art.get("description") or "",
            "url": art.get("url"),
            "image": art.get("image") or fetch_image_for_query(art.get("title","news"))
        })
    # Guardian
    for art in fetch_guardian():
        f = art.get("fields", {})
        articles.append({
            "title": art.get("webTitle"),
            "content": f.get("trailText") or "",
            "url": art.get("webUrl"),
            "image": f.get("thumbnail") or fetch_image_for_query(art.get("webTitle","news"))
        })
    # Clean and cap
    cleaned = []
    seen = set()
    for a in articles:
        if not a["title"] or not a["content"]:
            continue
        if a["title"] in seen:
            continue
        seen.add(a["title"])
        cleaned.append(a)
        if len(cleaned) >= 9:
            break
    return cleaned

def summarize(articles):
    summarizer = LsaSummarizer()
    out = []
    for a in articles:
        raw = BeautifulSoup(a["content"], "html.parser").get_text(" ")
        parser = PlaintextParser.from_string(raw, Tokenizer("english"))
        summary_sentences = summarizer(parser.document, 2)
        summary = " ".join(str(s) for s in summary_sentences) if summary_sentences else raw[:200] + "..."
        out.append({
            "title": a["title"],
            "summary": summary,
            "url": a["url"],
            "image": a["image"]
        })
    return out

def save_to_db(items):
    # use the Flask app context
    from app import app, db, NewsArticle
    with app.app_context():
        # Clear old records (keep recent 100)
        keep = 100
        total = NewsArticle.query.count()
        if total > keep:
            older = NewsArticle.query.order_by(NewsArticle.created_at.asc()).limit(total-keep).all()
            for o in older:
                db.session.delete(o)
            db.session.commit()
        # Insert
        for it in items:
            na = NewsArticle(
                title=it["title"],
                summary=it["summary"],
                url=it["url"],
                image=it["image"],
                published_at=None
            )
            db.session.add(na)
        db.session.commit()

if __name__ == "__main__":
    arts = aggregate()
    summarized = summarize(arts)
    save_to_db(summarized)
    print(f"Saved {len(summarized)} news items.")
