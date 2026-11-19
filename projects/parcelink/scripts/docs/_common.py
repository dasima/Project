"""Shared output and Chinese font options for the standalone generators."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class GeneratorContext:
    project_root: Path
    output_root: Path
    font_path: Path
    font_family: str

    def asset(self, relative_path: str) -> Path:
        """Prefer freshly generated figures, then checked-in project figures."""
        generated = self.output_root / relative_path
        return generated if generated.is_file() else self.project_root / relative_path


def _find_chinese_font() -> Path | None:
    candidates = [
        Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
        Path('/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf'),
        Path('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'),
        Path('/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf'),
        Path('/System/Library/Fonts/PingFang.ttc'),
        Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf'),
        Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # Fontconfig covers distribution-specific font locations. Check language
    # coverage because fc-match may otherwise silently return a Latin font.
    if shutil.which('fc-match'):
        try:
            result = subprocess.run(
                ['fc-match', '-f', '%{file}\n%{lang}\n', 'sans-serif:lang=zh-cn'],
                check=True, capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.splitlines()
            if len(lines) >= 2 and 'zh-cn' in lines[1].split('|'):
                candidate = Path(lines[0])
                if candidate.is_file():
                    return candidate
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def generator_context(project_root: Path, description: str) -> GeneratorContext:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        '--output-root', type=Path,
        default=Path(os.environ.get('DOCS_OUTPUT_ROOT', project_root / 'build/docs')),
        help='Root for docs/, assets/ and qa/ output (default: project/build/docs).',
    )
    parser.add_argument(
        '--font', type=Path, default=os.environ.get('DOCS_FONT_PATH'),
        help='Chinese .ttf/.otf/.ttc font file (or DOCS_FONT_PATH).',
    )
    parser.add_argument(
        '--font-family', default=os.environ.get('DOCS_FONT_FAMILY'),
        help='Word/SVG font family; defaults to the selected font file family.',
    )
    args = parser.parse_args()
    font_path = args.font.expanduser().resolve() if args.font else _find_chinese_font()
    if font_path is None or not font_path.is_file():
        parser.error('No Chinese font found. Install Noto Sans CJK SC or set '
                     '--font / DOCS_FONT_PATH to a Chinese font file.')
    from PIL import ImageFont
    try:
        family = ImageFont.truetype(str(font_path), 12).getname()[0]
    except OSError as exc:
        parser.error(f'Cannot read font {font_path}: {exc}')
    return GeneratorContext(
        project_root=project_root,
        output_root=args.output_root.expanduser().resolve(),
        font_path=font_path,
        font_family=args.font_family or family,
    )
