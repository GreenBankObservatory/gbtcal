# `gbtcal`

`gbtcal` is a GBT-specific calibration library for continuum data. It is intended for use with all receivers that take continuum data and use the GBT's IF system.

See also: https://safe.nrao.edu/wiki/bin/view/GB/Software/DcrCalibrationDocs

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

This is a simple module for comparing results computed by gbtcal
with that originally computed by Sparrow (GFM).
The Sparrow results live in files with descriptive filenames,
such as <projectname>.<scannumber>.<receiver>.
The home of the data that these Sparrow results were created from
live in a separate file, organized by receiver, project path, and
scan numbers.
The basic flow of these tests is to:

   * Find where all the DCR data lives in the archive by reading the
      above mentioned file
   * For each of these scans:
      * Computing the various DCR Calibration results
      * Compare these results to what are in the Sparrow files
   * All results are printed to a report, including any problems
      encountered, besides the obvious mismatching results

## Use as a Third Party Package

If you simply want to use 'gbtcal' as a 3rd party package, here are the simple steps:

   * source /home/gbtcal/release/release_gbtcal_env/bin/activate
   * export PYTHONPATH=/home/gbtcal/release:$PYTHONPATH

In your python code:

   * from gbtcal.calibrate import calibrate
   * data = calibrate(projpath, scan, calMode, polMode), where:
      * projpath - the path to your project, ex: /home/gbtdata/AGBT16A_353_83
      * scan - the number for the scan you want to calibrate
      * calMode - the calibration mode, possibly one of 'Raw', 'TotalPower', 'DualBeam'.
      * polMode - the polarization mode, possibly one of 'XL', 'YR', 'Avg'


## Dataflow Overview

The dataflow can be broken down into two phases, decoding and calibration.

### Decoding

This is the beginning of the pipeline. A scan is selected, along with a calibration option (e.g. Total Power) and a polarization option (e.g. 'XL'). The IF and DCR FITS files for the given scan are loaded and then merged together. The merging process is somewhat non-trivial because the DCR data is stored in the time-domain and must be mapped to the physical feed that took the data, the polarization of the data, and the calibration (phase) states under which the data was taken. The result is a single Astropy table, retaining the original FITS column names, that contains the mapped/decoded data.

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

## Calibrator Stategy Classes

As seen in this repo's UML, there is a class hierarchy of Calibrators, that can be extended for new receivers that need
their own way of calibrating DCR data.  Each of these classes will also used different classes for their converter, polarization and beam calibration phases.

Here's brief overview of the classes:

### Calibrator

This is the abstract base class that contains common methods almost all receivers will need for calibrating their DCR data.

### TraditionalCalibrator

Most of our receivers can calibrate their DCR data with this class (a child of Calibrator).  This calibrator will gather receiver calibration temperatures from the receiver calibration FITS file.  It will and these in an 'Antenna Temperature', or 'Total Power' equation by its convert class CalDiodeConverter.


### CalSeqCalibrator

This is another abstract class (child of Calibrator).  This is for receivers that don't use a receiver calibration FITS file, but instead need to calculate their 'gains' from other scans.  These gains are then used in the CalSeqConverter class.

Examples of children of this class are the WBandCalibrator class and ArgusCalibrator, each of which have helper classes to calculate their gains from other scans.

### KaCalibrator

This is the ugly duckling or black sheep of this group of classes, and is part of the reason why such a generic framework had to be constructed to cover all DCR calibration cases.

The Ka receiver has only X polarization in its first feed, and only Y in its second. In addition its beam calibration step is completely different from the other classes.

It is currently _somewhat_ hacked together, but this reveals a yet-to-be-resolved shortcoming of the pipeline structure rather than some intractable problem. Basically, instead of fully delegating each pipeline step to its respective class, a `Calibrator` instead has a method for each pipeline step that in turn calls the respective class. The respective class then has a very limited scope -- it is typically operating on only a single feed, or polarization, etc. Ka breaks this model, and so instead of having an `InterBeamOperator` subclass it simply does everything inside its `interBeamCalibrate` method. Not the worst thing in the world, but it could definitely be cleaned up.

## Table Driven Behavior

Much of the behavior for determining how to calibrate a specific set of DCR data is determined by the receiver is used.  Instead of using conditionals to implement this receiver specific behavior, we use a table-driven approach.

The file `rcvrTable.csv` contains this "receiver table", and is an enhanced comma-separated file used by `rcvr_table.py` to determine how
each receiver's DCR data should be calibrated.  For example, the "Cal Strategy" column contains the name of the calibrator class that each receiver should use.  Other useful columns are "Num Beams" and "Num Pols".

 This is similar to the wiki page:
 https://safe.nrao.edu/wiki/bin/view/GB/Knowledge/WhichReceiverIsThat

## Examples

 The UML also has some excellent examples drawn out, but here we'll also flesh out how these are used.

### L-band, XL polarization, Raw data

 This is the equivalent of the data you would see in the GFM Continuum plugin, for the 'X' or 'L' polarization, using the 'Sig / No Cal' phase.

   * The raw data table is found from the project path and scan number using gbtcal.decode
   * The receiver table is loaded from the CSV file    * calibrate.doCalibrate converts the GFM-style polarization and calibration options to the appropriate values for flags that determine what steps the calibrator will do.  In our case, we won't be do *any* steps.
   * calibrate.doCalibrate also determines from the receiver table's 'Cal Strategy' column what calibrator class to use.  In our case, Rcvr1_2 is the TraditionalCalibrator class.
   * finally, we call this class's object's calibrate method, passing in the 'XL' option.
   * since our class won't be performing conversion, inter-beam or inter-polarization operations, it simply:
      * calls selectNonCalData: this is essentially getting the 'raw' data and placing it in a calTable
      * calls selectBeam: this is a no-op, since L-band has one beam.  But our calTable is passed on to a polTable
      * calls selectPol: here we select the 'XL' polarization from the polTable - and that's our final answer!

### L-band, Average polarization, Total Power data.

This is the equivalent of what you might see in the GFM Pointing Plugin, when the options selected are 'Total Power' & 'Both'.

   * we follow the same first two steps as the case above
   * this time, calibrate.doCalibrate maps these GFM-style choices to these flags:
      * performConversion = True; because we asked for Total Power
      * performInterPolOp = True; because we asked for Average polarization
      * performInterBeamOp = False; because we didn't ask for something like Dual Beam, which would have been invalid for this single beam receiver anyways.
   * we choose the TraditionalCalibrator again this time, from the receiver table
   * this time the call to the object's calibrate method sees different steps followed:
      * convertToKelvin uses the TraditionalCalibrator's converter class (CalDiodCalibrator) to find the receiver calibration temperatures, and use these with the Antenna Temperature equation to convert our raw values to the new values in the calTable
      * selectBeam is called again, as in the previous case (no-op), to produce the polTable
      * interPolCalibrate uses the TraditionalCalibrator's interPolCalibrator class (InterPolAverager) to average the two polarizations.  That's our final answer!

