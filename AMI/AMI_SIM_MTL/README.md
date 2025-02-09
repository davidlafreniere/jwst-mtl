# The AMI Simulation wrapper

    Last updated 2022-02-14

## 1 AMISIM

Installing AMISIM requires cloning the github repository and installing some
python modules (we handle the python modules as part of the requirements) to run
the AMI simulation wrapper.

To clone AMISIM use the following command:

    git clone git@github.com:anand0xff/ami_sim.git

(If not using SSH, use `git clone https://github.com/anand0xff/ami_sim.git`).

This will create an ami_sim directory in your current working directory.

Please note down the AMISIM installation location you will need to for the 
yaml file. From this point on we will refer to this as `{AMISIM_ROOT}`.

All required python modules are installed with the `setup.cfg` file for 
the AMI Simulation wrapper (section \ref{sec:ami_sim_wrapper}). 
However one of the modules (webbpsf) requires some additional files to be 
downloaded and link to via an environmental variable. 
The instructions are here: 

https://webbpsf.readthedocs.io/en/stable/installation.html#installing-the-required-data-files}

but essentially you need to:

1. Download the following file: webbpsf-data-1.0.0.tar.gz [approx. 280 MB]
2. Untar webbpsf-data-1.0.0.tar.gz into a directory of your choosing.
3. Set the environment variable \lstinline{WEBBPSF_PATH} to point to that directory
   (e.g. `export WEBBPSF_PATH=}\$\lstinline{HOME/data/webbpsf-data`)


## 2 Mirage

Mirage is required for the AMI simulation wrapper and so installation will 
be done when installing the AMI simulation wrapper


## 3 The AMI Simulation wrapper

### 3.1 Installation

Installation of the AMI Simulation wrapper requires the cloning of the github 
repository and instllation some python modules.

To clone the AMI Simulation wrapper use the following command:

    git clone git@github.com:njcuk9999/jwst-mtl.git

This should create a directory called `jwst-mtl`.

We next recommend a new conda environment (though venv or pip can be used if you prefer).

To add a new conda environment use the following command (requires miniconda or 
anaconda to be installed first):

    conda create --name ami-env python=3.8

Then activate this environment with the following command:

    conda activate ami-env

Next we require you to change to a sub-directory within `jwst-mtl` github 
directory that was created when you cloned the repository above.

    cd jwst-mtl/AMI/AMI_SIM_MTL

Once in this directory you should see a `setup.cfg` file.

Check that you have pip and are in the correct conda environment (if using 
conda) using the following command:

    which pip

It should display something ending in `/envs/ami-env/bin/pip`.


You can now install the AMI simulation wrapper and its dependencies with the
following command:

    pip install .

To install for development, you can install in editable (`-e`) mode and add the "dev"
dependencies.

    pip install -e ".[dev]"

This will allow you to run and call the wrapper from within python or call the
wrapper function from the command line, when working in the virtual environment
created above. If successful you are ready to set up the simulation yaml file
and then run the simulation wrapper.

### 3.2 The simulation yaml file

You will find an example (commented) yaml file in the `inputs` directory 
(called `example.yaml`). 
Please do not edit this file but copy it to a new location and rename it.

It is separated into sections (the simulations and the global parameters). 
Each simulation has its own section and consists of one science observation 
`target` and a set of calibrators to go with that target.

Each target is allowed to have no companions or multiple companions (either 
being planets, disks or bars).

Currently supported simulations (using AMI-SIM) are:

 - target \& calibrator(s)
 - target + planet(s) \& calibrator(s)
 - target + disk(s) \& calibrator(s)
 - target + bar(s) \& calibrator(s)
 - target + planet(s) + disk(s) \& calibrator(s)
 - target + planet(s) + bar(s) \& calibrator(s)
 - target + planet(s) + disk(s) + bar(s) \& calibrator(s)

Note the following parameters MUST be set by the user

 - parameters.general.in_dir
 - parameters.general.out_dir
 - parameters.ami-sim.out_path
 - parameters.ami-sim.install-dir  (using the {AMISIM_ROOT} value)
 - parameters.ami-sim.psf.FXXX.path   (for each filter XXX)

the details are which are in the comments of the yaml file.

Note do not use the following parts of the wrapper (i.e. set them to False)
 
- parameters.mirage.use
- parameters.dms.use
- parameters.ami-cal.use
- parameters.implaneia.use

### 3.3 Running the wrapper

Once installation is complete and a yaml file has been made running is very simple.

The wrapper requires an APT file with the observation information. There are
examples in `inputs/`. The `example.yaml` file contains user-specified
parameters and `jwst_ami_p23_example.xml` is the corresponding APT file
(proposal ID 23, NIRISS AMI Observations of Extrasolar Planets Around a Host
Star). With these two files, the wrapper can be run immediately after
installation.

To run from a python script:

```python
# Import the wrapper
from ami_mtl.science import wrapper

# Enter the path to the yaml file (can be relative or absolute)
MY_YAML_FILE = "../inputs/example.yaml"

# Run the simulations
wrapper.main(WCONFIG=MY_YAML_FILE)
```

This should produce the simulation(s) as defined in the yaml file.

Otherwise if you have installed the wrapper with `pip` correctly, then you should be
able to just run the following from the command line:

    wrapper --config=../inputs/example.yaml


### 4 Observable extraction with AMICAL

[AMICAL](https://github.com/SydneyAstrophotonicInstrumentationLab/AMICAL) is
developed to analyse AMI observations from multiple facilities. It is compatible
with JWST/NIRISS. It can analyse either a direct output from `ami_sim` or a
mirage output processed with the DMS.

AMICAL should be installed when installing the wrapper with `pip`(see section
3.1 above). Otherwise, it can be installed with

    pip install amical


AMICAL performs four main tasks:
1. Cleaning: bad pixel correction, background subtraction, windowing, etc. (required for mirage output).
2. Observable extraction: going from a fits file to a "bispectrum" Python
   object.
3. Observable calibration: after extraction of a science target and a
   calibrator, AMICAL can calibrate the observables and save them to an OIFITS
    file.
4. Binary fit: after calibration, the OIFITS observables can be analyzed to fit
   a binary either with a $\chi^2$ grid (CANDID) or with a MCMC (PyMask).

To run AMICAL on the wrapper output, use the script `misc/run_amical.py`. The
options are in the "Constants" section at the top of the script. You can edit
those to analyze a specific file or to perform specific steps. The, you can run all AMICAL steps with 

    python misc/run_amical.py
