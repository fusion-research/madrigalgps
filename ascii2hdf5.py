#!/usr/bin/env python
"""
Michael Hirsch
Input: text file table
output: compressed HDF5
"""

from astropy.io import ascii

def ascii2hdf5(fn,ofn,h5path='data'):
    ascii.read(fn).write(ofn, format='hdf5', path=h5path, compression=True, overwrite=True)

if __name__ =='__main__':
    from argparse import ArgumentParser
    p = ArgumentParser(description="Convert ASCII text files of table data to HDF5 using AstroPy")
    p.add_argument('txtfn',help='ASCII text file to convert')
    p.add_argument('h5fn',help='HDF5 file to write')
    p.add_argument('--h5path',help='internal variable name of HDF5 table created from ASCII data',default='data')
    p = p.parse_args()

    ascii2hdf5(p.txtfn,p.h5fn,p.h5path)