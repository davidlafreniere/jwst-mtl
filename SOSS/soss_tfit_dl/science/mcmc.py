#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
# CODE NAME HERE

# CODE DESCRIPTION HERE

Created on 2022-04-06

@author: cook
"""
from astropy.io import fits
from astropy.table import Table, vstack
import numpy as np
import bottleneck as bn
import os
import pickle
import time as timemod
from tqdm import tqdm
from typing import Any, Dict, List, Optional, Tuple
import warnings

from soss_tfit.core import base
from soss_tfit.core import base_classes
from soss_tfit.science import general
from soss_tfit.science import models

# =============================================================================
# Define variables
# =============================================================================
__NAME__ = 'science.general.py'
__version__ = base.__version__
__date__ = base.__date__
__authors__ = base.__authors__
# get parameter dictionary
ParamDict = base_classes.ParamDict
# get FitParam class
FitParam = base_classes.FitParam
# get data class
InputData = general.InputData
# printer
cprint = base_classes.Printer()
# Out of bounds value
BADLPR = -np.inf

# These are the attributes of TransitFit that have the same length as x0
X_ATTRIBUTES = ['x0', 'beta', 'x0pos']


# =============================================================================
# Define fit class passed to mcmc code
# =============================================================================
class TransitFit:
    """
    One could just set all the correct values manually in this and
    expect it to work later
    """
    #params
    params: ParamDict
    # the number of integrations we have
    n_int: int
    # the number of parameters we have
    n_param: int
    # the number of photometric bandpasses we have
    n_phot: int
    # the total number of valid points (number of photometric bandpasses for
    #   each integration
    npt: int
    # numpy array [n_param, n_phot] the initial value of each parameter
    p0: np.ndarray
    # numpy array [n_param] whether we are fitting each parameter [Bool]
    fmask: np.ndarray
    # numpy array [n_param] whether chromatic fit used for each parameter [Bool]
    wmask: np.ndarray
    # priors [n_param]
    prior: List[Dict[str, Any]]
    # name of each parameter [n_param]
    pnames: List[str]
    pfullnames: List[str]
    # additional arguments passed to mcmc
    pkwargs: Dict[str, Any]
    # the position in the flattened x array [n_param, n_phot]
    p0pos: np.ndarray
    # the pre-set value of beta (if forced otherwise None) [n_param]
    pbetas: np.ndarray
    # -------------------------------------------------------------------------
    # the data:
    # -------------------------------------------------------------------------
    #     [0][WAVELENGTH][n_phot, n_int]
    phot: List[Dict[str, np.ndarray]]
    # the wavelength array [n_phot, n_int]
    wavelength: np.ndarray
    # the time array [n_phot, n_int]
    time: np.ndarray
    # the integration time array [n_phot, n_int]
    itime: np.ndarray
    # the flux array [n_phot, n_int]
    flux: np.ndarray
    # the flux error array [n_phot, n_int]
    fluxerr: np.ndarray
    # the order array [n_phot, n_int]
    orders: np.ndarray
    # the limits for each bin
    bin_limits: np.ndarray
    # -------------------------------------------------------------------------
    # parameters that must have shape [n_x]
    # -------------------------------------------------------------------------
    # the initial fitted parameters
    x0: np.ndarray
    # name of the fitted params flattened [n_x]
    xnames: np.ndarray
    xfullnames: np.ndarray
    # length of fitted params flattened [n_x]
    n_x: int
    # numpy array [n_param]
    beta: np.ndarray
    # the mapping from x0 onto p0 [n_x, 2] each element
    #   is the tuple position in p0
    x0pos: np.ndarray
    # the pre-set value of beta (if forced otherwise None) for fitted params
    #    [n_x]
    xbeta: np.ndarray
    # -------------------------------------------------------------------------
    # will be filled out by the mcmc
    # -------------------------------------------------------------------------
    # the current position chosen by the sampler
    n_tmp: int = 0
    # the previous accepted loglikelihood value
    llx: float
    # the current loglikelihood value
    llxt: float
    # the rejection [rejected, parameter number]   where rejected = 0 for
    #   accepted and rejected = 1 for rejected
    ac: List[int]

    def __init__(self):
        # the transitmodel function to use
        self.tmodel_func: None ###DL###
        # number of planets
        self.n_planets = 0
        # number of spots
        self.n_spots = 0
        # the number of integrations we have
        self.n_int = 0
        # the number of parameters we have
        self.n_param = 0
        # the number of photometric bandpasses we have
        self.n_phot = 0
        # numpy array [n_param, n_phot] the initial value of each parameter
        self.p0 = np.array([])
        # numpy array [n_param] whether we are fitting each parameter [Bool]
        self.fmask = np.array([])
        # numpy array [n_param] whether chromatic fit used for each parameter [Bool]
        self.wmask = np.array([])
        # priors [n_param]
        self.prior = []
        # name of each parameter
        self.pnames = []
        self.pfullnames = []
        # additional arguments passed to mcmc
        self.pkwargs = dict()
        # the position in the flattened x array [n_param, n_phot]
        self.p0pos = np.array([])
        #
        #the LD interpolation functions
        self.ld_func = []
        # -------------------------------------------------------------------------
        # the data:
        # -------------------------------------------------------------------------
        #     [0][WAVELENGTH][n_phot, n_int]
        self.phot = []
        # the wavelength array [n_phot, n_int]
        self.wavelength = np.array([])
        # the time array [n_phot, n_int]
        self.time = np.array([])
        # the integration time array [n_phot, n_int]
        self.itime = np.array([])
        # the flux array [n_phot, n_int]
        self.flux = np.array([])
        # the flux error array [n_phot, n_int]
        self.fluxerr = np.array([])
        # the order array [n_phot, n_int]
        self.orders = np.array([])
        # the bin limits in micron [n_phot, 2]   (start,end)
        self.bin_limits = np.array([])
        # -------------------------------------------------------------------------
        # parameters that must have shape [n_x]
        # -------------------------------------------------------------------------
        # the initial fitted parameters
        self.x0 = np.array([])
        self.xpriors = [] ###DL###
        # name of the fitted params flattened [n_x]
        self.xnames = np.array([])
        self.xfullnames = np.array([])
        # length of fitted params flattened [n_x]
        self.n_x = 0
        # numpy array [n_param]
        self.beta = np.array([])
        # the mapping from x0 onto p0 [n_x, 2] each element
        #   is the tuple position in p0
        self.x0pos = np.array([])
        # the pre-set value of beta (if forced otherwise None) for fitted params
        #    [n_x]
        self.xbeta = np.array([])
        # -------------------------------------------------------------------------
        # will be filled out by the mcmc
        # -------------------------------------------------------------------------
        # the current position chosen by the sampler
        self.n_tmp = 0
        # the loglikelihood value
        self.llx = BADLPR
        # the rejection [rejected, parameter number]   where rejected = 0 for
        #   accepted and rejected = 1 for rejected
        self.ac = []
        # define a dictionary to store the 2D positions of all x0 variables
        #   (for use when updating a single x variable)
        self.x0_to_p0 = dict()
       # numpy array [n_planet]
        self.tt_n = np.array([])
        # numpy array [nplanet, len(time)]
        self.tt_tobs = np.array([])
        # numpy array [nplanet, len(time)]
        self.tt_omc = np.array([])
        # numpy array [len(time)]
        self.tmodel_dtype = np.array([])
        
        self.n_trends = 0 ###DL###
        self.trends_vec = []
        
        self.rng = None

    def __getstate__(self) -> dict:
        """
        For when we have to pickle the class
        :return:
        """
        # set state to __dict__
        state = dict(self.__dict__)
        # return dictionary state
        return state

    def __setstate__(self, state: dict):
        """
        For when we have to unpickle the class

        :param state: dictionary from pickle
        :return:
        """
        # update dict with state
        self.__dict__.update(state)

    def copy(self) -> 'TransitFit':
        """
        Copy class - deep copying values which need copying
        e.g. p0, x0

        :return:
        """
        new = TransitFit()
        #the params
        new.params = self.params
        #the transit model function
        new.tmodel_func = self.tmodel_func ###DL###
        # number of planets
        new.n_planets = self.n_planets
        # number of planets
        new.n_spots = self.n_spots
        # the number of integrations we have
        new.n_int = self.n_int
        # the number of parameters we have
        new.n_param = self.n_param
        # the number of photometric bandpasses we have
        new.n_phot = self.n_phot
        # the total number of valid points (number of photometric bandpasses for
        #   each integration
        new.npt = self.npt
        # numpy array [n_param, n_phot] the initial value of each parameter
        new.p0 = np.array(self.p0)
        # numpy array [n_param] whether we are fitting each parameter [Bool]
        new.fmask = self.fmask
        # numpy array [n_param] whether chromatic fit used for each
        #     parameter [Bool]
        new.wmask = self.wmask
        # priors [n_param]
        new.prior = self.prior
        # name of each parameter
        new.pnames = self.pnames
        # additional arguments passed to mcmc
        new.pkwargs = self.pkwargs
        # the position in the flattened x array [n_param, n_phot]
        new.p0pos = self.p0pos
        #
        #the LD interpolation functions
        new.ld_func = self.ld_func
        #
        # ---------------------------------------------------------------------
        # the data:
        # ---------------------------------------------------------------------
        # the wavelength array [n_phot, n_int]
        new.wavelength = self.wavelength
        # the time array [n_phot, n_int]
        new.time = self.time
        # the integration time array [n_phot, n_int]
        new.itime = self.itime
        # the flux array [n_phot, n_int]
        new.flux = self.flux
        # the flux error array [n_phot, n_int]
        new.fluxerr = self.fluxerr
        # the order array [n_phot, n_int]
        new.orders = self.orders
        # the bin limits in micron [n_phot, 2]   (start,end)
        new.bin_limits = self.bin_limits
        # ---------------------------------------------------------------------
        # parameters that must have shape [n_x]
        # ---------------------------------------------------------------------
        # the initial fitted parameters
        new.x0 = np.array(self.x0)
        new.xpriors = self.xpriors ###DL###
        # name of the fitted params flattened [n_x]
        new.xnames = self.xnames
        new.xfullnames = self.xfullnames
        # length of fitted params flattened [n_x]
        new.n_x = self.n_x
        # numpy array [n_param]
        new.beta = np.array(self.beta)
        # the mapping from x0 onto p0 [n_x, 2] each element
        #   is the tuple poisition in p0
        new.x0pos = self.x0pos
        # ---------------------------------------------------------------------
        # will be filled out by the mcmc
        # ---------------------------------------------------------------------
        # the current position chosen by the sampler
        new.n_tmp = 0
        # the loglikelihood value
        new.llx = 1.0
        # the rejection [rejected, parameter number]   where rejected = 0 for
        #   accepted and rejected = 1 for rejected
        new.ac = []
        # ---------------------------------------------------------------------
        # the x0 to p0 translation dictionary
        new.x0_to_p0 = self.x0_to_p0
        new.tt_n = self.tt_n
        new.tt_tobs = self.tt_tobs
        new.tt_omc = self.tt_omc

        new.tmodel_dtype = self.tmodel_dtype
        
        new.n_trends = self.n_trends ###DL###
        new.trends_vec = self.trends_vec ###DL###

        new.rng = self.rng ### DL###
        
        return new

    def get_fitted_params(self):
        """
        Get the fitted parameters in a flattened way
        Here chromatic values add self.n_phot values and bolometric values add
        a single value

        also sets up the appropriate prior for each fitted param ###DL###

        :return: None, updates self.x0 and self.xnames
        """
        # set up storage
        x0 = []
        xnames = []
        xfullnames = []
        # position of x in p
        p0pos = np.zeros_like(self.p0)
        x0pos = []
        xbetas = []
        #for the priors
        xpriors = [] ###DL###
        # counter for x0 position
        count_x = 0
        # loop around all parameters
        for it, name in enumerate(self.pnames):
            # if we are not fitting this parameter skip
            if not self.fmask[it]:
                p0pos[it] = np.full(self.n_phot, -1)
                continue
            # if we have a wavelength dependence add all terms (one for each
            #   bandpass)
            if self.wmask[it]:
                x0 += list(self.p0[it])
                xpriors += [self.prior[it].copy() for i in range(self.n_phot)] ###DL###
                xnames += [self.pnames[it]] * self.n_phot
                xfullnames += [self.pfullnames[it]] * self.n_phot
                xbetas += [self.pbetas[it]] * self.n_phot
                # add to the positions so we can recover p0 from x0
                p0pos[it] = np.arange(count_x, count_x + self.n_phot)
                # update the x positions
                x0pos += list(zip(np.full(self.n_phot, it), np.arange(self.n_phot)))
                # update x0 position
                count_x += self.n_phot
            # else add the first term (all band passes should have the same
            #   value)
            else:
                x0 += [self.p0[it][0]]
                xpriors += [self.prior[it].copy()] ###DL###
                xnames += [self.pnames[it]]
                xfullnames += [self.pfullnames[it]]
                xbetas += [self.pbetas[it]]
                # add to the positions so we can recover p0 from x0
                p0pos[it] = np.full(self.n_phot, count_x)
                # update x0 position
                count_x += 1
                # update the x positions
                x0pos += [(it, 0)]
        # ---------------------------------------------------------------------
        # set values in class
        self.x0 = np.array(x0)
        self.xpriors = xpriors ###DL###
        self.xnames = np.array(xnames)
        self.xfullnames = np.array(xfullnames)
        self.n_x = len(x0)
        self.p0pos = np.array(p0pos, dtype=int)
        self.x0pos = np.array(x0pos)
        self.xbeta = np.array(xbetas)
        # ---------------------------------------------------------------------
        # define a new x0 to p0 translation dictionary
        x0_to_p0 = dict()
        # loop around the parameters in x and return the index positions of
        #   each p0 position (for each x)
        for it in range(self.n_x):
            # assign each x value
            x0_to_p0[it] = (self.p0pos == it).nonzero()
        self.x0_to_p0 = x0_to_p0
        
        #convert xpriors to be callable directly [func, args]
        for it in range(self.n_x):
            prior = self.xpriors[it]
            if 'func' in prior:
                if prior['func'] not in PRIOR_FUNC:
                    emsg = (f'prior.func is defined for {xnames[x_it]}, '
                            f'thus it must be one of the following:')
                    for pfkey in list(PRIOR_FUNC.keys()):
                        emsg += f'\n\t{pfkey}'
                    raise base_classes.TransitFitExcept(emsg)
                # set the prior function
                func = PRIOR_FUNC[prior['func']]
                # remove 'func' from prior (we don't want it in the function call)
                del prior['func']
            else:
                func = PRIOR_FUNC['uniform']
            
            self.xpriors[it] = [func,prior]

    def update_p0_from_x0(self):
        """
        Take a set of fitted parameters (x0) and project back into the
        full solution (p0)

        :return:
        """
        # loop around all parameters
        for it in range(self.n_x):
            # update the value of p0 from the translated value
            #     (in x0_to_p0 dict)
            self.p0[self.x0_to_p0[it]] = self.x0[it]
            # # find all places where it is valid
            # mask = it == self.p0pos
            # # update p0 with x0 value
            # self.p0[mask] = self.x0[it]

    def update_x0_from_p0(self):
        """
        Take a full solution (p0) and project back into the set of fitted
        parameters (x0)

        :return:
        """
        for it in range(self.n_x):
            # push the value into x
            self.x0[it] = self.p0[tuple(self.x0pos[it])]

    def generate_gibbs_sample(self, beta: np.ndarray):
        # choose random parameter to vary
        param_it = self.rng.integers(0, self.n_x)
        # update the position choosen by the sampler
        self.n_tmp = param_it
        # update the choosen value by a random number drawn from a gaussian
        #   with centre = 0 and fwhm = beta
        self.x0[param_it] += self.rng.normal(0.0, beta[param_it])
        # update just this parameter of the full solution
        self.p0[self.x0_to_p0[param_it]] = self.x0[param_it]
        # self.update_p0_from_x0()

    def generate_demcmc_sample(self, buffer, corbeta: float):
        # get the length of the buffer
        nbuffer = len(buffer[:, 0])
        # update the position choosen by the sampler
        self.n_tmp = -1
        # get two random numbers
        int1, int2 = self.rng.integers(0, nbuffer, size=2)
        # calculate the vector jump
        vector_jump = buffer[int1, :] - buffer[int2, :]
        # apply the vector jump to x0
        self.x0 += vector_jump * corbeta
        # update full solution
        self.update_p0_from_x0()

    def get(self, param_name: str, attribute_name: str):
        # get attribute
        attribute = self.__get_attribute(attribute_name)
        # deal with fitted parameters
        if attribute_name in X_ATTRIBUTES:
            return dict(zip(self.xnames, attribute))[param_name]
        else:
            return dict(zip(self.pnames, attribute))[param_name]

    def view(self, attribute_name: str,
             attribute: Optional[Any] = None):
        """
        View a parameter (i.e. p0, fmask, wmasl, beta, prior)
        with its associated

        :param attribute_name: if parameter is None this must be an attribute of
                     TransitFit, if parameter is defined can any string
                     describing the variable name

        :param attribute: can be unset, but if parameter_name if not in
                          TransitFit must be a vector of length = self.n_param

        examples:
            >> tfit.view('beta', beta[:, 0]) # view the 0th bandpass beta values
            >> tfit.view('p0', tfit.p0[:, 0])  # view the 0th bandpass p0 values
            >> tfit.view('prior')      # view the prior values
            >> tfit.view('fmask')     # view which values are fitted
            >> tfit.view('x0')      # view the flattened fitted parameters

        :return: None, prints to stdout
        """
        # get attribute
        attribute = self.__get_attribute(attribute_name, attribute)
        # deal with fitted parameters
        if attribute_name in X_ATTRIBUTES:
            names = self.xnames
            length = self.n_x
        else:
            names = self.pnames
            length = self.n_param

        # make sure we can view this parameter
        if len(attribute) != length:
            emsg = (f'TransitFit View Error: Cannot view parameter length '
                    f'(on first axis) must be: {length}')
            base_classes.TransitFitExcept(emsg)
        # loop around and print info
        for it in range(length):
            cprint(f'{names[it]:14s}: {attribute[it]}')

    def __get_attribute(self, attribute_name: str,
                        attribute: Optional[Any] = None) -> Any:
        # report error
        if not hasattr(self, attribute_name) and attribute is None:
            emsg = ('TransitFit View Error: Parameter name not set and '
                    '"parameter" not set. Please define one')
            base_classes.TransitFitExcept(emsg)
        elif attribute is None:
            attribute = getattr(self, attribute_name)

        return attribute

    def assign_beta(self, beta_kwargs: Optional[Dict[str, Any]] = None):
        """
        Assign beta from either beta_kwargs[key] = value
        or as fixed fraction of prior range

        note the value can either be a float or a np.ndarray of length the
           number of band passes

        :param beta_kwargs: dictionary, key value pairs to change beta values
                            for a specific parameter
        :return:
        """
        # deal with no beta_kwargs
        if beta_kwargs is None:
            beta_kwargs = dict()

        # start of with all values at zero (all fixed parameters have beta=0)
        self.beta = np.zeros(self.n_x)
        # loop through and find fitted parameters
        for it in range(self.n_x):
            # override beta values set in beta_kwargs
            if self.xnames[it] in beta_kwargs:
                # set beta value
                self.beta[it] = beta_kwargs[self.xnames[it]]
            # override beta value with those set in parameters
            elif self.xbeta[it] is not None:
                # set beta value
                self.beta[it] = self.xbeta[it]
            # else set beta as a one third or prior range
            else:
                #needs FIX !! would not work with non-uniform priors
                #should add clause on prior type and adapt
                self.beta[it] = (tfit.xpriors[it][1]['maximum']-tfit.xpriors[it][1]['minimum'])/3.

    def dump(self, **kwargs):
        """
        Dump the TransitFit object to a pickle file
        :param kwargs:
        :return:
        """
        # add additional data to the pickle
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])
        # get output path
        outpath = self.params['OUTDIR']
        outname = self.params['OUTNAME'] + '_tfit.pickle'
        # deal with no output dir
        if not os.path.exists(outpath):
            os.makedirs(outpath)

        with open(os.path.join(outpath, outname), 'wb') as pfile:
            pickle.dump(self, pfile)

        print('Dumped TransitFit object to file:',os.path.join(outpath, outname))
            
    @staticmethod
    def load(filename) -> 'TransitFit':
        """
        Load the TransitFit object from the pickle file

        :return:
        """
        # load the class and return
        with open(os.path.join(filename), 'rb') as pfile:
            return pickle.load(pfile)



# =============================================================================
# Define prior functions
#     Must have arguments value, **kwargs
#     Must return a float to add to the log prior
#     Must add prior functions to PRIOR_FUNC (below the function definitions)
# =============================================================================
def uniform_prior(value: float, minimum: float, maximum: float) -> float:
    """
    Simple uniform prior (return 0 if within bounds and BADLPR -np.inf
    otherwise)

    :param value: float, parameter value (passed in)
    :param minimum: float, the minimum allowed value
    :param maximum: float, the maximum allowed value
                    (above which lnprior is -np.inf)
    :return:
    """
    # test whether condition is less than the minimum of the prior
    if value < minimum:
        return BADLPR
    # test whether condition is greater than the maximum of the prior
    if value > maximum:
        return BADLPR
    # if we get to here we have passed this priors conditions -> return 1
    return 0.0


def gaussian_prior(value: float, mu: float, sigma: float) -> float:
    """
    Simple gaussian prior (in log space)

    :param value:
    :param mu:
    :param sigma:
    :return:
    """
    return -(value - mu) ** 2 / sigma ** 2

def trunc_gaussian_prior(value: float, mu: float, sigma: float, vmin: float, vmax: float) -> float:
    """
    Simple truncated gaussian prior (in log space)

    :param value:
    :param mu:
    :param sigma:
    :param vmin:
    :param vmax:
    :return:
    """
    # test whether value is less than the minimum of the prior
    if value < vmin:
        return BADLPR
    # test whether value is greater than the maximum of the prior
    if value > vmax:
        return BADLPR

    return -(value - mu) ** 2 / sigma ** 2



# Must add all prior functions to this dictionary for it to work
#    they key can then be used in the yaml
#    parameter:
#       prior:
#           func: key
PRIOR_FUNC = dict()
PRIOR_FUNC['uniform'] = uniform_prior
PRIOR_FUNC['gaussian'] = gaussian_prior
PRIOR_FUNC['tgaussian'] = trunc_gaussian_prior


# =============================================================================
# Define functions
# =============================================================================
def setup_params_mcmc(params: ParamDict, data: InputData) -> TransitFit:
    """
    Using params and data load everything in to the Transit Fit data class

    :param params: ParamDict, parameter dictionary of constants
    :param data: InputData, input data class

    :return: transit fit data class
    """
    # set function name
    func_name = __NAME__ + '.get_starting_params()'
    # get number of wavelength bandpasses
    n_phot = data.n_phot
    # get the number of planets to add
    n_planets = params['NPLANETS']
    # get the number of spots ###DL###
    n_spots = params['NSPOTS']    ###DL###    
    # get the number of trends ###DL###
    n_trends = params['NTRENDS']    ###DL###
    #get the transit model
    model = params['MODEL']
    TPS_ORDERED = models.TPS_ORDERED[model]
    TPSP_ORDERED = models.TPSP_ORDERED[model]
    TPP_ORDERED = models.TPP_ORDERED[model]
    TPH_ORDERED = models.TPH_ORDERED[model]
    TP_KWARGS = models.TP_KWARGS[model]

    # get the number of parameters we are adding
    n_param = len(TPS_ORDERED) + n_planets*len(TPP_ORDERED) + len(TPH_ORDERED) + \
              n_spots*len(TPSP_ORDERED) + n_trends ###DL###
    # -------------------------------------------------------------------------
    # set up storage
    transit_p0 = np.zeros([n_param, n_phot])
    transit_fmask = np.zeros(n_param, dtype=bool)
    transit_wmask = np.zeros(n_param, dtype=bool)
    transit_prior = []
    transit_pnames = []
    transit_pfullnames = []
    transit_pbetas = []
    # -------------------------------------------------------------------------
    # get the transit fit stellar params
    # -------------------------------------------------------------------------
    pnum = 0
    # loop around stellar parameters
    for key in TPS_ORDERED:
        pout = __assign_pvalue(key, params, n_phot, func_name)
        p0, fmask, wmask, prior, pname, pbeta = pout
        # add values to storage
        transit_p0[pnum] = p0
        transit_fmask[pnum] = fmask
        transit_wmask[pnum] = wmask
        transit_prior.append(prior)
        transit_pnames.append(pname)
        transit_pfullnames.append(key)
        transit_pbetas.append(pbeta)
        # add to the parameter number
        pnum += 1
    # -------------------------------------------------------------------------
    # get the spot params
    # -------------------------------------------------------------------------
    # loop around spots
    for nspot in range(1, n_spots + 1):
        # need the spot key
        skey = f'SPOT{nspot}'
        # check that we have thisspot
        if skey not in params:
            emsg = (f'ParamError: spot {nspot} not found. '
                    f'Please add or adjust "NSPOTS" parameter.')
            raise base_classes.TransitFitExcept(emsg)
        # get spot dictionary
        spotdict = params[skey]
        # loop around spotN parameters
        for key in TPSP_ORDERED:
            pout = __assign_pvalue(key, spotdict, n_phot, func_name)
            p0, fmask, wmask, prior, pname, pbeta = pout
            # add values to storage
            transit_p0[pnum] = p0
            transit_fmask[pnum] = fmask
            transit_wmask[pnum] = wmask
            transit_prior.append(prior)
            transit_pnames.append(f'{pname}{nspot}')
            transit_pfullnames.append(f'{key}_{nspot}')
            transit_pbetas.append(pbeta)
            # add to the parameter number
            pnum += 1  
    # -------------------------------------------------------------------------
    # get the transit fit planet params
    # -------------------------------------------------------------------------
    # loop around planets
    for nplanet in range(1, n_planets + 1):
        # need the planet key
        pkey = f'PLANET{nplanet}'
        # check that we have this planet
        if pkey not in params:
            emsg = (f'ParamError: planet {nplanet} not found. '
                    f'Please add or adjust "NPLANETS" parameter.')
            raise base_classes.TransitFitExcept(emsg)
        # get planet dictionary
        planetdict = params[pkey]
        # loop around planetN parameters
        for key in TPP_ORDERED:
            pout = __assign_pvalue(key, planetdict, n_phot, func_name)
            p0, fmask, wmask, prior, pname, pbeta = pout
            # add values to storage
            transit_p0[pnum] = p0
            transit_fmask[pnum] = fmask
            transit_wmask[pnum] = wmask
            transit_prior.append(prior)
            transit_pnames.append(f'{pname}{nplanet}')
            transit_pfullnames.append(f'{key}_{nplanet}')
            transit_pbetas.append(pbeta)
            # add to the parameter number
            pnum += 1
    # -------------------------------------------------------------------------
    # get the transit fit hyper params
    # -------------------------------------------------------------------------
    # loop around hyper parameters
    for key in TPH_ORDERED:
        pout = __assign_pvalue(key, params, n_phot, func_name)
        p0, fmask, wmask, prior, pname, pbeta = pout
        # hyper parameters are set to zero if not in fit mode
        transit_p0[pnum] = p0
        # add other values to storage
        transit_fmask[pnum] = fmask
        transit_wmask[pnum] = wmask
        transit_prior.append(prior)
        transit_pnames.append(pname)
        transit_pfullnames.append(key)
        transit_pbetas.append(pbeta)
        # add to the parameter number
        pnum += 1
    
    ###DL###
    # -------------------------------------------------------------------------
    # get the transit fit trend params
    # -------------------------------------------------------------------------
    # loop around trends parameters
    for ntrend in range(1, n_trends + 1):
        # need the planet key
        key = f'TREND_C{ntrend}'
        # check that we have this planet
        if key not in params:
            emsg = (f'ParamError: trend {ntrend} not found. '
                    f'Please add or adjust "NTRENDS" parameter.')
            raise base_classes.TransitFitExcept(emsg)
        pout = __assign_pvalue(key, params, n_phot, func_name)
        p0, fmask, wmask, prior, pname, pbeta = pout
        transit_p0[pnum] = p0
        # add other values to storage
        transit_fmask[pnum] = fmask
        transit_wmask[pnum] = wmask
        transit_prior.append(prior)
        transit_pnames.append(f'{pname}{ntrend}')
        transit_pfullnames.append(key)
        transit_pbetas.append(pbeta)
        #append parameter index number here? p0_tc_ind.append(pnum)
        # add to the parameter number
        pnum += 1

    # -------------------------------------------------------------------------
    # create a class for the fit
    # -------------------------------------------------------------------------
    tfit = TransitFit()
    #add the params
    tfit.params = params ###DL###
    # add the data to the transit fit
    tfit.tmodel_func= models.TMODEL_FUNC[model] ###DL###
    tfit.wavelength = data.phot['WAVELENGTH']
    tfit.time = data.phot['TIME']
    tfit.itime = data.phot['ITIME']
    tfit.flux = data.phot['FLUX']
    tfit.fluxerr = data.phot['FLUX_ERROR']
    tfit.orders = data.phot['ORDERS']
    tfit.bin_limits = data.phot['BIN_LIMITS']
    # add the parameters
    tfit.n_planets = n_planets ###DL###
    tfit.n_spots = n_spots ###DL###
    tfit.p0 = transit_p0
    tfit.fmask = transit_fmask
    tfit.wmask = transit_wmask
    tfit.prior = transit_prior
    tfit.pnames = np.array(transit_pnames)
    tfit.pfullnames = np.array(transit_pfullnames)
    tfit.pbetas = np.array(transit_pbetas)
    # set the number of params
    tfit.n_param = len(transit_p0)
    # set the number of photometric bandpasses
    tfit.n_phot = int(data.n_phot)
    # set the number of integrations
    tfit.n_int = int(data.n_int)
    # set the number of trends
    tfit.n_trends = n_trends ###DL###
    tfit.trends_vec = [None]*n_trends ###DL###
    # set the total number of valid points (number of photometric
    #   bandpasses for each integration)
    # TODO: if we have a data mask must not count invalid points
    tfit.npt = tfit.time.size
    # -------------------------------------------------------------------------
    # set additional arguments
    # -------------------------------------------------------------------------
    tfit.pkwargs = dict()
    # loop through transit param additional keyword arguments
    for key in TP_KWARGS:
        # if this key exists in params set it
        if key in params:
            tfit.pkwargs[key] = params[key]
    # -------------------------------------------------------------------------
    # update fitted parameters
    # -------------------------------------------------------------------------
    # set x0 and xnames
    tfit.get_fitted_params()
    # start of beta
    tfit.beta = np.zeros_like(tfit.x0)

    # deal with transit timing
    tfit.tt_n = np.zeros(n_planets, dtype=int)
    tfit.tt_tobs = np.zeros((n_planets, tfit.n_int))
    tfit.tt_omc = np.zeros((n_planets, tfit.n_int))

    # transit model data type
    tfit.tmodel_dtype = np.zeros(tfit.n_int, dtype=int)
    
    # assign beta values
    tfit.assign_beta()

    # -------------------------------------------------------------------------
    # return the transit fit class
    # -------------------------------------------------------------------------
    return tfit


def lnpriors(tfit) -> float:
    """
    Log prior function - basically runs the prior function for
    each parameter and each bandpass

    If any fail returns immediately

    :param tfit: the transit fit class

        tfit must have attributes:
            n_x: int, the number of fitted parameters
            x0: np.ndarray - the trial solution [n_x]
            xpriors: the prior function and args [n_x][func, {args}]

    :return: float, either lnprior value (if good) or -np.inf (if bad)
    """
    # set initial value of loglikelihood
    lnprior = 1.0
    # loop around all fitted parameters and test priors
    for x_it in range(tfit.n_x):      
        pfunc=tfit.xpriors[x_it][0]
        pargs=tfit.xpriors[x_it][1]
        lnprior += pfunc(tfit.x0[x_it], **pargs)
        
        if not (lnprior > BADLPR):
            return BADLPR

    # if we have got to here we return the good loglikelihood (all priors have
    #    passed)
    return lnprior

def lnprob(tfit: TransitFit) -> float:
    """
    The loglikelihood function

    :param tfit: the transit fit class

        tfit must have attributes:
            time: np.ndarray
            itime: np.ndarray
            flux: np.ndarray
            fluxerr: np.ndarray
            n_phot: int, the number of band passes
            n_param: int, the number of parameters (fitted and fixed)
            ntt:
            tobs:
            omc:
            p0: np.ndarray - the trial solution [n_param, n_phot]
            pnames: np.ndarray [n_param, n_phot] {STRING} - parameter names

    :return:
    """
    # -------------------------------------------------------------------------
    # lets get the values out of tfit (shallow copy)
    # -------------------------------------------------------------------------
    # the data
#     time = tfit.time
#     itime = tfit.itime
    flux = tfit.flux
    fluxerr = tfit.fluxerr
    # -------------------------------------------------------------------------
    # other parameters
    n_phot = tfit.n_phot
    #     ntt = tfit.pkwargs['NTT']
    #     tobs = tfit.pkwargs['T_OBS']
    #     omc = tfit.pkwargs['OMC']
    #     nintg = tfit.pkwargs['NINTG']
    # trial solution
#     sol = np.array(tfit.p0)
    # -------------------------------------------------------------------------
    # the hyper parameters
    # photometric error scale (DSC) for this bandpass
    dscale = tfit.get('DSC', 'p0')
#     # GP Kernel Amplitude (ASC) for this bandpass
#     ascale = tfit.get('ASC', 'p0')
#     # GP length scale (LSC) for this bandpass
#     lscale = tfit.get('LSC', 'p0')
#     # deal with the fitting of hyper parameters
#     fit_error_scale = tfit.get('DSC', 'fmask')
#     fit_amplitude_scale = tfit.get('ASC', 'fmask')
#     fit_length_scale = tfit.get('LSC', 'fmask')
    # -------------------------------------------------------------------------
    # Select model type: 1 = GP model, 2 = uncorrelated noise model
#     model_type = int(fit_amplitude_scale | fit_length_scale)
    model_type = 0 ###DL###
    
    # -------------------------------------------------------------------------
    # Step 1: Prior calculation
    # -------------------------------------------------------------------------
    # check priors
    logl = lnpriors(tfit)

    # if out of limits return here
    if not (logl > BADLPR):
        return BADLPR
    # -------------------------------------------------------------------------
    # Step 2: Calculate loglikelihood per band pass
    # -------------------------------------------------------------------------
    # QUESTION: Can we parallelize this?
    # QUESTION: If one phot_it is found to be inf, we can skip rest?
    # loop around band passes
    for phot_it in range(n_phot):        
        #compute model for this bandpass
        model=tfit.tmodel_func(tfit, phot_it)
            
        # Question: What about the GP model, currently it does not update logl
        # non-correlated noise-model
        if model_type == 0:
            sqrerr = np.square(fluxerr[phot_it] * dscale[phot_it])
            sqrdiff = np.square(flux[phot_it] - model)
            sumtot = -0.5 * bn.nansum(np.log(sqrerr) + sqrdiff / sqrerr)
        # check for NaNs -- we don't want these.
        if np.isfinite(sumtot):
            logl += sumtot
        # else we return our bad log likelihood
        else:
            return BADLPR
    # if we have got to here we return the good loglikelihood (sum of each
    #   bandpass)
    return logl


def mhg_mcmc(tfit: TransitFit, loglikelihood: Any, beta: np.ndarray,
             buffer: Optional[np.ndarray] = None,
             corbeta: Optional[float] = None) -> TransitFit:
    """
    A Metropolis-Hastings MCMC with Gibbs sampler

    :param tfit: the Transit fit class
    :param loglikelihood: The loglikelihodd function here
                          loglikelihood must have a single argument of type
                          Transit fit class
    :param beta: Gibb's factor : characteristic step size for each parameter
    :param buffer: Not used for mhg_mcmc (used in de_mhg_mcmc)
    :param corbeta: Not used for mhg_mcmc (used in de_mhg_mcmc)

    :return:
    """
    # we do not use buffer and corbeta here (used for de_mhg_mcmc)
    _ = buffer, corbeta
    # copy initial parameters (ready for a reset if rejected)
    p0 = tfit.p0.copy()
    x0 = tfit.x0.copy()
    llx0 = tfit.llx
    # -------------------------------------------------------------------------
    # Step 1: Generate trial state
    # -------------------------------------------------------------------------
    # Generate trial state with Gibbs sampler
    tfit.generate_gibbs_sample(beta)
    # -------------------------------------------------------------------------
    # Step 2: Compute log(p(x'|d))=log(p(x'))+log(p(d|x'))
    # -------------------------------------------------------------------------
    tfit.llx = loglikelihood(tfit)
    # -------------------------------------------------------------------------
    # Step 3 Compute the acceptance probability
    # -------------------------------------------------------------------------
    # llxt can be -np.inf --> therefore we suppress overflow warning here
    with warnings.catch_warnings(record=True) as _:
#         alpha = min(np.exp(tfit.llx - llx0), 1.0) #is this min() necessary?
        alpha = np.exp(tfit.llx - llx0)
    # -------------------------------------------------------------------------
    # Step 4 Accept or reject trial
    # -------------------------------------------------------------------------
    # generate a random number
    test = tfit.rng.random()
    # if test is less than our acceptance level accept new trial
    if test <= alpha:
        tfit.ac = [0, tfit.n_tmp]
    # else we reject and start from previous point (tfit0)
    else:
        tfit.x0 = x0
        tfit.p0 = p0
        tfit.llx = llx0
        tfit.ac = [1, tfit.n_tmp]
    # return tfit instance
    return tfit


def de_mhg_mcmc(tfit: TransitFit, loglikelihood: Any, beta: np.ndarray,
                buffer: Optional[np.ndarray] = None,
                corbeta: Optional[float] = None) -> TransitFit:
    """
    A Metropolis-Hastings MCMC with Gibbs sampler

    :param tfit: the Transit fit class
    :param loglikelihood: The loglikelihodd function here
                          loglikelihood must have a single argument of type
                          Transit fit class
    :param beta: ibb's factor : characteristic step size for each parameter
    :param buffer: np.ndarray, previous chains used as a buffer state to
                   calculate a vector jump
    :param corbeta: float, scale factor correction to the vector jump

    :return:
    """
    # deal with no buffer or corbeta
    if buffer is None and corbeta is None:
        emsg = 'buffer and corbeta must not be None for de_mhg_mcmc()'
        raise base_classes.TransitFitExcept(emsg)
    # copy initial parameters (ready for a reset if rejected)
    p0 = tfit.p0.copy()
    x0 = tfit.x0.copy()
    llx0 = tfit.llx
    # draw a random number to decide which sampler to use
    rsamp = tfit.rng.random()
    # -------------------------------------------------------------------------
    # Step 1: Generate trial state
    # -------------------------------------------------------------------------
    # if rsamp is less than 0.5 use a Gibbs sampler
    if rsamp < 0.5:
        # Generate trial state with Gibbs sampler
        tfit.generate_gibbs_sample(beta)
    # else we use our deMCMC sampler
    else:
        tfit.generate_demcmc_sample(buffer, corbeta)
    # -------------------------------------------------------------------------
    # Step 2: Compute log(p(x'|d))=log(p(x'))+log(p(d|x'))
    # -------------------------------------------------------------------------
    tfit.llx = loglikelihood(tfit)
    # -------------------------------------------------------------------------
    # Step 3 Compute the acceptance probability
    # -------------------------------------------------------------------------
    alpha = min(np.exp(tfit.llx - llx0), 1.0)
    # -------------------------------------------------------------------------
    # Step 4 Accept or reject trial
    # -------------------------------------------------------------------------
    # generate a random number
    test = tfit.rng.random()
    # if test is less than our acceptance level accept new trial
    if test <= alpha:
        tfit.ac = [0, tfit.n_tmp]
    # else we reject and start from previous point (tfit0)
    else:
        tfit.x0 = x0
        tfit.p0 = p0
        tfit.llx = llx0
        tfit.ac = [1, tfit.n_tmp]
    # return tfit instance
    return tfit


def beta_rescale(tfit: TransitFit,
                 mcmcfunc, loglikelihood,) -> np.ndarray:
    """
    Calculate rescaling of beta to improve acceptance rates

    :param tfit: Transit fit class of parameters
    :param mcmcfunc: MCMC function
            - arguments: tfit: TransitFit,
                         loglikelihood: Any,
                         beta: np.ndarray,
                         buffer: np.ndarray, corbeta: float
    :param loglikelihood: log likelihood function
        - arguments: tfit: TransitFit
    :return:
    """
    # get alow, ahigh define the acceptance rate range we want
    a_low = tfit.params['BETA_ALOW']
    a_high = tfit.params['BETA_AHIGH']
    # parameter controling how fast corscale changes - from Gregory 2011.
    delta = tfit.params['BETA_DELTA']
    # Number of steps in the beta rescale
    nsteps = tfit.params['NITER_COR']
    # burn-in for the beta rescale
    burnin_cor = tfit.params['BURNIN_COR']
    # maximum number of iterations for the beta rescale
    nloopsmax = tfit.params['BETA_NLOOPMAX']
    # number of fitted parameters
    n_x = tfit.n_x
    # copy tfit (for beta rescale only)
    tfitb = tfit.copy()
    # -------------------------------------------------------------------------
    # total number of accepted proposals
    nacor = np.zeros(n_x)
    # total number of accepted proposals immediately prior to rescaling
    nacor_sub = np.zeros(n_x)
    # total number of proposals
    nprop_p = np.zeros(n_x)
    # total number of proposals immediately prior to rescaling
    nprop_psub = np.zeros(n_x)
    # correction rescaling for each parameter
    corscale = np.ones(n_x)
    # -------------------------------------------------------------------------
    # print progress
    cprint('Beta Rescale: Initial Gen Chain', level='info')
    # initial run of gen chain
    hchain, hrejects, hlls = genchain(tfitb, nsteps, tfitb.beta, mcmcfunc,
                                loglikelihood, progress=True)
    # update x0 and p0 with the last chain
    tfitb = update_x0_p0_from_chain(tfitb, hchain, -1)
    # -------------------------------------------------------------------------
    # get the length of the chain
    nchain = hchain.shape[0]
    # calculate the initial values of n_prop and n_acc
    for chain_it in range(burnin_cor, nchain):
        # get the parameter number
        x_it = hrejects[chain_it, 1]
        # update the total number of proposals for this parameter number
        nprop_p[x_it] += 1
        # update total number of accepted proposals (hreject = 1 for rejection)
        nacor[x_it] += 1 - hrejects[chain_it, 0]
    # -------------------------------------------------------------------------
    # calculate the initial acceptance rate
    ac_rate = nacor / nprop_p
    # afix is an integer flag to indicate which beta entries need ot be
    #   updated - those within the limits of a_high and a_low do not need
    #   to be updated
    a_fix = ~((ac_rate < a_high) & (ac_rate > a_low))
    # -------------------------------------------------------------------------
    # Iterate around until all parameters are accepted (a_fix = False) or
    #   we hit the maximum number of iterations permitted
    # -------------------------------------------------------------------------
    # start counter to track number of iterations
    nloop = 1
    # condition based on all parameters being False (in a_fix)
    while np.sum(a_fix) > 0:
        # ---------------------------------------------------------------------
        # if we have a previous count on the number of proposal copy it
        #   over the total count
        if nloop > 1:
            nprop_p = np.array(nprop_psub)
            nacor = np.array(nacor_sub)
        # reset the sub counts for this loop
        nprop_psub = np.zeros(n_x)
        nacor_sub = np.zeros(n_x)
        # ---------------------------------------------------------------------
        # Make another chain starting with xin
        # New beta for Gibbs sampling
        beta_in = tfitb.beta * corscale
        # ---------------------------------------------------------------------
        # print progress
        cprint(f'Beta Rescale: Gen Chain loop {nloop}')
        # initial run of gen chain
        hchain, hrejects, hlls = genchain(tfitb, nsteps, beta_in, mcmcfunc,
                                    loglikelihood, progress=True)
        # update x0 and p0 with the last chain
        tfitb = update_x0_p0_from_chain(tfitb, hchain, -1)
        # ---------------------------------------------------------------------
        # scan through Markov-Chains and count number of states and acceptances
        # get the length of the chain
        nchain = hchain.shape[0]
        # calculate the initial values of n_prop and n_acc
        for chain_it in range(burnin_cor, nchain):
            # get the parameter number
            x_it = hrejects[chain_it, 1]
            # update the total number of proposals for this parameter number
            nprop_p[x_it] += 1
            # update total number of accepted proposals (hreject=1=rejection)
            nacor[x_it] += 1 - hrejects[chain_it, 0]
            # Update current number of proposals
            nprop_psub[x_it] += 1
            # Update current number of accepted proposals
            nacor_sub[x_it] += 1 - hrejects[chain_it, 0]
        # ---------------------------------------------------------------------
        # calculate the acceptance rates for each parameter
        ac_rate = nacor_sub / nprop_psub
        ac_rate_sub = (nacor - nacor_sub) / (nprop_p - nprop_psub)
        # calculate correction scale (only for a_fix = True)
        part1 = 0.75 * (ac_rate_sub[a_fix] + delta)
        part2 = 0.25 * (1.0 - ac_rate_sub[a_fix] + delta)
        corscale[a_fix] = np.abs(corscale[a_fix] * (part1 / part2) ** 0.25)
        # ---------------------------------------------------------------------
        # print current acceptance
        cprint(f'Beta Rescale: Loop {nloop}, Current Acceptance: ')
        for x_it in range(n_x):
            cprint(f'\t{tfitb.xnames[x_it]:3s}:{ac_rate[x_it]}')
        # ---------------------------------------------------------------------
        # check which parameters have achieved required acceptance rate
        #  - those within the limits of a_high and a_low do not need
        #    to be updated
        a_fix = ~((ac_rate < a_high) & (ac_rate > a_low))
        # ---------------------------------------------------------------------
        # if too many iterations, then we give up and exit
        if nloop >= nloopsmax:
            break
        # else update the count
        else:
            nloop += 1
    # -------------------------------------------------------------------------
    # print the final acceptance
    # print current acceptance
    cprint(f'Beta Rescale: Final Acceptance: ')
    for x_it in range(n_x):
        cprint(f'\t{tfitb.xnames[x_it]:3s}:{ac_rate[x_it]}')
    # -------------------------------------------------------------------------
    # return the correction scale
    return corscale

def beta_rescale_nwalker(tfit: TransitFit,
                 mcmcfunc, loglikelihood,) -> np.ndarray:
    """
    Calculate rescaling of beta to improve acceptance rates. This version uses N walkers
    rather than a single one.

    :param tfit: Transit fit class of parameters
    :param mcmcfunc: MCMC function
            - arguments: tfit: TransitFit,
                         loglikelihood: Any,
                         beta: np.ndarray,
                         buffer: np.ndarray, corbeta: float
    :param loglikelihood: log likelihood function
        - arguments: tfit: TransitFit
    :return:
    """
    # get alow, ahigh define the acceptance rate range we want
    a_low = tfit.params['BETA_ALOW']
    a_high = tfit.params['BETA_AHIGH']
    # parameter controling how fast corscale changes - from Gregory 2011.
#     delta = tfit.params['BETA_DELTA'] #don't change anymore

    # maximum number of iterations for the beta rescale
    nloopsmax = tfit.params['BETA_NLOOPMAX']
    # number of fitted parameters
    n_x = tfit.n_x
    # copy tfit (for beta rescale only)
#     tfitb = tfit.copy()
    # instantiate a sampler object
    sampler = Sampler(tfit, mode='trial')
    # -------------------------------------------------------------------------
    # total number of accepted proposals
    nacor = np.zeros(n_x)
    # total number of proposals
    nprop_p = np.zeros(n_x)
    # correction rescaling for each parameter
    corscale = np.ones(n_x)
    # flag for parameters that need beta updating
    a_fix = np.ones(n_x,dtype=bool)
    # -------------------------------------------------------------------------
#     # print progress
#     cprint('Beta Rescale: Initial Gen Chain', level='info')
#     # initial run of gen chain
#     hchain, hrejects, hlls = sampler.single_loop_beta(loglikelihood,mcmcfunc)

#     # update x0 and p0 with the last chain
#  #   sampler.tfit = update_x0_p0_from_chain(sampler.tfit, hchain, -1)
#     # -------------------------------------------------------------------------
#     # get the length of the chain
#     nchain = hchain.shape[0]
#     # calculate the initial values of n_prop and n_acc
#     for chain_it in range(nchain):
#         # get the parameter number
#         x_it = hrejects[chain_it, 1]
#         # update the total number of proposals for this parameter number
#         nprop_p[x_it] += 1
#         # update total number of accepted proposals (hreject = 1 for rejection)
#         nacor[x_it] += 1 - hrejects[chain_it, 0]
#     # -------------------------------------------------------------------------
#     # calculate the initial acceptance rate
#     ac_rate = nacor / nprop_p
#     # afix is an integer flag to indicate which beta entries need to be
#     #   updated - those within the limits of a_high and a_low do not need
#     #   to be updated
#     a_fix = ~((ac_rate < a_high) & (ac_rate > a_low))
    # -------------------------------------------------------------------------
    # Iterate around until all parameters are accepted (a_fix = False) or
    #   we hit the maximum number of iterations permitted
    # -------------------------------------------------------------------------
    # start counter to track number of iterations
    nloop = 1
    sampler.nloop=nloop
    # condition based on all parameters being False (in a_fix)
    while a_fix.any():
        if nloop>1:
            # update corscale
#             part1 = 0.75 * (ac_rate[a_fix] + 0.01)
#             part2 = 0.25 * (1.0 - ac_rate[a_fix] + 0.01)
#             corscale[a_fix] *= (part1 / part2) ** 0.4 #exponent control speed of change
            #always update all betas, even converged ones
            part1 = 0.75 * (ac_rate + 0.01)
            part2 = 0.25 * (1.0 - ac_rate + 0.01)
            corscale *= (part1 / part2) ** 0.5 #exponent control speed of change
        # ---------------------------------------------------------------------
        # Make another chain starting
        # New beta for Gibbs sampling
        beta_in = sampler.tfit.beta * corscale
        # ---------------------------------------------------------------------
        # print progress
        cprint(f'Beta Rescale: Gen Chain loop {nloop}')
        # initial run of gen chain
        hchain, hrejects, hlls = sampler.single_loop_beta(loglikelihood,
                                mcmcfunc, beta=beta_in)
        # update x0 and p0 with highest likelihood point
        sampler.tfit = update_x0_p0_from_chain(sampler.tfit, hchain, hlls.argmax())
        # ---------------------------------------------------------------------
        # scan through Markov-Chains and count number of states and acceptances
        # get the length of the chain
        nchain = hchain.shape[0]
        # calculate the initial values of n_prop and n_acc
        # reset the counts for this loop
        nprop = np.zeros(n_x)
        nac = np.zeros(n_x)
        for chain_it in range(nchain):
            # get the parameter number
            x_it = hrejects[chain_it, 1]
            # update the total number of proposals for this parameter number
            nprop[x_it] += 1
            # update total number of accepted proposals (hreject=1=rejection)
            nac[x_it] += 1 - hrejects[chain_it, 0]
        # ---------------------------------------------------------------------
        # calculate the acceptance rates for each parameter
        ac_rate = nac / nprop
        # update a_fix
        a_fix = ~((ac_rate < a_high) & (ac_rate > a_low))
        # ---------------------------------------------------------------------
        # print current acceptance
        cprint(f'Beta Rescale: Loop {nloop}, Current Acceptance & beta values: ',level='info',timestamp=0)
        for x_it in range(n_x):
            cprint(f"\t{x_it:4d}-{tfit.xnames[x_it]:3s}:{ac_rate[x_it]} "+
                   f"ok?={~a_fix[x_it]} beta={beta_in[x_it]} nprop={nprop[x_it]}",level='info',timestamp=0)
        cprint("\tNumber of parameters with beta converged(not-converged):"+
               f"{np.sum(~a_fix)}({np.sum(a_fix)})",level='info',timestamp=0)
        cprint(f"\t[min ac_rate={ac_rate.min()}, max ac_rate={ac_rate.max()}]",level='info',timestamp=0)

        # ---------------------------------------------------------------------
        # if too many iterations, then we give up and exit
        if nloop >= nloopsmax:
            break
        # else update the count
        else:
            nloop += 1
            sampler.nloop+=1
    # -------------------------------------------------------------------------
    # return the correction scale
    return corscale

def beta_rescale_nwalker_old(tfit: TransitFit,
                 mcmcfunc, loglikelihood,) -> np.ndarray:
    """
    Calculate rescaling of beta to improve acceptance rates. This version uses N walkers
    rather than a single one.

    :param tfit: Transit fit class of parameters
    :param mcmcfunc: MCMC function
            - arguments: tfit: TransitFit,
                         loglikelihood: Any,
                         beta: np.ndarray,
                         buffer: np.ndarray, corbeta: float
    :param loglikelihood: log likelihood function
        - arguments: tfit: TransitFit
    :return:
    """
    # get alow, ahigh define the acceptance rate range we want
    a_low = tfit.params['BETA_ALOW']
    a_high = tfit.params['BETA_AHIGH']
    # parameter controling how fast corscale changes - from Gregory 2011.
    delta = tfit.params['BETA_DELTA']
    # # Number of steps in the beta rescale
    # nsteps = tfit.params['NITER_COR']
    # # burn-in for the beta rescale
    # burnin_cor = tfit.params['BURNIN_COR']
    # maximum number of iterations for the beta rescale
    nloopsmax = tfit.params['BETA_NLOOPMAX']
    # number of fitted parameters
    n_x = tfit.n_x
    # copy tfit (for beta rescale only)
    tfitb = tfit.copy()
    # -------------------------------------------------------------------------
    # total number of accepted proposals
    nacor = np.zeros(n_x)
    # total number of accepted proposals immediately prior to rescaling
    nacor_sub = np.zeros(n_x)
    # total number of proposals
    nprop_p = np.zeros(n_x)
    # total number of proposals immediately prior to rescaling
    nprop_psub = np.zeros(n_x)
    # correction rescaling for each parameter
    corscale = np.ones(n_x)
    # -------------------------------------------------------------------------
    # print progress
    cprint('Beta Rescale: Initial Gen Chain', level='info')
    # initial run of gen chain
    sampler = Sampler(tfitb, mode='trial')
    hchain, hrejects, hlls = sampler.single_loop_beta(loglikelihood,mcmcfunc)

    # update x0 and p0 with the last chain
 #   sampler.tfit = update_x0_p0_from_chain(sampler.tfit, hchain, -1)
    # -------------------------------------------------------------------------
    # get the length of the chain
    nchain = hchain.shape[0]
    # calculate the initial values of n_prop and n_acc
    for chain_it in range(nchain):
        # get the parameter number
        x_it = hrejects[chain_it, 1]
        # update the total number of proposals for this parameter number
        nprop_p[x_it] += 1
        # update total number of accepted proposals (hreject = 1 for rejection)
        nacor[x_it] += 1 - hrejects[chain_it, 0]
    # -------------------------------------------------------------------------
    # calculate the initial acceptance rate
    ac_rate = nacor / nprop_p
    # afix is an integer flag to indicate which beta entries need to be
    #   updated - those within the limits of a_high and a_low do not need
    #   to be updated
    a_fix = ~((ac_rate < a_high) & (ac_rate > a_low))
    # -------------------------------------------------------------------------
    # Iterate around until all parameters are accepted (a_fix = False) or
    #   we hit the maximum number of iterations permitted
    # -------------------------------------------------------------------------
    # start counter to track number of iterations
    nloop = 1
    sampler.nloop=nloop
    # condition based on all parameters being False (in a_fix)
    while a_fix.any() > 0:
        # ---------------------------------------------------------------------
        # if we have a previous count on the number of proposal copy it
        #   over the total count
        if nloop > 1:
            nprop_p = np.array(nprop_psub)
            nacor = np.array(nacor_sub)
        # reset the sub counts for this loop
        nprop_psub = np.zeros(n_x)
        nacor_sub = np.zeros(n_x)
        # ---------------------------------------------------------------------
        # Make another chain starting with xin
        # New beta for Gibbs sampling
        beta_in = tfitb.beta * corscale
        # ---------------------------------------------------------------------
        # print progress
        cprint(f'Beta Rescale: Gen Chain loop {nloop}')
        # initial run of gen chain
        hchain, hrejects, hlls = sampler.single_loop_beta(loglikelihood,
                                mcmcfunc, beta=beta_in)
        # update x0 and p0 with the last chain
   #     sampler.tfit = update_x0_p0_from_chain(sampler.tfit, hchain, -1)
        # ---------------------------------------------------------------------
        # scan through Markov-Chains and count number of states and acceptances
        # get the length of the chain
        nchain = hchain.shape[0]
        # calculate the initial values of n_prop and n_acc
        for chain_it in range(nchain):
            # get the parameter number
            x_it = hrejects[chain_it, 1]
            # update the total number of proposals for this parameter number
            nprop_p[x_it] += 1
            # update total number of accepted proposals (hreject=1=rejection)
            nacor[x_it] += 1 - hrejects[chain_it, 0]
            # Update current number of proposals
            nprop_psub[x_it] += 1
            # Update current number of accepted proposals
            nacor_sub[x_it] += 1 - hrejects[chain_it, 0]
        # ---------------------------------------------------------------------
        # calculate the acceptance rates for each parameter
        ac_rate = nacor_sub / nprop_psub
        ac_rate_sub = (nacor - nacor_sub) / (nprop_p - nprop_psub)
        # calculate correction scale (only for a_fix = True)
#         part1 = 0.75 * (ac_rate_sub[a_fix] + delta) #original
#         part2 = 0.25 * (1.0 - ac_rate_sub[a_fix] + delta) #original
#         corscale[a_fix] = np.abs(corscale[a_fix] * (part1 / part2) ** 0.25) #original
        part1 = 0.75 * (ac_rate[a_fix] + 0.01)
        part2 = 0.25 * (1.0 - ac_rate[a_fix] + 0.01)
        corscale[a_fix] = corscale[a_fix] * (part1 / part2) ** 0.5

        #initial iteration is useless currently... its ac rates not used ????
        #could do just the main loop, no need for initial iteration
        #sampler.tfit is a copy, so not updated
        
        # ---------------------------------------------------------------------
        # print current acceptance
        cprint(f'Beta Rescale: Loop {nloop}, Current Acceptance: ')
        for x_it in range(n_x):
#             cprint(f'\t{tfitb.xnames[x_it]:3s}:{ac_rate[x_it]}')
            cprint(f'\t{tfitb.xnames[x_it]:3s}:{ac_rate[x_it]} ac_bef={ac_rate_sub[x_it]} x={sampler.tfit.x0[x_it]} beta={beta_in[x_it]}')

        # ---------------------------------------------------------------------
        # check which parameters have achieved required acceptance rate
        #  - those within the limits of a_high and a_low do not need
        #    to be updated
        a_fix = ~((ac_rate < a_high) & (ac_rate > a_low))
        cprint(f"Number of parameters with converged/not-converged beta:{np.sum(~a_fix)}/{np.sum(a_fix)}")
        # ---------------------------------------------------------------------
        # if too many iterations, then we give up and exit
        if nloop >= nloopsmax:
            break
        # else update the count
        else:
            nloop += 1
            sampler.nloop+=1
    # -------------------------------------------------------------------------
    # print the final acceptance
    # print current acceptance
    cprint(f'Beta Rescale: Final Acceptance: ')
    for x_it in range(n_x):
        cprint(f'\t{tfitb.xnames[x_it]:3s}:{ac_rate[x_it]}')
    # -------------------------------------------------------------------------
    # return the correction scale
    return corscale

def genchain(tfit: TransitFit, niter: int, beta: np.ndarray,
             mcmcfunc, loglikelihood,
             buffer: Optional = None, corbeta: float = 1.0,
             progress: bool = False,
             nwalker: Optional[int] = None,
             ngroup: Optional[int] = None,
             thinning: Optional[int] = 1) -> Tuple[np.ndarray, np.ndarray, np.ndarray]: ###DL###
    """
    Generate Markov Chain

    :param tfit: Transit fit class of parameters
    :param niter: int, the number of steps for each chain to run through
    :param beta: np.ndarray, the Gibb's factor : characteristic step size
                 for each parameter
    :param mcmcfunc: MCMC function
            - arguments: tfit: TransitFit,
                         loglikelihood: Any,
                         beta: np.ndarray,
                         buffer: np.ndarray, corbeta: float
    :param loglikelihood: log likelihood function
        - arguments: tfit: TransitFit
    :param buffer: np.ndarray, previous chains to use as a buffer
                   (mcmcfunc=deMCMC only)
    :param corbeta: float, a fractional multipier for previous chain used
                    as a buffer (mcmcfunc=deMCMC only)
    :param progress: bool, if True uses tqdm to print progress of the
                     MCMC chain
    :param nwalker: int, the number of walkers for printout (if not set assumes
                    we are running in single mode - not in parallel)
                    just modifies printout
    :param ngroup: int, the number of groups for printout (if not set assumes
                    we are running in single mode - not in paralell)
                    just modifies printout

    :return: tuple, 1. chains (numpy array [n_iter, n_x])
                    2. rejects (numpy array [n_iter, 2]
                       where reject=(rejected 1 or 0, parameter num changed)
                    3. loglikelihoods
    """
    #define the RNG here so that each worker in a multiprocessing has its own
    rng = np.random.default_rng()
    #attach it to tfit
    tfit.rng = rng
    
    # deal with no buffer set
    if buffer is None:
        buffer = []
    # -------------------------------------------------------------------------
    # pre-compute the first log-likelihood
    tfit.llx = loglikelihood(tfit)

    # -------------------------------------------------------------------------
    # Initialize arrays to hold chain values
    # (don't include the starting point, at start of loop it's just a repeat of
    #  the previous point in chain)
    nthinned=np.ceil(niter/thinning).astype(int)
    chains = np.empty([nthinned,tfit.x0.size])
    rejections = np.empty([nthinned,2],dtype=int)
    lls = np.empty(nthinned)

    # -------------------------------------------------------------------------
    # inner loop to save repeating code
    itt=0
    def inner_loop_code(tfitloop: TransitFit, itt, do_append=True): ###DL###
        #itt is the thinned iteration number
        # run the mcmc function
        tfitloop = mcmcfunc(tfitloop, loglikelihood, beta, buffer, corbeta)
        # add results to arrays
        if do_append:
            chains[itt,:] = tfitloop.x0.copy()
            rejections[itt,:] = tfitloop.ac[:]
            lls[itt] = tfitloop.llx
            itt+=1
        return tfitloop, itt

    # -------------------------------------------------------------------------
    # now to the full loop of niterations
    # -------------------------------------------------------------------------
    # deal with parallel process
    if nwalker is not None and ngroup is not None:
        # store timings
        timings = [0.0]
        # loop around iterations
        n_it_update = round(0.1 * niter) ###DL###
        for n_it in range(0, niter):
            # print every 10%
            if n_it % n_it_update == 0: ###DL###
                cprint(f'\tGroup={ngroup} walker={nwalker} '
                       f'iteration={n_it}/{niter}'
                       f' ({np.mean(timings):.3f} s/it)', flush=True)
            # start time
            start = timemod.time()
            tfit, itt = inner_loop_code(tfit, itt, do_append=not (n_it%thinning)) ###DL###
#             tfit = inner_loop_code(tfit)
            # add to timings
            timings.append(timemod.time() - start)
        # print timing
        cprint(f'\tGroup={ngroup} walker={nwalker} {niter} in '
               f'{np.sum(timings):.3f} s', level='warning')
    # deal with wanting to display process (linear run)
    elif progress:
        # loop around iterations
        for n_it in tqdm(range(0, niter)):
#             tfit = inner_loop_code(tfit) #DL, do we want thinning here?
            tfit, itt = inner_loop_code(tfit, itt, do_append=not (n_it%thinning)) 

    # otherwise display nothing
    else:
        # loop around iterations
        for n_it in range(0, niter):
#             tfit = inner_loop_code(tfit) #DL, do we want thinning here?
            tfit, itt = inner_loop_code(tfit, itt, do_append=not (n_it%thinning))

    # -------------------------------------------------------------------------
    # return the chains and rejections
    return chains, rejections, lls

def genchain_old(tfit: TransitFit, niter: int, beta: np.ndarray,
             mcmcfunc, loglikelihood,
             buffer: Optional = None, corbeta: float = 1.0,
             progress: bool = False,
             nwalker: Optional[int] = None,
             ngroup: Optional[int] = None,
             thinning: Optional[int] = 1) -> Tuple[np.ndarray, np.ndarray, np.ndarray]: ###DL###
    """
    Generate Markov Chain

    :param tfit: Transit fit class of parameters
    :param niter: int, the number of steps for each chain to run through
    :param beta: np.ndarray, the Gibb's factor : characteristic step size
                 for each parameter
    :param mcmcfunc: MCMC function
            - arguments: tfit: TransitFit,
                         loglikelihood: Any,
                         beta: np.ndarray,
                         buffer: np.ndarray, corbeta: float
    :param loglikelihood: log likelihood function
        - arguments: tfit: TransitFit
    :param buffer: np.ndarray, previous chains to use as a buffer
                   (mcmcfunc=deMCMC only)
    :param corbeta: float, a fractional multipier for previous chain used
                    as a buffer (mcmcfunc=deMCMC only)
    :param progress: bool, if True uses tqdm to print progress of the
                     MCMC chain
    :param nwalker: int, the number of walkers for printout (if not set assumes
                    we are running in single mode - not in parallel)
                    just modifies printout
    :param ngroup: int, the number of groups for printout (if not set assumes
                    we are running in single mode - not in paralell)
                    just modifies printout

    :return: tuple, 1. chains (numpy array [n_iter, n_x])
                    2. rejects (numpy array [n_iter, 2]
                       where reject=(rejected 1 or 0, parameter num changed)
                    3. loglikelihoods
    """
    #define the RNG here so that each worker in a multiprocessing has its own
    rng = np.random.default_rng()
    
    # deal with no buffer set
    if buffer is None:
        buffer = []
    # -------------------------------------------------------------------------
    # pre-compute the first log-likelihood
    tfit.llx = loglikelihood(tfit)

    # -------------------------------------------------------------------------
    # Initialize list to hold chain values
    # (don't include the starting point, at start of loop it's just a repeat of
    #  the previous point in chain)
    chains = []
    # Track our acceptance rate
    #    note reject=(rejected 1 or 0, parameter changed)
    rejections = []
    # Track the loglikelihood values
    lls = []

    # -------------------------------------------------------------------------
    # inner loop to save repeating code
    def inner_loop_code(tfitloop: TransitFit, do_append=True): ###DL###
        # run the mcmc function
        tfitloop = mcmcfunc(tfitloop, loglikelihood, beta, buffer, corbeta)
        # append results to chains and rejections lists
        if do_append: ###DL###
            chains.append(np.array(tfitloop.x0))
            rejections.append(np.array(tfitloop.ac))
            lls.append(tfitloop.llx) #append the value for this step, accepted or not
        return tfitloop

    # -------------------------------------------------------------------------
    # now to the full loop of niterations
    # -------------------------------------------------------------------------
    # deal with parallel process
    if nwalker is not None and ngroup is not None:
        # store timings
        timings = [0.0]
        # loop around iterations
        n_it_update = round(0.1 * niter) ###DL###
        for n_it in range(0, niter):
            # print every 10%
            if n_it % n_it_update == 0: ###DL###
                cprint(f'\tGroup={ngroup} walker={nwalker} '
                       f'iteration={n_it}/{niter}'
                       f' ({np.mean(timings):.3f} s/it)', flush=True)
            # start time
            start = timemod.time()
            tfit = inner_loop_code(tfit, do_append=not (n_it%thinning)) ###DL###
#             tfit = inner_loop_code(tfit)
            # add to timings
            timings.append(timemod.time() - start)
        # print timing
        cprint(f'\tGroup={ngroup} walker={nwalker} {niter} in '
               f'{np.sum(timings):.3f} s', level='warning')
    # deal with wanting to display process (linear run)
    elif progress:
        # loop around iterations
        for n_it in tqdm(range(0, niter)):
#             tfit = inner_loop_code(tfit) #DL, do we want thinning here?
            tfit = inner_loop_code(tfit, do_append=not (n_it%thinning)) 

    # otherwise display nothing
    else:
        # loop around iterations
        for n_it in range(0, niter):
#             tfit = inner_loop_code(tfit) #DL, do we want thinning here?
            tfit = inner_loop_code(tfit, do_append=not (n_it%thinning))

    # -------------------------------------------------------------------------
    # convert lists to arrays
    chains = np.array(chains)
    rejections = np.array(rejections)
    lls = np.array(lls)
    # -------------------------------------------------------------------------
    # return the chains and rejections
    return chains, rejections, lls


def calculate_acceptance_rates(rejections: np.ndarray,
                               burnin: int) -> Dict[int, float]:
    """
    Calculate Acceptance Rates

    :param rejections: np.ndarray [n_chains, 2]
                       where the second axis is (rejected, param_number)
                       rejected: 0 when accepted, 1 when rejected
                       param_number is either [-1, 0 to n_param]
                       when param_number is -1 we have deMCMC fit

    :param burnin: int, the number of chains the burn at the start

    :return: acceptance dictionary, keys = [-1, 0 to n_param]
             values = the acceptance for each key
    """
    # get the number of chains
    nchain = len(rejections[:, 0])
    # get the number of chains minus the burnin
    nchainb = nchain - burnin
    # acceptance is the fraction of chains accepted compared to total number
    #  (when burn in is considered)
    gaccept = (nchainb - np.sum(rejections[burnin:, 0])) / nchainb
    # print the global acceptance rate
    cprint(f'Global Acceptance Rate: {gaccept:.3f}')
    # -------------------------------------------------------------------------
    # storage of values
    acceptance_dict = dict()
    # -------------------------------------------------------------------------
    # deMCMC number of proposals
    de_nprop = 0
    # deMCMC acceptance rate
    de_accept_rate = 0
    # -------------------------------------------------------------------------
    # loop around parameter number
    # Question: Why can't we use the max number of parameters here?
    #           Is it because all parameters might not be selected by
    #           the Gibbs sampler?
    for p_num in range(max(rejections[burnin:, 1]) + 1):
        # deMCMC number of proposals
        de_nprop = 0
        # deMCMC acceptance rate
        de_accept_rate = 0
        # number of proposals
        n_prop = 0
        # acceptance rate
        accept_rate = 0
        # loop around each chain
        for chain_it in range(burnin, nchain):
            # if the rejection comes from this parameter
            if rejections[chain_it, 1] == p_num:
                # add one to the number of proposals
                n_prop += 1
                # add to the acceptance rate (0 = accept, 1 = reject)
                accept_rate += rejections[chain_it, 0]
            # if we are in deMCMC mode (n_param = -1) add to de variables
            elif rejections[chain_it, 1] == -1:
                # add one to the de number of proposals
                de_nprop += 1
                # add to the de acceptance rate (0 = accept, 1 = reject)
                de_accept_rate += rejections[chain_it, 0]
        # print the acceptance rate for this
        acceptance = (n_prop - accept_rate) / (n_prop + 1)
#         cprint(f'Param {p_num}: Acceptance Rate {acceptance:.3f}')
        # store for later use
        acceptance_dict[p_num] = acceptance

    # Question: This is only calculated for the last loop (as denprop reset
    #           inside loop) is this what we want?
    # if we have deMCMC results, report the acceptance rate.
    if de_nprop > 0:
        de_acceptance = (de_nprop - de_accept_rate) / de_nprop
        cprint(f'deMCMC: Acceptance Rate {de_acceptance:.3f}')
        # store for later use
        acceptance_dict[-1] = de_acceptance
    # return the acceptance dictionary
    return acceptance_dict


def gelman_rubin_convergence(chains: Dict[int, np.ndarray],
                             burnin: int, npt: int) -> np.ndarray:
    """
    Estimating PSRF

    See pdf doc BrooksGelman for info

    :param chains: dictionary of chains, each one being a np.ndarray
                   of shape [n_params, n_phot]
    :param burnin: int, the number of chains to burn
    :param npt: int, the number of parameters

    :return: numpy array [n_params], the gelman rubin convergence for each
             parameter
    """
    # get the number of walkers (c.f. number of chains)
    n_walkers = len(chains)
    # assume all chains have the same size
    n_chain = chains[0].shape[0] - burnin
    # get the number of parameters
    n_param = chains[0].shape[1]
    # -------------------------------------------------------------------------
    # allocate an array to hold mean calculations
    pmean = np.zeros((n_walkers, n_param))
    # allocate an array to hold variance calculations
    pvar = np.zeros((n_walkers, n_param))
    # -------------------------------------------------------------------------
    # loop over each walker
    for walker in range(n_walkers):
        # Generate means for each parameter in each chain
        pmean[walker] = np.mean(chains[walker][burnin:], axis=0)
        # Generate variance for each parameter in each chain
        pvar[walker] = np.var(chains[walker][burnin:], axis=0)
    # -------------------------------------------------------------------------
    # calculate the posterior mean for each parameter
    posteriormean = np.mean(pmean, axis=0)
    # -------------------------------------------------------------------------
    # Calculate between chains variance
    bvar = np.sum((pmean - posteriormean) ** 2, axis=0)
    bvar = bvar * n_chain / (n_walkers - 1.0)
    # -------------------------------------------------------------------------
    # Calculate within chain variance
    wvar = np.sum(pvar, axis=0)
    wvar = wvar / n_walkers
    # -------------------------------------------------------------------------
    # Calculate the pooled variance
    part1 = (n_chain - 1) * (wvar / n_chain)
    part2 = bvar * (n_walkers + 1) / (n_walkers * n_chain)
    vvar = part1 + part2
    # -------------------------------------------------------------------------
    # degrees of freedom
    dof = npt - 1
    # -------------------------------------------------------------------------
    # dof ratio for rc and ru
    dofr = (dof + 3.0) / (dof + 1.0)
    # -------------------------------------------------------------------------
    # PSRF from Brooks and Gelman (1997)
    rc = np.sqrt(dofr * vvar / wvar)
    # -------------------------------------------------------------------------
    # Calculate Ru
    # part1 = (n_chain - 1.0)/n_cahin
    # part2 = qa * (n_walkers + 1)/n_walkers
    # ru = np.sqrt((dofr * part1 * wvar) + part2)
    # -------------------------------------------------------------------------
    # return rc
    return rc


# =============================================================================
# MCMC Sampler
# =============================================================================
class Sampler:
    """
    The MCMC Sampler - this should look like the emcmc sampler
    """
    wchains: Dict[int, np.ndarray]
    wrejects: Dict[int, np.ndarray]
    grtest: np.ndarray
    chains: np.ndarray
    reject: np.ndarray
    acc_dict: Dict[int, float]

    def __init__(self, tfit: TransitFit, mode='full'):
        self.params = tfit.params
        self.tfit = tfit.copy()
        self.mode = mode
        self.wchains = dict()
        self.wrejects = dict()
        self.wlls = dict() #walker loglikelihoods
        self.nloop = None
        self.nsteps = None
        # gr test (shape: n_x)
        self.grtest = np.array([])
        # final combined chains
        self.chain = np.array([])
        self.reject = np.array([])
        self.lls = np.array([])
        self.acc_dict = dict()
        # added manually if required
        self.data = None
        self.results_table = Table()
        # set up storage of chainns
        for nwalker in range(self.params['WALKERS']):
            self.wchains[nwalker] = np.array([])
            self.wrejects[nwalker] = np.array([])
            self.wlls[nwalker] = np.array([])

    def run_mcmc(self, loglikelihood, mcmcfunc,
                 trial: Optional['Sampler'] = None):
        """
        Run the MCMC using a correction scale of beta previously
        calculated by betarescale)

        :param loglikelihood: log likelihood function
                - arguments: tfit: TransitFit
        :param mcmcfunc: MCMC function
                - arguments: tfit: TransitFit,
                             loglikelihood: Any,
                             beta: np.ndarray,
                             buffer: np.ndarray, corbeta: float
        :param trial: optional, Sampler class, a previous sampler to start
                      the chains from
        :return:
        """
        # ---------------------------------------------------------------------
        # get parameters from params
        # ---------------------------------------------------------------------
        # get the maximum number of loops for this mode
        nloopsmax = self.params['NLOOPMAX'][self.mode]
        # get the number of steps for the MCMC for this mode
        self.nsteps = self.params['NSTEPS'][self.mode]
        # ---------------------------------------------------------------------
        # deal with having a trial sampler
        in_sampler = trial
        # ---------------------------------------------------------------------
        # loop around
        # ---------------------------------------------------------------------
        # start loop counter
        self.nloop = 0 #initialize to 0, incremented at start of loop
        # ---------------------------------------------------------------------
        # Loop around iterations until we break (convergence met) or max
        #     number of loops exceeded
        # ---------------------------------------------------------------------
        while self.nloop < nloopsmax:
            # set up the args that go into single loop
            sargs = [loglikelihood, mcmcfunc, in_sampler]
            # run a single loop
            cond, in_sampler = self.single_loop(*sargs)
            # deal with condition met
            
            #could put the update to tfit x0 p0 here
            #could put the dump here
            
            if cond:
                break

    SingleLoopReturn = Tuple[bool, 'Sampler']

    def single_loop(self, loglikelihood, mcmcfunc, ##DL removed corscale
                    in_sampler: Optional['Sampler'] = None) -> SingleLoopReturn:
        """
        Run a single instance of the while loop

        :param loglikelihood: log likelihood function
                - arguments: tfit: TransitFit
        :param mcmcfunc: MCMC function
                - arguments: tfit: TransitFit,
                             loglikelihood: Any,
                             beta: np.ndarray,
                             buffer: np.ndarray, corbeta: float
        :param in_sampler: Previous sampler (if given) for a "trial" run this
                           can be None, if a "full" run, the first time this
                           is run it should be the "trial" otherwise it should
                           be the sampler from the previous loop

        :return: tuple,
                 1. cond: bool, True if single loop converged and we should
                    not to any more loops, False otherwise.
                 2. sampler: Sampler, the end state of the sampler, for
                    passing to the next call of "single_loop" - in trial mode
                    this will be None, in full mode this will be "self"
        """
        # ---------------------------------------------------------------------
        # get parameters from params
        # ---------------------------------------------------------------------
        # get the number of steps for the MCMC for this mode
        if self.nsteps is None:
            self.nsteps = self.params['NSTEPS'][self.mode]
        # set number of walkers
        nwalkers = self.params['WALKERS']
        # set the burnin parameter
        burninf = self.params['BURNINF'][self.mode]
        # convergence criteria for buffer
        buf_converge_crit = self.params['BUFFER_CONVERGE_CRIT']
        # the number of steps we add on next loop (if convergence not met)
        nsteps_inc = self.params['NSTEPS_INC'][self.mode]
        # correction to beta term for deMCMC
        corbeta = self.params['CORBETA'][self.mode]
        #thinning for chain
        thinning = self.params['THINNING'] ###DL###
        # ---------------------------------------------------------------------
        # increment loop counter
        self.nloop += 1
        # ---------------------------------------------------------------------
        # set the constant genchain parameters
        gkwargs = dict(niter=self.nsteps, beta=self.tfit.beta,
                       mcmcfunc=mcmcfunc, loglikelihood=loglikelihood,
                       corbeta=corbeta,thinning=thinning)
        # print progress
        cprint(f'MCMC Loop {self.nloop} [{self.mode}]', level='info')
        # -----------------------------------------------------------------
        # loop around walkers
        # -----------------------------------------------------------------
        # print progress
        cprint(f'\tGetting chains of {self.nsteps} steps for {nwalkers} walkers', level='info')
        # get the chains in a parallel way
        self.wchains, self.wrejects, self.wlls = _multi_process_pool(self, in_sampler,
                                                 nwalkers, gkwargs)
#         # push chains/rejects into Sampler
#         self.wchains = wchains
#         self.wrejects = wrejects
#         self.wlls = wlls

        # get number of chains to burn (using burn in fraction)
        burnin = int(self.wchains[0].shape[0] * burninf)
        # update the full chains
        self.chain, self.reject, self.lls = join_chains(self, burnin)

        # -----------------------------------------------------------------
        # Calculate acceptance rate
        # -----------------------------------------------------------------
        # print progress
        cprint('\tCalculating acceptance rate', level='info')
        # deal with differences between trial and full run
        # DL: why is there a difference?
#         if self.mode == 'trial':
#             rejects = self.wrejects[0]
#             burnin_full = int(self.wchains[0].shape[0] * burninf)
#         else:
#             rejects = self.reject
#             burnin_full = int(self.chain.shape[0] * burninf)
        #DL: always use the merge chains
        rejects = self.reject
        burnin_full = int(self.chain.shape[0] * burninf)
            
        # calculate acceptance for chain1
        self.acc_dict = calculate_acceptance_rates(rejects,burnin=burnin_full)
        
        # -----------------------------------------------------------------
        # Calculate the Gelman-Rubin Convergence
        # -----------------------------------------------------------------
        # print progress
        cprint('\tCalculating Gelman-Rubin Convergence.', level='info')
        # calculate the rc factor, npt is the number of total points
        self.grtest = gelman_rubin_convergence(self.wchains, burnin=burnin,
                                               npt=self.tfit.npt)

        # print results
        cprint('\tParam \t\tvalue \tGRconv \tACrate:',level='info',timestamp=0)
        for param_it in range(self.tfit.n_x):
            # print Rc parameter
            pargs = [param_it, self.tfit.xnames[param_it],self.chain[-1,param_it],
                     self.grtest[param_it],self.acc_dict[param_it]]
            cprint('\t{:3d} {:3s}: \t{:.5f} \t{:.4f} \t{:.3f}'.format(*pargs),
                   level='info',timestamp=0)

        # -----------------------------------------------------------------
        # Test criteria for success
        # -----------------------------------------------------------------
        # criteria for accepting mcmc chains
        #   all parameters grtest greater than or equal to
        #   buf_converge_crit
        # DL: shouldn't this be "converge_crit"? or perhaps depending on mode??
        # DL: 'full'-> "converge_crit", 'trial'-> "buf_converge_crit"
        success = (self.grtest < buf_converge_crit).all()
        cprint(f'GR convergence test result: {success}')
        
        if success:
            return True, self
        else:
            # add to the number of steps (for next loop)
            self.nsteps += nsteps_inc
            return False, self
    
    def single_loop_beta(self, loglikelihood, mcmcfunc, beta=None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Should be called by beta_rescale_nwalker. Runs a single loop with N walkers.
        
        :param loglikelihood: log likelihood function
                - arguments: tfit: TransitFit
        :param mcmcfunc: MCMC function
                - arguments: tfit: TransitFit,
                             loglikelihood: Any,
                             beta: np.ndarray,
                             buffer: np.ndarray, corbeta: float
                             
        :beta: the beta values for the sampling of parameters
        
        """
        # ---------------------------------------------------------------------
        # get parameters from params
        # ---------------------------------------------------------------------
        # get the number of steps for the MCMC for this mode
        nsteps = self.params['NITER_COR']
        # set number of walkers
        nwalkers = self.params['WALKERS']
        # set the burnin parameter
        burnin = self.params['BURNIN_COR']
        # correction to beta term for deMCMC
        corbeta = self.params['CORBETA'][self.mode]

        if beta is None:
            beta=self.tfit.beta

        # ---------------------------------------------------------------------
        # set the constant genchain parameters
        gkwargs = dict(niter=nsteps, beta=beta,
                       loglikelihood=loglikelihood, mcmcfunc=mcmcfunc,
                       corbeta=corbeta,thinning=1)
        # print progress
        cprint(f'MCMC Loop {self.nloop} [{self.mode}]', level='info')
        # -----------------------------------------------------------------
        # loop around walkers
        # -----------------------------------------------------------------
        # print progress
        cprint(f'\tGetting chains of {nsteps} steps for {nwalkers} walkers', level='info')
        #flush the current chains in sampler, in beta_rescale don't want to append
        for nwalker in range(nwalkers):
            self.wchains[nwalker] = np.array([])
            self.wrejects[nwalker] = np.array([])
            self.wlls[nwalker] = np.array([])
        # get the chains in a parallel way
        self.wchains, self.wrejects, self.wlls = _multi_process_pool(self, None,
                                                 nwalkers, gkwargs)
#         # push chains/rejects into Sampler
#         self.wchains = wchains
#         self.wrejects = wrejects
#         self.wlls = wlls

        # update the full chains
        self.chain, self.reject, self.lls = join_chains(self, burnin)

        return self.chain, self.reject, self.lls

    def posterior_print(self):

        # calulate medians
        medians = np.median(self.chain, axis=0)

        cprint('Posterior median values')
        # loop around parameters
        for x_it in range(self.tfit.n_x):
            # print argument
            pargs = [x_it, self.tfit.xnames[x_it], medians[x_it]]
            cprint('\t{0} {1:3s}: {2:.5f}'.format(*pargs))

    def results(self, start_chain: int = 0, do_t_depth = False):
        """
        Get the results using all sampler.chain

        :param start_chain: int, start the chain at a different point

        :return: astropy table of the results
        """
        # get which results we want
        result_mode = self.params['RESULT_MODE']
        # get number of samples for transit depth
        tdepth_samples = self.params['TRANSIT_DEPTH_NSAMPLES']
        # get length
        n_x = self.tfit.n_x
        # get the names
        xnames = self.tfit.xnames
        xfullnames = self.tfit.xfullnames
        # -----------------------------------------------------------------
        # get the p50, p16 and p84
        pvalues = general.sigma_percentiles()
        # get the percentile labels for the table
        label_p16 = 'P{0:3f}'.format(pvalues[0]).replace('.', '_')
        label_p84 = 'P{0:3f}'.format(pvalues[2]).replace('.', '_')
        # -----------------------------------------------------------------
        # create table
        table = Table()
        # add columns
        # TODO: Add Name + Shortname
        table['NAME'] = xfullnames
        table['SHORTNAME'] = xnames
        table['WAVE_CENT'] = np.full(n_x, np.nan)
        # if it is a fitted parameter
        if result_mode in ['mode', 'all']:
            table['MODE'] = np.zeros(n_x, dtype=float)
            table['MODE_UPPER'] = np.zeros(n_x, dtype=float)
            table['MODE_LOWER'] = np.zeros(n_x, dtype=float)
        # P50, P16, P84
        if result_mode in ['percentile', 'all']:
            table['P50'] = np.zeros(n_x, dtype=float)
            table[label_p16] = np.zeros(n_x, dtype=float)
            table[label_p84] = np.zeros(n_x, dtype=float)
            table['P50_UPPER'] = np.zeros(n_x, dtype=float)
            table['P50_LOWER'] = np.zeros(n_x, dtype=float)
        # -----------------------------------------------------------------
        # get the average wave center of all integrations for each bandpass
        wave_cent = np.mean(self.tfit.wavelength, axis=1)
        # -----------------------------------------------------------------
        # loop around fitted parameters
        for x_it in range(n_x):
            # if it is a fitted parameter
            if self.tfit.get(xnames[x_it], 'wmask'):
                # get the wave center value for this x0 parameter
                wave_cent_it = wave_cent[self.tfit.x0pos[x_it, 1]]
                table['WAVE_CENT'][x_it] = wave_cent_it
                # print
                cprint(f'\t Calculating results for {xnames[x_it]} '
                       f'{wave_cent_it:.3f} um')
            else:
                # print
                cprint(f'\t Calculating results for {xnames[x_it]}')
            # get the parameter chain
            pchain = self.chain[start_chain:, x_it] ###DL###
            # -----------------------------------------------------------------
            # deal with result mode
            if result_mode in ['mode', 'all']:
                # get the mode
                mode, x_eval, kde1 = transit_fit.modekdestimate(pchain, 0)
                # calculate the mode percentile value
                perc1 = transit_fit.intperc(mode, x_eval, kde1)
                # get the mode low and mode high values
                mode_upper = np.abs(perc1[1] - mode)
                mode_lower = np.abs(mode - perc1[0])
                # push into table
                table['MODE'][x_it] = mode
                table['MODE_LOWER'][x_it] = mode_lower
                table['MODE_UPPER'][x_it] = mode_upper
            # -----------------------------------------------------------------
            # deal with result mode
            if result_mode in ['percentile', 'all']:
                # calculate the percentile values
                percentiles = np.percentile(pchain, pvalues)
                # -------------------------------------------------------------
                table['P50'][x_it] = percentiles[1]
                table[label_p16][x_it] = percentiles[0]
                table[label_p84][x_it] = percentiles[2]
                # -------------------------------------------------------------
                # tabulate P50 lower and upper bounds
                table['P50_UPPER'] = table[label_p84] - table['P50']
                table['P50_LOWER'] = table['P50'] - table[label_p16]
                
        if do_t_depth: ###DL###
            # ---------------------------------------------------------------------
            # add in transit depth (new table stacked)
            # ---------------------------------------------------------------------
            depth_table = Table()
            depth_table['NAME'] = ['transit_depth'] * self.tfit.n_phot
            depth_table['SHORTNAME'] = ['TD'] * self.tfit.n_phot
            depth_table['WAVE_CENT'] = self.tfit.wavelength[:, 0]
            # ---------------------------------------------------------------------
            # deal with result mode
            if result_mode in ['mode', 'all']:
                # push into table
                depth_table['MODE'] = np.full(self.tfit.n_phot, np.nan)
                depth_table['MODE_LOWER'] = np.full(self.tfit.n_phot, np.nan)
                depth_table['MODE_UPPER'] = np.full(self.tfit.n_phot, np.nan)
            # ---------------------------------------------------------------------
            # deal with result mode
            if result_mode in ['percentile', 'all']:
                # get depth
                # TODO: add n_samples to yaml n_samples=10000
                dout = self.results_tdepth(n_samples=tdepth_samples)
                # push into table
                depth_table['P50'] = dout[0]
                depth_table[label_p16] = dout[1]
                depth_table[label_p84] = dout[2]
                depth_table['P50_UPPER'] = dout[4]
                depth_table['P50_LOWER'] = dout[3]
            # stack the table to add the depth table
            table = vstack([table, depth_table])
        # ---------------------------------------------------------------------
        # save the results table
        # ---------------------------------------------------------------------
        self.results_table = table ###DL###

    def results_tdepth(self, n_samples: int = 10000):
        """
        Calculate the transit depth parameter by taking random samples
        of the chains and calculating the transit model

        :param n_samples:
        :return:
        """
        # get the p50, p16 and p84
        pvalues = general.sigma_percentiles()
        # randomly pick sample indices in the chain
        csample = np.arange(self.chain.shape[0])
        chain_samples_idx = rng.choice(csample, n_samples, replace=False)
        # to store the depths at mid-transit
        depth = np.zeros((n_samples, self.tfit.n_phot))
        # index of EP1 in p axis 0
        time_idx_p = (self.tfit.pnames == 'EP1').nonzero()[0]
        # loop over the samples in the chain
        for n_it in range(n_samples):
            print('a')
            # copy tfit
            tfit_tmp = self.tfit.copy()
            # get the fitted parameters values for this sample
            tfit_tmp.x0 = self.chain[chain_samples_idx[n_it], :]
            # update p with parameters values from that sample
            tfit_tmp.update_p0_from_x0()
            ptmp = tfit_tmp.p0
            # get nintg
            nintg = self.tfit.pkwargs['NINTG']
            # initialize the model value
            model = np.array([0.]) #must be array here, and float
            # loop over band passes and calculate depth
            print('b')
            for bp in range(self.tfit.n_phot):
                # call transit model and evaluate at time EP1 (middle transit)
                tfit5.transitmodel(tfit_tmp.n_planets, ptmp[:, bp],
                                   ptmp[time_idx_p, bp], 1.e-5, tfit_tmp.tt_n,
                                   tfit_tmp.tt_tobs[:, time_idx_p],
                                   tfit_tmp.tt_omc[:, time_idx_p],
                                   model, tfit_tmp.tmodel_dtype[time_idx_p],
                                   nintg)
                
#                 tfit5.transitmodel(tfit.n_planets, tfit.p0[:, phot_it], tfit.time[phot_it],
#                    tfit.itime[phot_it], tfit.tt_n, tfit.tt_tobs,
#                    tfit.tt_omc, model, tfit.tmodel_dtype, tfit.pkwargs['NINTG'])


                print(model)
                depth[n_it, bp] = 1.0 - model
        # get the depths 16th, 50th and 86th
        d16, d50, d84 = np.percentile(depth, pvalues, axis=0)
        d_elo = d50 - d16
        d_ehi = d84 - d50
        # get depth 50th + and - values
        return d50, d16, d84, d_elo, d_ehi

    def print_results(self, pkind: str = 'mode',
                      key: Optional[str] = None):
        """
        Print the results to screen for pkind = "mode" or "percentile"

        :param pkind: str, either "mode" or "percentile"
        :param key: str or None, if set filters the printout by this key

        :return: None, prints to standard output
        """
        # get which results we want
        result_mode = self.params['RESULT_MODE']
        # get results table
        results = self.results_table
        # check key is valid
        if (key is not None) and (key not in self.tfit.xnames):
            emsg = 'Sampler Results Error: key = {key} is not valid.'
            emsg += '\tMust be: {0}'.format(','.join(set(self.tfit.xnames)))
            raise base_classes.TransitFitExcept(emsg)
        # loop around rows of the table
        for row in range(len(results)):
            # deal with a parameter filter
            if key is not None:
                if results['NAME'][row] != key:
                    continue
            # get print arguments
            if pkind == 'mode' and result_mode in ['mode', 'all']:
                pargs = [results['NAME'][row], results['MODE'][row],
                         results['MODE_UPPER'][row], results['MODE_LOWER'][row]]
                # print values
                cprint('\t{0:3s}={1:.8f}+{2:.8f}-{3:.8f}'.format(*pargs))
            elif pkind == 'percentile' and result_mode in ['percentile', 'all']:
                pargs = [results['NAME'][row], results['P50'][row],
                         results['P50_UPPER'][row], results['P50_LOWER'][row]]
                # print values
                cprint('\t{0:3s}={1:.8f}+{2:.8f}-{3:.8f}'.format(*pargs))

    def save_results(self):
        # get results table
        results = self.results_table
        # get output path
        outpath = self.params['OUTDIR']
        outname = self.params['OUTNAME'] + '_results'
        # deal with no output dir
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        # ---------------------------------------------------------------------
        # write fits file
        # ---------------------------------------------------------------------
        # construct fits filename
        fitspath = os.path.join(outpath, outname + '.fits')
        # generate a basic fits header
        header0 = fits.Header()
        header0['VERSION'] = base.__version__
        header0['PDATE'] = base.time.now().fits
        header0['VDATE'] = base.__date__
        # generate the primary hdu (no data here)
        hdu0 = fits.PrimaryHDU(header=header0)
        # ---------------------------------------------------------------------
        # add the results
        header1 = fits.Header()
        header1['EXTNAME'] = ('RESULTS', 'Name of the extension')
        hdu1 = fits.BinTableHDU(results, header=header1)
        # ---------------------------------------------------------------------
        # add the param table - so we always know the parameters used
        header2 = fits.Header()
        header2['EXTNAME'] = ('PARAMTABLE', 'Name of the extension')
        hdu2 = fits.BinTableHDU(self.params.param_table(), header=header2)
        # ---------------------------------------------------------------------
        # try to write to disk
        with warnings.catch_warnings(record=True) as _:
            try:
                hdulist = fits.HDUList([hdu0, hdu1, hdu2])
                hdulist.writeto(fitspath, overwrite=True)
                hdulist.close()
            except Exception as e:
                emsg = 'Save Results Error {0}\n\t{1}: {2}'
                eargs = [fitspath, type(e), str(e)]
                raise base_classes.TransitFitExcept(emsg.format(*eargs))
        # print progress
        cprint(f'\tSaved {fitspath}')
        # ---------------------------------------------------------------------
        # write ascii file
        # ---------------------------------------------------------------------
        # construct fits filename
        asciipath = os.path.join(outpath, outname + '.txt')
        # ---------------------------------------------------------------------
        # try to write to disk
        with warnings.catch_warnings(record=True) as _:
            try:
                results.write(asciipath, format='ascii', overwrite=True)
            except Exception as e:
                emsg = 'Save Results Error {0}\n\t{1}: {2}'
                eargs = [asciipath, type(e), str(e)]
                raise base_classes.TransitFitExcept(emsg.format(*eargs))
        # print progress
        cprint(f'\tSaved {asciipath}')

    def save_chains(self):
        # get output path
        outpath = self.params['OUTDIR']
        outname = self.params['OUTNAME'] + '_chains'
        # deal with no output dir
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        # ---------------------------------------------------------------------
        # write fits file
        # ---------------------------------------------------------------------
        # construct fits filename
        fitspath = os.path.join(outpath, outname + '.fits')
        # generate a basic fits header
        header0 = fits.Header()
        header0['VERSION'] = base.__version__
        header0['PDATE'] = base.time.now().fits
        header0['VDATE'] = base.__date__
        # generate the primary hdu (no data here)
        hdu0 = fits.PrimaryHDU(header=header0)
        # ---------------------------------------------------------------------
        # add the chains
        header1 = fits.Header()
        header1['EXTNAME'] = ('RESULTS', 'Name of the extension')
        hdu1 = fits.ImageHDU(header=header1)
        hdu1.data = self.chain
        # add the rejects
        header2 = fits.Header()
        header1['EXTNAME'] = ('RESULTS', 'Name of the extension')
        hdu2 = fits.ImageHDU(header=header2)
        hdu2.data = self.reject
        # ---------------------------------------------------------------------
        # add the param table - so we always know the parameters used
        header3 = fits.Header()
        header3['EXTNAME'] = ('PARAMTABLE', 'Name of the extension')
        hdu3 = fits.BinTableHDU(self.params.param_table(), header=header3)
        # ---------------------------------------------------------------------
        # try to write to disk
        with warnings.catch_warnings(record=True) as _:
            try:
                hdulist = fits.HDUList([hdu0, hdu1, hdu2, hdu3])
                hdulist.writeto(fitspath, overwrite=True)
                hdulist.close()
            except Exception as e:
                emsg = 'Save Results Error {0}\n\t{1}: {2}'
                eargs = [fitspath, type(e), str(e)]
                raise base_classes.TransitFitExcept(emsg.format(*eargs))
        # print progress
        cprint(f'\tSaved {fitspath}')

    def load_chains(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load the chains (and rejects) from fits file

        :return:
        """
        # get output path
        outpath = self.params['OUTDIR']
        outname = self.params['OUTNAME'] + '_chains'
        # construct fits filename
        fitspath = os.path.join(outpath, outname + '.fits')
        # load the chains and rejects from fits file
        chains = fits.getdata(fitspath, ext=1)
        rejects = fits.getdata(fitspath, ext=2)
        # return chains and rejects
        return chains, rejects

    def dump(self, **kwargs):
        """
        Dump the sampler to a pickle file
        :param kwargs:
        :return:
        """
        # add additional data to the pickle
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])
        # get output path
        outpath = self.params['OUTDIR']
        outname = self.params['OUTNAME'] + '_sampler_'+self.mode+'.pickle'
        # deal with no output dir
        if not os.path.exists(outpath):
            os.makedirs(outpath)

        with open(os.path.join(outpath, outname), 'wb') as pfile:
            pickle.dump(self, pfile)
        print('Sampler object dumped to file:', os.path.join(outpath, outname))

    @staticmethod
    def load(filename) -> 'Sampler':
        """
        Load the sampler class from the pickle file

        :return:
        """
        # load the class and return
        with open(os.path.join(filename), 'rb') as pfile:
            return pickle.load(pfile)


def merge_chains(chain1: np.ndarray, chain2: np.ndarray) -> np.ndarray:
    """
    Merge two chains, and account for the first chain being empty

    :param chain1: np.ndarray, the first chain
    :param chain2: np.ndarray, the second chain
    :return:
    """
    if chain1.shape[0] == 0:
        return np.array(chain2)
    else:
        return np.concatenate([chain1, chain2])


def start_from_previous_chains(current: Sampler, tfit: TransitFit,
                               previous: Sampler
                               ) -> Tuple[Optional[np.ndarray], TransitFit]:
    """
    Start from a previous chain (be it a previous sampler (i.e. trial) or
    from the current chain)

    :param current: Current Sampler class (usually self)
    :param tfit: Transit fit parameter container
    :param previous: Previous Sampler class (can also be self if using a
                     previous chain from the same sampler) or a different
                     sampler (e.g. from a trial run)

    :return: tuple, 1. the buffer (previous chains burnt in and combined)
             2. the update tfit (x0 and p0) using most recent chain
             (chains[-1])
    """
    # if in trial mode we don't do this
    if current.mode == 'trial':
        # set the buffer to None and return tfit as it is
        return None, tfit
    # set the burnin parameter
    burninf = current.params['BURNINF'][current.mode]
    # get the burn in from trial shape
    burnin = int(previous.wchains[0].shape[0] * burninf)
    # get buffer (by joining chains)
    buffer, _, _ = join_chains(previous, burnin)
    # loop around walkers in the trial
    for walker in previous.wchains:
        # get start point for this chain (the last chain
        #    from trial sampler)
        update_x0_p0_from_chain(tfit, previous.wchains[walker], -1)

    # return the buffer (
    return buffer, tfit


def join_chains(sampler: Sampler, burnin: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Join a set of sampler chains and rejects (using a burnin)

    :param sampler: Sampler class
    :param burnin: int, the number of chains to burn

    :return: tuple 1. the combined chain arrays, 2. the combined reject arrays, 
                   3. the comgined lls array
    """
    chains, rejects, lls = np.array([]), np.array([]), np.array([])
    # loop around chains
    for walker in sampler.wchains:
        # get the chains without the burnin chains
        walker_chain = sampler.wchains[walker][burnin:]
        # get the rejects
        walker_reject = sampler.wrejects[walker][burnin:]
        # get the lls
        walker_lls = sampler.wlls[walker][burnin:]
        # add walker to chains
        chains = merge_chains(chains, walker_chain)
        # add walker to rejects
        rejects = merge_chains(rejects, walker_reject)
        # add walker to lls
        lls = merge_chains(lls, walker_lls)
    # return the combined chains and rejects
    return chains, rejects, lls


def update_x0_p0_from_chain(tfit: TransitFit, chain: np.ndarray,
                            chain_num: int) -> TransitFit:
    """
    Update the x0 and p0 from a specific chain

    :param tfit: Transit fit parameter container
    :param chain: np.ndarray, the chain [n_steps, x_n]
    :param chain_num: int, the position in chain to get (positive to count
                      from start, negative to count from end)

    :return: the updated Transit fit parameter container
    """
    # set x0 to the last chain position
    tfit.x0 = chain[chain_num, :]
    # update solution
    tfit.update_p0_from_x0()
    # return updated tfit
    return tfit


# =============================================================================
# Define worker functions
# =============================================================================
PvalueReturn = Tuple[np.ndarray, bool, bool, Optional[Dict[str, Any]],
                     str, Optional[Any]]


def __assign_pvalue(key: str, pdict: ParamDict, n_phot: int, func_name: str):
    """
    Get the pvalue from params (pdict)

    :param key: str, the key to get
    :param pdict: ParamDict, the parameter dictionary to get value from
    :param n_phot: int, the number of photometric band passes
    :param func_name: str, the function name (for source)

    :return: tuple, 1. the solution (p0), 2. whether value is to be fitted
                    3. whether the parameter is wavelength dependent
                    4. the prior dictionary, 5. the name of the parameter
                    6. the forced beta value (None if not forced)
    """
    # deal with key = None
    if key is None:
        p0 = np.zeros(n_phot)
        fmask = False
        wmask = False
        prior = None
        pnames = 'Undefined'
        pbeta = None
        return p0, fmask, wmask, prior, pnames, pbeta
    # deal with key not in params (bad)
    if key not in pdict:
        emsg = f'ParamError: key {key} must be set. func={func_name}'
        raise base_classes.TransitFitExcept(emsg)
    # get the value for this key
    fitparam = pdict[key]
    # only consider FitParams classes
    if not isinstance(fitparam, FitParam):
        emsg = (f'ParamError: key {key} must be a FitParam. '
                f'\n\tGot {key}={fitparam}'
                f'\n\tfunc={func_name}')
        raise base_classes.TransitFitExcept(emsg)
    # get the properties from the fit param class
    p0, fmask, wmask, prior, pnames, pbeta = fitparam.get_value(n_phot)

    return p0, fmask, wmask, prior, pnames, pbeta


MultiReturn = Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray]]


