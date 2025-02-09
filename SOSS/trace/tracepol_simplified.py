"""
Created on Mon Feb 17 13:31:58 2020

@author: talens-irex
"""

import numpy as np

from numpy.polynomial import Legendre

import matplotlib.pyplot as plt

from astropy.io import ascii

# SUBSTRIP256 keeps columns 0:255 (0 based) in the nat frame.
# SUBSTRIP96 keeps columns 150:245 (0 based) in the nat frame.

# Default parameters for the CV3 calibration of the trace positions.
ANGLE_CV3 = 1.3824300138
ORIGIN_CV3 = np.array([1419.8897384173, 472.9340739229])


def apply_rotation(coords, origin=ORIGIN_CV3, angle=ANGLE_CV3):
    """Rotate a point counterclockwise by a given angle around a given origin.
    The angle should be given in radians. This transformation is performed
    in the native coordinates (aka ds9).

    The defaults were obtained using calibrate_tracepol.py

    :param coords: x, y coordinates to rotate.
    :param origin: point around which to rotate the coordinates.
    :param angle: angle in degrees.

    :type coords: Tuple(array[float], array[float])
    :type origin: array[float]
    :type angle: float

    :returns: x_rot, y_rot - rotated coordinates.
    :rtype: Tuple(array[float], array[float])
    """

    x, y = coords
    origin_x, origin_y = origin
    angle = np.deg2rad(angle)

    dx, dy = x - origin_x, y - origin_y
    x_rot = np.cos(angle) * dx - np.sin(angle) * dy + origin_x
    y_rot = np.sin(angle) * dx + np.cos(angle) * dy + origin_y

    return x_rot, y_rot


def trace_polynomial(trace, m=1, maxorder=15):
    """Fit a polynomial to the trace of order m and return a
    dictionary containing the parameters and validity intervals.

    :param trace: astropy table containing modelled trace points.
    :param m: spectral order for which to fit a polynomial.
    :param maxorder: maximum polynomial order to use.

    :type trace: astropy.table.Table
    :type m: int
    :type maxorder: int

    :returns: pars - dictionary containg the polynomial solution.
    :rtype: dict
    """

    # TODO added arbitrary maxorder to deal with poor exrapolatian, revisit when extrapolation fixed.

    # Select the data for order m.
    mask = (trace['order'] == m)
    wave = trace['Wavelength'][mask]
    spatpix_ref = trace['ypos'][mask]
    specpix_ref = trace['xpos'][mask]

    # Find the edges of the domain.
    wavemin = np.amin(wave)
    wavemax = np.amax(wave)

    # Compute the polynomial parameters for x and y.
    order = 0
    while order <= maxorder:

        spatpol = Legendre.fit(np.log(wave), spatpix_ref, order)
        specpol = Legendre.fit(np.log(wave), specpix_ref, order)

        spatpixp_nat = spatpol(np.log(wave))
        specpixp_nat = specpol(np.log(wave))

        if np.all(np.abs(spatpix_ref - spatpixp_nat) < 0.5) & np.all(np.abs(specpix_ref - specpixp_nat) < 0.5):
            break

        order += 1

    # Compute the transform back to wavelength.
    #wavegrid = wavemin + (wavemax - wavemin) * np.linspace(0., 1., 501)
    #specgrid = specpol(np.log(wavegrid))
    #wavepol = Legendre.fit(specgrid, np.log(wavegrid), order)

    # Add the parameters to a dictionary.
    pars = dict()
    pars['spat_coef'] = spatpol.coef
    pars['spat_domain'] = spatpol.domain
    pars['spec_coef'] = specpol.coef
    pars['spec_domain'] = specpol.domain
    #pars['wave_coef'] = wavepol.coef
    #pars['wave_domain'] = wavepol.domain

    return pars


