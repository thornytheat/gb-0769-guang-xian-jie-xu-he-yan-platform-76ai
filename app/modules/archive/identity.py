import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter

from app.config import SPEC, SPEC_DUAL


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rule_of(settings):
    return SPEC_DUAL if settings.get('wavelengths_nm') else SPEC


def line_of(settings, design_sha256):
    return digest(canonical(['line', settings['length_mm'], settings['zero_a_mm'],
                             settings['zero_b_mm'], design_sha256]))


def record(material, computed, started):
    sources = {key:digest(value.encode()) for key,value in material['traces'].items()}
    settings = computed['calibration']['settings']
    rule = rule_of(settings)
    identifier = digest(canonical([rule, sources, settings]))
    manifest = {'inspection_id':identifier,'rule':rule,'traces_sha256':sources,'settings':settings,
                'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'duration_ms':round(1000*(perf_counter()-started)), 'computed':computed}
    if rule == SPEC_DUAL:
        manifest['line_id'] = line_of(settings, sources['design'])
    return manifest
