import threading
import io
from typing import Callable, Dict, Tuple
from PIL import Image, ImageDraw
import customtkinter as ctk
import requests

# Cache key: "url_WxH" -> CTkImage
_cache: Dict[str, ctk.CTkImage] = {}
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


def _to_ctk_image(pil_img: Image.Image, width: int, height: int) -> ctk.CTkImage:
    """PIL Image → CTkImage (HighDPI safe, no warning)."""
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(width, height))


def load_image_async(
    url: str,
    width: int,
    height: int,
    callback: Callable[[ctk.CTkImage], None],
    rounded: bool = True,
) -> None:
    """
    Async mein image download karo aur callback mein CTkImage do.
    Callback CTk main thread se call hogi (after_idle via widget) —
    lekin yahan hum sirf callback() call karte hain; caller ko
    widget.after(0, lambda: label.configure(image=img)) use karna chahiye.
    """
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
                pil_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            else:
                pil_img = _make_placeholder(width, height, "NO IMG")

            pil_img = pil_img.resize((width, height), Image.LANCZOS)
            if rounded:
                pil_img = _rounded_image(pil_img, radius=8)

        except Exception:
            pil_img = _make_placeholder(width, height, "NO IMG")
            if rounded:
                pil_img = _rounded_image(pil_img, radius=8)

        ctk_img = _to_ctk_image(pil_img, width, height)
        with _lock:
            _cache[cache_key] = ctk_img
        callback(ctk_img)

    threading.Thread(target=worker, daemon=True).start()


def clear_cache() -> None:
    with _lock:
        _cache.clear()