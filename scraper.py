import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, quote_plus

try:
    import cloudscraper
    _scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    def _get(url: str, timeout: int = 25):
        return _scraper.get(url, timeout=timeout)
    _BACKEND = "cloudscraper"
except ImportError:
    import requests
    _SESSION = requests.Session()
    _SESSION.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    })
    def _get(url: str, timeout: int = 25):
        return _SESSION.get(url, timeout=timeout)
    _BACKEND = "requests"

from bs4 import BeautifulSoup

TIMEOUT = 25
DEBUG = True


def _dbg(msg: str):
    if DEBUG:
        print(f"[DEBUG] {msg}")


_dbg(f"HTTP backend: {_BACKEND}")


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


# ─────────────────────────────────────────────
#  Shared detail page fetcher
# ─────────────────────────────────────────────

def _fetch_details_generic(game: GameResult) -> GameResult:
    try:
        resp = _get(game.url, TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        game.magnets = list(dict.fromkeys(
            a["href"] for a in soup.find_all("a", href=re.compile(r"^magnet:"))
        ))
        for a in soup.find_all("a", href=re.compile(r"\.torrent($|\?)", re.I)):
            if a["href"] not in game.magnets:
                game.magnets.append(a["href"])

        content_div = (
            soup.find("div", class_="entry-content") or
            soup.find("div", class_="post-content") or
            soup.find("div", class_=re.compile(r"content|article[-_]body", re.I))
        )
        if content_div:
            paras = content_div.find_all("p")
            lines = [p.get_text(" ", strip=True) for p in paras[:8]
                     if len(p.get_text(strip=True)) > 20]
            game.description = "\n".join(lines[:4])

        featured = soup.find("img", class_=re.compile(
            r"attachment|wp-post-image|featured|thumbnail", re.I))
        if featured:
            src = (featured.get("src") or featured.get("data-src") or
                   featured.get("data-lazy-src") or "")
            if src:
                game.image_url = src

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
        _dbg(f"[{game.source} Detail Error] {e}")
    return game


def _check_cf_block(name: str, html: str) -> bool:
    """Returns True if Cloudflare is blocking us."""
    lower = html[:2000].lower()
    blocked = ("just a moment" in lower or
               "cf-browser-verification" in html or
               "challenge" in lower or
               len(html) < 500)
    if blocked:
        _dbg(f"[{name}] *** Cloudflare/bot block detected (html={len(html)} bytes) ***")
    return blocked


# ─────────────────────────────────────────────
#  FitGirl — standard WP <article>
# ─────────────────────────────────────────────

FITGIRL_BASE = "https://fitgirl-repacks.site"


def fitgirl_search(query: str) -> List[GameResult]:
    results = []
    url = f"{FITGIRL_BASE}/?s={quote_plus(query)}"
    _dbg(f"[FitGirl] GET {url}")
    try:
        resp = _get(url)
        resp.raise_for_status()
        if _check_cf_block("FitGirl", resp.text):
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article")
        _dbg(f"[FitGirl] articles: {len(articles)}")
        for art in articles:
            try:
                a_tag = art.find("a", rel=lambda r: r and "bookmark" in r)
                if not a_tag:
                    for h in ["h1", "h2", "h3"]:
                        ht = art.find(h)
                        if ht:
                            a_tag = ht.find("a", href=True)
                            if a_tag:
                                break
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag["href"]
                if not title or not href.startswith("http"):
                    continue
                img = art.find("img")
                image_url = ""
                if img:
                    image_url = (img.get("src") or img.get("data-src") or
                                 img.get("data-lazy-src") or "")
                time_tag = art.find("time")
                date = time_tag.get_text(strip=True) if time_tag else "Unknown"
                m = re.search(r"(\d[\d.,]*\s*(?:GB|MB|TB))", art.get_text(" "), re.I)
                size = m.group(1) if m else "Unknown"
                results.append(GameResult(title=title, source="FitGirl", url=href,
                                          size=size, date=date, image_url=image_url))
            except Exception:
                continue
    except Exception as e:
        _dbg(f"[FitGirl Search Error] {e}")
    _dbg(f"[FitGirl] results: {len(results)}")
    return results


def fitgirl_fetch_details(game: GameResult) -> GameResult:
    return _fetch_details_generic(game)


# ─────────────────────────────────────────────
#  RG Mechanics — h2.post-title > a[rel=bookmark]
# ─────────────────────────────────────────────

RGMECHANICS_BASE = "https://rgmechanics.com"


def rgmechanics_search(query: str) -> List[GameResult]:
    results = []
    url = f"{RGMECHANICS_BASE}/?s={quote_plus(query)}"
    _dbg(f"[RG Mechanics] GET {url}")
    try:
        resp = _get(url)
        resp.raise_for_status()
        _dbg(f"[RG Mechanics] HTML length: {len(resp.text)}")
        if _check_cf_block("RG Mechanics", resp.text):
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        post_titles = soup.find_all("h2", class_="post-title")
        _dbg(f"[RG Mechanics] h2.post-title: {len(post_titles)}")

        # Fallback: any <article> tags
        if not post_titles:
            _dbg("[RG Mechanics] Trying <article> fallback")
            for art in soup.find_all("article"):
                a = art.find("a", rel=lambda r: r and "bookmark" in r) or \
                    art.find("h2", {}).and_then(lambda h: h.find("a")) if hasattr(art.find("h2", {}), 'and_then') else None
                if not a:
                    h2 = art.find("h2")
                    if h2:
                        a = h2.find("a", href=True)
                if a:
                    title = a.get_text(strip=True)
                    href = a["href"]
                    if title and href.startswith("http"):
                        img = art.find("img")
                        image_url = img.get("src", "") if img else ""
                        results.append(GameResult(title=title, source="RG Mechanics",
                                                  url=href, image_url=image_url))
            return results

        for h2 in post_titles:
            try:
                a_tag = (h2.find("a", rel=lambda r: r and "bookmark" in r)
                         or h2.find("a", href=True))
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag["href"]
                if not title or not href.startswith("http"):
                    continue
                post_div = h2.find_parent("div", id=re.compile(r"^post-\d+"))
                image_url = date = size = ""
                if post_div:
                    img = post_div.find("img")
                    if img:
                        image_url = (img.get("src") or img.get("data-src") or
                                     img.get("data-lazy-src") or "")
                    date_a = post_div.find("a", class_="post-date")
                    date = date_a.get_text(strip=True) if date_a else "Unknown"
                    m = re.search(r"(\d[\d.,]*\s*(?:GB|MB|TB))",
                                  post_div.get_text(" "), re.I)
                    size = m.group(1) if m else "Unknown"
                results.append(GameResult(title=title, source="RG Mechanics", url=href,
                                          size=size, date=date, image_url=image_url))
            except Exception:
                continue
    except Exception as e:
        _dbg(f"[RG Mechanics Search Error] {e}")
    _dbg(f"[RG Mechanics] results: {len(results)}")
    return results


def rgmechanics_fetch_details(game: GameResult) -> GameResult:
    return _fetch_details_generic(game)


# ─────────────────────────────────────────────
#  GoGUnlocked — div.cover-item
# ─────────────────────────────────────────────

GOGUNLOCKED_BASE = "https://gogunlocked.com"


def gogunlocked_search(query: str) -> List[GameResult]:
    results = []
    url = f"{GOGUNLOCKED_BASE}/?s={quote_plus(query)}"
    _dbg(f"[GoGUnlocked] GET {url}")
    try:
        resp = _get(url)
        resp.raise_for_status()
        _dbg(f"[GoGUnlocked] HTML length: {len(resp.text)}")
        if _check_cf_block("GoGUnlocked", resp.text):
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.find_all("div", class_="cover-item")
        _dbg(f"[GoGUnlocked] div.cover-item: {len(items)}")

        # Fallback: any <article> or post divs
        if not items:
            _dbg("[GoGUnlocked] Trying article/post fallback")
            for art in (soup.find_all("article") or
                        soup.find_all("div", class_=re.compile(r"\bpost\b"))):
                a = art.find("a", href=True)
                if a:
                    title = a.get_text(strip=True)
                    href = a["href"]
                    if len(title) > 4 and href.startswith("http"):
                        img = art.find("img")
                        image_url = img.get("src", "") if img else ""
                        results.append(GameResult(title=title, source="GoGUnlocked",
                                                  url=href, image_url=image_url))
            return results

        for item in items:
            try:
                title_div = item.find("div", class_="cover-item-content__title")
                if not title_div:
                    continue
                a_tag = title_div.find("a", href=True)
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag["href"]
                if not title or not href.startswith("http"):
                    continue
                img_div = item.find("div", class_="cover-item-image")
                image_url = ""
                if img_div:
                    img = img_div.find("img")
                    if img:
                        image_url = (img.get("src") or img.get("data-src") or
                                     img.get("data-lazy-src") or "")
                results.append(GameResult(title=title, source="GoGUnlocked",
                                          url=href, image_url=image_url))
            except Exception:
                continue
    except Exception as e:
        _dbg(f"[GoGUnlocked Search Error] {e}")
    _dbg(f"[GoGUnlocked] results: {len(results)}")
    return results


def gogunlocked_fetch_details(game: GameResult) -> GameResult:
    return _fetch_details_generic(game)


# ─────────────────────────────────────────────
#  CroTorrent — article.latestPost
# ─────────────────────────────────────────────

CROTORRENT_BASE = "https://crotorrents.com"


def crotorrent_search(query: str) -> List[GameResult]:
    results = []
    url = f"{CROTORRENT_BASE}/?s={quote_plus(query)}"
    _dbg(f"[CroTorrent] GET {url}")
    try:
        resp = _get(url)
        resp.raise_for_status()
        _dbg(f"[CroTorrent] HTML length: {len(resp.text)}")
        if _check_cf_block("CroTorrent", resp.text):
            return results
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article", class_="latestPost")
        _dbg(f"[CroTorrent] article.latestPost: {len(articles)}")

        # Fallback: any <article>
        if not articles:
            _dbg("[CroTorrent] Trying generic <article> fallback")
            articles = soup.find_all("article")
            _dbg(f"[CroTorrent] generic articles: {len(articles)}")

        for art in articles:
            try:
                h2 = art.find("h2", class_=re.compile(r"\btitle\b")) or art.find("h2")
                if not h2:
                    continue
                a_tag = h2.find("a", href=True)
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag["href"]
                if not title or not href.startswith("http"):
                    continue

                thumb_div = art.find("div", class_="featured-thumbnail")
                image_url = ""
                if thumb_div:
                    img = thumb_div.find("img")
                    if img:
                        image_url = img.get("src") or img.get("data-src") or ""
                if not image_url:
                    img = art.find("img")
                    if img:
                        image_url = img.get("src") or img.get("data-src") or ""

                time_span = art.find("span", class_="thetime")
                date = "Unknown"
                if time_span:
                    inner = time_span.find("span")
                    date = (inner or time_span).get_text(strip=True)
                if date == "Unknown":
                    time_tag = art.find("time")
                    if time_tag:
                        date = time_tag.get_text(strip=True)

                cat_span = art.find("span", class_="thecategory")
                genres = ""
                if cat_span:
                    genres = ", ".join(a.get_text(strip=True)
                                      for a in cat_span.find_all("a"))

                results.append(GameResult(title=title, source="CroTorrent",
                                          url=href, date=date,
                                          image_url=image_url, genres=genres))
            except Exception:
                continue
    except Exception as e:
        _dbg(f"[CroTorrent Search Error] {e}")
    _dbg(f"[CroTorrent] results: {len(results)}")
    return results


def crotorrent_fetch_details(game: GameResult) -> GameResult:
    return _fetch_details_generic(game)


# ─────────────────────────────────────────────
#  Aggregator
# ─────────────────────────────────────────────

SOURCE_MAP = {
    "FitGirl":      (fitgirl_search,      fitgirl_fetch_details),
    "GoGUnlocked":  (gogunlocked_search,  gogunlocked_fetch_details),
    "RG Mechanics": (rgmechanics_search,  rgmechanics_fetch_details),
    "CroTorrent":   (crotorrent_search,   crotorrent_fetch_details),
}

ALL_SOURCES = list(SOURCE_MAP.keys())


def search_all(query: str, sources: List[str] = None) -> List[GameResult]:
    if sources is None:
        sources = ALL_SOURCES
    results = []
    for src in sources:
        if src in SOURCE_MAP:
            search_fn, _ = SOURCE_MAP[src]
            found = search_fn(query)
            _dbg(f"[{src}] → {len(found)} results")
            results.extend(found)
    return results


def fetch_details(game: GameResult) -> GameResult:
    _, detail_fn = SOURCE_MAP.get(game.source, (None, None))
    if detail_fn:
        return detail_fn(game)
    return game