#!/usr/bin/python3

##--Michael duPont
##--METAR-RasPi
##--Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate
##--2014-09-03

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
updateInterval = 600.0      #Seconds between server pings
buttonInterval = 0.2        #Seconds between plate button reads
scrollInterval = 0.5        #Seconds between row 2 char scroll
timeoutInterval = 60.0      #Seconds between connection retries
logMETAR = False            #Log METAR data
logName = "METARlog.txt"    #METAR log name
ident = [11 , 12 , 5 , 24]  #Default station ident, ex. [11,12,5,24] = KLEX

##--Global Vars
numRows = 2
numCols = 16
lcd = Adafruit_CharLCDPlate()
lcdColors = [lcd.GREEN,lcd.BLUE,lcd.RED,lcd.VIOLET,lcd.ON]
replacements = [['00000KT','CALM']]   #String replacement for Line2 (scrolling data)
cloudList = ['CLR','SKC','FEW','SCT','BKN','OVC']
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
	lcd.setCursor(0,1)
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
	try:
		response = urllib2.urlopen('http://www.aviationweather.gov/adds/metars/?station_ids='+station+'&std_trans=standard&chk_metars=on&hoursStr=most+recent+only&submitmet=Submit')
		html = response.read()
		reportStart = html.find('>'+station)   #Report begins with station iden
		reportEnd = html[reportStart:].find('<')   #Report ends with html bracket
		return html[reportStart+1:reportStart+reportEnd].replace('\n ','')
	except:
		return None

#Returns a dictionary of parsed METAR data
#Keys: Station, Time, Wind-Direction, Wind-Speed, Visibility, Altimeter, Temperature, Dewpoint, Cloud-List, Other-List, Remarks
def parseMETAR(txt):
	retWX = {}
	#Remove remarks and split
	if txt.find('RMK') != -1:
		retWX['Remarks'] = txt[txt.find('RMK')+4:]
		wxData = txt[:txt.find('RMK')-1].split(' ')
	else:
		retWX['Remarks'] = ''
		wxData = txt.split(' ')
	#Station and Time
	retWX['Station'] = wxData.pop(0)
	retWX['Time'] = wxData.pop(0)
	#Sanitize wxData
	if wxData[0] == 'AUTO': wxData.pop(0)          #Indicates report was automated
	if wxData[len(wxData)-1] == '$': wxData.pop()  #Indicates station needs maintenance
	#Surface wind
	if wxData[0][len(wxData[0])-2:] == 'KT':
		retWX['Wind-Direction'] = wxData[0][:3]
		retWX['Wind-Speed'] = wxData[0][3:5]
		wxData.pop(0)
	else:
		retWX['Wind-Direction'] = ''
		retWX['Wind-Speed'] = ''
	#Visibility
	if wxData[0].find('SM') != -1:   #10SM
		retWX['Visibility'] = wxData[0][:wxData[0].find('SM')]
		wxData.pop(0)
	elif wxData[1].find('SM') != -1:   #2 1/2SM
		vis1 = wxData.pop(0)  #2
		vis2 = wxData[0][:wxData[0].find('SM')]  #1/2
		wxData.pop(0)
		retWX['Visibility'] = str(int(vis1)*int(vis2[2])+int(vis2[0]))+vis2[1:]  #5/2
	else:
		retWX['Visibility'] = ''
	#Altimeter
	if (wxData[len(wxData)-1][0] == 'A'):
		retWX['Altimeter'] = wxData[len(wxData)-1][1:]
		wxData.pop()
	else: retWX['Altimeter'] = 'NONE'
	#Temp/Dewpoint
	if wxData[len(wxData)-1].find('/') != -1:
		TD = wxData[len(wxData)-1].split('/')
		retWX['Temperature'] = TD[0]
		retWX['Dewpoint'] = TD[1]
	else:
		retWX['Temperature'] = ''
		retWX['Dewpoint'] = ''
	wxData.pop()
	#Clouds
	clouds = []
	for i in reversed(range(len(wxData))):
		if (wxData[i][:3] in cloudList) or (wxData[i][:2] == 'VV'):
			clouds.append(wxData.pop(i))
	clouds.reverse()
	retWX['Cloud-List'] = clouds
	#Other weather
	retWX['Other-List'] = wxData
	if logMETAR: logData(logName , retWX)
	if not logMETAR: print(retWX)
	return retWX

