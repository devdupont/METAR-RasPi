#!/usr/bin/python3

##--Michael duPont
##--METAR-RasPi : mplate
##--Display ICAO METAR weather data with a Raspberry Pi and Adafruit LCD plate
##--2015-01-06

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
##--At the end of a line scroll:
##----Holding select button displays iden selection screen
##----Holding left and right buttons gives option to shutdown the Pi

##--Uses Adafruit RGB Negative 16x2 LCD - https://www.adafruit.com/product/1110
##--Software library for LCD plate - https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code

from mlogic import *
from time import sleep
from copy import copy
from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
import os , sys

##--User Vars
buttonInterval = 0.2     #Seconds between plate button reads
scrollInterval = 0.5     #Seconds between row 2 char scroll

##--Global Vars
numRows = 2
numCols = 16
lcd = Adafruit_CharLCDPlate()
lcdColors = [lcd.GREEN,lcd.BLUE,lcd.RED,lcd.VIOLET,lcd.ON]
replacements = [['00000KT','CALM'],['10SM','UNLM']]   #String replacement for Line2 (scrolling data)
path = os.path.abspath(os.path.dirname(sys.argv[0]))

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
	lcd.message(getIdent(ident)+' selected\nFetching METAR')

#Display timeout message and sleep
#Returns None
def lcdTimeout():
	if logMETAR: print(timestamp('Connection Timeout'))
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
	lcd.message('No Weather Data\nFor '+getIdent(ident))
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
	alt = parsedWX['Altimeter']
	line1 = parsedWX['Station']+' '+parsedWX['Time'][2:]+' '+alt[:2]+'.'+alt[2:]
	if txt.find('A'+alt) != -1:	line2 = txt[:txt.find('A'+alt)-1].split(' ',2)[2]
	elif txt.find('RMK') != -1:	line2 = txt[:txt.find('RMK')-1].split(' ',2)[2]
	else: line2 = txt.split(' ',2)[2]
	for rep in replacements: line2 = string.replace(line2 , rep[0] , rep[1]) #Any other string replacements
	return line1 , line2 , getFlightRules(parsedWX['Visibility'],getCeiling(parsedWX['Cloud-List']))

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
		METARtxt = getMETAR(getIdent(ident)) #Fetch current METAR
		while type(METARtxt) == int: #Fetch data until success
			if METARtxt == 0: lcdTimeout()       #Bad Connection
			elif METARtxt == 1:
				if userSelected: lcdBadStation() #Invalid Station
				else:
					if logMETAR: print(timestamp('Ignoring non-user generated selection'))
					METARtxt = copy(lastMETAR)   #Server data lookup error
					break
			else: return 1                       #Code error
			METARtxt = getMETAR(getIdent(ident))
		userSelected = False
		lastMETAR = copy(METARtxt)
		if logMETAR: print(timestamp(METARtxt))
		L1,L2,FR = createDisplayData(METARtxt)            #Create display data
		if logMETAR: print('\t' + L1 + '\n\t' + L2) #Log METAR data
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

main()
