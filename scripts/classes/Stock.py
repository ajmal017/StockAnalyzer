# -*- coding: utf-8 -*-

# ---------- MODULES ----------
# standard modules
import sys, os
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pandas import DataFrame
import pandas as pd
import commentjson as json

# 3rd party modules
import yfinance as yf

# custom modules
currentFolder = os.path.dirname(os.path.abspath(__file__))
main_path = currentFolder.replace('classes','')
if main_path not in sys.path:
    sys.path.append(main_path)

from utils.yfinance_extension import loadExtraIncomeStatementData, load_CashFlow, load_KeyStatistics
from utils.generic import mergeDataFrame, npDateTime64_2_str
from classes.FinnhubAPI import FinnhubClient
from classes.FinancialDataManager import DataLoader

# ---------- VARIABLES ----------

# Einstellungen, damit Pandas DataFrames immer vollstaendig geplotted werden
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

# DEV-VARIABLES
DEBUG = False

# currencies
EURO = u"Euro"
DOLLAR = u"Dollar"


# ---------- CLASSES ----------
class Stock:

    """
        TODO: plotten der strongBuy, buy, hold, sell und strongSell empfehlungen (auch aus mehreren Quellen, z.B. yahoo finance, Finnhub, ...)
        TODO: Settings Datei entwerfen; Standardisierte Felder (zukünftiges CF Wachstum, zuküngtiges Gewinnwachstum) und einen Freitext, \
            dort koennen manuelle Infos oder Hinweise eingetragen werden. Pro Aktie ein File; bei Analysen wird immer der pessimistischste Wert \
            aus Analysten | eigene Meinung | extrapolierte Werte herangezogen 
    """

    # constant variables for deciding, how much data should be loaded
    LOAD_BASIC_DATA = 1
    LOAD_ALL_DATA = 2

    # variables
    PE_RATIO = 'P/E'
    BOOK_VALUE_PER_SHARE = 'bookValuePerShare'
    EARNINGS_PER_SHARE = 'EPS'
    MARKET_PRICE = 'marketPrice'
    DIVIDEND = 'dividend'
    DIVIDEND_YIELD = 'dividendYield'
    MARKET_CAP = 'marketCap'
    SHARES_OUTSTANDING = 'sharesOutstanding'

    # global variables
    NET_INCOME = 'Net Income'
    FREE_CASH_FLOW = 'freeCashFlow'

    # Format des Datums
    DATE_FORMAT = '%Y-%m-%d'


    def __init__(self,stockName='',stockSymbol='',growthRateEstimate=None, margin_of_safety=None, discountRate=None):

        self.symbol = None
        self.indexSymbol = None
        self.dates = None
        self.assumptions = None

        if stockName != '':
            stockData = loadStockFile(stockName)
            self.symbol = stockData.stockSymbol
            self.indexSymbol = stockData.indexSymbol
            self.dates = stockData.dates
            self.assumptions = stockData.assumptions
        
        if stockSymbol != '':
            self.symbol = stockSymbol
            self.assumptions = {}

            if discountRate is not None:
                self.assumptions["discountRate"] = discountRate

            if growthRateEstimate is not None:
                growth_year_1_to_5, growth_year_6_to_10, growth_year_10ff = Stock.estimateGrowthRates(growthRateEstimate)
                self.assumptions["growth_year_1_to_5"] = growth_year_1_to_5
                self.assumptions["growth_year_6_to_10"] = growth_year_6_to_10
                self.assumptions["growth_year_10ff"] = growth_year_10ff

            if (margin_of_safety is not None) and (isinstance(margin_of_safety,int) or isinstance(margin_of_safety,float)):
                self.assumptions["margin_of_safety"] = margin_of_safety 
            else:
                self.assumptions["margin_of_safety"] = 40 

        # init variables for data, which will be loaded from yahoo finance
        self.info = None
        self.name = None
        self._ticker = None
        self._currency = None
        self._company = None
        self._peerGroup = None
        self._currencySymbol = ''
        self._test = None
        self._dataLoader = None

        self._finnhubClient = None
        self._financialStatements= None

        # dict and DataFrame to store all information
        self.basicData = {}
        self.keyStatistics = {}
        self.financialData = DataFrame()
        # DataFrame for storing estimates for the future
        self.estimates = DataFrame()

        self.historicalData = None
        self.historicalDataRelative = None

        # storing recommendations for buying, holding and selling
        self.recommendations = None

        self.loadMainData()


    def loadMainData(self):
        self.getStockName()
        self.getBookValuePerShare()
        self.getCurrentStockValue()
        self.getEarningsPerShare()
        self.getDividend()
        self.getPriceEarnigsRatio()
        self.loadFinancialStatements()
        self.getRecommendations()
        self.getKeyStatistics()
        #self.getEstimates()

        # monthly historical data
        self.historicalData = self.ticker.history(period="5y", interval = "1wk")


    def calcRelativeHistoricalData(self):
        # take all absolute values and override them afterwards
        self.historicalDataRelative = self.historicalData.loc[:,'Close'].copy()

        firstDate = npDateTime64_2_str(self.historicalDataRelative.index.values[0])
        firstValue = self.historicalDataRelative.loc[firstDate]
        for row in self.historicalDataRelative.index.values:
            date = npDateTime64_2_str(row)
            self.historicalDataRelative.loc[date] = self.historicalDataRelative.loc[date]/firstValue*100      

    @property
    def ticker(self):
        if self._ticker is not None:
            return self._ticker
        elif self.symbol is not None:
            self._ticker = yf.Ticker(self.symbol)
            return self._ticker
        else:
            raise ValueError('Stock symbol missing.')

    @ticker.setter
    def ticker(self,ticker):
        if not isinstance(ticker,yf.Ticker):
            raise TypeError('The ticker "' + str(ticker) + '" is no instance of yfinance.Ticker')
        else:
            self._ticker = ticker

    @property
    def company(self):
        if self._company is None:
            info = self.ticker.info
            c = Company()
            c.shortName = info['shortName']
            c.longName = info['longName']
            c.businessSummary = info['longBusinessSummary']
            c.zipCode = info['zip']
            c.country = info['country']
            c.market = info['market']
            c.sector = info['sector']
            c.industry = info['industry']
            c.enterpriseValue = info['enterpriseValue']
            c.website = info['website']
            self._company = c

        return self._company

    @company.setter
    def company(self,company):
        if not isinstance(company,Company):
            raise TypeError('The ticker "' + str(company) + '" is no instance of Stock.Company')
        else:
            self._company = company

    @property
    def peerGroup(self):
        if self._peerGroup is None:
            self._peerGroup = FinnhubClient(self.symbol).getPeerGroup()

        return self._peerGroup

    @peerGroup.setter
    def peerGroup(self,peerGroup):
        self._peerGroup = peerGroup

    @property
    def currency(self):
        if self._currency is None:
            if self.info is None:
                self.getInfo()

            if 'currency' in self.info.keys():
                self._currency = self.info['currency']
            else:
                raise KeyError('Missing key "currency" in stock information')

        return self._currency

    @currency.setter
    def currency(self,currency):
        if isinstance(currency,str):
            self._currency = currency
        else:
            raise TypeError('Cannot set "currency" of type "' + type(currency) + '". It needs to be of type "str"')

    @property
    def currencySymbol(self):
        if self._currencySymbol == '':
            if self._currency == 'EUR':
                self._currencySymbol = EURO
            else:
                self._currencySymbol = DOLLAR
        
        return self._currencySymbol

    
    @property
    def __DataLoader(self):
        if self._dataLoader is None:
            self._dataLoader = DataLoader(self.symbol)
        return self._dataLoader

    @__DataLoader.setter
    def __DataLoader(self,dataLoader):
        if isinstance(dataLoader,DataLoader):
            self._dataLoader = dataLoader
        else:
            raise TypeError('Argument "dataLoader" must be of type "DataLoader". You passed a object of type "' + type(dataLoader) + '"')


    @property
    def financialStatements(self):
        if self._financialStatements is None:
            self._financialStatements = self.loadFinancialStatements()
        return self._financialStatements


    def loadFinancialStatements(self):
        self._financialStatements = self.__DataLoader.getFinancialStatements()
        return self._financialStatements


    def getInfo(self):
        if self.info is not None:
            return self.info   
        self.info = self.ticker.info


    def getStockName(self):
        if self.company is None:
            return self.company.longName
        else:
            if self.info is None:
                self.getInfo()
        
            if 'longName' in self.info.keys():
                self.company.longName = self.info['longName']
            else:
                raise KeyError('Missing key "longName" in stock information')

            return self.company.longName

    
    def getBookValuePerShare(self):
        if self.info is None:
            self.getInfo()

        if 'bookValue' in self.info.keys():
            self.basicData[self.BOOK_VALUE_PER_SHARE] = self.info['bookValue']
        else:
            raise KeyError('Missing Key "bookValue"')

        return self.basicData[self.BOOK_VALUE_PER_SHARE]
        

    def getCurrentStockValue(self):
        if self.info is None:
            self.getInfo()

        key = 'regularMarketPrice'
        if key in self.info.keys():
            self.basicData[self.MARKET_PRICE] = self.info[key]
        else:
            raise KeyError('Missing key "%s"' %(key))

        return self.basicData[self.MARKET_PRICE]

    
    def getEarningsPerShare(self):
        if self.info is None:
            self.getInfo()

        if ('trailingEps' in self.info.keys()):
            self.basicData[self.EARNINGS_PER_SHARE] = self.info['trailingEps']
            
        if self.EARNINGS_PER_SHARE not in self.basicData.keys():
            raise KeyError('Missing key "trailingEps" in stock information')

        return self.basicData[self.EARNINGS_PER_SHARE]


    def getPriceEarnigsRatio(self):
        if self.info is None:
            self.getInfo()

        if 'trailingPE' in self.info.keys():
            self.basicData[self.PE_RATIO] = self.info['trailingPE']

        if self.PE_RATIO not in self.basicData.keys():
            raise KeyError('Missing key "trailingPE" in stock information')

        return self.basicData[self.PE_RATIO]


    def getDividend(self):
        if self.info is None:
            self.getInfo()

        dividend = 0
        if ('dividendRate' in self.info.keys()):
            if (self.info['dividendRate'] is None):
                dividend = 0
            else:
                dividend = self.info['dividendRate'] 
        else:
            raise KeyError('Missing key "dividendRate" in stock information')

        # store dividend in basic stock data dict
        self.basicData[self.DIVIDEND] = dividend
        
        # calculate the dividend yield for the current market price in Percent
        if not self.isItemInBasicData(self.MARKET_PRICE):
            self.getCurrentStockValue()

        self.basicData[self.DIVIDEND_YIELD] = dividend/self.getBasicDataItem(self.MARKET_PRICE)*100

        return self.basicData[self.DIVIDEND]

    
    def getKeyStatistics(self):
        if self.ticker is None:
            self.getTicker()
            
        # extension
        self.keyStatistics = load_KeyStatistics(self.symbol)
        return self.keyStatistics

    
    def getEstimates(self):
        epsEstimates = FinnhubClient(self.symbol).getEpsEstimates()

        df = DataFrame()
        for data in epsEstimates:
            eps = data['epsAvg']
            period = data['period']
            df.loc[self.EARNINGS_PER_SHARE,period] = eps

        # descending order of date column
        df = df.reindex(sorted(df.columns,reverse=True), axis=1)

        # add data frame to estimates data frame
        self.estimates = mergeDataFrame(self.estimates,df)

        return df


    def getBasicDataItem(self,keyName):
        return self.basicData[keyName]


    def isItemInBasicData(self,keyName):
        return keyName in self.basicData.keys()


    def getRecommendations(self):
        recommendations = FinnhubClient(self.symbol).getRecommendationsDataFrame()
        self.recommendations = recommendations
        return recommendations


    def getHistoricalStockPrice(self,startDate,endDate=None):

        # Start date
        start = datetime.strptime(startDate,Stock.DATE_FORMAT) + relativedelta(days=1)
        startDate = start.strftime(Stock.DATE_FORMAT)

        # End date
        if endDate is None:
            end = start + relativedelta(days=1)
        else:
            end = datetime.strptime(endDate,Stock.DATE_FORMAT) + relativedelta(days=1)
        endDate = end.strftime(Stock.DATE_FORMAT)

        # Load data from yahoo finance
        return yf.download(self.symbol,start=startDate,end=endDate)


    # Funktion zur Berechnung eines Gewichteten Mittelwerts
    def calcMeanWeightedValue(self,value):
        if isinstance(value,list) or isinstance(value,tuple):
            # Faktoren für die einzelnen Jahre
            # Die letzten Werte der Liste werden dabei mit den höchsten Faktoren bewertet
            # Faktoren in 1er-Schritten von 1 aufsteigend
            interval = 0.5
            factors = list(np.arange(1,len(value)*interval+1,interval))

            # Alle Werte mit den Faktoren gewichten
            weightedValues = [v*f for v,f in zip(value,factors)]
            
            # Gewichteter Mittelwert
            weightedMeanValue = sum(weightedValues)/sum(factors)
            return weightedMeanValue
        else:
            return value


    @staticmethod
    def estimateGrowthRates(growthRate):
        return growthRate, growthRate/2, min(growthRate/4,3)


    # Funktion zur Formattierung der Ausgabe
    def __str__(self):
        return '<Stock Object \'{stockName}\'>'.format(stockName=self.name)




