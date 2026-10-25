"""Validate complete graph counts before reuse or report generation."""
import json
import math


def is_complete_count(record, expected_commodities=None):
    if not isinstance(record, dict) or record.get('status') != 'complete':
        return False
    rows = record.get('records')
    if not isinstance(rows, list) or not rows:
        return False
    if any(not isinstance(row, dict) or type(row.get('k')) is not int for row in rows):
        return False
    count = len(rows) if expected_commodities is None else expected_commodities
    if len(rows) != count or {row.get('k') for row in rows} != set(range(count)):
        return False
    if any(row.get('status') != 'complete' for row in rows):
        return False
    for key in ('states', 'transport', 'sink'):
        if any(type(row.get(key)) is not int or row[key] < 0 for row in rows):
            return False
        if type(record.get(key)) is not int or record[key] != sum(row[key] for row in rows):
            return False
    for key in ('full_states', 'full_transport', 'full_sink',
                'bound_states', 'bound_transport', 'bound_sink'):
        if type(record.get(key)) is not int or record[key] < 0:
            return False
    seconds = record.get('count_seconds')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        return False
    return True


def read_complete_count(path, expected_commodities=None):
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and is_complete_count(record, expected_commodities) else None