def _multi_process_pool_old(sampler: Sampler, in_sampler: Sampler, nwalkers: int,
                        gkwargs: dict) -> MultiReturn:
    """
    Multiprocessing using multiprocessing.Process

    split into groups based on the max number of N_WALKER_THREADS requested

    :param sampler: Sampler class
    :param nwalkers: int, the total number of walkers
    :param gkwargs: dictionary, constant args to pass to the linear process

    :return: tuple, 1. dictionary the chains for each walker
                    2. dictionary the rejects for each walker
    """
    # deal with Pool specific imports
    from multiprocessing import get_context
    from multiprocessing import set_start_method
    try:
        set_start_method("spawn")
    except RuntimeError:
        pass
    # start process manager
    wchains = dict()
    wrejects = dict()
    wlls = dict()
    # get the number of threads (N_WALKER_THREADS)
    n_walker_threads = sampler.params['N_WALKER_THREADS']
    # --------------------------------------------------------------------------
    # populate the return dictionary
    for nwalker in range(nwalkers):
        wchains[nwalker] = np.array([])
        wrejects[nwalker] = np.array([])
        wlls[nwalker] = np.array([])
    # --------------------------------------------------------------------------
    # list of params for each entry
    params_per_process = []
    # populate params for each sub group
    for nwalker in range(nwalkers):
        args = (sampler, in_sampler, nwalker, gkwargs, 0)
        params_per_process.append(args)
    # start parallel jobs
    with get_context('spawn').Pool(n_walker_threads, maxtasksperchild=1) as pool:
        results = pool.starmap(_linear_process, params_per_process)
    # --------------------------------------------------------------------------
    # fudge back into return dictionary
    for row in range(len(results)):
        wchains[row] = results[row][0]
        wrejects[row] = results[row][1]
        wlls[row] = results[row][2]
    # --------------------------------------------------------------------------
    # return these
    return wchains, wrejects, wlls

