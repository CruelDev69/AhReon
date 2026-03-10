import threading
import io
import hashlib
from typing import Callable, Dict, Optional
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import requests

_cache: Dict[str, ImageTk.PhotoImage] = {}
_lock = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def _make_placeholder(width: int, height: int, text: str = "?") -> Image.Image:
    img = Image.new("RGB", (width, height), color="#1a1a2e")
    draw = ImageDraw.Draw(img)
    for x in range(0, width, 20):
        draw.line([(x, 0), (x, height)], fill="#202035", width=1)
    for y in range(0, height, 20):
        draw.line([(0, y), (width, y)], fill="#202035", width=1)
    draw.text((width // 2, height // 2), text, fill="#404060", anchor="mm")
    return img


def _rounded_image(img: Image.Image, radius: int = 10) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=radius, fill=255)
    result = img.copy()
    result.putalpha(mask)
    bg = Image.new("RGBA", img.size, (26, 26, 46, 255))
    bg.paste(result, mask=result)
    return bg.convert("RGB")


def load_image_async(
    url: str,
    width: int,
    height: int,
    callback: Callable[[ImageTk.PhotoImage], None],
    rounded: bool = True,
) -> None:
    cache_key = f"{url}_{width}x{height}"
    with _lock:
        if cache_key in _cache:
            callback(_cache[cache_key])
            return

    def worker():
        try:
            if url and url.startswith("http"):
                resp = requests.get(url, headers=HEADERS, timeout=8)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            else:
                img = _make_placeholder(width, height, "NO IMG")

            img = img.resize((width, height), Image.LANCZOS)
            if rounded:
                img = _rounded_image(img, radius=8)

            photo = ImageTk.PhotoImage(img)
            with _lock:
                _cache[cache_key] = photo
            callback(photo)
        except Exception:
            img = _make_placeholder(width, height, "NO IMG")
            if rounded:
                img = _rounded_image(img, radius=8)
            photo = ImageTk.PhotoImage(img)
            with _lock:
                _cache[cache_key] = photo
            callback(photo)

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def clear_cache():
    with _lock:
        _cache.clear()
