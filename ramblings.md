I want to calibrate some data.

My data is taken across n beams. One of these is the track beam; another is the reference. The other beams don't matter.

I can either calibrate these two beams separately, or I can calibrate them together. So, we now have two types of calibration:

### Single Beam calibration (intra-beam)

In this mode, we only care about the data from a single beam. We have two choices:

1. Do nothing to the gains
2. Calibrate this data based on some known calibrator -- a diode, etc. The data will remain the same shape, but its temperatures will be adjusted

### Dual Beam calibration (inter-beam)

1. Do nothing to the gains, but do some sort of inter-beam calculations -- subtract them, average them, etc.
2. Calibrate the gains, and do some sort of inter-beam calculations -- subtract them, average them, etc.

## So...

This all seems somewhat muddle together, doesn't it? Let's try that again:

### Intra-Beam Calibration

The adjustment of the power values of the data from a given beam based on some known calibrator. There is _no_ reference to any other beam!

### Inter-Beam Calibration

The adjustment of the power values of the data by combining the data from two beams (be it subtraction, averaging, etc.).

## Getting there...

So, what we have is two _wholly separate_ calibration types.  Intra-Beam calibration can be done without Inter-Beam calibration, and vice versa. What, then, does this imply as far as architecture?

## Okay, but what about receiver-specific stuff?

Fine, each receiver might have different ways of implementing Inter- and Intra-Beam calibrations. But, at a high level, all receivers can perform Intra-Beam calibrations, and all receivers with more than one beam can perform Inter-Beam calibrations

So, having different Calibrators for each receiver still makes sense

## And what about polarization?

Right, that thing! We again can break this down into two categories:

### Intra-Polarization Calibration
As far as I know, this makes _no sense_ -- there is never a circumstance where this is viable. However, one could conceive of a situation where you wanted to average, for example, the data from two feeds containing the same polarization.

We can, of course, also apply gains to a polarization -- but only if it is within a feed, so this doesn't really belong here.

### Inter-Polarization Calibration
Within a given feed, there can be up to two polarizations. This means that we can do exactly the same operations as Inter-Beam Calibration -- subtract, average, etc. Hmmmm... perhaps what really matters is the number of "data streams"? More on that later


## So, what does that leave us with?

Well... it looks like there are some more similarities that we can merge.

### Intra-Datastream Calibration
The adjustment of the power values of a datastream based on some known calibrator. There is _no_ reference to any other datastream!

### Inter-Datastream Calibration
The adjustment of the power values of two datastreams by combining them in some manner (be it subtraction, averaging, etc.).

Okay... fine. But is that a useful distinction for us? Not sure yet.


## Tracing the signal...

Let's just try some examples, because I'm all fucked up.

### DualBeam, Single Pol

I have a dataset that is across two feeds and one polarization

I want to do "DualBeam" calibration on these feeds

So, I need to combine the the data from each feed. Let's just say it will be by subtracting it -- one beam is the signal, the other is the sky/ref

First, though, I want to attenuate each feed. Both feeds are referenced against a calibration diode, so I can generate a Tcal for each and apply it.

After that is done, I need to do my subtraction. Then, I have a single dataset containing attenuated, calibrated data.

So, how to break this down into algorithms? We have:

1. Attenuate
2. InterBeamSubtract

### DualBeam, Dual Pol

#### One pol per beam
I think this is what Ka is -- two beams, each with a different polarization.

Again, I first attenuate each beam.

Then, I simply average them together. You can think of this as the average of the data from two feeds, or as the average of the data from two polarizations -- either or both are fine/equivalent. Ka is unique in this case because it observes via beamswitching, which (I THINK) means you have two beams looking at the same source (although I assume not at the same time, hence the switching?)

1. Attenuate
2. InterBeamAverage


#### Two pols per beam

This is what Q band is, I think? Two beam, each with two pols. This is the most complicated case possible, I believe:

Let's say I want to calibrate both of my beams and both of my polarizations. That is, average my polarizations in each beam, then perform some sort of dual beam calibration on the resultant data streams. So:

1. Attenuate both beams
2. InterPolAverage
3. InterBeamSubtraction

Or, I could say I just want a single polarization. That is, don't average the polarizations, instead just pick one:

1. Attenuate the selected polarization in both beams
2. InterBeamAverage between selected pols

Or, I could say that I want a single pol but only one beam.

1. Attenuate the selected polarization in the beam
2. Select indicated pol data from said beam

Or, I could say that I want a single pol, one beam, and no attenuation at all. This is then simply a selection operation:

1. Select indicated pol data from selected beam

### Single Beam, Dual Pol

For L Band or something we just have one beam, but two polarizations. So, we can't do inter-beam operations obviously, but inter-polarization operations are just fine.


#### Average Pols
Let's say we want to average our polarizations. That's easy enough, we've discussed that before -- first attenuate, then average

1. Attenuate
1. InterPolAverage

Or we could skip attenuation and just average! I honestly don't know what this really means... do we end up with the data from when the cal was on, too?

1. InterPolAverage

#### Single pol

Our only operation possible is to attenuate. There's no other data to perform operations with

1. Attenuate



## So, how should this actually work?

I have a Calibrate class which is the entry point to all calibration. It expects a decoded data table at init. It also expects to be given the necessary parts of the pipeline -- an attenuator, an inter-pol cal, and an inter-beam cal (or any set of those, even none of them at all). It walks through the three-step pipeline, performing only the steps that it is supposed to perform. Easy enough, right?

Okay, but this requires some thinking about who gets what knowledge about the table. It is my feeling that our lower level functions are too knowledgable about what they are "supposed" to do, and that is hindering us. To attenuate, for example, all we should need is the rows in a table that need to be attenuated.


Representing None:

Raw = None ?




################


Okay, so we made it through the pipeline. How to clean up? I think we need to define the roles of a the "old" Calibrator with respect to the "new" Calibrator.

Old Calibrator: This was responsible for _everything_ -- it navigated through the entirety of the "pre processing" pipeline from decode -> calibration

New Calibrator: This is responsible for _only_ the calibration step. But, it breaks it down further into a "sub pipeline":
    1. Attenuate
    2. Inter-pol cal
    3. Inter-beam cal