def get_tracepars(filename=None, origin=ORIGIN_CV3, angle=ANGLE_CV3,
                  disable_rotation=False):
    """Read a file containing the trace profile and generate
    polynomial parameters for each order.

    :param filename: file containing modelled trace points.
    :param origin: point around which to rotate the coordinates.
    :param angle: angle in degrees.
    :param disable_rotation: True or False to disable the rotation calibration that brings
    the optics model file in agreement with the CV3 data.

    :type filename: str
    :type origin: array[float]
    :type angle: float

    :returns: tracepars - a dictionary containg the parameters for the polynomial fits.
    For example tracepars[-1] returns the parameters for order = -1 as a dictionary.
    :rtype: dict
    """

    if filename is None:
        filename = 'NIRISS_GR700_trace_extended.csv'  # TODO Switch to pkg_resources in the future.

    # Read the trace.
    trace = ascii.read(filename)  # Read the Code V trace model from file. DS9 coordinates are used.

    # Convert from the ds9 (native) coordinates to DMS coordinates
    x = trace['xpos'].copy()
    y = trace['ypos'].copy()
    # Rotate 90 degrees and mirror vertically, making sure that the SUBSTRIP256 origin is conserved
    trace['xpos'] = 2048*0.018 - y
    trace['ypos'] = 256*0.018 - x

    # Convert to pixel coordinates.
    trace['xpos'] /= 0.018  # Convert from micron to pixels.
    trace['ypos'] /= 0.018  # Convert from micron to pixels.
    trace['xpos'] -= 0.5  # Set the origin at the center of the lower-left pixel.
    trace['ypos'] -= 0.5  # Set the origin at the center of the lower-left pixel.
    # trace['xpos'] -= 0.0  # Set the origin at the center of the lower-left pixel.
    # trace['ypos'] -= 0.0  # Set the origin at the center of the lower-left pixel.

    #plt.figure()
    #plt.scatter(trace['xpos'], trace['ypos'])
    #plt.show()

    # Apply rotation around point (by default).
    if not disable_rotation:
        trace['xpos'], trace['ypos'] = apply_rotation((trace['xpos'], trace['ypos']), origin=origin, angle=angle)

    # Compute polynomial parameters for different orders.
    tracepars = dict()
    for m in np.unique(trace['order']):
        pars = trace_polynomial(trace, m=m)
        tracepars[m] = pars

    return tracepars


def bounds_check(values, lower, upper):
    """Perform a simple bounds check on an array.

    :param values: an array of values.
    :param lower: the lower bound of the valid range.
    :param upper: the upper bound of the valid range.

    :type values: array[float]
    :type lower: float
    :type upper: float

    :returns: mask - a boolean array that is True when values is between lower and upper.
    :rtype: array[bool]
    """

    mask = (values >= lower) & (values <= upper)

    return mask


def subarray_wavelength_bounds(tracepars, m=1, subarray='SUBSTRIP256',
                               specpix_offset=0, spatpix_offset=0):
    """Compute the minimum and maximum wavelength of a given order in a given
    subarray.

    :param tracepars: the trace polynomial solutions returned by get_tracepars.
    :param subarray: the output coordinate subarray.
    :param m: the spectral order.
    :param specpix_offset: a pixel offset by which the traces are positioned
        relative to the model given by tracepars.
    :param spatpix_offset: a pixel offset by which the traces are positioned
        relative to the model given by tracepars.

    :returns: (wave_min, wave_max), (pixel_min, pixel_max) - A tuple of
        wavelength bounds and a tuple of the corresponding pixel bounds.
    :rtype: Tuple(Tuple(float, float), Tuple(float, float))
    """

    # Generate wavelengths (microns) spanning all orders
    wavelength = np.linspace(0.5, 5.5, 50001)

    # Convert wavelengths to dms pixel coordinates in the requested subarray.
    specpix, spatpix, _ = wavelength_to_pix(wavelength, tracepars, m=m, subarray=subarray)

    # Apply the offsets.
    specpix = specpix + specpix_offset
    spatpix = spatpix + spatpix_offset

    # Determine the valid region in both pixel coordinate directions.
    mask_spec = (specpix >= 0) & (specpix < 2048)

    if subarray == 'SUBSTRIP256':
        mask_spat = (spatpix >= 0) & (spatpix < 256)
    elif subarray == 'SUBSTRIP96':
        mask_spat = (spatpix >= 0) & (spatpix < 96)
    elif subarray == 'FULL':
        mask_spat = (spatpix >= 0) & (spatpix < 2048)
    else:
        msg = 'Unknown subarray: {}'
        raise ValueError(msg.format(subarray))

    # Combine the masks.
    mask = mask_spec & mask_spat

    # Obtain the bounds in wavelength units.
    wave_min = np.min(wavelength[mask])
    wave_max = np.max(wavelength[mask])

    # Obtain the bounds in pixel units.
    pixel_min = np.min(specpix[mask])
    pixel_max = np.max(specpix[mask])

    return (wave_min, wave_max), (pixel_min, pixel_max)




