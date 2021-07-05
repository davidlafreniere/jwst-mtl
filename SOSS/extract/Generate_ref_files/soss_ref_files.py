#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  4 15:35:32 2020

@author: albert
"""

from datetime import datetime

import numpy as np
from astropy.io import fits
from astropy.table import Table

from SOSS.trace import tracepol  # TODO in the future this should not depend on tracepol.


# ==============================================================================
# Code for generating the spectral trace reference file.
# ==============================================================================


def init_spec_trace(wave_grid, xtrace, ytrace, tilt, throughput, subarray, filename=None):
    """Generate the NIRISS SOSS 1D trace reference file.
    """

    # Default filename.
    filepattern = 'SOSS_ref_trace_table_{}.fits'

    # TODO perform checks on input.
    # TODO enough wavelength range resolution, etc.

    if filename is None:
        filename = filepattern.format(subarray)

    # Create the reference file.
    hdul = list()
    hdu = fits.PrimaryHDU()
    hdu.header['DATE'] = (datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'Date this file was created (UTC)')
    hdu.header['ORIGIN'] = ('SOSS Team MTL', 'Orginazation responsible for creating file')
    hdu.header['TELESCOP'] = ('JWST', 'Telescope used to acquire the data')
    hdu.header['INSTRUME'] = ('NIRISS', 'Instrument used to acquire the data')
    hdu.header['SUBARRAY'] = (subarray, 'Subarray used')
    hdu.header['FILENAME'] = (filename, 'Name of the file')
    hdu.header['REFTYPE'] = ('SPECTRACE', 'Reference file type')
    hdu.header['PEDIGREE'] = ('GROUND', 'The pedigree of the refernce file')
    hdu.header['DESCRIP'] = ('1D trace decscription', 'Desription of the reference file')
    hdu.header['AUTHOR'] = ('Geert Jan Talens', 'Author of the reference file')
    hdu.header['USEAFTER'] = ('2000-01-01T00:00:00', 'Use after date of the reference file')
    hdu.header['EXP_TYPE'] = ('NIS_SOSS', 'Type of data in the exposure')
    hdul.append(hdu)

    # Order 1 table.
    col1 = fits.Column(name='WAVELENGTH', format='F', array=wave_grid)
    col2 = fits.Column(name='X', format='F', array=xtrace[:, 0])
    col3 = fits.Column(name='Y', format='F', array=ytrace[:, 0])
    col4 = fits.Column(name='THROUGHPUT', format='F', array=throughput[:, 0])
    col5 = fits.Column(name='TILT', format='F', array=tilt[:, 0])
    cols = fits.ColDefs([col1, col2, col3, col4, col5])

    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.header['ORDER'] = (1, 'Spectral order.')
    hdu.header['EXTNAME'] = 'ORDER'
    hdu.header['EXTVER'] = 1
    hdul.append(hdu)

    # Order 2 table.
    col1 = fits.Column(name='WAVELENGTH', format='F', array=wave_grid)
    col2 = fits.Column(name='X', format='F', array=xtrace[:, 1])
    col3 = fits.Column(name='Y', format='F', array=ytrace[:, 1])
    col4 = fits.Column(name='THROUGHPUT', format='F', array=throughput[:, 1])
    col5 = fits.Column(name='TILT', format='F', array=tilt[:, 1])
    cols = fits.ColDefs([col1, col2, col3, col4, col5])

    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.header['ORDER'] = (2, 'Spectral order.')
    hdu.header['EXTNAME'] = 'ORDER'
    hdu.header['EXTVER'] = 2
    hdul.append(hdu)

    # Order 3 table.
    col1 = fits.Column(name='WAVELENGTH', format='F', array=wave_grid)
    col2 = fits.Column(name='X', format='F', array=xtrace[:, 2])
    col3 = fits.Column(name='Y', format='F', array=ytrace[:, 2])
    col4 = fits.Column(name='THROUGHPUT', format='F', array=throughput[:, 2])
    col5 = fits.Column(name='TILT', format='F', array=tilt[:, 2])
    cols = fits.ColDefs([col1, col2, col3, col4, col5])

    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.header['ORDER'] = (3, 'Spectral order.')
    hdu.header['EXTNAME'] = 'ORDER'
    hdu.header['EXTVER'] = 3
    hdul.append(hdu)

    hdul = fits.HDUList(hdul)

    return hdul


# ==============================================================================
# Code for generating the wave map reference file.
# ==============================================================================


def calc_2d_wave_map(wave_grid, x_dms, y_dms, tilt, oversample=2, padding=10, maxiter=5, dtol=1e-2):
    """Compute the 2D wavelength map on the detector.

    :param wave_grid: The wavelength corresponding to the x_dms, y_dms, and tilt values.
    :param x_dms: the trace x position on the detector in DMS coordinates.
    :param y_dms: the trace y position on the detector in DMS coordinates.
    :param tilt: the trace tilt angle in degrees.
    :param oversample: the oversampling factor of the input coordinates.
    :param padding: the native pixel padding around the edge of the detector.
    :param maxiter: the maximum number of iterations used when solving for the wavelength at each pixel.
    :param dtol: the tolerance of the iterative solution in pixels.

    :type wave_grid: array[float]
    :type x_dms: array[float]
    :type y_dms: array[float]
    :type tilt: array[float]
    :type oversample: int
    :type padding: int
    :type maxiter: int
    :type dtol: float

    :returns: wave_map_2d - an array containing the wavelength at each pixel on the detector.
    :rtype: array[float]
    """

    os = np.copy(oversample)
    xpad = np.copy(padding)
    ypad = np.copy(padding)

    # No need to compute wavelengths across the entire detector, slightly larger than SUBSTRIP256 will do.
    dimx, dimy = 2048, 300
    y_dms = y_dms + (dimy - 2048)  # Adjust y-coordinate to area of interest.

    # Generate the oversampled grid of pixel coordinates.
    x_vec = np.arange((dimx + 2*xpad)*os)/os - (os - 1)/(2*os) - xpad
    y_vec = np.arange((dimy + 2*ypad)*os)/os - (os - 1)/(2*os) - ypad
    x_grid, y_grid = np.meshgrid(x_vec, y_vec)

    # Iteratively compute the wavelength at each pixel.
    delta_x = 0.0  # A shift in x represents a shift in wavelength.
    for niter in range(maxiter):

        # Assume all y have same wavelength.
        wave_iterated = np.interp(x_grid - delta_x, x_dms[::-1], wave_grid[::-1])  # Invert arrays to get increasing x.

        # Compute the tilt angle at the wavelengths.
        tilt_tmp = np.interp(wave_iterated, wave_grid, tilt)

        # Compute the trace position at the wavelengths.
        x_estimate = np.interp(wave_iterated, wave_grid, x_dms)
        y_estimate = np.interp(wave_iterated, wave_grid, y_dms)

        # Project that back to pixel coordinates.
        x_iterated = x_estimate + (y_grid - y_estimate)*np.tan(np.deg2rad(tilt_tmp))

        # Measure error between requested and iterated position.
        delta_x = delta_x + (x_iterated - x_grid)

        # If the desired precision has been reached end iterations.
        if np.all(np.abs(x_iterated - x_grid) < dtol):
            break

    # Evaluate the final wavelength map, this time setting out-of-bounds values to NaN.
    wave_map_2d = np.interp(x_grid - delta_x, x_dms[::-1], wave_grid[::-1], left=np.nan, right=np.nan)

    # Extend to full detector size.
    tmp = np.full((os*(dimx + 2*xpad), os*(dimx + 2*xpad)), fill_value=np.nan)
    tmp[-os*(dimy + 2*ypad):] = wave_map_2d
    wave_map_2d = tmp

    return wave_map_2d


def init_wave_map():
    """Generate the NIRISS SOSS 2D wavelength reference file."""

    # Fixed parameters for the 2D wavelength map reference file.
    padding = 10
    oversample = 2
    orders = [1, 2, 3]
    subarrays = ['FULL', 'SUBSTRIP96', 'SUBSTRIP256']
    soss_ref_trace_table = 'SOSS_ref_trace_table_FULL.fits'  # Input SOSS reference file.
    filepattern = 'SOSS_ref_2D_wave_{}.fits'  # Output SOSS reference file.

    for subarray in subarrays:

        if subarray == 'FULL':
            lrow = 0
            urow = oversample * (2048 + 2 * padding)
            lcol = 0
            ucol = oversample * (2048 + 2 * padding)
            filename = filepattern.format(subarray)
        elif subarray == 'SUBSTRIP96':
            lrow = oversample * (2048 - 246)
            urow = oversample * (2048 - 150 + 2 * padding)
            lcol = 0
            ucol = oversample * (2048 + 2 * padding)
            filename = filepattern.format(subarray)
        elif subarray == 'SUBSTRIP256':
            lrow = oversample * (2048 - 256)
            urow = oversample * (2048 + 2 * padding)
            lcol = 0
            ucol = oversample * (2048 + 2 * padding)
            filename = filepattern.format(subarray)
        else:
            raise ValueError('Unknown subarray: {}'.format(subarray))

        # Start building the output fits file.
        hdul = list()
        hdu = fits.PrimaryHDU()
        hdu.header['DATE'] = (datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'Date this file was created (UTC)')
        hdu.header['ORIGIN'] = ('SOSS Team MTL', 'Orginazation responsible for creating file')
        hdu.header['TELESCOP'] = ('JWST', 'Telescope used to acquire the data')
        hdu.header['INSTRUME'] = ('NIRISS', 'Instrument used to acquire the data')
        hdu.header['SUBARRAY'] = (subarray, 'Subarray used')
        hdu.header['FILENAME'] = (filename, 'Name of the file')
        hdu.header['REFTYPE'] = ('WAVEMAP', 'Reference file type')
        hdu.header['PEDIGREE'] = ('GROUND', 'The pedigree of the refernce file')
        hdu.header['DESCRIP'] = ('2D wavelength map', 'Desription of the reference file')
        hdu.header['AUTHOR'] = ('Geert Jan Talens', 'Author of the reference file')
        hdu.header['USEAFTER'] = ('2000-01-01T00:00:00', 'Use after date of the reference file')
        hdu.header['EXP_TYPE'] = ('NIS_SOSS', 'Type of data in the exposure')
        hdul.append(hdu)

        for m in orders:

            # Read the 1D trace reference file.
            data = fits.getdata(soss_ref_trace_table, ext=m)

            # Unpack the 1D trace info.
            wave_grid = data['WAVELENGTH']
            x_dms = data['X']
            y_dms = data['Y']
            tilt = data['TILT']

            # Compute the 2D wavelength map.
            wave_map_2d = calc_2d_wave_map(wave_grid, x_dms, y_dms, tilt, oversample=oversample, padding=padding)

            # Add the 2D wavelength map to the fits file.
            hdu = fits.ImageHDU(wave_map_2d[lrow:urow, lcol:ucol].astype('float32'))
            hdu.header['ORDER'] = (m, 'Spectral order.')
            hdu.header['OVERSAMP'] = (oversample, 'Pixel oversampling.')
            hdu.header['PADDING'] = (padding, 'Native pixel-size padding around the image.')
            hdu.header['EXTNAME'] = 'ORDER'
            hdu.header['EXTVER'] = m
            hdul.append(hdu)

        hdul = fits.HDUList(hdul)
        hdul.writeto(filename, overwrite=True)
        hdul.writeto(filename + '.gz', overwrite=True)

    return


# ==============================================================================
# Code for generating the spectral profile reference file.
# ==============================================================================


def init_spec_profile(profile_file=None):
    """"""

    if profile_file is None:
        'files/2DTrace.fits'

    # Fixed parameters for the 2D wavelength map reference file.
    padding = 10
    oversample = 2
    orders = [1, 2, 3]
    subarrays = ['FULL', 'SUBSTRIP96', 'SUBSTRIP256']
    filepattern = 'SOSS_ref_2D_profile_{}.fits'  # Output SOSS reference file.

    for subarray in subarrays:

        if subarray == 'FULL':
            lrow = 0
            urow = oversample * (2048 + 2 * padding)
            lcol = 0
            ucol = oversample * (2048 + 2 * padding)
            filename = filepattern.format(subarray)
        elif subarray == 'SUBSTRIP96':
            lrow = oversample * (2048 - 246)
            urow = oversample * (2048 - 150 + 2 * padding)
            lcol = 0
            ucol = oversample * (2048 + 2 * padding)
            filename = filepattern.format(subarray)
        elif subarray == 'SUBSTRIP256':
            lrow = oversample * (2048 - 256)
            urow = oversample * (2048 + 2 * padding)
            lcol = 0
            ucol = oversample * (2048 + 2 * padding)
            filename = filepattern.format(subarray)
        else:
            raise ValueError('Unknown subarray: {}'.format(subarray))

        # Start building the output fits file.
        hdul = list()
        hdu = fits.PrimaryHDU()
        hdu.header['DATE'] = (datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'Date this file was created (UTC)')
        hdu.header['ORIGIN'] = ('SOSS Team MTL', 'Orginazation responsible for creating file')
        hdu.header['TELESCOP'] = ('JWST', 'Telescope used to acquire the data')
        hdu.header['INSTRUME'] = ('NIRISS', 'Instrument used to acquire the data')
        hdu.header['SUBARRAY'] = (subarray, 'Subarray used')
        hdu.header['FILENAME'] = (filename, 'Name of the file')
        hdu.header['REFTYPE'] = ('SPECPROFILE', 'Reference file type')
        hdu.header['PEDIGREE'] = ('GROUND', 'The pedigree of the refernce file')
        hdu.header['DESCRIP'] = ('2D trace profile', 'Desription of the reference file')
        hdu.header['AUTHOR'] = ('Loic Albert', 'Author of the reference file')
        hdu.header['USEAFTER'] = ('2000-01-01T00:00:00', 'Use after date of the reference file')
        hdu.header['EXP_TYPE'] = ('NIS_SOSS', 'Type of data in the exposure')
        hdul.append(hdu)

        for m in orders:

            # TODO Read file provided by Loïc, replace with function that generates this info in the future.
            profile_2d = fits.getdata(profile_file, ext=0)
            profile_2d = profile_2d[m - 1]

            nrows, ncols = profile_2d.shape
            dimy = oversample*(2048 + 2*padding)
            dimx = oversample*(2048 + 2*padding)

            tmp = np.full((dimy, dimx), fill_value=np.nan)
            tmp[-nrows:] = profile_2d
            profile_2d = tmp

            # Add the 2D wavelength map to the fits file.
            hdu = fits.ImageHDU(profile_2d[lrow:urow, lcol:ucol].astype('float32'))
            hdu.header['ORDER'] = (m, 'Spectral order.')
            hdu.header['OVERSAMP'] = (oversample, 'Pixel oversampling.')
            hdu.header['PADDING'] = (padding, 'Native pixel-size padding around the image.')
            hdu.header['EXTNAME'] = 'ORDER'
            hdu.header['EXTVER'] = m
            hdul.append(hdu)

        hdul = fits.HDUList(hdul)
        hdul.writeto(filename, overwrite=True)
        hdul.writeto(filename + '.gz', overwrite=True)

    return


# ==============================================================================
# Code for generating the spectral kernel reference file.
# ==============================================================================


def init_spec_kernel(wavelengths, kernels, specos, halfwidth,
                     nwave, wavemin, wavemax, filename=None):
    """"""

    # Output SOSS reference file.
    if filename is None:
        filename = 'SOSS_ref_spectral_kernel.fits'

    # TODO perform checks on the input.

    # Start building the output fits file.
    hdul = list()
    hdu = fits.PrimaryHDU()
    hdu.header['DATE'] = (datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'Date this file was created (UTC)')
    hdu.header['ORIGIN'] = ('SOSS Team MTL', 'Orginazation responsible for creating file')
    hdu.header['TELESCOP'] = ('JWST', 'Telescope used to acquire the data')
    hdu.header['INSTRUME'] = ('NIRISS', 'Instrument used to acquire the data')
    hdu.header['FILENAME'] = (filename, 'Name of the file')
    hdu.header['REFTYPE'] = ('SPECKERNEL', 'Reference file type')
    hdu.header['PEDIGREE'] = ('GROUND', 'The pedigree of the refernce file')
    hdu.header['DESCRIP'] = ('Convolution kernels', 'Desription of the reference file')
    hdu.header['AUTHOR'] = ('Loic Albert', 'Author of the reference file')
    hdu.header['USEAFTER'] = ('2000-01-01T00:00:00', 'Use after date of the reference file')
    hdu.header['EXP_TYPE'] = ('NIS_SOSS', 'Type of data in the exposure')
    hdul.append(hdu)

    # Create the wavelength extension.
    hdu = fits.ImageHDU(wavelengths.astype('float32'))
    hdu.header['EXTVER'] = 1
    hdu.header['EXTNAME'] = 'WAVELENGTHS'
    hdu.header['NWAVE'] = (nwave, 'The number of wavelengths used.')
    hdu.header['WAVEMIN'] = (wavemin, 'Wavelength of the first kernel (in microns).')
    hdu.header['WAVEMAX'] = (wavemax, 'Wavelength of the last kernel (in microns).')
    hdul.append(hdu)

    # Create the kernel extension.
    hdu = fits.ImageHDU(kernels.astype('float32'))
    hdu.header['EXTVER'] = 1
    hdu.header['EXTNAME'] = 'KERNELS'
    hdu.header['SPECOS'] = (specos, 'The spectral oversampling of the native pixels.')
    hdu.header['HALFWIDT'] = (halfwidth, 'The half width of the kernel in native pixels.')
    hdu.header['INDCENTR'] = (specos*halfwidth + 1, 'Index of the kernel centroid.')
    hdul.append(hdu)

    # Write the file to disk.
    hdul = fits.HDUList(hdul)

    return hdul


def main():

    return


if __name__ == '__main__':
    main()
