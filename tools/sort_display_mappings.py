import json
from collections import OrderedDict
from pathlib import Path


def main() -> None:
    p = Path(__file__).resolve().parents[1] / 'mappings' / 'display_mappings.json'
    with p.open('r', encoding='utf-8') as f:
        data = json.load(f)

    # Deduplicate by base (category:cleanName), keeping the last occurrence
    base_to_full = {}
    full_to_value = {}
    for full_key, val in data.items():
        if ':' in full_key:
            cat, rest = full_key.split(':', 1)
        else:
            cat, rest = '', full_key
        clean = rest.split('#', 1)[0]
        base = f'{cat}:{clean}'
        base_to_full[base] = full_key
        full_to_value[full_key] = val

    # Sort by base key (category then clean name)
    sorted_bases = sorted(base_to_full.keys(), key=lambda s: (s.split(':', 1)[0], s.split(':', 1)[1]))

    out = OrderedDict()
    for base in sorted_bases:
        fk = base_to_full[base]
        out[fk] = full_to_value[fk]

    with p.open('w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()