def wavelength_to_pix(wavelength, tracepars, m=1, subarray='SUBSTRIP256', oversample=1):
    """Convert wavelength to pixel coordinates for order m.

    :param wavelength: wavelength values in microns.
    :param tracepars: the trace polynomial solutions returned by get_tracepars.
    :param m: the spectral order.
    :param frame: the coordinate frame of the output coordinates (nat, dms or sim).
    :param subarray: the subarray of the output coordinates (SUBARRAY256 or SUBARRAY96).
    :param oversample: the oversampling factor of the outpur coordinates.

    :type wavelength: array[float]
    :type tracepars: dict
    :type m: int
    :type frame: str
    :type subarray: str
    :type oversample: int

    :returns: specpix - the spectral pixel coordinates, spatpix - the spatial pixel coordinates,
    mask - an array that is True when the specpix values were within the valid range of the polynomial.
    :rtype: Tuple(array[float], array[float], array[bool])
    """

    # Convert wavelength to nat pixel coordinates.
    w2spec = Legendre(tracepars[m]['spec_coef'], domain=tracepars[m]['spec_domain'])
    w2spat = Legendre(tracepars[m]['spat_coef'], domain=tracepars[m]['spat_domain'])

    specpix_nat = w2spec(np.log(wavelength))
    spatpix_nat = w2spat(np.log(wavelength))
    mask = bounds_check(np.log(wavelength), tracepars[m]['spec_domain'][0], tracepars[m]['spec_domain'][1])

    ## Convert coordinates to the requested frame.
    #specpix, spatpix = pix_ref_to_frame(specpix_nat, spatpix_nat, frame=frame, subarray=subarray)

    # Oversample the coordinates.
    specpix = specpix_nat * oversample
    spatpix = spatpix_nat * oversample

    return specpix, spatpix, mask

def specpix_to_wavelength_new(specpix, tracepars, m=1, oversample=1):
    """Convert the spectral pixel coordinate to wavelength for order m.

    :param specpix: the pixel values.
    :param tracepars: the trace polynomial solutions returned by get_tracepars.
    :param m: the spectral order.
    :param oversample: the oversampling factor of the input coordinates.

    :type specpix: array[float]
    :type tracepars: dict
    :type m: int
    :type frame: str
    :type oversample: int

    :returns: wavelength - an array containing the wavelengths corresponding to specpix,
    mask - an array that is True when the specpix values were within the valid range of the polynomial.
    :rtype: Tuple(array[float], array[bool])
    """
    # Convert wavelength to nat pixel coordinates.
    w2spec = Legendre(tracepars[m]['spec_coef'], domain=tracepars[m]['spec_domain'])
    #w2spat = Legendre(tracepars[m]['spat_coef'], domain=tracepars[m]['spat_domain']) - not used

    # Do the forward transformation on the widest range of wavelengths
    wavelength_generic = np.linspace(0.4,5.5,51001)
    # Apply the transformation on these wavelengths
    specpix_nat = w2spec(np.log(wavelength_generic))
    #spatpix_nat = w2spat(np.log(wavelength_generic)) - not used

    # Interpolate the wide range of wavelengths to the ones actually requested
    wavelength = np.interp(specpix / oversample, specpix_nat, wavelength_generic)
    mask = bounds_check(np.log(wavelength), tracepars[m]['spec_domain'][0], tracepars[m]['spec_domain'][1])

    return wavelength, mask


