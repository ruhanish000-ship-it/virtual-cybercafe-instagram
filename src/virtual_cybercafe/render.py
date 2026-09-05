from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .music import generate_original_music


WIDTH, HEIGHT = 1080, 1920
POST_WIDTH, POST_HEIGHT = 1080, 1350
MARGIN = 82


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _font_path(bold: bool = False) -> str:
    candidates = (
        [
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Install fonts-noto-core or DejaVu Sans fonts")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_font_path(bold), size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fitted_lines(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start_size: int, min_size: int, bold: bool
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start_size, min_size - 1, -2):
        font = _font(size, bold)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = _font(min_size, bold)
    lines = _wrap(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while draw.textbbox((0, 0), last + "…", font=font)[2] > max_width and len(last) > 2:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return font, lines


def _background(palette: dict, accent_variant: int) -> Image.Image:
    navy = _hex(palette["navy"])
    blue = _hex(palette["blue"])
    image = Image.new("RGB", (WIDTH, HEIGHT), navy)
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        colour = tuple(int(navy[i] * (1 - ratio * 0.62) + blue[i] * ratio * 0.62) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = colour
    draw = ImageDraw.Draw(image, "RGBA")
    cyan = (*_hex(palette["cyan"]), 36)
    saffron = (*_hex(palette["saffron"]), 34)
    if accent_variant % 2:
        draw.ellipse((690, -180, 1250, 380), fill=cyan)
        draw.ellipse((-250, 1340, 410, 2010), fill=saffron)
    else:
        draw.ellipse((-240, -220, 410, 440), fill=saffron)
        draw.ellipse((760, 1370, 1260, 1900), fill=cyan)
    for offset in range(0, 8):
        x = 860 + offset * 32
        draw.line((x, 0, x - 610, HEIGHT), fill=(255, 255, 255, 9), width=2)
    return image


def _brand_header(draw: ImageDraw.ImageDraw, brand: dict, palette: dict, slide: int) -> None:
    cyan = _hex(palette["cyan"])
    white = _hex(palette["white"])
    muted = _hex(palette["muted"])
    draw.rounded_rectangle((MARGIN, 74, MARGIN + 76, 150), radius=22, fill=cyan)
    draw.text((MARGIN + 23, 83), "V", font=_font(45, True), fill=_hex(palette["navy"]))
    draw.text((MARGIN + 98, 78), brand["brand_name"], font=_font(34, True), fill=white)
    draw.text((MARGIN + 98, 121), brand["handle"], font=_font(23), fill=muted)
    draw.text((WIDTH - MARGIN - 92, 89), f"{slide}/5", font=_font(27, True), fill=muted)


def _pill(draw: ImageDraw.ImageDraw, text: str, palette: dict, y: int) -> int:
    font = _font(28, True)
    max_width = WIDTH - 2 * MARGIN - 46
    fitted, lines = _fitted_lines(draw, text.upper(), max_width, 1, 28, 20, True)
    content = lines[0]
    box = draw.textbbox((0, 0), content, font=fitted)
    width = min(box[2] - box[0] + 46, WIDTH - 2 * MARGIN)
    draw.rounded_rectangle((MARGIN, y, MARGIN + width, y + 58), radius=29, fill=_hex(palette["saffron"]))
    draw.text((MARGIN + 23, y + 10), content, font=fitted, fill=_hex(palette["navy"]))
    return y + 82


def _title(draw: ImageDraw.ImageDraw, text: str, palette: dict, y: int, max_lines: int = 4) -> int:
    font, lines = _fitted_lines(draw, text, WIDTH - 2 * MARGIN, max_lines, 82, 50, True)
    line_height = int(font.size * 1.14)
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=_hex(palette["white"]))
        y += line_height
    return y


def _subtitle(draw: ImageDraw.ImageDraw, text: str, palette: dict, y: int) -> int:
    font, lines = _fitted_lines(draw, text, WIDTH - 2 * MARGIN, 3, 44, 32, False)
    line_height = int(font.size * 1.35)
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=_hex(palette["muted"]))
        y += line_height
    return y


def _footer(draw: ImageDraw.ImageDraw, brand: dict, palette: dict) -> None:
    draw.line((MARGIN, HEIGHT - 170, WIDTH - MARGIN, HEIGHT - 170), fill=(*_hex(palette["white"]), 45), width=2)
    footer = "PRIVATE ASSISTANCE • VERIFY ON OFFICIAL PORTAL"
    draw.text((MARGIN, HEIGHT - 138), footer, font=_font(21, True), fill=_hex(palette["muted"]))
    draw.text((MARGIN, HEIGHT - 100), brand["service_area"], font=_font(24), fill=_hex(palette["white"]))


def _bullet_cards(draw: ImageDraw.ImageDraw, items: list[str], palette: dict, y: int) -> None:
    white = _hex(palette["white"])
    muted = _hex(palette["muted"])
    cyan = _hex(palette["cyan"])
    for number, item in enumerate(items, 1):
        height = 210
        draw.rounded_rectangle(
            (MARGIN, y, WIDTH - MARGIN, y + height), radius=34, fill=(255, 255, 255, 20), outline=(255, 255, 255, 35), width=2
        )
        draw.ellipse((MARGIN + 34, y + 58, MARGIN + 102, y + 126), fill=cyan)
        draw.text((MARGIN + 57, y + 70), str(number), anchor="mm", font=_font(31, True), fill=_hex(palette["navy"]))
        font, lines = _fitted_lines(draw, item, WIDTH - 2 * MARGIN - 170, 3, 40, 31, True)
        line_y = y + 50
        for line in lines:
            draw.text((MARGIN + 136, line_y), line, font=font, fill=white)
            line_y += int(font.size * 1.24)
        if number < len(items):
            draw.text((MARGIN + 138, y + 147), "Clear guidance • Correct upload", font=_font(22), fill=muted)
        y += height + 30


def _slide_one(post: dict, brand: dict, palette: dict) -> Image.Image:
    image = _background(palette, 1)
    draw = ImageDraw.Draw(image, "RGBA")
    _brand_header(draw, brand, palette, 1)
    y = _pill(draw, post["category"], palette, 315)
    y = _title(draw, post["hook"], palette, y + 40, 4)
    _subtitle(draw, post["title"], palette, y + 55)
    draw.rounded_rectangle((MARGIN, 1230, WIDTH - MARGIN, 1475), radius=38, fill=(255, 255, 255, 20))
    draw.text((MARGIN + 42, 1280), "SAVE THIS", font=_font(29, True), fill=_hex(palette["saffron"]))
    draw.text((MARGIN + 42, 1340), "Document help, form support\nand clear next steps.", font=_font(39, True), fill=_hex(palette["white"]), spacing=10)
    _footer(draw, brand, palette)
    return image


def _slide_list(post: dict, brand: dict, palette: dict, slide: int, heading: str, items: list[str]) -> Image.Image:
    image = _background(palette, slide)
    draw = ImageDraw.Draw(image, "RGBA")
    _brand_header(draw, brand, palette, slide)
    y = _pill(draw, post["category"], palette, 260)
    _title(draw, heading, palette, y + 20, 2)
    _bullet_cards(draw, items[:3], palette, 590)
    _footer(draw, brand, palette)
    return image


def _slide_process(post: dict, brand: dict, palette: dict) -> Image.Image:
    process = ["Send your requirement", "We check the document list", "Get form and submission assistance"]
    return _slide_list(post, brand, palette, 3, "A simple 3-step process", process)


def _slide_cta(post: dict, brand: dict, palette: dict) -> Image.Image:
    image = _background(palette, 5)
    draw = ImageDraw.Draw(image, "RGBA")
    _brand_header(draw, brand, palette, 5)
    draw.text((MARGIN, 340), "NEED HELP?", font=_font(38, True), fill=_hex(palette["saffron"]))
    y = _title(draw, f"DM “{brand['cta_keyword']}”", palette, 430, 2)
    _subtitle(draw, "Get the correct checklist before you apply.", palette, y + 28)
    draw.rounded_rectangle((MARGIN, 900, WIDTH - MARGIN, 1260), radius=44, fill=_hex(palette["cyan"]))
    draw.text((WIDTH // 2, 1002), brand["brand_name"], anchor="mm", font=_font(55, True), fill=_hex(palette["navy"]))
    draw.text((WIDTH // 2, 1090), brand["handle"], anchor="mm", font=_font(34, True), fill=_hex(palette["navy"]))
    draw.text((WIDTH // 2, 1170), brand["service_area"], anchor="mm", font=_font(27), fill=_hex(palette["navy"]))
    _footer(draw, brand, palette)
    return image


def create_frames(post: dict, brand: dict, output_dir: Path) -> list[Path]:
    palette = brand["palette"]
    output_dir.mkdir(parents=True, exist_ok=True)
    images = [
        _slide_one(post, brand, palette),
        _slide_list(post, brand, palette, 2, "How we can help", post["bullets"]),
        _slide_process(post, brand, palette),
        _slide_list(post, brand, palette, 4, "Keep these ready", post["documents"]),
        _slide_cta(post, brand, palette),
    ]
    paths: list[Path] = []
    for index, image in enumerate(images, 1):
        path = output_dir / f"frame_{index}.png"
        image.save(path, format="PNG", optimize=True)
        paths.append(path)
    images[0].save(output_dir / "cover.jpg", format="JPEG", quality=92, optimize=True)
    return paths


def create_static_post(post: dict, brand: dict, output_dir: Path) -> Path:
    palette = brand["palette"]
    navy = _hex(palette["navy"])
    blue = _hex(palette["blue"])
    white = _hex(palette["white"])
    muted = _hex(palette["muted"])
    cyan = _hex(palette["cyan"])
    saffron = _hex(palette["saffron"])
    image = Image.new("RGB", (POST_WIDTH, POST_HEIGHT), navy)
    pixels = image.load()
    for y in range(POST_HEIGHT):
        ratio = y / POST_HEIGHT
        colour = tuple(int(navy[i] * (1 - ratio * 0.68) + blue[i] * ratio * 0.68) for i in range(3))
        for x in range(POST_WIDTH):
            pixels[x, y] = colour
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((760, -210, 1260, 290), fill=(*cyan, 32))
    draw.ellipse((-230, 1060, 280, 1570), fill=(*saffron, 25))
    for offset in range(7):
        x = 900 + offset * 34
        draw.line((x, 0, x - 390, POST_HEIGHT), fill=(255, 255, 255, 9), width=2)

    # Compact brand header for a 4:5 feed post.
    draw.rounded_rectangle((MARGIN, 48, MARGIN + 64, 112), radius=19, fill=cyan)
    draw.text((MARGIN + 32, 80), "V", anchor="mm", font=_font(37, True), fill=navy)
    draw.text((MARGIN + 86, 50), brand["brand_name"], font=_font(31, True), fill=white)
    draw.text((MARGIN + 86, 88), brand["handle"], font=_font(20), fill=muted)

    category_font, category_lines = _fitted_lines(draw, post["category"].upper(), 410, 1, 24, 18, True)
    category = category_lines[0]
    category_width = min(draw.textbbox((0, 0), category, font=category_font)[2] + 40, 470)
    draw.rounded_rectangle((MARGIN, 170, MARGIN + category_width, 220), radius=25, fill=saffron)
    draw.text((MARGIN + 20, 180), category, font=category_font, fill=navy)

    hook_font, hook_lines = _fitted_lines(draw, post["hook"], POST_WIDTH - 2 * MARGIN, 3, 61, 40, True)
    y = 265
    for line in hook_lines:
        draw.text((MARGIN, y), line, font=hook_font, fill=white)
        y += int(hook_font.size * 1.12)
    topic_font, topic_lines = _fitted_lines(draw, post["title"], POST_WIDTH - 2 * MARGIN, 2, 31, 24, False)
    y += 18
    for line in topic_lines:
        draw.text((MARGIN, y), line, font=topic_font, fill=muted)
        y += int(topic_font.size * 1.20)

    cards_y = max(535, y + 34)
    for number, item in enumerate(post["bullets"][:3], 1):
        card_height = 128
        draw.rounded_rectangle(
            (MARGIN, cards_y, POST_WIDTH - MARGIN, cards_y + card_height),
            radius=28,
            fill=(255, 255, 255, 20),
            outline=(255, 255, 255, 35),
            width=2,
        )
        draw.ellipse((MARGIN + 27, cards_y + 32, MARGIN + 91, cards_y + 96), fill=cyan)
        draw.text((MARGIN + 59, cards_y + 64), str(number), anchor="mm", font=_font(27, True), fill=navy)
        item_font, item_lines = _fitted_lines(draw, item, POST_WIDTH - 2 * MARGIN - 145, 2, 31, 24, True)
        item_y = cards_y + 32
        for line in item_lines:
            draw.text((MARGIN + 121, item_y), line, font=item_font, fill=white)
            item_y += int(item_font.size * 1.18)
        cards_y += card_height + 18

    cta_top = 1030
    draw.rounded_rectangle((MARGIN, cta_top, POST_WIDTH - MARGIN, cta_top + 165), radius=35, fill=cyan)
    draw.text((MARGIN + 35, cta_top + 30), "NEED ASSISTANCE?", font=_font(23, True), fill=navy)
    draw.text(
        (MARGIN + 35, cta_top + 72),
        f"DM “{brand['cta_keyword']}” for the checklist",
        font=_font(34, True),
        fill=navy,
    )

    draw.line((MARGIN, 1250, POST_WIDTH - MARGIN, 1250), fill=(*white, 45), width=2)
    draw.text((MARGIN, 1271), "PRIVATE ASSISTANCE • VERIFY ON OFFICIAL PORTAL", font=_font(19, True), fill=muted)
    draw.text((POST_WIDTH - MARGIN, 1303), brand["service_area"], anchor="ra", font=_font(21), fill=white)
    destination = output_dir / "static-post.jpg"
    image.save(destination, format="JPEG", quality=93, optimize=True)
    return destination


def render_reel(
    post: dict, brand: dict, output_dir: Path, assets_dir: Path | None = None
) -> tuple[Path, Path, Path]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required. Install it before rendering.")
    frames = create_frames(post, brand, output_dir)
    static_post = create_static_post(post, brand, output_dir)
    custom_music = None
    if assets_dir:
        for filename in ("custom_music.mp3", "custom_music.wav", "custom_music.m4a"):
            candidate = assets_dir / filename
            if candidate.exists():
                custom_music = candidate
                break
    music = custom_music or generate_original_music(output_dir / "background_music.wav", duration=17.0)
    # The opening hook stays fully readable for 3.65 seconds before its transition.
    durations = [4.0, 2.8, 2.8, 2.8, 3.2]
    fade = 0.35
    inputs: list[str] = []
    for frame, duration in zip(frames, durations, strict=True):
        inputs.extend(["-loop", "1", "-framerate", "30", "-t", str(duration + 0.2), "-i", str(frame)])
    inputs.extend(["-i", str(music)])

    filters = []
    for i, duration in enumerate(durations):
        filters.append(
            f"[{i}:v]scale={WIDTH}:{HEIGHT},"
            "zoompan=z='min(1.0+0.00034*on,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={WIDTH}x{HEIGHT}:fps=30,trim=duration={duration},setpts=PTS-STARTPTS,"
            f"format=yuv420p,settb=AVTB[v{i}]"
        )
    previous = "v0"
    timeline = durations[0]
    transitions = ["fade", "smoothleft", "fade", "smoothup"]
    for i in range(1, len(frames)):
        output = f"x{i}"
        offset = round(timeline - fade, 2)
        filters.append(
            f"[{previous}][v{i}]xfade=transition={transitions[i - 1]}:duration={fade}:offset={offset}[{output}]"
        )
        previous = output
        timeline += durations[i] - fade
    total = sum(durations) - (len(frames) - 1) * fade
    filters.append(f"[{len(frames)}:a]volume=0.34,afade=t=out:st={total - 1.1:.2f}:d=1.1[a]")

    reel = output_dir / "reel.mp4"
    command = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{previous}]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "24",
        "-profile:v",
        "main",
        "-level",
        "4.0",
        "-tag:v",
        "avc1",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-b:a",
        "128k",
        "-t",
        f"{total:.2f}",
        "-movflags",
        "+faststart",
        str(reel),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(f"ffmpeg failed: {completed.stderr[-1600:]}")
    return reel, output_dir / "cover.jpg", static_post
