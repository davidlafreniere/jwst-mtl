# JWST Pipeline


Here is a collection of all the documentation related to the pipeline
specifically those related to NIRISS.




---




## Contents

1. [Pipeline installation](#pipeline-installation)
2. [Running the pipeline](#running-the-pipeline)
3. [Getting Calibrations](#setting-up-the-calibration-reference-data-system-crds)
4. [Pipeline at compute canada](#pipeline-compute-canada)



---




## Pipeline installation

In the future the jwst pipeline will be part of astroconda. However for now it
is not officially supported.

Installation documentation is [here](https://github.com/spacetelescope/jwst).

First install miniconda3 or anaconda3.

Then create a new conda environment (after first updating conda and the conda channels)
```
conda update conda
conda config --add channels conda-forge
conda config --add channels http://ssb.stsci.edu/astroconda
conda create --name {NAME} python=3.7
conda activate {NAME}
```
where {NAME} is the environment name (e.g. "jwstpipe")

Then install the jwst pipeline from github via pip
```
pip install git+https://github.com/spacetelescope/jwst
```

[Back to top](#jwst-pipeline)





---





## Running the pipeline

To run the stage 1 pipeline on a (simulated) fits file type

```
strun jwst.pipeline.Detector1Pipeline ng4ni3_uncal.fits
```

For more information on running the pipeline from [terminal](https://jwst-pipeline.readthedocs.io/en/latest/jwst/introduction.html#running-from-the-command-line) or from [python](https://jwst-pipeline.readthedocs.io/en/latest/jwst/introduction.html#running-from-within-python) see the documentation.


[Back to top](#jwst-pipeline)





---





## Setting up the Calibration Reference Data System (CRDS)

You need to set two paths to get calibration data
```
export CRDS_PATH={PATH_TO_CACHE}
export CRDS_SERVER_URL=https://jwst-crds.stsci.edu
```

Info on CRDS is [here](https://jwst-crds.stsci.edu/)


### Obtaining reference data

Either one can visit the website and browse for a specific file ([here](https://jwst-crds.stsci.edu/))
or one can use the command line tools.

Last update: 2020-01-14

Current pmap:  jwst_0579.pmap

Current NIRISS imap: jwst_niriss_0123.imap

Reference maps:
```
area, dark, distortion, drizpars, extract1d, flat, gain, ipc, linearity, mask, pathloss, persat, photom, readnoise, saturation, specwcs, superbias, throughput, trapdensity, trappars, wavelengthrange, wfssbkg
```

#### Using the command line

The following command will download all the context files
(see [here](https://jwst-crds.stsci.edu/static/users_guide/overview.html#kinds-of-crds-files))

i.e. downloads:
- Pipeline context files (.pmap)
- Instrument context files (.imap)
- Reference Type Mapping (.rmap)

```
crds sync --all
```
into the path set by `CRDS_PATH` above.

Organise cached references by instrument as follows:
```
crds sync --organize=instrument --verbose
```


Then one can download a single one of these context files
(Browse them at `{CRDS_PATH}/mappings/jwst`)

after choosing one (or many) map files to sync, type the following
```
crds sync --contexts jwst_niriss_0123.imap --fetch-references
```
This will download the fits files into the `{CRDS_PATH}/references/jwst/niriss/` if you followed all steps above
note the total file size is around 11.9 GB

[Back to top](#jwst-pipeline)




---




## Pipeline Compute Canada

Currently the pipeline is set up on the beluga server at compute canada.

### Step 1: Logging into beluga

```
ssh {USER}@beluga.computecanada.ca
```
where `{USER}` is your compute canada user name

### Step 2: First time setup

Run the first time setup script
```
source ~/projects/def-dlafre/pipeline/setup/firsttime.sh
```

### Step 3: Setup for pipeline use

to run this command every time you log in to beluga type:
```
jwstpipe
```

Note it is located here:`~/projects/def-dlafre/pipeline/setup/jwstpipe.sh`

#### IMPORTANT: Do not source this in your ~/.bashrc (will lead to an infinite loop)
