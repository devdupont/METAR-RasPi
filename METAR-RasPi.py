#!/usr/bin/python3

##--Michael duPont
##--METAR-RasPi
##--Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate
##--2014-08-31

##--Use plate keypad to select ICAO station/airport iden to display METAR data
##----Left/Right - Choose position
##----Up/Down    - Choose character A-9
##----Select     - Confirm station iden
##--LCD panel now displays current METAR data (pulled from aviationweather.gov)
##----Line1      - IDEN HHMMZ BA.RO
##----Line2      - Rest of METAR report
##--LCD backlight indicates current Flight Rules
##----Green      - VFR
##----Blue       - MVFR
##----Red        - IFR
##----Violet     - LIFR
##--Holding select button at the end of a line scroll displays iden selection screen

##--Uses Adafruit RGB Negative 16x2 LCD - https://www.adafruit.com/product/1110
##--Software library for LCD plate - https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code
##--Note: Code runs Python 3.x and may not be fully compatable with 2.x

from time import sleep
from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
import urllib2
import string

##--User Vars
numRows = 2                 #Vertical chars
numCols = 16                #Horizontal chars
updateInterval = 600.0      #Seconds between server pings
buttonInterval = 0.2        #Seconds between plate button reads
scrollInterval = 0.5        #Seconds between row 2 char scroll
logMETAR = True             #Log METAR data
logName = "METARlog.txt"    #METAR log name
ident = [11 , 12 , 5 , 24]  #Default station ident, ex. [11,12,5,24] = KLEX

##--Global Vars
lcd = Adafruit_CharLCDPlate()
lcdColors = [lcd.GREEN,lcd.BLUE,lcd.RED,lcd.VIOLET,lcd.ON]
replacements = [['00000KT','CALM']]   #String replacement for line2 (scrolling data)
cloudList = ['FEW','SCT','BKN','OVC']
charList = [' ','A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','0','1','2','3','4','5','6','7','8','9']

#Converts 'ident' values to chars
#Returns 4-char string
def getIdent(identList):
	ret = ''
	for num in identList: ret += charList[num]
	return ret

#Program setup
#Returns None
def setup():
	lcd.begin(numCols, numRows)
	lcd.clear()
	return None

#Select METAR station
#Use LCD to update 'ident' values
#Returns None
def selectMETAR():
	cursorPos = 0
	selected = False
	
	lcd.clear()
	lcd.setCursor(0,0)
	lcd.message('4-Digit METAR')
	#Display default iden
	for row in range(4):
		lcd.setCursor(row,1)
		lcd.message(charList[ident[row]])
	lcd.setCursor(1,1)
	lcd.cursor()
	sleep(1)   #Allow finger to be lifted from select button
	#Selection loop
	while not selected:
		#Previous char
		if lcd.buttonPressed(lcd.UP):
			curNum = ident[cursorPos]
			if curNum == 0: curNum = len(charList)
			ident[cursorPos] = curNum-1
			lcd.message(charList[ident[cursorPos]])
		#Next char
		elif lcd.buttonPressed(lcd.DOWN):
			newNum = ident[cursorPos]+1
			if newNum == len(charList): newNum = 0
			ident[cursorPos] = newNum
			lcd.message(charList[ident[cursorPos]])
		#Move cursor right
		elif lcd.buttonPressed(lcd.RIGHT):
			if cursorPos < 3:
				cursorPos += 1
		#Move cursor left
		elif lcd.buttonPressed(lcd.LEFT):
			if cursorPos > 0:
				cursorPos -= 1
		#Confirm iden
		elif lcd.buttonPressed(lcd.SELECT):
			selected = True
		lcd.setCursor(cursorPos,1)
		sleep(buttonInterval)
	lcd.noCursor()
	return None

#Get METAR report for 'station' from www.aviationweather.gov
#Returns METAR report string
def getMETAR(station):
	response = urllib2.urlopen('http://www.aviationweather.gov/adds/metars/?station_ids='+station+'&std_trans=standard&chk_metars=on&hoursStr=most+recent+only&submitmet=Submit')
	html = response.read()
	reportStart = html.find(station)   #Report begins with station iden
	reportEnd = html[reportStart:].find('<')   #Report ends with html bracket
	return html[reportStart:reportStart+reportEnd]

