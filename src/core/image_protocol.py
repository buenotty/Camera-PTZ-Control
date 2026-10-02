"""Map only fields advertised by the camera; preserve its other ISP values."""
from src.core.models import ImageSettings, ExposureMode, WhiteBalanceMode

FIELDS = {
    'brightness': ('Luminance',), 'contrast': ('Contrast',),
    'saturation': ('Saturation',), 'sharpness': ('Sharpness',),
    'hue': ('Hue', 'ucHue'), 'exposure_mode': ('eExposureMode',),
    'white_balance_mode': ('eWBMode',), 'gain': ('ucManualGain',),
    'iris': ('ucManualIris',), 'shutter_speed': ('uiMShutterSpeed',),
    'red_gain': ('ucRGGain',), 'blue_gain': ('ucBGGain',),
    'exposure_compensation_value': ('BExpCPS',),
    'blc': ('bBacklightCompensation',), 'wdr': ('eWDMode',),
    'noise_reduction': ('uc2DNR',), 'flip': ('bVertInvert',),
    'mirror': ('bHorzInvert',),
}
EXPOSURE = {ExposureMode.AUTO: 0, ExposureMode.MANUAL: 1,
            ExposureMode.IRIS_PRIORITY: 2, ExposureMode.SHUTTER_PRIORITY: 3}
WHITE_BALANCE = {WhiteBalanceMode.AUTO: 1, WhiteBalanceMode.INDOOR: 2,
                 WhiteBalanceMode.OUTDOOR: 3, WhiteBalanceMode.MANUAL: 4,
                 WhiteBalanceMode.ONE_PUSH: 5}


def supported_settings(params):
    fields = {name for name, aliases in FIELDS.items() if any(k in params for k in aliases)}
    for name, mapping in [('exposure_mode', EXPOSURE), ('white_balance_mode', WHITE_BALANCE)]:
        key = FIELDS[name][0]
        if name in fields and str(params[key]) not in {str(v) for v in mapping.values()}:
            fields.remove(name)
    for name in ('blc', 'wdr', 'flip', 'mirror'):
        key = FIELDS[name][0]
        if name in fields and str(params[key]) not in ("0", "1"):
            fields.remove(name)
    return fields


def encode_setting(name, value, params):
    keys = [k for k in FIELDS.get(name, ()) if k in params]
    if not keys:
        raise ValueError('A câmera não informa suporte a este ajuste.')
    if name == 'exposure_mode':
        value = EXPOSURE[value]
    elif name == 'white_balance_mode':
        value = WHITE_BALANCE[value]
    else:
        value = int(value)
    return {key: value for key in keys}


def decode_settings(params):
    settings = ImageSettings()
    for name, aliases in FIELDS.items():
        key = next((k for k in aliases if k in params), None)
        if key is None:
            continue
        value = params[key]
        if name == 'exposure_mode':
            value = next((k for k, v in EXPOSURE.items() if v == int(value)), ExposureMode.AUTO)
        elif name == 'white_balance_mode':
            value = next((k for k, v in WHITE_BALANCE.items() if v == int(value)), WhiteBalanceMode.AUTO)
        elif isinstance(getattr(settings, name), bool):
            value = bool(int(value))
        else:
            value = int(value)
        setattr(settings, name, value)
    return settings
