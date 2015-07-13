#!/usr/bin/env python2
from madrigalWeb import madrigalWeb as MW
from os.path import join,basename
from os import mkdir
from time import time
# globals
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
if __name__ == '__main__':
    from argparse import ArgumentParser
    p = ArgumentParser(description='scan Madrigal with criteria')
    p.add_argument('filtername',help='madrigal filter filename (local file)',nargs='?',default='enddown.txt')
    p.add_argument('-u','--username',help='your name',default='guest')
    p.add_argument('-e','--email',help='your email',default='guest')
    p.add_argument('-i','--institution',help='your institution',default='nobody')
    p.add_argument('--download',help='type of file to download',default='hdf5')
    p.add_argument('--madurl',help='madrigal server url',default='http://isr.sri.com/madrigal/')
    p.add_argument('--outdir',help='path to save madrigal data to',default='files')
    p = p.parse_args()

    tic = time()
    files = getFiles(p.filtername,limit)
    print('filtered file list in {:.4f} sec.'.format(time()-tic))
    try:
        mkdir(p.outdir)
    except OSError: #directory already exists
        pass
    #%%
    print('connecting to {}'.format(p.madurl))
    site = MW.MadrigalData(p.madurl)

    for f in files:
        print('processing {}'.format(f))
        site.downloadFile(f, join(p.outdir,basename(f)+'.h5'),
                          p.username,p.email,p.institution,p.download)
