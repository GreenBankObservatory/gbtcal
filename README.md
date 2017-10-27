# `gbtcal`

`gbtcal` is a GBT-specific calibration library for continuum data. It is intended for use with all receivers that take continuum data and use the GBT's IF system.

## Setup

Simply run `createEnv` to get your environment set up.

You will also probably want to add the repo root to your `PYTHONPATH` if you are planning on running anything directly.

## Tests

All tests reside in `gbtcal/test`

### "Unit" Tests

Note that we don't really have unit tests in this repo. Instead we have various types of regression tests. So, when we say "unit tests" in the context of this repo, what we really mean is "the tests that `nose` runs".

These tests can be run via `$ nosetests` in the repo root.

These tests compare `gbtcal` results to results from `sparrow`. The sparrow results are being tracked alongside the repo.

### Regression Tests

Run via `$ python gbtcal/test/regression_tests.py`

TODO: Describe these further

## Dataflow Overview

The dataflow can be broken down into two phases, decoding and calibration.

### Decoding

This is the beginning of the pipeline. A scan is selected, along with a calibration option (e.g. Total Power) and a calibration option (e.g. 'XL'). The IF and DCR FITS files for the given scan are loaded and then merged together. The merging process is somewhat non-trivial because the DCR data is stored in the time-domain and must be mapped to the physical feed that took the data, the polarization of the data, and the calibration states under which the data was taken. The result is a single Astropy table, retaining the original FITS column names, that contains the mapped/decoded data.

### Calibration

Calibration takes a decoded IF/DCR table as its input, as well as the desired calibration/polarization options, and then calibrates the data.

This stage of the pipeline is somewhat more complicated. Decoding is the same for all continuum receivers, but calibration is not -- it must be altered based on various receiver quirks. To accommodate this in a clean manner, we have taken a compositional approach to the calibration pipeline. It is broken down into three phases, each of which is implemented via a class hierarchy. A `Calibrator` subclass then composes its pipeline by selecting a class from each stage of the pipeline. To calibrate, the `Calibrator`'s `calibrate` method is called, which actually steps through the calibration pipeline and eventually returns the calibrated data.

#### Conversion/Attenuation/Gainification

We still aren't really sure what to call this. It would be called "Total Power" in the old code, and is currently called attenuation in the new code. However, none of those are wholly accurate names. Basically what is happening in this stage is that the raw counts/voltages that are recorded by the DCR are being converted into Kelvin.

To accommodate the various ways that this is done, new subclasses of `Attenuate` can be created. All `Attenuate` classes must implement an `attenuate` method to provide a common interface to `Calibrator`.

#### Inter-Beam Operations

All operations that require data from two different feeds/beams should be done here. We have only a couple that are currently implemented, but again this is very generic and all sorts of different things could be plugged in here.

Most commonly this stage simply subtracts the reference data from the signal data.

#### Inter-Polarization Operations

Right now this is literally just polarization averaging. However, it has been left discrete and generic to accommodate other possible polarization calibration operations. The idea here is that any sort of operations that require data from two different polarizations (within a feed) would be done in this stage.

An `InterPolCalibrate` class must implement a `calibrate` method.
