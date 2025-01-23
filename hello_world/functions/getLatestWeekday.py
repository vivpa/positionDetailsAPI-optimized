import datetime as dt 
import pandas as pd 
import pandas_market_calendars as mcal 

def getLatestWeekday(inputDate): 
    prevDate = pd.to_datetime(inputDate).date() 
    nyseCalendar = mcal.get_calendar('NYSE') 
    tplNyseHolidays = nyseCalendar.holidays() 
    dfNyseHolidays = pd.DataFrame(tplNyseHolidays.holidays) 
    dfNyseHolidays.columns = ['Holidays'] 
    dfNyseHolidays['Year'] = dfNyseHolidays['Holidays'].dt.year 
    currentYear = inputDate.year + 2 
    dfNyseHolidays = dfNyseHolidays[(dfNyseHolidays['Year'] >= 1950) & (dfNyseHolidays['Year'] <= currentYear)].copy() 
    lstNyseHolidays = list(dfNyseHolidays['Holidays'].dt.date) 
    
    while 1: 
        if prevDate.weekday() == 5 or prevDate.weekday() == 6 or prevDate in lstNyseHolidays: 
            prevDate = prevDate - dt.timedelta(days = 1) 
        else: 
            break 
    
    return pd.to_datetime(prevDate) 
