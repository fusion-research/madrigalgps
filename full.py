from __future__ import division
from ephem import readtle,Observer
import numpy as np
from pandas import date_range, DataFrame,Panel
from dateutil.parser import parse
from re import search
import h5py
import matplotlib.pyplot as plt


def loopsat(tlefn,dates,obslla):
    obs = setupobs(obslla)

    data,belowhoriz = compsat(tlefn,obs,dates)

    return data,obs,belowhoriz


def setupobs(lla):
    obs = Observer()
    try:
        obs.lat = str(lla[0]); obs.lon = str(lla[1]); obs.elevation=float(lla[2])
    except ValueError:
        print('observation location not specified. defaults to lat=0, lon=0')
    return obs


def compsat(tlefn,obs,dates):
    cols = ['az','el','lat','lon','alt','srange']
    sats,satnum = loadTLE(tlefn)

    data = Panel(items=dates, major_axis=satnum, minor_axis=cols)
    for d in dates:
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
    with open(filename) as f:
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


def makeDates(sy,smo,sd,duration):
    dates=[]
    for mi in range(duration):
        hours=mi//60
        minutes=mi - 60*hours
        dates.append(parse("{}-{}-{}T{}:{}:00".format(sy,smo,sd,hours,minutes)))
    return dates
        
        
def findIntersection(data,dates,beamfile,dist):
    
    intersections = {}
    svs=list(data.major_axis)
    svs.sort()
    for svnum in svs:
        print svnum
        beams = set()
        
        for beam in beamfile:
            if beam[1]<0:
                beamaz = beam[1]+360
            else:
                beamaz = beam[1]
            for time in dates:
                daz = abs(beamaz-data[time,svnum,'az'])
                dele = abs(beam[2]-data[time,svnum,'el'])
                if daz<dist and dele<dist:
                    beams.add(beam[0])
        intersections[svnum]=beams
           
    return intersections


def checkFile(filename,intersections):
    matches = []
    h5=h5py.File(filename)
    beamids=set()
    
    for beamid in h5['Data']['Table Layout']['beamid']:
        beamids.add(beamid)
    
    for sv in intersections:
        matches.append(intersections[sv].intersection(beamids))
    return matches
    

print 'make dates'
dates = makeDates(2015,01,01,720)

print 'make data'
tlefn = 'gps-ops.txt'
obslla = [65,-148,0]
data,obs,belowhoriz = loopsat(tlefn,dates,obslla)

print 'find intersection'
beamfile = np.loadtxt("PFISRbeammap.txt")
dist = 1
intersections = findIntersection(data,dates,beamfile,dist)

end=False
i=0
while not end:
    try:
        print checkFile('files/{}.h5'.format(i),intersections)
        i+=1
    except:
        end = True
        
print i, "files checked"