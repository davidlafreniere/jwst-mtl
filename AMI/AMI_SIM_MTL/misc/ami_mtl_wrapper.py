#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
# CODE NAME HERE

# CODE DESCRIPTION HERE

Created on 2021-02-15

@author: cook
"""

from ami_mtl.core.core import param_functions
from ami_mtl.core.core import log_functions
from ami_mtl.core.instrument import constants
from ami_mtl.science import wrap


# =============================================================================
# Define variables
# =============================================================================
# set name
__NAME__ = 'ami_mtl_wrapper.py'
__DESCRIPTION__ = ('wrapper around simulation + extraction + analysis codes '
                   'for JWST AMI mode')
# get default constants
consts = constants.Consts
# copy for update
lconsts = consts.copy(__NAME__)
# set very basic constants
__VERSION__ = lconsts.constants['PACKAGE_VERSION'].value
__DATE__ = lconsts.constants['PACKAGE_VERSION_DATE'].value
# set up the logger
log = log_functions.Log()
# define group name
group = 'recipe'

# =============================================================================
# Define arguments
# =============================================================================
# Define the config file
lconsts.add_argument('WCONFIG', value=None, dtype=str,
                     source=__NAME__, user=True, argument=True,
                     group=group,
                     description='Define the target as it appears in the '
                                 'APT file',
                     command=['--config'])

# =============================================================================
# Define functions
# =============================================================================
def main(**kwargs):
    """
    Main function: Do not add code here, add it in __main__
    :param kwargs:
    :return:
    """
    # for error handling set these
    params = consts.constants
    # wrap in error handler
    try:
        # get params (run time + config file + constants file)
        params = param_functions.setup(lconsts, kwargs, log=log,
                                       desc=__DESCRIPTION__, name=__NAME__)
        # run the __main__ to return products
        if not params['GENERATE_CONFIG_FILE']:
            returns = __main__(params)
            param_functions.success_end(params)
            return returns
    except Exception as e:
        if hasattr(e, '__log__'):
            log.exception(e.__log__())
            log.error(e.__log__())
        else:
            emsg = 'UNEXPECTED ERROR {0}: {1}'
            log.exception(emsg.format(type(e), str(e)))
            log.error(emsg.format(type(e), str(e)))
        return params
    except SystemExit as _:
        return params


def __main__(params):
    # =========================================================================
    # deal with wrapper file
    # =========================================================================
    simulations = wrap.load_simulations(params, str(params['WCONFIG']))

    # =========================================================================
    # Simulation section
    # =========================================================================
    wrap.sim_module(simulations)

    # =========================================================================
    # DMS section
    # =========================================================================
    # TODO: Add in later

    # =========================================================================
    # Extraction section
    # =========================================================================
    # wrap around ami-cal extraction
    # TODO: Add in later
    # wrap.amical_extraction(simulations)

    # =========================================================================
    # Analysis section
    # =========================================================================
    # wrap around ami-cal analysis
    # TODO: Add in later
    # wrap.amical_analysis(simulations)

    # =========================================================================
    # End of code
    # =========================================================================
    return params


# =============================================================================
# Start of code
# =============================================================================
if __name__ == "__main__":
    # test
    import sys
    # copy the yaml in ../inputs to somewhere not in the github repo
    sys.argv = 'test.py --config=/data/jwst_ami/data/neil_wrap/inputs/example.yaml'.split()

    # setup parameters
    params = param_functions.setup(lconsts, dict(), log=log,
                                   desc=__DESCRIPTION__, name=__NAME__)
    # load simulations
    simulations = wrap.load_simulations(params, str(params['WCONFIG']))

    # wrap around the simulation module
    wrap.sim_module(simulations)

    # TODO: wrap around dms
    # wrap.do_dms(simulations)

    # wrap around ami-cal extraction
    wrap.amical_extraction(simulations)

    # wrap around ami-cal analysis
    wrap.amical_analysis(simulations)

    # run main code
    #ll = main()

    # log end
    param_functions.success_end(params)

# =============================================================================
# End of code
# =============================================================================