#Returns a list[string] of parsed METAR data
#Format out: [ [wind-direction,wind-speed] , visibility , altimeter , [Temp,Dewpoint] , Ceiling ]
def parseMETAR(txt):
	retWX = []
	#Remove remarks and split
	if txt.find('RMK') != -1: wxData = txt[:txt.find('RMK')-1].split(' ')[2:]
	else: wxData = txt.split(' ')[2:]
	#Sanitize wxData
	if wxData[0] == 'AUTO': wxData.pop(0)          #Indicates report was automated
	if wxData[len(wxData)-1] == '$': wxData.pop()  #Indicates station needs maintenance
	#Surface wind
	retWX.append([wxData[0][:3],wxData[0][3:5]])
	wxData.pop(0)
	#Visibility
	retWX.append(wxData[0][:len(wxData[0])-2])
	wxData.pop(0)
	#Altimeter
	retWX.append(wxData[len(wxData)-1][1:])
	wxData.pop()
	#Temp/Dewpoint
	retWX.append(wxData[len(wxData)-1].split('/'))
	wxData.pop()
	#Ceiling
	if 'CLR' in wxData:
		retWX.append('CLR')
		wxData.remove('CLR')
	elif 'SKC' in wxData:
		retWX.append('SKC')
		wxData.remove('SKC')
	else:
		#Get first(lowest) cloud layer
		for i in range(len(wxData)):
			if (len(wxData[i]) == 6) and (wxData[i][:3] in cloudList):
				retWX.append(wxData[i])
				break
		#Remove cloud data
		for i in range(len(wxData),0):
			if (len(wxData[i]) == 6) and (wxData[i][:3] in cloudList): wxData.pop(i)
	#Other weather
	#retWX.append[wxData]
	#print(wxData)
	return retWX

#Returns int based on current flight rules from parsed METAR data
#0=VFR , 1=MVFR , 2=IFR , 3=LIFR
def getFlightRules(wxList):
	#Parse visibility
	vis = wxList[1]
	if vis.find('/') != -1: vis = 0 #Fraction visibility = less than one mile
	else: vis = int(vis)
	#Parse ceiling
	cld = wxList[4]
	if (cld[:3] == 'BKN') or (cld[:3] == 'OVC'): cld = int(cld[3:]) #Only 'Broken' and 'Overcast' are considdered FR ceilings
	else: cld = 99
	#Determine flight rules
	if (vis < 5) or (cld < 30):
		if (vis < 3) or (cld < 10):
			if (vis < 1) or (cld < 5):
				return 3 #LIFR
			return 2 #IFR
		return 1 #MVFR
	return 0 #VFR

#Display METAR selection screen on LCD
#Returns None
def lcdSelect():
	lcd.backlight(lcdColors[4])
	selectMETAR()
	lcd.clear()
	lcd.message(getIdent(ident)+'\nSelected')

#Returns tuple of display data from METAR txt (Line1,Line2,BLInt)
#Line1: IDEN HHMMZ BB.bb
#Line2: Rest of METAR report
#BLInt: Flight rules int
def createDisplayData(txt):
	#Create list of [Iden,Time,Rest]
	if txt.find('RMK') != -1: wxData = txt[:txt.find('RMK')-1].split(' ',2)
	else: wxData = txt.split(' ',2)
	#Create parsed list of data
	parsedWX = parseMETAR(txt)
	line1 = wxData[0] + ' ' + wxData[1][2:] + ' ' + parsedWX[2][:2]+'.'+parsedWX[2][2:]
	line2 = string.replace(wxData[2] , ' A'+parsedWX[2] , '') #Remove altimeter
	for rep in replacements: line2 = string.replace(line2 , rep[0] , rep[1]) #Any other string replacements
	return line1 , line2 , getFlightRules(parsedWX)

#Display METAR data on LCD plate
#Returns approx time elapsed (float)
def displayMETAR(line1 , line2 , lcdLight):
	lcd.clear()
	#Set LCD color to match current flight rules
	lcd.backlight(lcdColors[lcdLight])
	#Write row 1
	lcd.setCursor(0,0)
	lcd.message(line1)
	#Scroll row 2
	timeElapsed = 0.0
	if line2 <= numCols:  #No need to scroll line
		lcd.setCursor(0,1)
		lcd.message(line2 , lcd.TRUNCATE)
		sleep(2)
		timeElapsed += 2
	else:
		lcd.setCursor(0,1)
		lcd.message(line2[:numCols] , lcd.TRUNCATE)
		sleep(2) #Pause to read line start
		timeElapsed += 2
		for i in range(1 , len(line2)-(numCols-1)):
			lcd.setCursor(0,1)
			lcd.message(line2[i:i+numCols] , lcd.TRUNCATE)
			sleep(scrollInterval)
			timeElapsed += scrollInterval
		sleep(2) #Pause to read line end
		timeElapsed += 2
	return timeElapsed

#Write a variable number of datapoints to a log
#Returns None
def logData(fname, *data):
	fout = open(fname , 'a')
	for datum in data: fout.write(datum+'\n')
	fout.write('\n')
	fout.close()
	return None

#Program Main
#Returns 1
def main():
	setup()     #Initial Setup
	lcdSelect() #Show Ident Selection
	while True:
		METARtxt = getMETAR(getIdent(ident))     #Fetch current METAR
		L1,L2,FR = createDisplayData(METARtxt)   #Create display data
		if logMETAR: logData(logName , METARtxt , L1 , L2)   #Log METAR data
		totalTime = 0.0
		while totalTime < updateInterval:        #Loop until program fetches new data
			totalTime += displayMETAR(L1,L2,FR)  #Cycle display one loop. Add elapsed time to total time
			if lcd.buttonPressed(lcd.SELECT):    #If select button pressed at end of a cycle
				lcdSelect()  #Show Ident Selection
				break        #Break to fetch new METAR
	return 1

main()
