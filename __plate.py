"""
Michael duPont - michael@mdupont.com
plate.py - Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate

Use plate keypad to select ICAO station/airport iden to display METAR data
  Left/Right - Choose position
  Up/Down    - Choose character A-9
  Select     - Confirm station iden
LCD panel now displays current METAR data (pulled from aviationweather.gov)
  Line1      - IDEN HHMMZ BA.RO   or   IDEN HHMMZ NOSIG
  Line2      - Rest of METAR report
LCD backlight indicates current Flight Rules
  Green      - VFR
  Blue       - MVFR
  Red        - IFR
  Violet     - LIFR
At the end of a line scroll:
  Holding select button displays iden selection screen
  Holding left and right buttons gives option to shutdown the Pi

Uses Adafruit RGB Negative 16x2 LCD - https://www.adafruit.com/product/1110
Software library for LCD plate - https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code
"""

# stdlib
import os
import sys
from copy import copy
from time import sleep
# library
import avwx
from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
# module
import config as cfg
from common import logger, ident_to_station

numRows = 2
numCols = 16
lcd = Adafruit_CharLCDPlate()
lcdColors = [lcd.GREEN,lcd.BLUE,lcd.RED,lcd.VIOLET,lcd.ON]
replacements = [['00000KT','CALM'],['00000MPS','CALM'],['10SM','UNLM'],['9999','UNLM']]   #String replacement for Line2 (scrolling data)

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
		#Shutdown option
		if lcd.buttonPressed(lcd.LEFT) and lcd.buttonPressed(lcd.RIGHT):
			lcdShutdown()
			lcd.clear() #If no, reset screen
			lcd.setCursor(0,0)
			lcd.message('4-Digit METAR')
			for row in range(4):
				lcd.setCursor(row,1)
				lcd.message(charList[ident[row]])
			lcd.setCursor(0,1)
			lcd.cursor()
			sleep(1)
		#Previous char
		elif lcd.buttonPressed(lcd.UP):
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

#Display METAR selection screen on LCD
#Returns None
def lcdSelect():
	lcd.backlight(lcdColors[4])
	selectMETAR()
	lcd.clear()
	lcd.message(ident_to_station(ident)+' selected\nFetching METAR')

#Display timeout message and sleep
#Returns None
def lcdTimeout():
	logger.warning('Connection Timeout')
	lcd.backlight(lcdColors[4])
	lcd.clear()
	lcd.setCursor(0,0)
	lcd.message('No connection\nCheck back soon')
	sleep(timeoutInterval)	

#Display invalid station message and sleep
#Returns None
def lcdBadStation():
	lcd.clear()
	lcd.setCursor(0,0)
	lcd.message('No Weather Data\nFor '+ident_to_station(ident))
	sleep(3)
	lcdSelect()	

#Display shutdown option
#Shuts down Pi or returns None
def lcdShutdown():
	selection = False
	selected = False
	lcd.backlight(lcdColors[4])
	lcd.clear()
	lcd.setCursor(0,0)
	if shutdownOnExit: lcd.message('Shutdown the Pi?\nY N')
	else: lcd.message('Quit the program?\nY N')
	lcd.setCursor(2,1)
	lcd.cursor()
	sleep(1)   #Allow finger to be lifted from LR buttons
	#Selection loop
	while not selected:
		#Move cursor right
		if lcd.buttonPressed(lcd.RIGHT) and selection:
			lcd.setCursor(2,1)
			selection = False
		#Move cursor left
		elif lcd.buttonPressed(lcd.LEFT) and not selection:
			lcd.setCursor(0,1)
			selection = True
		#Confirm selection
		elif lcd.buttonPressed(lcd.SELECT):
			selected = True
		sleep(buttonInterval)
	lcd.noCursor()
	if not selection: return None
	lcd.clear()
	lcd.backlight(lcd.OFF)
	if shutdownOnExit: os.system('shutdown -h now')
	sys.exit()

#Returns tuple of display data from METAR txt (Line1,Line2,BLInt)
#Line1: IDEN HHMMZ BB.bb
#Line2: Rest of METAR report
#BLInt: Flight rules int
def createDisplayData(txt):
	#Create dictionary of data
	parsedWX = parseMETAR(txt)
	#Create Lines
	if displayNOSIG:
		if parsedWX['Remarks'].find('NOSIG') != -1:
			line1 = parsedWX['Station']+' '+parsedWX['Time'][2:]+' NOSIG'
			txt = txt.replace(' NOSIG' , '')
		else: line1 = parsedWX['Station']+' '+parsedWX['Time'][2:]
	else:
		alt = parsedWX['Altimeter']
		if alt == '': alt = '----'
		line1 = parsedWX['Station']+' '+parsedWX['Time'][2:]+' '+alt[:2]+'.'+alt[2:]
		txt = txt.replace(' A'+alt , '') #Remove Alt
		txt = txt.replace(' Q'+alt , '') #Remove Alt
	line2 = txt.split(' ',2)[2] #Remove ID and Time
	if (not includeRemarks) and line2.find('RMK') != -1: line2 = line2[:line2.find('RMK')] #Opt remove Remarks
	for rep in replacements: line2 = string.replace(line2 , rep[0] , rep[1]) #Any other string replacements
	return line1 , line2.strip(' ') , getFlightRules(parsedWX['Visibility'],getCeiling(parsedWX['Cloud-List']))

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
	sleep(2) #Pause to read line / line end
	return timeElapsed + 2

#Program Main
#Returns 1 if error, else 0
def main():
	lastMETAR = ''
	userSelected = True
	setup()     #Initial Setup
	lcdSelect() #Show Ident Selection
	while True:
		METARtxt = getMETAR(ident_to_station(ident)) #Fetch current METAR
		while type(METARtxt) == int: #Fetch data until success
			if METARtxt == 0: lcdTimeout()       #Bad Connection
			elif METARtxt == 1:
				if userSelected: lcdBadStation() #Invalid Station
				else:
					logger.info('Ignoring non-user generated selection')
					METARtxt = copy(lastMETAR)   #Server data lookup error
					break
			else: return 1                       #Code error
			METARtxt = getMETAR(ident_to_station(ident))
		userSelected = False
		lastMETAR = copy(METARtxt)
		logger.info(METARtxt)
		L1,L2,FR = createDisplayData(METARtxt)            #Create display data
		logger.info('\t' + L1 + '\n\t' + L2) #Log METAR data
		totalTime = 0.0
		while totalTime < updateInterval:        #Loop until program fetches new data
			totalTime += displayMETAR(L1,L2,FR)  #Cycle display one loop. Add elapsed time to total time
			if lcd.buttonPressed(lcd.SELECT):    #If select button pressed at end of a cycle
				lcdSelect()  #Show Ident Selection
				userSelected = True
				break        #Break to fetch new METAR
			elif lcd.buttonPressed(lcd.LEFT) and lcd.buttonPressed(lcd.RIGHT):  #If right and left
				lcdShutdown() #Shutdown option
				
	return 0

if __name__ == '__main__': main()
