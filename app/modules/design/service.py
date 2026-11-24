from app.modules.loss.verdict import verdict
from app.modules.pairs.optimal import best_pairs


def reconcile(calibrated, joined, loss):
    declared = calibrated['settings'].get('wavelengths_nm')
    if declared:
        return reconcile_wavelengths(calibrated, joined, loss, declared)
    points, measurements = calibrated['aligned']['design'], loss['rows']
    tolerance = calibrated['settings']['design_tol_mm']
    valid = [row for row in points if not row.get('code')]
    links = best_pairs([r['chain_mm']*2 for r in valid], [r['midpoint_half_mm'] for r in measurements], tolerance*2)
    mapped = {valid[i]['id']: measurements[j] for i,j in links}
    used = {j for _,j in links}
    rows = []
    for point in points:
        pair = mapped.get(point['id'])
        near_singles = [dict(id=r['id'], source=r['source'], line=r['line']) for r in joined['singles']
                        if abs(r['chain_mm']-point['chain_mm']) <= tolerance and not point.get('code')]
        if not pair:
            code = point.get('code') or ('SINGLE_SIDE_ONLY' if near_singles else 'NO_COUPLED_EVIDENCE')
        else:
            code = verdict(pair['net_double_mdb'], point['limit_mdb'])
        bucket = {'PASS':'passed','OVER_LIMIT':'over_limit'}.get(code,'missing')
        rows.append({'joint': point['id'], 'chain_mm': point['chain_mm'], 'design_line': point['line'],
                     'limit_mdb': point['limit_mdb'], 'pair': pair['pair'] if pair else None,
                     'net_db': pair['net_db'] if pair else None, 'code':code,'bucket':bucket, 'near_singles': near_singles,
                     'a_line': pair['a']['line'] if pair else None, 'b_line': pair['b']['line'] if pair else None,
                     'gain_ends': pair['gain_ends'] if pair else []})
    totals = {key: sum(r['bucket'] == key for r in rows) for key in ('passed','over_limit','missing')}
    orphans = [r for i,r in enumerate(measurements) if i not in used]
    measured = len(calibrated['aligned']['a']) + len(calibrated['aligned']['b'])
    return {'design_count':len(points), **totals, 'balanced':len(points)==sum(totals.values()), 'rows':rows,
            'orphans':orphans, 'orphan_pairs':len(orphans), 'singles': joined['singles'], 'single_count':joined['single_count'],
            'measurements':measured, 'measurements_balanced': measured == 2*(len(mapped)+len(orphans))+joined['single_count']}


def reconcile_wavelengths(calibrated, joined, loss, declared):
    """每个设计接头按声明波长分别对账：同波长双端读数才算证据。"""
    points, measurements = calibrated['aligned']['design'], loss['rows']
    tolerance = calibrated['settings']['design_tol_mm']
    valid = [row for row in points if not row.get('code')]
    valid_chains = [row['chain_mm']*2 for row in valid]
    mapped, used = {}, set()
    for wl in declared:
        indices = [k for k, row in enumerate(measurements) if row.get('wavelength') == wl]
        links = best_pairs(valid_chains, [measurements[k]['midpoint_half_mm'] for k in indices], tolerance*2)
        for i, j in links:
            mapped[(valid[i]['id'], wl)] = measurements[indices[j]]
            used.add(indices[j])
    rows = []
    for point in points:
        per = {}
        for wl in declared:
            pair = mapped.get((point['id'], wl))
            near = [dict(id=r['id'], source=r['source'], line=r['line']) for r in joined['singles']
                    if r.get('wavelength') == wl and abs(r['chain_mm']-point['chain_mm']) <= tolerance
                    and not point.get('code')]
            if not pair:
                code = point.get('code') or ('SINGLE_SIDE_ONLY' if near else 'NO_COUPLED_EVIDENCE')
                per[str(wl)] = {'code': code, 'pair': None, 'net_db': None, 'a_line': None, 'b_line': None,
                                'gain_ends': [], 'near_singles': near}
            else:
                code = verdict(pair['net_double_mdb'], point['limit_mdb'])
                per[str(wl)] = {'code': code, 'pair': pair['pair'], 'net_db': pair['net_db'],
                                'a_line': pair['a']['line'], 'b_line': pair['b']['line'],
                                'gain_ends': pair['gain_ends'], 'near_singles': near}
        codes = [per[str(wl)]['code'] for wl in declared]
        overall = point.get('code') or next((code for code in
                    ('OVER_LIMIT','INVALID_NET_GAIN','SINGLE_SIDE_ONLY','NO_COUPLED_EVIDENCE') if code in codes), 'PASS')
        bucket = {'PASS':'passed','OVER_LIMIT':'over_limit'}.get(overall,'missing')
        rows.append({'joint': point['id'], 'chain_mm': point['chain_mm'], 'design_line': point['line'],
                     'limit_mdb': point['limit_mdb'], 'code': overall, 'bucket': bucket, 'per_wavelength': per})
    totals = {key: sum(r['bucket'] == key for r in rows) for key in ('passed','over_limit','missing')}
    orphans = [r for k, r in enumerate(measurements) if k not in used]
    measured = len(calibrated['aligned']['a']) + len(calibrated['aligned']['b'])
    return {'design_count':len(points), **totals, 'balanced':len(points)==sum(totals.values()), 'rows':rows,
            'orphans':orphans, 'orphan_pairs':len(orphans), 'singles': joined['singles'], 'single_count':joined['single_count'],
            'measurements':measured, 'wavelengths': declared,
            'measurements_balanced': measured == 2*(len(mapped)+len(orphans))+joined['single_count']}
