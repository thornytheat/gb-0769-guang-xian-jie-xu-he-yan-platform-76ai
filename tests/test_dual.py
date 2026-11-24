import pytest

from app.input import sample


def archive(client, payload):
    return client.post('/api/inspections', json=payload)


def certificate(client, identifier):
    return client.get('/api/certificate/' + identifier).json


@pytest.fixture
def dual_line(client):
    first = archive(client, {'sample': 'dual'}).json['inspection_id']
    return first


def test_trial_pass_covers_only_dual_end_wavelength(client, dual_line):
    r = certificate(client, dual_line)
    assert r['rule'] == 'splice-2.0' and r['line_id']
    assert r['approved'] is False and r['blockers'] == ['MISSING_DUAL_END']
    assert r['wavelengths']['1310'] == {'status': 'DUAL_END_PASS', 'joints': 3, 'passed': 3, 'over_limit': 0, 'missing': 0}
    assert r['wavelengths']['1550']['status'] == 'INCOMPLETE'
    trial = r['trial_pass']
    assert trial['released'] is True and trial['suspended'] is False
    assert trial['wavelengths'] == [1310]
    assert trial['withheld'] == [{'wavelength': 1550, 'reason': 'MISSING_DUAL_END_EVIDENCE'}]


def test_missing_wavelength_is_not_marked_approved(client, dual_line):
    r = certificate(client, dual_line)
    assert r['wavelengths']['1550']['missing'] == 3
    assert 1550 not in r['trial_pass']['wavelengths']


def test_cross_wavelength_same_connector_never_pairs(client):
    r = client.post('/api/pairs', json={'sample': 'dual'}).json
    assert all(pair['a']['wavelength'] == pair['b']['wavelength'] for pair in r['pairs'])
    assert {pair['wavelength'] for pair in r['pairs']} == {1310}
    singles = {(row['id'], row['wavelength']) for row in r['singles']}
    # A-11 与 B-01 链程同为 200 m，但 1550 与 1310 不能凑成双端
    assert ('A-11', 1550) in singles and ('B-01', 1310) not in singles


def test_dual_design_preview_is_per_wavelength(client):
    r = client.post('/api/design', json={'sample': 'dual'}).json
    first = r['rows'][0]
    assert first['per_wavelength']['1310']['code'] == 'PASS'
    assert first['per_wavelength']['1550']['code'] == 'SINGLE_SIDE_ONLY'
    assert (r['passed'], r['over_limit'], r['missing']) == (0, 0, 3)


def test_late_over_limit_supplement_suspends_trial_pass(client, dual_line):
    assert certificate(client, dual_line)['trial_pass']['released'] is True
    late = archive(client, {'sample': 'dual_late'}).json['inspection_id']
    assert late != dual_line
    for identifier in (dual_line, late):
        r = certificate(client, identifier)
        assert r['trial_pass']['released'] is False and r['trial_pass']['suspended'] is True
        assert r['trial_pass']['wavelengths'] == []
        assert 'LOSS_OVER_LIMIT' in r['blockers'] and r['approved'] is False
        assert any(item.get('joint') == 'J-01' and item['wavelength'] == 1550
                   for item in r['suspension']['evidence'])


def test_formal_handover_needs_every_declared_wavelength(client, dual_line):
    assert certificate(client, dual_line)['approved'] is False
    archive(client, {'sample': 'dual_full'})
    r = certificate(client, dual_line)
    assert r['approved'] is True and r['blockers'] == []
    assert all(item['status'] == 'DUAL_END_PASS' for item in r['wavelengths'].values())
    assert r['trial_pass']['released'] is True and r['trial_pass']['wavelengths'] == [1310, 1550]


def test_unlabeled_readings_never_count_as_wavelength_evidence(client):
    material = sample('dual')
    material['traces']['a'] = 'event,distance,unit,loss_db\nA-01,200,m,0.10\nA-02,500,m,0.12\nA-03,800,m,0.09\n'
    identifier = archive(client, material).json['inspection_id']
    r = certificate(client, identifier)
    assert r['trial_pass']['released'] is False
    assert r['wavelengths']['1310']['status'] == 'INCOMPLETE'
    assert r['unlabeled_readings'] == 3


