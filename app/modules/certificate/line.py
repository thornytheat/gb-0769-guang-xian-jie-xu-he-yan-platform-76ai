"""线路级证据池：同一物理线路的多次归档（含晚到补测）合并重算。

pooling 只归并带波长标签的归一化读数；未标波长的旧读数留在无标签组，
不作任何波长的双端凭据。同一事件同一波长的冲突补测整组撤出并留痕。

超限证据按归档顺序逐前缀评估：任一历史前缀的证据池证实任一波长超限，
即留痕停放行；后续冲突把读数撤出当前池，也不能抹去已证实的超限。
"""
from app.modules.calibration.service import calibrate
from app.modules.design.service import reconcile
from app.modules.loss.service import judge
from app.modules.loss.verdict import verdict
from app.modules.pairs.service import join


def pooled_rows(records):
    seen = {}
    for rec in records:
        for side in ('a', 'b'):
            for row in rec['computed']['trace']['traces'][side]:
                key = (side, row['id'], row.get('wavelength'))
                seen.setdefault(key, []).append((row, rec['inspection_id']))
    rows, conflicts = {'a': [], 'b': []}, []
    for (side, event, wl), entries in sorted(seen.items(), key=lambda item: (item[0][0], item[0][1], item[0][2] is None, item[0][2] or 0)):
        distinct = {(row['mm'], row['loss_mdb']) for row, _ in entries}
        if len(distinct) > 1:
            conflicts.append({'source': side, 'id': event, 'wavelength': wl,
                              'records': sorted({identifier for _, identifier in entries})})
            continue
        rows[side].append(entries[0][0])
    return rows, conflicts


def evaluate(rows, design_rows, settings):
    traces = {'a': rows['a'], 'b': rows['b'], 'design': design_rows}
    calibrated = calibrate(traces, settings)
    joined = join(calibrated)
    loss = judge(joined, settings)
    return reconcile(calibrated, joined, loss)


def wavelength_status(design, declared):
    status = {}
    for wl in declared:
        cells = [row['per_wavelength'][str(wl)] for row in design['rows']]
        passed = sum(cell['code'] == 'PASS' for cell in cells)
        over = sum(cell['code'] == 'OVER_LIMIT' for cell in cells)
        missing = len(cells) - passed - over
        if not cells:
            state = 'NO_DESIGN'
        elif over:
            state = 'OVER_LIMIT'
        elif missing:
            state = 'INCOMPLETE'
        else:
            state = 'DUAL_END_PASS'
        status[str(wl)] = {'status': state, 'joints': len(cells), 'passed': passed,
                           'over_limit': over, 'missing': missing}
    return status


def over_limit_evidence(design, declared, reference_mdb):
    """任一前缀证据池中，任一波长被双端证据证实超限的证据。"""
    found = []
    for row in design['rows']:
        for wl, cell in row['per_wavelength'].items():
            if cell['code'] == 'OVER_LIMIT':
                found.append(('joint', row['joint'], int(wl), cell['net_db']))
    for orphan in design['orphans']:
        wl = orphan.get('wavelength')
        if wl in declared and verdict(orphan['net_double_mdb'], reference_mdb) == 'OVER_LIMIT':
            found.append(('pair', orphan['pair'], wl, orphan['net_db']))
    return found


def line_state(records):
    latest = records[-1]
    settings = latest['settings']
    declared = settings['wavelengths_nm']
    suspension, seen = [], set()
    for k in range(1, len(records) + 1):
        prefix_settings = records[k - 1]['settings']
        rows, _ = pooled_rows(records[:k])
        design_k = evaluate(rows, records[k - 1]['computed']['trace']['traces']['design'], prefix_settings)
        origin = 'record:' + records[k - 1]['inspection_id'][:12]
        for kind, key, wl, net_db in over_limit_evidence(design_k, prefix_settings['wavelengths_nm'],
                                                         prefix_settings['reference_limit_mdb']):
            if (kind, key, wl) not in seen:
                seen.add((kind, key, wl))
                suspension.append({kind: key, 'wavelength': wl, 'net_db': net_db, 'origin': origin})
    rows, conflicts = pooled_rows(records)
    design = evaluate(rows, latest['computed']['trace']['traces']['design'], settings)
    return {'settings': settings, 'declared': declared, 'design': design, 'latest': latest,
            'wavelengths': wavelength_status(design, declared),
            'suspension': suspension,
            'conflicts': conflicts,
            'unlabeled_readings': sum(1 for side in ('a', 'b') for row in rows[side] if row.get('wavelength') is None)}
