#!/usr/bin/env python2
from madrigalWeb import madrigalWeb as MW
from os.path import join,basename
from os import mkdir
from time import time
# globals
madfiltfn = "later files.txt"
limit = 100

def getFiles(filename,limit):

    with open(filename,'r') as f:
        files = []
        line = f.readline()
        while line and len(files)<limit:
            if line.startswith('/opt/madrigal') and not f.readline().startswith('No records'):
                    files.append(line.strip())
            line = f.readline()

    return files
#%% main program

url = 'http://isr.sri.com/madrigal/'
outdir = 'files'
username = 'greg starr'
email = 'gstarr@bu.edu'
institution = 'BU'
dltype = 'hdf5'


tic = time()
files = getFiles(madfiltfn,limit)
print('filtered file list in {:.4f} sec.'.format(time()-tic))
try:
    mkdir(outdir)
except OSError: #directory already exists
    pass
#%%
print('connecting to {}'.format(url))
site = MW.MadrigalData(url)

for f in files:
    print('processing {}'.format(f))
    site.downloadFile(f,join(outdir,basename(f)+'.h5'),username,email,institution,dltype)