def test_legacy_archive_same_line_does_not_feed_dual_line(client, dual_line):
    legacy = sample('dual')
    legacy['traces']['a'] = legacy['traces']['a'].replace(',wavelength', '').replace(',1310', '').replace(',1550', '')
    legacy['traces']['b'] = 'event,distance,unit,loss_db\nB-01,800,m,0.08\nB-02,500,m,0.10\nB-03,200,m,0.11\nB-11,800,m,0.14\nB-12,500,m,0.15\nB-13,200,m,0.12\n'
    del legacy['settings']['wavelengths_nm']
    old = archive(client, legacy).json
    assert old['record']['rule'] == 'splice-1.0'
    assert certificate(client, old['inspection_id'])['approved'] is True  # 原签发件仍可核验
    r = certificate(client, dual_line)
    assert r['evidence_records'] == [dual_line]
    assert r['wavelengths']['1550']['status'] == 'INCOMPLETE'


def test_labeled_traces_require_declaration(client):
    material = sample('dual')
    del material['settings']['wavelengths_nm']
    r = archive(client, material)
    assert (r.status_code, r.json['code']) == (422, 'WAVELENGTH_UNDECLARED')


@pytest.mark.parametrize('declared', ['1310,abc', '1310,9000', '1310,'])
def test_bad_wavelength_declaration_rejected(client, declared):
    material = sample('dual')
    material['settings']['wavelengths_nm'] = declared
    r = archive(client, material)
    assert (r.status_code, r.json['code']) == (422, 'BAD_SETTING')


def test_empty_declaration_falls_back_to_legacy_and_rejects_labels(client):
    material = sample('dual')
    material['settings']['wavelengths_nm'] = ''
    r = archive(client, material)
    assert (r.status_code, r.json['code']) == (422, 'WAVELENGTH_UNDECLARED')


def test_undeclared_wavelength_rows_are_isolated(client):
    material = sample('dual')
    material['traces']['b'] += 'B-99,100,m,0.10,1625\n'
    r = client.post('/api/calibration', json=material).json
    assert [(row['id'], row['code']) for row in r['outliers']] == [('B-99', 'WAVELENGTH_UNDECLARED')]


def test_bad_wavelength_value_is_isolated(client):
    material = sample('dual')
    material['traces']['a'] += 'A-99,100,m,0.10,9000\n'
    r = client.post('/api/trace', json=material).json
    assert any(row['code'] == 'BAD_WAVELENGTH' and row['line'] == 8 for row in r['isolated'])


def test_same_event_id_at_distinct_wavelengths_is_not_a_conflict(client):
    material = sample('dual')
    material['traces']['a'] = 'event,distance,unit,loss_db,wavelength\nA-01,200,m,0.10,1310\nA-01,200,m,0.11,1550\n'
    r = client.post('/api/trace', json=material).json
    assert sorted((row['id'], row['wavelength']) for row in r['traces']['a']) == [('A-01', 1310), ('A-01', 1550)]
    assert r['reason_counts'] == {}


def test_conflicting_supplement_withdrawn_but_over_limit_stays(client, dual_line):
    late = archive(client, {'sample': 'dual_late'}).json['inspection_id']   # B-11 @1550 = 0.35 → J-01 超限
    full = archive(client, {'sample': 'dual_full'}).json['inspection_id']   # B-11 @1550 = 0.14 → 与上一记录冲突
    r = certificate(client, dual_line)
    conflict, = r['conflicts']
    assert (conflict['source'], conflict['id'], conflict['wavelength']) == ('b', 'B-11', 1550)
    assert conflict['records'] == sorted([late, full])
    assert 'CONFLICTING_SUPPLEMENT' in r['blockers'] and r['approved'] is False
    # 已归档的超限证据不随冲突撤出：试通件保持停止放行
    assert r['trial_pass']['suspended'] is True and r['trial_pass']['released'] is False
    assert any(item.get('joint') == 'J-01' and item['wavelength'] == 1550 for item in r['suspension']['evidence'])


def test_certificate_page_shows_trial_pass_and_suspension(client, dual_line):
    page = client.get('/inspect/certificate?inspection=' + dual_line)
    assert '试通件 · 放行 · 覆盖波长 1310 nm'.encode() in page.data
    assert '正式交工 · 待处置'.encode() in page.data
    archive(client, {'sample': 'dual_late'})
    page = client.get('/inspect/certificate?inspection=' + dual_line)
    assert '试通件 · 停止放行'.encode() in page.data


def test_export_carries_trial_pass(client, dual_line):
    pack = client.get('/api/export/' + dual_line).json
    assert pack['trial_pass']['wavelengths'] == [1310] and pack['line_id']
