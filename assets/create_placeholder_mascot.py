"""
Run this once to generate a placeholder chip_happy.png for testing.
Replace assets/chip_happy.png with your real mascot artwork.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

SIZE = (160, 160)
GREEN = (0, 217, 111)
DARK  = (20, 20, 30)

img  = Image.new("RGBA", SIZE, (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Robot head
draw.rounded_rectangle([(20, 30), (140, 130)], radius=18, fill=GREEN)
# Eyes
draw.ellipse([(45, 55), (70, 80)],  fill=DARK)
draw.ellipse([(90, 55), (115, 80)], fill=DARK)
draw.ellipse([(51, 61), (64, 74)],  fill=(255, 255, 255))
draw.ellipse([(96, 61), (109, 74)], fill=(255, 255, 255))
# Smile
draw.arc([(50, 88), (110, 118)], start=10, end=170, fill=DARK, width=4)
# Antenna
draw.line([(80, 30), (80, 10)], fill=DARK, width=4)
draw.ellipse([(72, 2), (88, 18)], fill=(0, 153, 255))
# Ears
draw.rectangle([(10, 60), (22, 90)], fill=DARK)
draw.rectangle([(138, 60), (150, 90)], fill=DARK)

out = Path(__file__).parent / "chip_happy.png"
img.save(out)
print(f"Saved placeholder mascot → {out}")