def _multi_process_pool(sampler: Sampler, in_sampler: Sampler, nwalkers: int,
                        gkwargs: dict) -> MultiReturn:
    """
    Multiprocessing using multiprocessing.Process

    split into groups based on the max number of N_WALKER_THREADS requested

    :param sampler: Sampler class
    :param nwalkers: int, the total number of walkers
    :param gkwargs: dictionary, constant args to pass to the linear process

    :return: tuple, 1. dictionary the chains for each walker
                    2. dictionary the rejects for each walker
    """
    # deal with Pool specific imports
    from multiprocessing import get_context
#     from multiprocessing import set_start_method
#     try:
#         set_start_method("spawn")
#     except RuntimeError:
#         pass

    # --------------------------------------------------------------------------
    #setup the buffer if in_sampler
    if in_sampler is not None:
        #we want the buffer to be the merged walker chains from in_sampler
        #this is already available in in_sampler.chain
        buffer=in_sampler.chain
    else:
        buffer=None
    #if using mhg_mcmc then don't need a buffer
    #set it to None to reduce memory usage of pool processes
    if gkwargs['mcmcfunc'].__name__=='mhg_mcmc':
        buffer=None
    
    # list of params for each entry
    params_per_process = []
    # populate params for each sub group
    for nwalker in range(nwalkers):
        #copy the tfit for this walker
        htfit = sampler.tfit.copy()
        
        #update the starting point of this walker
        if in_sampler is not None:
            update_x0_p0_from_chain(htfit, in_sampler.wchains[nwalker], -1)

        args = (htfit, buffer, nwalker, gkwargs, 0)
        params_per_process.append(args)
        
    # get the number of threads (N_WALKER_THREADS)
    n_walker_threads = sampler.params['N_WALKER_THREADS']
    # start parallel jobs
    with get_context('fork').Pool(n_walker_threads, maxtasksperchild=1) as pool:
        results = pool.starmap(_linear_process, params_per_process)
