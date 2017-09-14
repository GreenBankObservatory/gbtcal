class Calibrator(object):
    def __init__(self, receiverInfoTable, ifDcrDataTable):
        self.receiverInfoTable = receiverInfoTable
        self.ifDcrDataTable = ifDcrDataTable

    def findCalFactors(self):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")
        
    def doMath(self, factors):
        raise NotImplementedError("doMath() must be implemented for "
                                  "all Calibrator subclasses!")

    def calibrate(self, polOption='Both', doGain=True, refBeam=None):
        factors = self.findCalFactors()
        self.doMath(factors)


class TraditionalCalibrator(Calibrator):
    def findCalFactors(self):
        print("Looking at tCals and stuff")

    def doMath(self, factors):
        # This is the same for all "Traditional" calibrators
        print("Doing math for trad cal")


class CalSeqCalibrator(Calibrator):
    def doMath(self, factors):
        # This is the same for all "Cal Seq" calibrators -- right now
        # just W band and Argus
        print("Doing math for Cal Seq calibration")


class WBandCalibrator(CalSeqCalibrator):
    def findCalFactors(self):
        print("Finding cal factors for W band using Cal Seq and stuff")


class ArgusCalibrator(CalSeqCalibrator):
    def findCalFactors(self):
        print("Finding cal factors for Argus doing whatever it does")


class InvalidCalibrator(Calibrator):
    pass
