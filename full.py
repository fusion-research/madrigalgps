from __future__ import division
from os.path import join
from datetime import datetime
from ephem import readtle,Observer
import numpy as np
from pandas import date_range, DataFrame,Panel
from pandas.io.pytables import read_hdf
from re import search
import h5py
import matplotlib.pyplot as plt
from time import time
from glob import glob
from warnings import warn
#
# glabals
tlefn = 'gps-ops.txt'
obslla = [65,-148,0]
beamfn = "PFISRbeammap.h5"
satfreq='5T' #T means minutes
datadir='files'
maxangdist=10 #degrees
maxdtsec = 15


def loopsat(tlefn,dates,obslla):
    obs = setupobs(obslla)
    return compsat(tlefn,obs,dates)[0]

def setupobs(lla):
    obs = Observer()
    try:
        obs.lat = str(lla[0]); obs.lon = str(lla[1]); obs.elevation=float(lla[2])
    except ValueError:
        warn('observation location not specified. defaults to lat=0, lon=0')
    return obs


def compsat(tlefn,obs,dates):
    cols = ['az','el','lat','lon','alt','srange']
    sats,satnum = loadTLE(tlefn)

    data = Panel(items=dates, major_axis=satnum, minor_axis=cols)
    for j,d in enumerate(dates):
        obs.date = d

        df = DataFrame(index=satnum,columns=cols)
        for i,s in enumerate(sats):
            si = satnum[i]
            s.compute(obs)
            df.at[si,['lat','lon','alt']] = np.degrees(s.sublat), np.degrees(s.sublong), s.elevation
            df.at[si,['az','el','srange']] = np.degrees(s.az), np.degrees(s.alt), s.range

        belowhoriz = df['el']<0
        df.ix[belowhoriz,['az','el','srange']] = np.nan

        data[d] = df

    return data,belowhoriz


def loadTLE(filename):
    """ Loads a TLE file and creates a list of satellites.
    http://blog.thetelegraphic.com/2012/gps-sattelite-tracking-in-python-using-pyephem/
    """
    #pat = '(?<=PRN)\d\d'
    with open(filename,'r') as f:
        satlist = []; prn = []
        l1 = f.readline()
        while l1:
            l2 = f.readline()
            l3 = f.readline()
            sat = readtle(l1,l2,l3)
            satlist.append(sat)

            prn.append(int(search(r'(?<=PRN)\s*\d\d',sat.name).group()))
            l1 = f.readline()

    return satlist,prn


def makeDates(sy,smo,sd):
    # 75x faster than for loop
    return date_range(start='{}-{}-{}T00:00:00'.format(sy,smo,sd),
                        end='{}-{}-{}T12:00:00'.format(sy,smo,sd),
                        freq=satfreq,closed='left').to_pydatetime().tolist()

def findIntersection(satdata,beamisr,dates,beamfn,maxdist):
    """
    iterate over time: for each time, was there a beam intersection for any satellite?
    There are 477 beams and 32 satellites.
    Would possibly be more efficient to use k-dimensional tree.
    In lieu of that, generally chose to loop over the variable with fewer elements for greater speed.
    Note: there are a lot of NaN satellite entries, making the satellite looping even faster
    """
    beamisr.loc[beamisr['AZM']<0,'AZM'] += 360

    #make a column (minor_axis) to store beam intersection ID for each sat at each time
    satdata.loc[:,:,'intersect'] = np.NaN

    for i,df in satdata.iteritems(): # for each time...
        #throw away satellites below horizon (majority are discarded for any time)
        df.dropna(axis=0,how='any',thresh=4,inplace=True)

        for r,d in df.iterrows(): # for each sat at this time...
            dist = np.hypot(d['az']-beamisr['AZM'], d['el']-beamisr['ELM'])
            if dist.min() < maxdist:
                satdata.loc[i,r,'intersect'] = beamisr.loc[dist.argmin(),'BEAMID']

    nIntersect = satdata.loc[:,:,'intersect'].count().sum()
    print('{} intersections found across all times and satellites.'.format(nIntersect))
    if nIntersect==0:
        raise ValueError('No satellite/radar intersections found at any time')

    return satdata


def checkFile(fn,satdata,beamisr,maxdtsec):
    """
    we need to find matching ISR beam IDs very near the time the satellite
    passes through the ISR beam.
    for speed, use Unix epoch time (seconds since Jan 1, 1970) for comparisons

    Note: the Madrigal HDF5 data is read in as a Numpy structured array

    output:
    tecisr: 2-D DataFrame, beamid x time

    """
    h5p = '/Data/Table Layout'
    #rows: satellite.  cols: time
    intersections = satdata.loc[:,:,'intersect']
    intersections.dropna(axis=1,how='all',inplace=True)

    beamlist = beamisr['BEAMID'].values # have to make a copy to sort
    beamlist.sort()

    tecisr = DataFrame(index=beamlist, columns=intersections.columns)

    try:
        with h5py.File(fn,'r',libver='latest') as f:
            for t in intersections: #for each time...
                #get the times for matching beam ids (not necessarily matching in time yet...)
                timeutc = f[h5p]['ut1_unix'][np.in1d(f[h5p]['beamid'].astype(int),intersections[t].dropna().astype(int))]
                #any of the times of those beams close enough?
                goodbeams = f[h5p][(timeutc - (t-datetime(1970,1,1)).total_seconds()) < maxdtsec]
                #TODO not tested past this point
                #TODO account for the case where there are two times and one beam that overlap with the satellite.
                """
                goodbeams will have numerous rows corresponding to each matching time & beam id
                each row is a range cell. These rows will be numerically integrated over Ne.
                """
                uniqbeamid = np.unique(goodbeams['beamid'])
                for b in uniqbeamid:
                    rows = np.where(np.isclose(goodbeams['beamid'],b))[0] #this is one beam's rows, all range bins
                    tecisr.loc[t,b] = np.trapz(goodbeams[rows,'ne'],goodbeams[rows,'range'])


    except ValueError as e:
        warn('{} does not seem to have the needed data fields e.g. "beamid", "ut1_unix" may be missing.   {}'.format(fn,e))
        return None

    return tecisr

#%% main program
dates = makeDates(2015,06,01)

tic = time()
satdata = loopsat(tlefn,dates,obslla)
print('{:.1f} seconds to compute orbits'.format(time()-tic))


tic = time()
beamisr = read_hdf(beamfn,'data')
satdata = findIntersection(satdata,beamisr,dates,beamfn,maxangdist)
print('{:.1f} seconds to compute intersections'.format(time()-tic))

flist = glob(join(datadir,'*.h5'))
for f in flist:
    goodbeams = checkFile(f,satdata,beamisr,maxdtsec)