class StockIndex():

    # Index Symbols
    DOW_JONES_INDEX_SYMBOL = '^DJI'
    DAX_INDEX_SYMBOL = '^GDAXI'
    MDAX_INDEX_SYMBOL = '^MDAXI'
    SDAX_INDEX_SYMBOL = '^SDAXI'

    def __init__(self,indexSymbol):

        self.symbol = indexSymbol
        self.ticker = yf.Ticker(indexSymbol)

        self.historicalData = None

        self.loadHistoricalData()

    def loadHistoricalData(self,startDate=None,endDate=None):

        if (startDate is None) and (endDate is None):
            return self.ticker.history(period="5y", interval = "1wk")
        else:
            if (startDate is None) and (endDate is not None):
                raise ValueError('Missing startDate. You passed endDate=' + str(endDate) + ' but no startDate')
            elif (startDate is not None) and (endDate is None):
                end = datetime.strptime(startDate)+1
                endDate = end.strftime(Stock.DATE_FORMAT)
            
            # add one day to start and end, to get the correct intervall
            start = datetime.strptime(startDate,Stock.DATE_FORMAT) + relativedelta(days=1)
            startDate = start.strftime(Stock.DATE_FORMAT)
            end = datetime.strptime(endDate,Stock.DATE_FORMAT) + relativedelta(days=1)
            endDate = end.strftime(Stock.DATE_FORMAT)

            # load data from yahoo finance
            return yf.download(self.symbol, start=startDate, end=endDate)




