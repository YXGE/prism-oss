"""Generate Prism's PNG PWA icons from simple vector-like Pillow shapes."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "icons"


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    scale = size / 512
    image = Image.new("RGB", (size, size), "#b96f52")
    draw = ImageDraw.Draw(image)
    radius = int((0 if maskable else 118) * scale)
    if radius:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill="#b96f52")

    def points(values):
        return [(int(x * scale), int(y * scale)) for x, y in values]

    inset = 22 if maskable else 0
    if inset:
        # Keep the whole mark inside Android's maskable safe zone.
        mark_scale = 0.82
        origin = 46

        def remap(values):
            return [(origin + x * mark_scale, origin + y * mark_scale) for x, y in values]
    else:
        remap = lambda values: values

    draw.polygon(points(remap([(256, 92), (407, 181), (360, 390), (152, 390), (105, 181)])), fill="#f7f2e9")
    draw.polygon(points(remap([(256, 92), (360, 390), (256, 307), (152, 390)])), fill="#ded6ca")
    draw.polygon(points(remap([(256, 92), (407, 181), (256, 307), (105, 181)])), fill="#fffaf2")
    draw.polygon(points(remap([(256, 149), (341, 199), (256, 270), (171, 199)])), fill="#2a2724")
    cx, cy = remap([(256, 199)])[0]
    cx *= scale
    cy *= scale
    r = 18 * scale * (0.82 if maskable else 1)
    draw.ellipse((int(cx - r), int(cy - r), int(cx + r), int(cy + r)), fill="#b96f52")
    return image.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_icon(192).save(OUT / "prism-192.png", optimize=True)
    make_icon(512).save(OUT / "prism-512.png", optimize=True)
    make_icon(512, maskable=True).save(OUT / "prism-maskable-512.png", optimize=True)


if __name__ == "__main__":
    main()
