# -*- coding: utf-8 -*-

# ---------- MODULES ----------
# standard modules
import numpy as np
from datetime import datetime

# 3rd party modules
import yfinance as yf
from utils.yfinance_extension import get_annualDilutedEPS


# QuoteTimeSeriesStore
# QuoteSummaryStore


# ---------- VARIABLES ----------

# DEV-VARIABLES
DEBUG = False

# default symbol for the stock exchange trading place
# - de: XETRA
exchangeTradingPlace = 'DE'

# currencies
EURO = u"Euro"
DOLLAR = u"Dollar"


# ---------- CLASSES ----------
class Stock:
    def __init__(self,growthRateAnnualyPrc,symbol=''):

        self.growthRateAnnualy = growthRateAnnualyPrc/100

        # init variables for data, which will be loaded from yahoo finance
        self.info = None
        self.ticker = None
        self.currency = None
        self.currencySymbol = ''
        self.currentStockValue = None
        self.bookValuePerShare = None
        self.dividend = None
        self.netIncome = None
        self.priceEarningsRatio = None
        self.earningsPerShare = None

        #
        self.mainDataLoaded = False

        # Exchange traing place
        if len(symbol.split('.')) == 2:
            self.symbol = symbol
        else:
            self.symbol = symbol + '.' + exchangeTradingPlace

        # Load data
        self.loadMainData()

    def loadMainData(self):
        self.getStockName()
        self.getBookValuePerShare()
        self.getCurrency()
        self.getCurrentStockValue()
        self.getEarningsPerShare()
        self.meanEarningsPerShare = self.earningsPerShare
        self.getDividend()
        self.getPriceEarnigsRatio()

        print(get_annualDilutedEPS(self.symbol))

        # change the flag to indicate that all data has been loaded
        self.mainDataLoaded = True


    def getTicker(self):
        if DEBUG:
            print('Creating ticker...')

        if self.symbol is not None:
            self.ticker = yf.Ticker(self.symbol)
        else:
            raise ValueError('Stock symbol missing.')

        if DEBUG:
            print('Created ticker successfully')


    def getInfo(self):
        if DEBUG:
            print('Loading information...')

        if self.info is not None:
            return self.info
        elif self.ticker is None:
            self.getTicker()
        
        self.info = self.ticker.info

        if DEBUG:
            print(self.info)
            print('Information loaded successfully')


    def getStockName(self):
        if self.info is None:
            self.getInfo()
        
        if 'longName' in self.info.keys():
            self.name = self.info['longName']
        else:
            raise KeyError('Missing key "longName" in stock information')

    
    def getBookValuePerShare(self):
        if self.info is None:
            self.getInfo()
        self.bookValuePerShare = self.info['bookValue']

    
    def getCurrency(self):
        if self.info is None:
            self.getInfo()

        if 'currency' in self.info.keys():
            self.currency = self.info['currency']
        else:
            raise KeyError('Missing key "currency" in stock information')

        if self.currency == 'EUR':
            self.currencySymbol = EURO
        else:
            self.currencySymbol = DOLLAR

    
    def getCurrentStockValue(self):
        if self.ticker is None:
            self.getTicker()

        lastDayData = self.ticker.history(period='1d')
        closeValue = lastDayData.iloc[0]['Close']
        self.currentStockValue = closeValue

    
    def getEarningsPerShare(self):
        if self.info is None:
            self.getInfo()

        if ('forwardEps' in self.info.keys()) and (self.info['forwardEps'] is not None):
            self.earningsPerShare = self.info['forwardEps']
        elif 'trailingEps' in self.info.keys():
            self.earningsPerShare = self.info['trailingEps']
        else:
            raise KeyError('Missing key "trailingEps" or "forwardEps" in stock information')


    def getPriceEarnigsRatio(self):
        if self.info is None:
            self.getInfo()

        if ('forwardPE' in self.info.keys()) and (self.info['forwardPE'] is not None):
            self.priceEarningsRatio = self.info['forwardPE']
        elif 'trailingPE' in self.info.keys():
            self.priceEarningsRatio = self.info['trailingPE']
        else:
            raise KeyError('Missing key "trailingPE" or "forwardPE" in stock information')


    def getDividend(self):
        if self.info is None:
            self.getInfo()

        if 'dividendRate' in self.info.keys():
            self.dividend = self.info['dividendRate']
        else:
            raise KeyError('Missing key "dividendRate" in stock information')


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


    # Funktion zur Formattierung der Ausgabe
    def __str__(self):
        return '<Stock Object \'{stockName}\'>'.format(stockName=self.name)
