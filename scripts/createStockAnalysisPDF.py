
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classes.Stock import Stock
from classes.StockCompare import StockCompare, StockComparePDF
from classes.StockAnalyzer import StockAnalyzer

symbol = 'MSFT'

stock = Stock(symbol=symbol)
StockAnalyzer(stock).printAnalysis()

msftCompare = StockCompare(symbol)
peerGroupList = msftCompare.getPeerGroup(symbol=symbol)
df = msftCompare.getPeerGroupChangePrc(peerGroupList)
mainValueCompareDF = msftCompare.comparePeerGoupMainValues(peerGroupList)

pdf_filename = symbol + '_peer_group_compare.pdf'
scPDF = StockComparePDF(pdf_filename)
scPDF.addPlot(df)

scPDF.addTable(mainValueCompareDF)

scPDF.closePDF()
