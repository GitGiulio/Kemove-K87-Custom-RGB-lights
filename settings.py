"""Validated, thread-safe live previews and atomic settings persistence."""
from copy import deepcopy
import json
import math
from pathlib import Path
import threading

FPS_STEPS = [0.125, 0.25, 0.5] + list(range(1, 31))
ROOT = Path(__file__).resolve().parent


def defaults():
    return dict(brightness=.35, fps=10, smoothing=.08, mode='spatial',
                press_enabled=False, press_color=[255, 255, 255], exceptions={})


def validate(value):
    result = defaults()
    result.update(deepcopy(value))
    for name, low, high in [('brightness', 0, 1), ('fps', .125, 30), ('smoothing', 0, 2)]:
        v = result[name]
        if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError(f'Invalid {name}: expected {low} to {high}')
    if result['mode'] not in ('spatial', 'average') or type(result['press_enabled']) is not bool:
        raise ValueError('Invalid lighting mode')
    def color(rgb):
        if not isinstance(rgb, (list, tuple)) or len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb):
            raise ValueError('Invalid RGB color')
    color(result['press_color'])
    valid_keys = {str(k['index']) for k in json.loads((ROOT / 'k87-layout.json').read_text(encoding='utf-8'))}
    if not isinstance(result['exceptions'], dict):
        raise ValueError('Invalid key exceptions')
    for index, rule in result['exceptions'].items():
        if index not in valid_keys or not isinstance(rule, dict) or rule.get('mode') not in ('screen', 'fixed', 'off'):
            raise ValueError('Invalid key exception')
        color(rule.get('color'))
    return result


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / 'settings.json'
        raw = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        self.saved = validate(raw)
        self.current = deepcopy(self.saved)
        self.lock = threading.Lock()

    def get(self):
        with self.lock:
            return deepcopy(self.current)

    def preview(self, value):
        value = validate(value)
        with self.lock:
            self.current = value

    def save(self):
        with self.lock:
            temporary = self.path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(self.current, indent=2) + '\n', encoding='utf-8')
            temporary.replace(self.path)
            self.saved = deepcopy(self.current)

    def cancel(self):
        with self.lock:
            self.current = deepcopy(self.saved)
