# New Calibrator Framework

## Here's how it works

A `Calibrator` is a class responsible for producing calibrated data from an `IfDcrTable`. That is, given a calibration and polarization mode, it will query the Table for the relevant information and perform the operations necessary to produce the relevant calibrated data.

Calibration for most receivers can be performed in the same manner. For these cases there exists the TraditionalCalibrator. For receivers that deviate from standard behavior, a new Calibrator subclass can be created.

A Calibrator's interface with the outside world is its calibrate method. This method is defined in the base Calibrator class, and it is currently not overridden by any of its children, although it could be if necessary.

The calibrate method breaks calibration down into three steps:

### 1. Collapse the IfDcrTable by means of either attenuation, or selection

First of all, what do I mean by attenuate? I'm using it to mean the application of a gain. I don't know of a general term that encompasses both amplification and attenuation, unfortunately. Perhaps we could revert back to using "total power" to refer to this "attenuation".

Previously this was handled by either `calibrateTotalPower` (attenuation) or `getRawPower` (selection).


### 2. Collapse the IfDcrTable by means of either some inter-polarization operation, or selection

Previously this step was combined with (1). This allowed for only one type of inter-polarization operation, which is fine since we currently only support averaging. However, because:
1. This is a fundamentally different operation than attenuation
2. This allows for any number of new inter-polarization operations to be implemented
I have separated this into a discrete step

### 3. Collapse the IfDcrTable by means of either some inter-beam operation, or selection

This has always been a discrete step. Most commonly this takes the form of simple beam subtraction, but there are several caveats for things like OOF and Ka. There are also other sorts of inter-beam operations that could be imagined, so I have kept this generic in terminology



## Improvements

The pipeline should be more pipeliney. I think that formalizing the "selector" concept would be nice. Like, instead of passing in an InterPolAverage instance, perhaps a Selector(pol=X) could be passed in? Would be more obvious what was going on
