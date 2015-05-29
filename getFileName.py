
def getFiles(filename,limit):

    rawfile = open(filename)
    i=0
    files = []
    print 'finding files'

    while i<limit:
        line = rawfile.readline()

        if '\n' not in line:
            return files

        if len(line)>50:
            nextline = rawfile.readline()
            if 'No records were selected with the filters above' not in nextline:
                files.append(line.strip())
                print i
                i+=1

    rawfile.close()
    return files


from madrigalWeb import madrigalWeb as MW
print('connecting to site')
site = MW.MadrigalData('http://isr.sri.com/madrigal/')
filename = "filestodownload.txt"
limit = 100
print('getFiles')
files = getFiles(filename,limit)

print 'downloading files'
for f in files:
    print(files.index(f))
    site.downloadFile(f,"files/"+str(files.index(f))+".h5",username,email,institution,"hdf5")
