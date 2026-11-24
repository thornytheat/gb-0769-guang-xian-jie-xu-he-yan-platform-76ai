from bisect import bisect_left, bisect_right

from .optimal import best_pairs


def join(calibrated):
    a, b = [calibrated['aligned'][key] for key in ('a','b')]
    settings = calibrated['settings']
    tolerance = settings['pair_tol_mm']
    declared = settings.get('wavelengths_nm')
    if declared:
        order = {nm: index for index, nm in enumerate(declared)}
        groups = sorted({row.get('wavelength') for row in a + b},
                        key=lambda wl: (wl is None, order.get(wl, len(order))))
    else:
        groups = [None]
    pairs, singles = [], []
    for wl in groups:
        left_rows = [row for row in a if row.get('wavelength') == wl] if declared else a
        right_rows = [row for row in b if row.get('wavelength') == wl] if declared else b
        left = [row['chain_mm'] for row in left_rows]
        right = [row['chain_mm'] for row in right_rows]
        indices = best_pairs(left, right, tolerance)
        used_a, used_b = set(), set()
        for i, j in indices:
            used_a.add(i)
            used_b.add(j)
            x, y = left[i], right[j]
            candidates = right_rows[bisect_left(right, x-tolerance):bisect_right(right, x+tolerance)]
            pair = {'pair': f'P{len(pairs)+1:03d}', 'a': left_rows[i], 'b': right_rows[j], 'span_mm': abs(x-y),
                    'midpoint_half_mm': x+y, 'possible_b': [r['id'] for r in candidates]}
            if declared:
                pair['wavelength'] = wl
            pairs.append(pair)
        for rows, other, used, opposite in ((left_rows,right,used_a,'B'),(right_rows,left,used_b,'A')):
            for i, row in enumerate(rows):
                if i not in used:
                    x = row['chain_mm']
                    competing = bisect_left(other, x-tolerance) < bisect_right(other, x+tolerance)
                    singles.append({**row, 'code': 'PAIR_COMPETITION' if competing else f'NO_{opposite}_NEARBY'})
    result = {'pairs': pairs, 'singles': singles, 'pair_count': len(pairs), 'single_count': len(singles),
              'total_span_mm': sum(r['span_mm'] for r in pairs), 'balanced': len(a)+len(b) == 2*len(pairs)+len(singles)}
    if declared:
        result['wavelengths'] = declared
    return result
