This is the table generated for /home/sandboxes/tchamber/repos/sparrow/sandbox/sparrow/gbt/api/scans/data, which is an old dataset from ~2004.
This is what we have referred to as the "pathological case", where we cannot uniquely select a phase based on feed, polarization, frequency.
That is, the DCR recorded more data than it "should have", and the last half (or first half?) of the table is redundant.

            RECEIVER              FEED RECEPTOR POLARIZE CENTER_SKY BANDWDTH  PORT SRFEED1 SRFEED2 HIGH_CAL SIGREF  CAL    DATA [300]        TCAL     INDEX
              none                none   none     none       Hz        Hz     none   none    none    none
             str32               int32   str8     str2    float32   float32  int32  int32   int32   int32   uint8  uint8     int32         float64    int64
-------------------------------- ----- -------- -------- ---------- -------- ----- ------- ------- -------- ------ ----- -------------- ------------- -----
Rcvr1_2                              1 XL             X    1.41e+09    8e+07     1       0       0        0      0     0 30770 .. 30662 1.58350000381     0
Rcvr1_2                              1 XL             X    1.41e+09    8e+07     1       0       0        0      0     1 32611 .. 32479 1.58350000381     1
Rcvr1_2                              1 YR             Y    1.41e+09    8e+07     3       0       0        0      0     0 32872 .. 32782 1.63750000596     2
Rcvr1_2                              1 YR             Y    1.41e+09    8e+07     3       0       0        0      0     1 34865 .. 34808 1.63750000596     3
Rcvr1_2                              1 XL             X    1.41e+09    8e+07     5       0       0        0      0     0 30231 .. 30117 1.58350000381     4
Rcvr1_2                              1 XL             X    1.41e+09    8e+07     5       0       0        0      0     1 32121 .. 31992 1.58350000381     5
Rcvr1_2                              1 YR             Y    1.41e+09    8e+07     7       0       0        0      0     0 30511 .. 30466 1.63750000596     6
Rcvr1_2                              1 YR             Y    1.41e+09    8e+07     7       0       0        0      0     1 32534 .. 32519 1.63750000596     7


This table is from /home/gbtdata/AGBT16B_285_01, and represents a "proper" dataset

            RECEIVER             FEED RECEPTOR POLARIZE CENTER_SKY BANDWDTH PORT SRFEED1 SRFEED2 HIGH_CAL SIGREF CAL   DATA [589]        TCAL     INDEX
              none               none   none     none       Hz        Hz    none   none    none    none                                                
-------------------------------- ---- -------- -------- ---------- -------- ---- ------- ------- -------- ------ --- -------------- ------------- -----
Rcvr1_2                             1 XL             X     1.4e+09    8e+07    1       0       0        0      0   0 40739 .. 38709 1.42582168283     0
Rcvr1_2                             1 XL             X     1.4e+09    8e+07    1       0       0        0      0   1 41993 .. 39842 1.42582168283     1
Rcvr1_2                             1 YR             Y     1.4e+09    8e+07    3       0       0        0      0   0 42376 .. 40347 1.45186871066     2
Rcvr1_2                             1 YR             Y     1.4e+09    8e+07    3       0       0        0      0   1 43813 .. 41631 1.45186871066     3


So, for my own sanity...

Another way of putting this is that Rcvr1_2 has only one feed, two polarizations, and has a noise diode that can be toggled. That yields four total states, yet 8
datasets are represented below. What, then, is the data in ports 5 and 7? Is this what Richard was talking about when he said that data could be taken if the system configuration
had not been reset from a previous project?

We know that you can't simply select all of the data for a given feed, polarization, frequency and cal that the data for a given phase. What could we then select by?

Well, we know that the IF FITS file lists the port that was used for each data array, so that seems to be the _actual_ source of truth. But how does that help us?

What do SRFEED1 and SRFEED2 do? Anything? Are they even useful?
----FOllow up with Richard and ask what these do? Read sw proj note about IF FITS file first!

Do we ever need RECEPTOR?

Paul and Richard seem to think that, for typical observations, each unique set of (feed, polarization, frequency) should map to its own dataset.
But what about bandwidth? Is it just that it is always paired to frequency for typical observing?
---make sure this is in the code

TCAL is agnostic to CAL, because that is time-domain, rather than physical-domain 
