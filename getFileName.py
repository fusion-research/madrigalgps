from madrigalWeb import madrigalWeb as MW
from os.path import join
# globals
madfiltfn = "filestodownload.txt"
limit = 100

def getFiles(filename,limit):

    with open(filename,'r') as fraw:
        i=0
        files = []
        for line in fraw:
            if i>limit: break

            if line.startswith('/opt/madrigal'):
                files.append(line.strip())
                i+=1

    return files
#%% main program
from argparse import ArgumentParser
p = ArgumentParser(description='scan Madrigal with criteria')
p.add_argument('username',help='your name',nargs='?',default='guest')
p.add_argument('email',help='your email',nargs='?',default='guest')
p.add_argument('institution',help='your institution',nargs='?',default='Acme, Inc.')
p.add_argument('--download',help='type of file to download',default='hdf5')
p.add_argument('--madurl',help='madrigal server url',default='http://isr.sri.com/madrigal/')
p = p.parse_args()

print('connecting to {}'.format(p.madurl))
site = MW.MadrigalData(p.madurl)
print('saving Madrigal filter output to {}'.format(madfiltfn))
files = getFiles(madfiltfn,limit)

for f in files:
    print('processing {}'.format(files.index(f)))
    site.downloadFile(f, join("files",str(files.index(f))+".h5"),
                      p.username,p.email,p.institution,p.download)
