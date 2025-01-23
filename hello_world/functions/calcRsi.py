
def calcRsi(dfPricesFinal, tickerSymbol, numOfDays): 
    serDailyPriceChanges = (dfPricesFinal[tickerSymbol] - dfPricesFinal[tickerSymbol].shift(1)).dropna() 
    serDailyPriceChanges = serDailyPriceChanges[-1 * numOfDays :] 
    
    averagePositiveChange = serDailyPriceChanges[serDailyPriceChanges >= 0].mean() 
    averageNegativeChange = -1 * serDailyPriceChanges[serDailyPriceChanges < 0].mean() 
    
    if averageNegativeChange == 0: 
        rsiValue = 0.0 
    else: 
        rsiValue = 100.0 - 100.0 / (1 + averagePositiveChange / averageNegativeChange) 
    
    return rsiValue 
