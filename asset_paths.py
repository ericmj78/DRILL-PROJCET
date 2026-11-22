"""기존 코드의 이미지 이름을 실제 한국어 파일 이름으로 연결한다."""
import json
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parent / 'assets'
NAME_MAP = json.loads((ASSET_ROOT / '이미지_이름_대조표.json').read_text(encoding='utf-8'))


def asset_path(name):
    relative = Path(name).as_posix()
    return ASSET_ROOT / NAME_MAP.get(relative, relative)
