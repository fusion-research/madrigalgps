from datetime import datetime


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