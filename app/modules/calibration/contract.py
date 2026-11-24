from app.errors import InspectionError
from app.modules.trace.units import scaled, wavelength

FIELDS = ('length_m', 'zero_a_m', 'zero_b_m', 'pair_tol_m', 'design_tol_m', 'reference_limit_db')
OPTIONAL = ('wavelengths_nm',)


def declared_wavelengths(raw):
    if isinstance(raw, str):
        parts = [piece.strip() for piece in raw.split(',')]
    elif isinstance(raw, (list, tuple)):
        parts = [piece if type(piece) is int else str(piece) for piece in raw]
    else:
        raise InspectionError('BAD_SETTING')
    try:
        declared = sorted({wavelength(str(piece)) for piece in parts})
    except ValueError:
        raise InspectionError('BAD_SETTING') from None
    if not declared:
        raise InspectionError('BAD_SETTING')
    return declared


def setup(metadata):
    if not isinstance(metadata, dict) or not set(FIELDS) <= set(metadata) <= set(FIELDS) | set(OPTIONAL):
        raise InspectionError('SETTING_FIELDS')
    numbers = []
    try:
        for key in FIELDS:
            number = metadata[key]
            if not isinstance(number, str) and type(number) is not int:
                raise ValueError
            maximum = 10_000 if key == 'reference_limit_db' else 500_000_000
            numbers.append(scaled(str(number), 1000, 0, maximum))
    except ValueError:
        raise InspectionError('BAD_SETTING') from None
    length, za, zb, tolerance, design_tolerance, reference = numbers
    if length == 0 or max(tolerance, design_tolerance) > length:
        raise InspectionError('BAD_LINK_RANGE')
    settings = {'length_mm': length, 'zero_a_mm': za, 'zero_b_mm': zb, 'pair_tol_mm': tolerance,
                'design_tol_mm': design_tolerance, 'reference_limit_mdb': reference}
    declared = metadata.get('wavelengths_nm')
    if declared not in (None, ''):
        settings['wavelengths_nm'] = declared_wavelengths(declared)
    return settings
