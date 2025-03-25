import numpy as np 
import pandas as pd 

def retrieveIntrinioStockPricesAndDividends(strTickers, startDate, endDate, snowflakeConnection): 
    # Retrieves adjusted closing prices from intrinio via Snowflake
    
    # :param tickers: string of tickers with a single space between them. eg. 'AGG SPY HYG'
    # :param start_date: date from which to pull data. eg. Timestamp('2017-06-30 00:00:00')
    # :param end_date: date till which to pull data. eg. Timestamp('2022-06-30 00:00:00')
    
    # :return df: 1. closing price and dividend data 
    #             2. sorted in ascending order of date
    
    # Converting tickers to structure ('ABC','DEF','XYZ'). Reqd for sql query 
    if type(strTickers) == str or type(strTickers) == np.str_: 
        lstTickers = strTickers.split(' ') 
    elif type(strTickers) == list: 
        lstTickers = strTickers 
    else: 
        lstTickers = strTickers 
    
    lstTickersSql = "(%s)" % str(lstTickers).strip('[]') 
    
    # Sql query 
    query = """ 
    select DATE, TICKER, CLOSE, SPLIT_RATIO, EX_DIVIDEND, ADJ_CLOSE 
    from INTRINIO.PUBLIC.STOCK_PRICES_USCOMP 
    where TICKER in """ + lstTickersSql + """ 
    and Date >=' """ + str(startDate.date()) + "'" + """ 
    and Date <=' """ + str(endDate.date()) + "'" + """ 
    order by DATE""" 
    
    # Read data into memory 
    dfTemp = snowflakeConnection.execute(query) 
    
    lstColNames = [] 
    for i in snowflakeConnection.description: 
        lstColNames.append(i[0]) 
    
    dfTemp = pd.DataFrame(dfTemp, columns = lstColNames)
    
    dfPricesSplitAdj = pd.pivot_table(dfTemp, values = 'ADJ_CLOSE', index = 'DATE', columns = 'TICKER') 
    dfPricesFinalNonAdj = pd.pivot_table(dfTemp, values = 'CLOSE', index = 'DATE', columns = 'TICKER') 
    dfAdjFactors = pd.pivot_table(dfTemp, values = 'SPLIT_RATIO', index = 'DATE', columns = 'TICKER') 
    dfDividendsNonAdj = pd.pivot_table(dfTemp, values = 'EX_DIVIDEND', index = 'DATE', columns = 'TICKER') 
    
    return dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsNonAdj 