def loadStockFile(stockName,stocksFile='scripts/data/stocks.json'):

    if not os.path.isfile(stocksFile):
        raise Exception('The file "' + stocksFile + '" does not exist. This file needs to contain the stock list.')

    with open(stocksFile) as f:
        stockJSON = json.load(f)

    # Finden der angegebenen Aktie im JSON-File
    allStockNames = [s["Name"] for s in stockJSON["Stocks"]]
    if stockName not in allStockNames:
        raise ValueError('There is no stock named "' + stockName + '" in the file "' + stocksFile + '".')

    stock = stockJSON["Stocks"][allStockNames.index(stockName)]

    # Erstellen eines StockData Objekts
    stockData = StockData(stockName=stock["Name"],stockSymbol=stock["Symbol"])

    # Auslesen von Symbol und dem Index, in dem die Aktie gelistet ist
    if stock["Index"] != "":
        stockIndex = stock["Index"]
        allIndexNames = [i["Name"] for i in stockJSON["Index"]]
        if stockIndex not in allIndexNames:
            raise ValueError('There is no index named "' + stockIndex + '" in the file "' + stocksFile + '".')

        stockData.indexName = stockIndex
        stockData.indexSymbol = stockJSON["Index"][allIndexNames.index(stockIndex)]["Symbol"]
    else:
        stockData.indexName = None
        stockData.indexSymbol = None

    # Öffnen des zur Aktie zugehoerigen Data-Files mit
    # - der Wachstumsprognose
    # - Daten fuer das DCF-Verfahren
    # - Veroeffentlichungsterminen von Quartals- und Jahreszahlen
    if "data_file" in stock.keys() and (stock["data_file"] != ""):
        data_file = 'scripts/data/' + stock["data_file"]

        if not os.path.isfile(data_file):
            raise Exception('The file "' + data_file + '" does not exist.')

        # Laden des zusaetzlichen Files mit den Daten zur Aktie
        with open(data_file) as f:
            stockExtraData = json.load(f)

        # Annahmen auslesen
        if "assumptions" not in stockExtraData.keys():
            raise KeyError('The key "assumptions" is missing in the file "' + data_file + '".')

        stockData.assumptions = stockExtraData["assumptions"]

        if "dates" not in stockExtraData.keys():
            raise KeyError('The key "dates" is missing in the file "' + data_file + '".')

        stockData.dates = stockExtraData["dates"]
    else:
        stockData.dates = None
        stockData.assumptions = None

    return stockData

    
