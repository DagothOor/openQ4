"""Rebuild the openQ4 TrueType font set from the retail Quake 4 bitmap fonts.

Usage:
    python build_openq4_fonts.py --source <dir with *_48.fontdat/*.tga>
                                 --donors <dir with Noto*-var.ttf>
                                 --output <dir for the .ttf files>
                                 [--faces chain,marine,...]

The source directory is populated by ``extract_source_fonts.py``, which pulls
``fonts/english/*`` out of the installed Quake 4 pk4 archives.
"""
from __future__ import annotations

import argparse
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from q4font.build import FaceBuilder, FaceSpec
from q4font.charset import unicode_ranges
from q4font.trace import TraceOptions

VERSION = "1.100"

# Every retail atlas fills the bullet's slot with a solid, cap-high missing-glyph
# box, so the bullet is rebuilt from the face's own middle dot.
BULLET = 0x2022


def _accented(low: int, high: int) -> tuple[int, ...]:
	"""The Latin-1 letters in a range that carry an accent (not AE, eth or thorn)."""
	return tuple(
		cp for cp in range(low, high)
		if unicodedata.decomposition(chr(cp)) and not unicodedata.decomposition(chr(cp)).startswith("<")
	)


# ProFont's 48 point atlas had no room above a capital, and the console's 16
# pixel cells none above any letter, so Raven ran the accents into the letters
# and, on the console, shortened the letters under them. Those are recomposed
# from the face's own letters and accents.
ACCENTED_CAPITALS = _accented(0xC0, 0xDF)
ACCENTED_LETTERS = ACCENTED_CAPITALS + _accented(0xE0, 0x100)

FACES: dict[str, FaceSpec] = {
	"chain": FaceSpec(
		source="chain",
		family="openQ4 Chain",
		description="Wide squarish techno sans used across the Quake 4 menus and HUD.",
		rebuild=(BULLET,),
	),
	"lowpixel": FaceSpec(
		source="lowpixel",
		family="openQ4 LowPixel",
		description="Neo-grotesque companion face used for dense HUD readouts.",
		rebuild=(BULLET,),
	),
	"marine": FaceSpec(
		source="marine",
		family="openQ4 Marine",
		all_caps=True,
		description="All-caps military stencil face used for radio and objective text.",
		# Its sharp s slot holds a B; as a small capital it is written SS.
		rebuild=(BULLET, 0x00DF),
	),
	"profont": FaceSpec(
		source="profont",
		family="openQ4 ProFont",
		description="Rounded technical face used for terminals and readouts.",
		# The copyright, registered and percent signs were cut off at the left
		# when Raven rendered the atlas, so the traced shapes are broken.
		rebuild=(BULLET, 0x00A9, 0x00AE, 0x0025) + ACCENTED_CAPITALS,
	),
	"r_strogg": FaceSpec(
		source="r_strogg",
		family="openQ4 Roman Strogg",
		all_caps=True,
		description="Angular oblique Strogg-Roman face used for Strogg interfaces.",
		rebuild=(BULLET, 0x00DF),
	),
	"bigchars": FaceSpec(
		source="bigchars",
		family="openQ4 BigChars",
		grid_atlas="bigchars.tga",
		description="Console and loading-screen face, traced from the fixed-cell bigchars sheet.",
		rebuild=ACCENTED_LETTERS,
		# The sheet slips around 0xDD: Y-acute's cell draws the sharp s, and
		# the thorn and sharp s cells hold stray copies of a-grave and a-acute.
		cell_remap=((0xDD, 0x00DF), (0xDE, None), (0xDF, None)),
		marks_from_spacing=True,
	),
	"strogg": FaceSpec(
		source="strogg",
		family="openQ4 Strogg",
		extended=False,
		all_caps=True,
		description="Strogg rune face. Latin letters map to runes; other scripts are intentionally absent.",
	),
}


def composable_codepoints(second_pass: bool = False) -> list[int]:
	"""Everything worth attempting as base + mark, in a stable order."""
	ranges = unicode_ranges()
	blocks = ("greek", "cyrillic", "cyrillic_supp") if second_pass else ("latin_ext_a", "latin_ext_b", "latin_ext_add")
	# Latin-1 first: its letters are traced, except where a face rebuilds them.
	wanted: list[int] = [] if second_pass else list(range(0x00C0, 0x0100))
	for block in blocks:
		low, high = ranges[block]
		wanted.extend(range(low, high + 1))
	return wanted


def build_face(key: str, spec: FaceSpec, source: Path, donors: Path, output: Path) -> dict:
	started = time.perf_counter()
	builder = FaceBuilder(spec, source, donors, TraceOptions())

	builder.trace_source()
	metrics = builder.measure()
	builder.extract_marks(metrics)
	builder.extend_marks(metrics)
	# Dotless i must exist before composing, so i-acute and friends are built
	# on it rather than stacking the accent on the dot.
	builder.synthesize_letters(metrics)
	builder.compose(composable_codepoints())
	builder.alias_homoglyphs()
	# Accented Cyrillic whose base is a shared Latin shape (Yo, for instance)
	# is composed here so it uses the authentic letter rather than the donor's.
	# Anything whose base is donor-only is left for the donor, which keeps the
	# accent consistent with the letter underneath it.
	builder.compose(composable_codepoints(second_pass=True))
	builder.synthesize_latin1(metrics)
	builder.synthesize_shapes(metrics)
	builder.import_donors(metrics)
	builder.fit_to_cell(metrics)
	builder.force_monospace()
	builder.fold_to_base()

	destination = output / f"{key}.ttf"
	builder.emit(destination, metrics, VERSION)

	elapsed = time.perf_counter() - started
	report = dict(builder.report)
	report.update(
		{
			"file": destination.name,
			"glyphs": len(builder.glyphs),
			"mapped": len(builder.cmap),
			"cap": metrics.cap_height,
			"xheight": metrics.x_height,
			"ascender": metrics.ascender,
			"descender": metrics.descender,
			"seconds": round(elapsed, 1),
			"bytes": destination.stat().st_size,
		}
	)
	return report


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--source", required=True, type=Path)
	parser.add_argument("--donors", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--faces", default="")
	arguments = parser.parse_args()

	keys = [k.strip() for k in arguments.faces.split(",") if k.strip()] or list(FACES)
	unknown = [k for k in keys if k not in FACES]
	if unknown:
		parser.error(f"unknown face(s): {', '.join(unknown)}")

	arguments.output.mkdir(parents=True, exist_ok=True)
	for key in keys:
		report = build_face(key, FACES[key], arguments.source, arguments.donors, arguments.output)
		summary = " ".join(f"{name}={value}" for name, value in report.items())
		print(f"{key:9s} {summary}", flush=True)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