#Returns int based on current flight rules from parsed METAR data
#0=VFR , 1=MVFR , 2=IFR , 3=LIFR
def getFlightRules(vis , cld):
	#Parse visibility
	if (vis == '') and (cld == ''): return 4 #Not enought data
	if (vis == ''): vis = 99
	elif vis.find('/') != -1:
		if vis[0] == 'M': vis = 0
		else: vis = int(vis[0]) / int(vis[2])
	else: vis = int(vis)
	#Parse ceiling
	if (cld[:3] == 'BKN') or (cld[:3] == 'OVC'): cld = int(cld[3:6])
	elif cld[:2] == 'VV': cld = int(cld[2:5])
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
	lcd.message(getIdent(ident)+' selected\nFetching METAR')

#Display timeout message and sleep
#Returns None
def lcdTimeout():
	if logMETAR: logData(logName , 'No connection')
	lcd.clear()
	lcd.setCursor(0,0)
	lcd.message('No connection\nCheck back soon')
	sleep(timeoutInterval)	

#Display invalid station message and sleep
#Returns None
def lcdBadStation():
	lcd.clear()
	lcd.setCursor(0,0)
	lcd.message('Invalid Station\n'+getIdent(ident))
	sleep(3)
	lcdSelect()

#Returns tuple of display data from METAR txt (Line1,Line2,BLInt)
#Line1: IDEN HHMMZ BB.bb
#Line2: Rest of METAR report
#BLInt: Flight rules int
def createDisplayData(txt):
	#Create dictionary of data
	parsedWX = parseMETAR(txt)
	#Create Lines
	alt = parsedWX['Altimeter']
	line1 = parsedWX['Station']+' '+parsedWX['Time'][2:]+' '+alt[:2]+'.'+alt[2:]
	if txt.find('A'+alt) != -1:	line2 = txt[:txt.find('A'+alt)-1].split(' ',2)[2]
	elif txt.find('RMK') != -1:	line2 = txt[:txt.find('RMK')-1].split(' ',2)[2]
	else: line2 = txt.split(' ',2)[2]
	for rep in replacements: line2 = string.replace(line2 , rep[0] , rep[1]) #Any other string replacements
	#Get flight rules
	vis = parsedWX['Visibility']
	cld = ''
	#Only 'Broken', 'Overcast', and 'Vertical Visibility' are considdered ceilings
	#Prevents errors due to lack of cloud information (eg. '' or 'FEW///')
	for cloud in parsedWX['Cloud-List']:
		if (cloud[len(cloud)-1] != '/') and ((cloud[:3] == 'BKN') or (cloud[:3] == 'OVC') or (cloud[:2] == 'VV')):
			cld = cloud
			break
	return line1 , line2 , getFlightRules(vis,cld)

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
	fout.close()
	return None

#Program Main
#Returns 1
def main():
	setup()     #Initial Setup
	lcdSelect() #Show Ident Selection
	while True:
		METARtxt = getMETAR(getIdent(ident)) #Fetch current METAR
		while (not METARtxt) or (METARtxt == getIdent(ident)): #Fetch data until success
			if METARtxt == getIdent(ident): lcdBadStation()    #If invalid station
			else: lcdTimeout()   #Else there's a bad connection
			METARtxt = getMETAR(getIdent(ident))
		L1,L2,FR = createDisplayData(METARtxt)            #Create display data
		if logMETAR: logData(logName,METARtxt,L1,L2,'\n') #Log METAR data
		totalTime = 0.0
		while totalTime < updateInterval:        #Loop until program fetches new data
			totalTime += displayMETAR(L1,L2,FR)  #Cycle display one loop. Add elapsed time to total time
			if lcd.buttonPressed(lcd.SELECT):    #If select button pressed at end of a cycle
				lcdSelect()  #Show Ident Selection
				break        #Break to fetch new METAR
	return 1

main()