"""
    Class for storing stock data from the file
"""
class StockData():

    def __init__(self,stockName,stockSymbol,indexName='',indexSymbol='',assumptions={},dates={}):

        self._stockName = stockName
        self._stockSymbol = stockSymbol
        self._indexName = indexName
        self._indexSymbol = indexSymbol
        self._assumptions = assumptions
        self._dates = dates

    @property
    def stockName(self):
        return self._stockName

    @stockName.setter
    def stockName(self,name):
        self._stockName = name

    @property
    def stockSymbol(self):
        return self._stockSymbol

    @stockSymbol.setter
    def stockSymbol(self,symbol):
        self._stockSymbol = symbol

    @property
    def indexName(self):
        return self._indexName

    @indexName.setter
    def indexName(self,name):
        self._indexName = name

    @property
    def indexSymbol(self):
        return self._indexSymbol

    @indexSymbol.setter
    def indexSymbol(self,symbol):
        self._indexSymbol = symbol

    @property
    def assumptions(self):
        return self._assumptions

    @assumptions.setter
    def assumptions(self,assumptionsDict):
        if (not isinstance(assumptionsDict,dict)) and (assumptionsDict is not None):
            raise TypeError('The assumptions need to be in a dict. ' + assumptionsDict + ' is not allowed.')
        self._assumptions = assumptionsDict

    @property
    def dates(self):
        return self._dates

    @dates.setter
    def dates(self,datesDict):
        if (not isinstance(datesDict,dict)) and (datesDict is not None):
            raise TypeError('The dates need to be in a dict. ' + datesDict + ' is not allowed.')
        self._dates = datesDict

    def __str__(self):
        return '<StockData object "' + self._stockName + '" ("' + self._stockSymbol + '")>'
    

