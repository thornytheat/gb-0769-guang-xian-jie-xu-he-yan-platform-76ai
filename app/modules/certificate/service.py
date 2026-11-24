from app.config import SPEC_DUAL
from app.modules.archive.identity import canonical, digest
from app.modules.archive.storage import for_line, get
from .line import line_state

SCOPE_NOTICE = '本试通件仅覆盖所列波长的双端达标证据；未列波长未经验收，不视为合格。'


def certify(record, line_records=None):
    if record['rule'] != SPEC_DUAL:
        stages = record['computed']
        design = stages['design']
        blockers = []
        if design['missing']:
            blockers.append('MISSING_JOINTS')
        if design['over_limit']:
            blockers.append('LOSS_OVER_LIMIT')
        if not design['design_count']:
            blockers.append('EMPTY_DESIGN')
        if any(line['source'] == 'design' and line['code'] != 'DUPLICATE_EVENT' for line in stages['trace']['isolated']):
            blockers.append('UNVERIFIED_DESIGN_ROWS')
        return {'inspection_id':record['inspection_id'], 'approved': not blockers,
                'blockers':blockers, 'integrity_sha256':digest(canonical(record)), 'record':record}
    return certify_dual(record, line_records or [record])


def certify_stored(database, identifier):
    record = get(database, identifier)
    if record['rule'] != SPEC_DUAL:
        return certify(record)
    return certify(record, for_line(database, record['line_id']))


def certify_dual(record, records):
    state = line_state(records)
    declared = state['declared']
    status = state['wavelengths']
    suspension = state['suspension']
    design = state['design']
    latest = state['latest']

    blockers = []
    if design['design_count'] and any(item['status'] != 'DUAL_END_PASS' for item in status.values()):
        blockers.append('MISSING_DUAL_END')
    if suspension:
        blockers.append('LOSS_OVER_LIMIT')
    if state['conflicts']:
        blockers.append('CONFLICTING_SUPPLEMENT')
    if not design['design_count']:
        blockers.append('EMPTY_DESIGN')
    if any(line['source'] == 'design' and line['code'] != 'DUPLICATE_EVENT'
           for line in latest['computed']['trace']['isolated']):
        blockers.append('UNVERIFIED_DESIGN_ROWS')

    covered = [wl for wl in declared if status[str(wl)]['status'] == 'DUAL_END_PASS']
    withheld = [{'wavelength': wl, 'reason': 'OVER_LIMIT' if status[str(wl)]['status'] == 'OVER_LIMIT'
                 else 'MISSING_DUAL_END_EVIDENCE'}
                for wl in declared if status[str(wl)]['status'] != 'DUAL_END_PASS']
    released = not suspension and bool(covered)
    trial_pass = {'released': released, 'suspended': bool(suspension),
                  'wavelengths': covered if released else [], 'withheld': withheld,
                  'scope': SCOPE_NOTICE,
                  'conditions': ['正式交工须全部声明波长（' + '、'.join(f'{wl} nm' for wl in declared) + '）均有双端达标证据',
                                 '补测记录一旦证实任一波长超限，本件即停止放行']}
    return {'inspection_id':record['inspection_id'], 'rule':record['rule'], 'line_id':record['line_id'],
            'approved': not blockers, 'blockers':blockers, 'wavelengths':status, 'trial_pass':trial_pass,
            'suspension':{'active':bool(suspension), 'evidence':suspension},
            'conflicts':state['conflicts'], 'unlabeled_readings':state['unlabeled_readings'],
            'evidence_records':[rec['inspection_id'] for rec in records],
            'integrity_sha256':digest(canonical(record)), 'record':record}
