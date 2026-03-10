import requests
from bs4 import BeautifulSoup
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, quote_plus

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 15


@dataclass
class GameResult:
    title: str
    source: str
    url: str
    size: str = "Unknown"
    date: str = "Unknown"
    image_url: str = ""
    magnets: List[str] = field(default_factory=list)
    description: str = ""
    genres: str = ""
    languages: str = ""

def _parse_wp_article(article, source: str, base_url: str) -> Optional[GameResult]:
    try:
        a_tag = article.find("a", rel=lambda r: r and "bookmark" in r)
        if not a_tag:
            for tag in ["h1", "h2", "h3"]:
                heading = article.find(tag)
                if heading:
                    a_tag = heading.find("a")
                    if a_tag:
                        break
        if not a_tag:
            a_tag = article.find("a", href=True)
        if not a_tag:
            return None

        title = a_tag.get_text(strip=True)
        url   = a_tag["href"]
        if url.startswith("/"):
            url = urljoin(base_url, url)
        if not title or not url.startswith("http"):
            return None

        img = article.find("img")
        image_url = ""
        if img:
            image_url = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if image_url.startswith("/"):
            image_url = urljoin(base_url, image_url)

        time_tag = article.find("time")
        date = time_tag.get_text(strip=True) if time_tag else "Unknown"

        size = "Unknown"
        text = article.get_text(" ")
        m = re.search(r"(\d[\d.,]*\s*(?:GB|MB|TB))", text, re.I)
        if m:
            size = m.group(1)

        return GameResult(title=title, source=source, url=url,
                          size=size, date=date, image_url=image_url)
    except Exception:
        return None


def _wp_search(base_url: str, source: str, query: str) -> List[GameResult]:
    results = []
    search_url = f"{base_url}/?s={quote_plus(query)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article")
        if not articles:
            articles = soup.find_all("div", class_=re.compile(r"\bpost\b|\bentry\b|\bhentry\b", re.I))
        for art in articles:
            g = _parse_wp_article(art, source, base_url)
            if g:
                results.append(g)
    except Exception as e:
        print(f"[{source} Search Error] {e}")
    return results


def _wp_fetch_details(game: GameResult) -> GameResult:
    try:
        resp = requests.get(game.url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        game.magnets = list(dict.fromkeys(
            a["href"] for a in soup.find_all("a", href=re.compile(r"^magnet:"))
        ))
        torrent_links = [
            a["href"] for a in soup.find_all("a", href=re.compile(r"\.torrent($|\?)", re.I))
        ]
        for tl in torrent_links:
            if tl not in game.magnets:
                game.magnets.append(tl)
        content_div = (soup.find("div", class_="entry-content") or
                       soup.find("div", class_="post-content") or
                       soup.find("div", class_=re.compile(r"content|article-body", re.I)))
        if content_div:
            paras = content_div.find_all("p")
            lines = [p.get_text(" ", strip=True) for p in paras[:8]
                     if len(p.get_text(strip=True)) > 20]
            game.description = "\n".join(lines[:4])
        featured = soup.find("img", class_=re.compile(
            r"attachment|wp-post-image|featured|thumbnail", re.I))
        if featured and featured.get("src"):
            game.image_url = featured["src"]

        full_text = soup.get_text(" ")
        m = re.search(r"(\d[\d.,]*\s*(?:GB|MB|TB))", full_text, re.I)
        if m:
            game.size = m.group(1)

        m = re.search(r"(?:Genre|Genres|Tags)[/\w\s]*?:\s*([^\n<]{3,80})", full_text, re.I)
        if m:
            game.genres = m.group(1).strip()
        m = re.search(r"Languages?:\s*([^\n<]{3,120})", full_text, re.I)
        if m:
            game.languages = m.group(1).strip()[:120]

    except Exception as e:
        print(f"[{game.source} Detail Error] {e}")
    return game

FITGIRL_BASE = "https://fitgirl-repacks.site"

def fitgirl_search(query: str) -> List[GameResult]:
    return _wp_search(FITGIRL_BASE, "FitGirl", query)

def fitgirl_fetch_details(game: GameResult) -> GameResult:
    return _wp_fetch_details(game)

GOGUNLOCKED_BASE = "https://gogunlocked.com"

def gogunlocked_search(query: str) -> List[GameResult]:
    return _wp_search(GOGUNLOCKED_BASE, "GoGUnlocked", query)

def gogunlocked_fetch_details(game: GameResult) -> GameResult:
    return _wp_fetch_details(game)

RGMECHANICS_BASE = "https://rgmechanics.com"

def rgmechanics_search(query: str) -> List[GameResult]:
    return _wp_search(RGMECHANICS_BASE, "RG Mechanics", query)

def rgmechanics_fetch_details(game: GameResult) -> GameResult:
    return _wp_fetch_details(game)

CROTORRENT_BASE = "https://crotorrents.com"

def crotorrent_search(query: str) -> List[GameResult]:
    results = _wp_search(CROTORRENT_BASE, "CroTorrent", query)
    if not results:
        results = _wp_search("https://crotorrent.com", "CroTorrent", query)
    return results

def crotorrent_fetch_details(game: GameResult) -> GameResult:
    return _wp_fetch_details(game)

SOURCE_MAP = {
    "FitGirl":     (fitgirl_search,     fitgirl_fetch_details),
    "GoGUnlocked": (gogunlocked_search, gogunlocked_fetch_details),
    "RG Mechanics":(rgmechanics_search, rgmechanics_fetch_details),
    "CroTorrent":  (crotorrent_search,  crotorrent_fetch_details),
}

ALL_SOURCES = list(SOURCE_MAP.keys())


def search_all(query: str, sources: List[str] = None) -> List[GameResult]:
    if sources is None:
        sources = ALL_SOURCES
    results = []
    for src in sources:
        if src in SOURCE_MAP:
            search_fn, _ = SOURCE_MAP[src]
            results.extend(search_fn(query))
    return results


def fetch_details(game: GameResult) -> GameResult:
    _, detail_fn = SOURCE_MAP.get(game.source, (None, None))
    if detail_fn:
        return detail_fn(game)
    return game
