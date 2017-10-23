class Constant(object):
    @classmethod
    def all(cls):
        members = [attr for attr in dir(cls)
                   if not callable(getattr(cls, attr)) and not
                   attr.startswith("__")]
        return members

    @classmethod
    def isValid(cls, value):
        return value in cls.all()

    @classmethod
    def areValid(cls, values):
        return all([cls.isValid(value) for value in values])


class POLOPTS(Constant):
    XL = 'XL'
    YR = 'YR'
    AVG = 'Avg'


class CALOPTS(Constant):
    RAW = 'Raw'
    TOTALPOWER = 'TotalPower'
    DUALBEAM = 'DualBeam'
    BEAMSWITCH = 'BeamSwitch'
    BEAMSWITCHEDTBONLY = 'BeamSwitchedTBOnly'

class ATTENTYPES(Constant):
    GFM = 'GFM'
    OOF = 'OOF'

class POLS(Constant):
    X = 'X'
    Y = 'Y'
    L = 'L'
    R = 'R'
    LINEAR = (X, Y)
    CIRCULAR = (L, R)

    @classmethod
    def all(cls):
        return cls.LINEAR + cls.CIRCULAR