class Company():

    def __init__(self):
        self._shortName = None
        self._longName = None
        self._zipCode = None
        self._sector = None
        self._businessSummary = None
        self._country = None
        self._website = None
        self._industry = None
        self._market = None
        self._enterpriseValue = None

    @property
    def shortName(self):
        return self._shortName

    @shortName.setter
    def shortName(self,name):
        self._shortName = name

    @property
    def longName(self):
        return self._longName

    @longName.setter
    def longName(self,name):
        self._longName = name

    @property
    def zipCode(self):
        return self._zip

    @zipCode.setter
    def zipCode(self,zipCode):
        self._zipCode = zipCode

    @property
    def sector(self):
        return self._sector

    @sector.setter
    def sector(self,sector):
        self._sector = sector

    @property
    def businessSummary(self):
        return self._businessSummary

    @businessSummary.setter
    def businessSummary(self,summary):
        self._businessSummary = summary

    @property
    def country(self):
        return self._country

    @country.setter
    def country(self,country):
        self._country = country

    @property
    def website(self):
        return self._website

    @website.setter
    def website(self,website):
        self._website = website

    @property
    def industry(self):
        return self._industry

    @industry.setter
    def industry(self,industry):
        self._industry = industry

    @property
    def market(self):
        return self._market

    @market.setter
    def market(self,market):
        self._market = market

    @property
    def enterpriseValue(self):
        return self._enterpriseValue

    @enterpriseValue.setter
    def enterpriseValue(self,value):
        self._enterpriseValue = value

    def __str__(self):
        return '<Stock.Company object "' + self.shortName + '">'