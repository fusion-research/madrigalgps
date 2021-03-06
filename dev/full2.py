from __future__ import division
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
import math
from warnings import warn
from os import remove


def dateCalc(ow,os):
    if os<0:
        ow-=1
        os+=7*24*60*60
    dic = dict([(6,30),(7,31),(8,31),(9,30),(10,31),(11,30),(12,31),(1,31),(2,28),(3,31),(4,30),(5,31)])
    odays = os/(60*60*24) + ow*7
    oseconds = os%(60*60*24)
    seconds = 0
    minute = 1
    hour = 5
    month = 1
    year = 1980
    day = 6

    for i in range(odays):
        if year%4==0:
            dic[2]=29
        else:
            dic[2]=28

        if day==dic[month]:
            if month==12:
                month=1
                year+=1
            else:
                month+=1
            day=1
        else:
            day+=1

    hour += oseconds/(60*60)
    if hour>24:
        day += 1
        hour -= 24
    oseconds-=(60*60*(hour-5))
    minute=oseconds/60
    seconds=oseconds%60

    return datetime(year,month,day,hour,minute,seconds)


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
            if np.isfinite(s.sublat): #if sublat is nan, that means SGP4 couldn't solve for position
                df.at[si,['lat','lon','alt']] = np.degrees(s.sublat), np.degrees(s.sublong), s.elevation
                df.at[si,['az','el','srange']] = np.degrees(s.az), np.degrees(s.alt), s.range
        #FIXME: add dropna for times that sublat is NaN
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

    for t,df in satdata.iteritems(): # for each time...
        #throw away satellites below horizon (majority are discarded for any time)
        df.dropna(axis=0,how='any',thresh=4,inplace=True)

        for svnum,d in df.iterrows(): # for each sat at this time...
            dist = np.hypot(d['az']-beamisr['AZM'], d['el']-beamisr['ELM'])
            if dist.min() < maxdist:
                satdata.loc[t,svnum,'intersect'] = beamisr.loc[dist.argmin(),'BEAMID']

    nIntersect = satdata.loc[:,:,'intersect'].count().sum()
    print('{} intersections found across all times and satellites.'.format(nIntersect))
    if nIntersect==0:
        print 'no intersections found'

    return satdata


def checkFile(fn,satdata,beamisr,maxdtsec):
    """
    we need to find matching ISR beam IDs very near the time the satellite
    passes through the ISR beam.
    for speed, use Unix epoch time (seconds since Jan 1, 1970) for comparisons

    Note: the Madrigal HDF5 data is read in as a Numpy structured array

    Algorithm (not optimized):
    1) knowing what satellites will eventually intersect beams, are any of those beamids in this file?
    2) knowing what times intersections will occur, do those times exist in this file for those beams?
    3) For the beams that meet conditions 1 and 2, compute TEC by numerical integration of NE

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
                #mask for matching beam ids (not necessarily matching in time yet...)
                intmask = np.in1d(f[h5p]['beamid'].astype(int),intersections[t].dropna().astype(int))
                if not intmask.any(): #no overlap, no point in evaluating times
                    continue
                #mask for matching times (not necessarily matching beamids)
                timemask =np.absolute(f[h5p]['ut1_unix'] - (t.to_pydatetime()-datetime(1970,1,1)).total_seconds()) < maxdtsec
                #mask for where beamid and times "match"
                inttimemask = intmask & timemask
                #retrieve "good" rows of HDF5 that are the correct Beam ID(s) and time(s)
                intdata = f[h5p][inttimemask]

                #TODO not tested past this point
                #TODO account for the case where there are two times and one beam that overlap with the satellite.
                """
                intdata will have numerous rows corresponding to each matching time & beam id
                each row is a range cell. These rows will be numerically integrated over Ne.
                """
                uniqbeamid = np.unique(intdata['beamid']).astype(int)
                for b in uniqbeamid:
                    mask = np.isclose(intdata['beamid'],b) #this is one beam's rows, all range bins
                    mask &= np.isfinite(intdata['nel'][mask]) #dropna
                    tecisr.loc[b,t] = np.trapz(10**intdata['nel'][mask], intdata['range'][mask])

    except:
        remove(fn)

    tecisr.dropna(axis=1,how='all',inplace=True) #only retain times with TEC data (vast majority don't have)
    return tecisr

# glabals
tlefn = 'gps-ops2013.txt'
obslla = [65,-148,0]
beamfn = "PFISRbeammap.h5"
satfreq='1T' #T means minutes
datadir='files'
maxangdist=5 #degrees
maxdtsec = 60
beamisr = read_hdf(beamfn,'data')

flist = glob('files/*.h5')

year = 0
month = 0
day = 0
data = []
for f in flist:
    tic = time()
    if year!=int(f[9:11])+2000 or month!=int(f[11:13]) or day!=int(f[13:15]):
        year = int(f[9:11])+2000
        month = int(f[11:13])
        day = int(f[13:15])
        print 'new date:',month,day,year
        dates = makeDates(year,month,day)
        satdata = loopsat(tlefn,dates,obslla)
        satdata = findIntersection(satdata,beamisr,dates,beamfn,maxangdist)
    tecisr = checkFile(f,satdata,beamisr,maxdtsec)
    for t in tecisr:
        for tec in tecisr[t]:
            if not math.isnan(tec):
                for bid in satdata[t,:,'intersect']:
                    if not math.isnan(bid):
                        current = (t,bid,satdata[t,:,'intersect'][satdata[t,:,'intersect']==bid].index[0],tec)
                        print current
                        data.append(current)

    print('{:.1f} sec. to compute TEC for {} times in {}'.format(time()-tic,tecisr.shape[1],f))

gpsdata = np.loadtxt('gpsData\ionio_dataout_2013_349_0402.log')
data=np.array(data)