def specpix_to_wavelength(specpix, tracepars, m=1, oversample=1):
    """Convert the spectral pixel coordinate to wavelength for order m.

    :param specpix: the pixel values.
    :param tracepars: the trace polynomial solutions returned by get_tracepars.
    :param m: the spectral order.
    :param oversample: the oversampling factor of the input coordinates.

    :type specpix: array[float]
    :type tracepars: dict
    :type m: int
    :type frame: str
    :type oversample: int

    :returns: wavelength - an array containing the wavelengths corresponding to specpix,
    mask - an array that is True when the specpix values were within the valid range of the polynomial.
    :rtype: Tuple(array[float], array[bool])
    """

    # Remove any oversampling.
    specpix_nat = specpix / oversample

    # Convert the specpix coordinates to wavelength.
    spec2w = Legendre(tracepars[m]['wave_coef'], domain=tracepars[m]['wave_domain'])

    with np.errstate(over='ignore'):
        wavelength = np.exp(spec2w(specpix_nat))
    mask = bounds_check(specpix_nat, tracepars[m]['wave_domain'][0], tracepars[m]['wave_domain'][1])

    return wavelength, mask


def wavelength_map_2d(tracepars, m=1, subarray='SUBSTRIP256', oversample=1, use_tilt=False):
    """Compute the wavelengths of order m in dms coordinates for the specified subarray.

    :param tracepars: the trace polynomial solutions returned by get_tracepars.
    :param m: the spectral order.
    :param subarray: the subarray of the output coordinates (SUBARRAY256 or SUBARRAY96).
    :param oversample: the oversampling factor of the input coordinates.
    :param use_tilt: Include the effect of tilt in the output.

    :type tracepars: dict
    :type m: int
    :type subarray: str
    :type oversample: int
    :type use_tilt: bool

    :returns: wavelength_map - A 2D array of wavelength values across the detector.
    :rtype: array[float]
    """

    if use_tilt:
        raise ValueError("The 'use_tilt' option has not yet been implemented.")

    # Get the coordinates of the pixels in the subarray.
    spatpix_dms, specpix_dms = np.indices((256 * int(oversample), 2048 * int(oversample)))

    # Convert to wavelengths using the trace polynomials.
    wavelength_map, mask = specpix_to_wavelength(specpix_dms, tracepars, m=m, frame='dms', oversample=oversample)

    # Set out-of-bounds and reference pixels to zero.
    wavelength_map[~mask] = 0
    wavelength_map[-4 * int(oversample):] = 0
    wavelength_map[:, :4 * int(oversample)] = 0
    wavelength_map[:, -4 * int(oversample):] = 0

    if subarray == 'SUBSTRIP256':
        pass
    elif subarray == 'SUBSTRIP96':
        wavelength_map = wavelength_map[10 * int(oversample):106 * int(oversample)]
    else:
        raise ValueError('Unknown subarray: {}'.format(subarray))

    return wavelength_map


def test_tracepol(filename=None):
    ''' Test tracepol consistency'''

    import matplotlib.pyplot as plt

    if filename is None:
        filename = '/genesis/jwst/jwst-ref-soss/trace_model/NIRISS_GR700_trace_extended.csv'  # TODO Switch to pkg_resources in the future.

    pars = get_tracepars(filename)

    w = np.linspace(0.84, 2.9, 50)
    specpix_dms, spatpix_dms, mask = wavelength_to_pix(w, pars, m=1)
    wave, mask = specpix_to_wavelength(specpix_dms, pars, m=1)

    dw = wave - w


    plt.figure()
    plt.scatter(specpix_dms, dw, color='red')
    plt.show()

    # xindx = np.linspace(0,2047,2048)

    return