#     with get_context('spawn').Pool(n_walker_threads, maxtasksperchild=1) as pool:
#         results = pool.starmap(_linear_process, params_per_process)
    
    # --------------------------------------------------------------------------
    # create the return dictionary
    wchains = dict()
    wrejects = dict()
    wlls = dict()
#     for nwalker in range(nwalkers):
#         wchains[nwalker] = np.array([])
#         wrejects[nwalker] = np.array([])
#         wlls[nwalker] = np.array([])

    # fudge back results into return dictionary
    for row in range(len(results)):
        # push chains into walker storage
        wchains[row] = merge_chains(sampler.wchains[row], results[row][0])
        # push rejects into walker storage
        wrejects[row] = merge_chains(sampler.wrejects[row], results[row][1])
        # push lls into walker storage
        wlls[row] = merge_chains(sampler.wlls[row], results[row][2])
    # --------------------------------------------------------------------------
    # return these
    return wchains, wrejects, wlls

def _linear_process(htfit: TransitFit, buffer: np.ndarray,
                    nwalker: int, gkwargs: dict,
                    ngroup: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    The linear process to run in parallel

    :param htfit: TransitFit object
    :param buffer: previous chain used as buffer for de_mcmc
    :param nwalker: int, the walker number
    :param gkwargs: dictionary, constant args to pass to genchain
    :param ngroup: int, the group number

    :return: tuple, 1. the chains, 2. the rejects, 3. the loglikelihoods
    """
    # get chains and rejects for this walker
    hchains, hrejects, hlls = genchain(htfit, buffer=buffer, nwalker=nwalker,
                                 ngroup=ngroup, **gkwargs)

    # return the return_dict
    return hchains, hrejects, hlls

def _linear_process_old(sampler: Sampler, in_sampler: Sampler,
                    nwalker: int, gkwargs: dict,
                    ngroup: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    The linear process to run in parallel

    :param sampler: Sampler class
    :param in_sampler: Sampler class, used for buffer if provided
    :param nwalker: int, the walker number
    :param gkwargs: dictionary, constant args to pass to the linear process
    :param ngroup: int, the group number

    :return: tuple, 1. the chains, 2. the rejects, 3. the loglikelihoods
    """
    # copy tfit
    htfit = sampler.tfit.copy()
    # get the buffer from previous chain and update tfit from
    #   previous chain.
    # Previous chain can be from another sampler or from a
    #   previous iteration of the NLOOP while loop
    # Also updates the starting x0 and p0 for htfit
    buffer, htfit = start_from_previous_chains(sampler, htfit, in_sampler)
    if in_sampler is not None: ###DL###
        update_x0_p0_from_chain(htfit, in_sampler.wchains[nwalker], -1) ###DL### patch to use state of current worker
    # get chains and rejects for this walker
    hchains, hrejects, hlls = genchain(htfit, buffer=buffer, nwalker=nwalker,
                                 ngroup=ngroup, **gkwargs) ###DL###
    # push chains into walker storage
    wchains = merge_chains(sampler.wchains[nwalker], hchains)
    # push rejects into walker storage
    wrejects = merge_chains(sampler.wrejects[nwalker], hrejects)
    # push lls into walker storage
    wlls = merge_chains(sampler.wlls[nwalker], hlls)

    # return the return_dict
    return wchains, wrejects, wlls


# =============================================================================
# Start of code
# =============================================================================
if __name__ == "__main__":
    # print hello world
    print('Hello World')

# =============================================================================
# End of code
# =============================================================================
