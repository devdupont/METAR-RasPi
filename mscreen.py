#!/usr/bin/python

##--Michael duPont
##--METAR-RasPi : mscreen
##--Display ICAO METAR weather data with a Raspberry Pi and Adafruit 320x240 Touch PiTFT
##--2015-04-08

##--Set runOnPi to False and disable line 52 for use with other screens/testing and add back in as necessary

from mlogic import *
from copy import copy
import pygame , sys , os , time , math

##--User Vars
invertBW = True   #Aka dark mode. Replace white and black pixels
runOnPi = True    #Set to False if not running on a RasPi. Changes env settings

##--Global Vars
specialchar = [u'\u25b2',u'\u25bc',u'\u2713',u'\u2715',u'\u2699',u'\u00B0',u'\u2600',u'\u263E',u'\u2139']
white = 255,255,255
black = 0,0,0
red = 255,0,0
green = 0,255,0
blue = 0,0,255
purple = 150,0,255
gray = 60,60,60
path = os.path.abspath(os.path.dirname(sys.argv[0]))
pygame.init()
font12 = pygame.font.Font(path+'/icons/DejaVuSans.ttf' , 12)
font16 = pygame.font.Font(path+'/icons/DejaVuSans.ttf' , 16)
font18 = pygame.font.Font(path+'/icons/DejaVuSans.ttf' , 18)
font26 = pygame.font.Font(path+'/icons/DejaVuSans.ttf' , 26)
font32 = pygame.font.Font(path+'/icons/DejaVuSans.ttf' , 32)
font48 = pygame.font.Font(path+'/icons/DejaVuSans.ttf' , 48)

#Convert Bool to int for program and invert B/W if True
if invertBW:
	invertBW = 1
	black , white = white , black
else:
	invertBW = -1

class METARScreen:
	screenWidth = 320
	screenHeight = 240
	win = None
	screenIdent = ident
	oldIdent = copy(ident)
	
	def __init__(self):
		print('Running init')
		self.win = pygame.display.set_mode((self.screenWidth,self.screenHeight))
		if runOnPi: pygame.mouse.set_visible(False)   #Hide mouse for touchscreen input/Disable if test non touchscreen
		print('Finished running init')
		
	
	#Selection touch button control
	#Returns True if selection has been made, else False
	def __selection_OnClick(self,pos,firstRun):
		if 24 <= pos[0] <= 60:  #Column 1
			if 15 <= pos[1] <= 70: self.__selection_UpdateIdent(0,0)     #Up
			elif 165 <= pos[1] <= 210: self.__selection_UpdateIdent(0,1) #Down
		elif 80 <= pos[0] <= 115:  #Column 2
			if 15 <= pos[1] <= 70: self.__selection_UpdateIdent(1,0)
			elif 165 <= pos[1] <= 210: self.__selection_UpdateIdent(1,1)
		elif 135 <= pos[0] <= 170:  #Column 3
			if 15 <= pos[1] <= 70: self.__selection_UpdateIdent(2,0)
			elif 165 <= pos[1] <= 210: self.__selection_UpdateIdent(2,1)
		elif 190 <= pos[0] <= 225:  #Column 4
			if 15 <= pos[1] <= 70: self.__selection_UpdateIdent(3,0)
			elif 165 <= pos[1] <= 210: self.__selection_UpdateIdent(3,1)
		elif 245 <= pos[0] <= 305:  #Select/Cancel
			if 55 <= pos[1] <= 105: #Select. Update new ident
				self.oldIdent = copy(self.screenIdent)
				return True
			elif 135 <= pos[1] <= 185: #Cancel
				#If firstRun, offer shutdown. If not shutdown, reload selection screen
				if firstRun and not self.__options_Shutdown():
					self.__selection_Load()
					return False
				#Else revert to old ident
				else:
					self.screenIdent = copy(self.oldIdent)
					return True
		return False
	
	#Load selection screen elements
	#Returns None
	def __selection_Load(self):
		self.win.fill(white)  #Clear screen
		#Draw Selection Grid
		pos=([28,10],[28,160],[30,90])  #Left-most column positions [up,down,char]
		for i in range(3):  #For row
			for k in range(4):  #For column
				if i == 2: element = font48.render(charList[self.screenIdent[k]] , 1 , black)
				else: element = font48.render(specialchar[i] , 1 , black)
				self.win.blit(element , pos[i])
				pos[i][0] += 55
		#Draw Select Button
		pygame.draw.circle(self.win , green , (275,80) , 25)
		self.win.blit(font48.render(specialchar[2] , 1 , (0,0,0)) , (255,53))
		#Draw Cancel Button
		pygame.draw.circle(self.win, red , (275,160) , 25)
		self.win.blit(font48.render(specialchar[3] , 1 , (0,0,0)) , (255,133))
		pygame.display.flip()
	
	#Updates ident and replaces ident char on display
	#pos : 0-3 column , direc : True down/False up
	#Returns None
	def __selection_UpdateIdent(self,pos,direc):
		#Update ident
		if direc:
			self.screenIdent[pos] += 1
			if self.screenIdent[pos] == len(charList): self.screenIdent[pos] = 0
		else:
			if self.screenIdent[pos] == 0: self.screenIdent[pos] = len(charList)
			self.screenIdent[pos] -= 1
		#Update display
		if pos == 0: pygame.draw.rect(self.win , white , (24,90,55,55))
		elif pos == 1: pygame.draw.rect(self.win , white , (80,90,55,55))
		elif pos == 2: pygame.draw.rect(self.win , white , (135,90,55,55))
		else: pygame.draw.rect(self.win , white , (190,90,55,55))
		element = font48.render(charList[self.screenIdent[pos]] , 1 , black)
		self.win.blit(element , [30+pos*55,90])
		pygame.display.flip()
	
	#Runs station selection screen, updates ident, and displays load screen once selection made or cancelled
	#Returns None
	def selectStation(self , firstRun = False):
		print(timestamp('Select Loaded'))
		self.__selection_Load() #Load selection display
		while True: #Input loop
			for event in pygame.event.get():
				if event.type == pygame.MOUSEBUTTONDOWN:
					#Run input control and continue if selection made
					if self.__selection_OnClick(pygame.mouse.get_pos() , firstRun):
						#Display load screen
						self.win.fill(white)
						self.win.blit(font32.render('Fetching weather' , 1 , black) , (25,70))
						self.win.blit(font32.render('data for '+getIdent(self.screenIdent) , 1 , black) , (25,120))
						pygame.display.flip()
						return None
	
	#Display invalid station message and sleep
	#Returns None
	def error_badStation(self , firstRun = False):
		self.win.fill(white)  #Clear screen
		self.win.blit(font32.render("No weather data" , 1 , black) , (25,70))
		self.win.blit(font32.render("for "+getIdent(self.screenIdent) , 1 , black) , (25,120))
		pygame.display.flip()
		time.sleep(3)
		self.selectStation(firstRun)
	
	#Display timeout message and sleep
	#Returns None
	def error_timeout(self):
		if logMETAR: print(timestamp('Connection Timeout'))
		self.win.fill(white)  #Clear screen
		self.win.blit(font32.render("No connection" , 1 , black) , (25,70))
		self.win.blit(font32.render("Check back soon" , 1 , black) , (25,120))
		pygame.display.flip()
		time.sleep(timeoutInterval)
	
	#Load Main static background elements
	#Returns None
	def __display_LoadStatic(self):
		self.win.fill(white)
		#Cloud Axis
		self.win.blit(font18.render('Clouds AGL' , 1 , black) , (205,35))
		pygame.draw.lines(self.win , black , False , ((200,60),(200,230),(310,230)) , 3)
		#Settings
		pygame.draw.circle(self.win , gray , (40,213) , 24)
		self.win.blit(font48.render(specialchar[4] , 1 , white) , (19,185))
		#Wind Compass
		pygame.draw.circle(self.win , gray , (40,80) , 35 , 3)
		pygame.display.flip()
	
	#Load Main dynamic foreground elements
	#data : parsed METAR library
	#Returns True if "Other-WX" or "Remarks" is not empty, else False
	def __display_LoadDynamic(self , data):
		#Station and Time
		self.win.blit(font26.render(data['Station']+'  '+data['Time'][:2]+'-'+data['Time'][2:4]+':'+data['Time'][4:] , 1 , black) , (5,5))
		#Current Flight Rules
		fr = getFlightRules(data['Visibility'] , getCeiling(data['Cloud-List']))
		if fr == 0: self.win.blit(font26.render('VFR' , 1 , green) , (263,5))
		elif fr == 1: self.win.blit(font26.render('MVFR' , 1 , blue) , (241,5))
		elif fr == 2: self.win.blit(font26.render('IFR' , 1 , red) , (273,5))
		elif fr == 3: self.win.blit(font26.render('LIFR' , 1 , purple) , (258,5))
		else: self.win.blit(font26.render('N/A' , 1 , black) , (269,5))
		#Wind
		windDir = data['Wind-Direction']
		if data['Wind-Speed'] == '00': 1
		elif windDir == 'VRB': self.win.blit(font26.render('VRB' , 1 , black) , (15,66))
		elif windDir != '' and windDir[0] != '/': 
			pygame.draw.line(self.win , red , (40,80) , (40+35*math.cos((int(windDir)-90)*math.pi/180),80+35*math.sin((int(windDir)-90)*math.pi/180)) , 2)
			if len(data['Wind-Variable-Dir']) == 2:
				pygame.draw.line(self.win , blue , (40,80) , (40+35*math.cos((int(data['Wind-Variable-Dir'][0])-90)*math.pi/180),80+35*math.sin((int(data['Wind-Variable-Dir'][0])-90)*math.pi/180)) , 2)
				pygame.draw.line(self.win , blue , (40,80) , (40+35*math.cos((int(data['Wind-Variable-Dir'][1])-90)*math.pi/180),80+35*math.sin((int(data['Wind-Variable-Dir'][1])-90)*math.pi/180)) , 2)
			self.win.blit(font26.render(windDir , 1 , black) , (15,66))
		else: self.win.blit(font48.render(specialchar[3] , 1 , red) , (20,54))
		if data['Wind-Speed'] == '00': self.win.blit(font18.render('Calm' , 1 , black) , (17,126))
		elif data['Wind-Speed'].find('-') != -1: self.win.blit(font18.render(data['Wind-Speed']+' kt' , 1 , black) , (5,116))
		else: self.win.blit(font18.render(data['Wind-Speed']+' kt' , 1 , black) , (17,116))
		if data['Wind-Speed'] == '00': 1
		elif data['Wind-Gust'].find('-') != -1: self.win.blit(font18.render('G: '+data['Wind-Gust'] , 1 , black) , (5,137))
		elif data['Wind-Gust'] != '': self.win.blit(font18.render('G: '+data['Wind-Gust'] , 1 , black) , (17,137))
		else: self.win.blit(font18.render('No Gust' , 1 , black) , (5,137))
		#Temperature / Dewpoint / Humidity
		temp = data['Temperature']
		dew = data['Dewpoint']
		if dew != '' and dew[0] != '/':
			if dew[0] == 'M': dew = -1 * int(dew[1:])
			else: dew = int(dew)
			self.win.blit(font18.render('DEW: '+str(dew)+specialchar[5] , 1 , black) , (105,114))
		else: self.win.blit(font18.render('DEW: --' , 1 , black) , (105,114))
		if temp != '' and temp[0] != '/':
			if temp[0] == 'M': temp = -1 * int(temp[1:])
			else: temp = int(temp)
			fileNum = temp//12+2
			if fileNum < 0: fileNum = 0
			if invertBW > 0: self.win.blit(pygame.image.load(path+'/icons/Therm'+str(fileNum)+'I.png') , (60,50))
			else: self.win.blit(pygame.image.load(path+'/icons/Therm'+str(fileNum)+'.png') , (60,50))
			self.win.blit(font18.render('TMP: '+str(temp)+specialchar[5] , 1 , black) , (110,50))
			tempDiff = temp - 15
			if tempDiff < 0: self.win.blit(font18.render('STD: -'+str(abs(tempDiff))+specialchar[5] , 1 , black) , (110,82))
			else: self.win.blit(font18.render('STD:+'+str(tempDiff)+specialchar[5] , 1 , black) , (110,82))				
		else:
			if invertBW > 0: self.win.blit(pygame.image.load(path+'/icons/Therm0I.png') , (60,50))
			else: self.win.blit(pygame.image.load(path+'/icons/Therm0.png') , (60,50))
			self.win.blit(font18.render('TMP: --' , 1 , black) , (110,50))
			self.win.blit(font18.render('STD: --' , 1 , black) , (110,82))
		if type(temp) == int and type(dew) == int:
			relHum = str((6.11*10.0**(7.5*dew/(237.7+dew)))/(6.11*10.0**(7.5*temp/(237.7+temp)))*100)
			self.win.blit(font18.render('HMD: '+relHum[:relHum.find('.')]+'%' , 1 , black) , (90,146))
		else: self.win.blit(font18.render('HMD: --' , 1 , black) , (90,146))
		#Altimeter
		altm = data['Altimeter']
		if altm != '' and altm[0] != '/':
			altm = altm[:2] + '.' + altm[2:]
			self.win.blit(font18.render('ALT:  '+altm , 1 , black) , (90,178))
		else:
			self.win.blit(font18.render('ALT: --' , 1 , black) , (90,178))
		#Visibility
		vis = data['Visibility']
		if vis != '' and vis[0] != '/':
			if len(vis) == 4 and vis.isdigit(): self.win.blit(font18.render('VIS: '+vis+'M' , 1 , black) , (90,210))
			else: self.win.blit(font18.render('VIS: '+vis+'SM' , 1 , black) , (90,210))
		else: self.win.blit(font18.render('VIS: --' , 1 , black) , (90,210))
		#Cloud Layers
		clouds = copy(data['Cloud-List'])
		clouds.reverse()
		if len(clouds) == 0 or clouds[0] in ['CLR','SKC']: self.win.blit(font32.render('CLR' , 1 , blue) , (226,120))
		else:
			top = 80
			LRBool = 1
			for cloud in clouds:
				if cloud[1][0] != '/':
					if int(cloud[1]) > top: top = int(cloud[1])
					drawHeight = 220-160*int(cloud[1])/top
					if LRBool > 0:
						self.win.blit(font12.render(cloud[0]+cloud[1] , 1 , blue) , (210,drawHeight))
						pygame.draw.line(self.win , blue , (262,drawHeight+7) , (308,drawHeight+7))
					else:
						self.win.blit(font12.render(cloud[0]+cloud[1] , 1 , blue) , (260,drawHeight))
						pygame.draw.line(self.win , blue , (210,drawHeight+7) , (255,drawHeight+7))
					LRBool *= -1
		#Other Weather data
		moreData = True
		if data['Remarks'] != '' and data['Other-List'] != []:
			pygame.draw.rect(self.win , purple , ((3,159),(80,27)) , 2)
			self.win.blit(font18.render('WX/RMK' , 1 , purple) , (4,162))
		else:
			if data['Remarks'] != '':
				pygame.draw.rect(self.win , blue , ((3,159),(80,27)) , 2)
				self.win.blit(font18.render('RMK' , 1 , blue) , (21,162))
			elif data['Other-List'] != []:
				pygame.draw.rect(self.win , red , ((3,159),(80,27)) , 2)
				self.win.blit(font18.render('WX' , 1 , red) , (26,162))
			else: moreData = False
		pygame.display.flip()
		return moreData
	
	#Display available Other Weather / Remarks and cancel button control
	#wxList : List of raw other weather , rmk : Remarks string
	#Returns None
	#Note: This function is designed to easily add more display data
	def __display_OtherData(self , wxList , rmk):
		def getY(numHead , numLine): return 5+26*numHead+23*numLine
		#Load
		self.win.fill(white)
		numHead , numLine = 0 , 0
		#Weather
		if wxList != []:
			self.win.blit(font18.render('Other Weather' , 1 , black) , (8,getY(numHead,numLine)))
			numHead += 1
			offset = -75
			for wx in wxList:
				wx = translateWX(wx).strip() #Translate raw WX
				#Column overflow control
				if len(wx) > 17:
					if offset > 0: numLine += 1
					offset = -75
				self.win.blit(font16.render(wx , 1 , black) , (85+offset,getY(numHead,numLine)))
				if len(wx) > 17: numLine += 1
				else:
					if offset > 0: numLine += 1
					offset *= -1
			if offset > 0: numLine += 1
		#Remarks
		if rmk != '':
			self.win.blit(font18.render('Remarks' , 1 , black) , (8,getY(numHead,numLine)))
			numHead += 1
			#Line overflow control
			while len(rmk) > 28:
				cutPoint = rmk[:28].rfind(' ')
				self.win.blit(font16.render(rmk[:cutPoint] , 1 , black) , (10,getY(numHead,numLine)))
				numLine += 1
				rmk = rmk[cutPoint+1:]
			self.win.blit(font16.render(rmk , 1 , black) , (10,getY(numHead,numLine)))
			numLine += 1
		#Cancel Button
		pygame.draw.circle(self.win , gray , (40,213) , 24)
		self.win.blit(font48.render(specialchar[3] , 1 , white) , (20,185))
		pygame.display.flip()
		while True: #Input loop
			for event in pygame.event.get():
				if event.type == pygame.MOUSEBUTTONDOWN:
					pos = pygame.mouse.get_pos()
					if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return None
	
	#Run main data display and options touch button control
	#data : parsed METAR library
	#Returns True if options button pressed, False when elapsed time > update time
	def displayMETAR(self , data):
		self.__display_LoadStatic()
		moreData = self.__display_LoadDynamic(data)
		updateTime = time.time() + updateInterval
		while time.time() <= updateTime: #Input loop, exit if elapsed time > update time
			for event in pygame.event.get():
				if event.type == pygame.MOUSEBUTTONDOWN:
					pos = pygame.mouse.get_pos()
					#If settings button
					if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return True
					#If other wx/rmk button
					elif moreData and (3 <= pos[0] <= 83) and (159 <= pos[1] <= 186):
						otherList = data['Other-List']
						if data['Runway-Visibility'] != '': otherList = otherList.append(data['Runway-Visibility'])
						self.__display_OtherData(otherList , data['Remarks'])
						self.__display_LoadStatic()
						moreData = self.__display_LoadDynamic(data)
		return False
	
	#Load options bar elements
	#Returns None
	def __options_Load(self):
		#Clear Option background
		pygame.draw.rect(self.win , white , ((0,190),(85,50)))
		pygame.draw.rect(self.win , white , ((85,180),(335,60)))
		#Cancel Button
		pygame.draw.circle(self.win , gray , (40,213) , 24)
		self.win.blit(font48.render(specialchar[3] , 1 , white) , (20,185))
		#Selection Button
		pygame.draw.circle(self.win , green , (100,213) , 24)
		self.win.blit(font26.render(specialchar[0] , 1 , white) , (90,183))
		self.win.blit(font26.render(specialchar[1] , 1 , white) , (90,207))
		#Shutdown Button
		pygame.draw.circle(self.win , red , (160,213) , 24)
		pygame.draw.circle(self.win , white , (160,213) , 18)
		pygame.draw.circle(self.win , red , (160,213) , 15)
		pygame.draw.rect(self.win , white , ((158,203),(4,20)))
		#Invert Button
		pygame.draw.circle(self.win , black , (220,213) , 24)
		if invertBW > 0: self.win.blit(font48.render(specialchar[6] , 1 , white) , (198,185))
		else: self.win.blit(font48.render(specialchar[7] , 1 , white) , (202,185))
		#Info Button
		pygame.draw.circle(self.win , purple , (280,213) , 24)
		self.win.blit(font48.render(specialchar[8] , 1 , white) , (271,185))
		pygame.display.flip()
	
	#Options touch button control
	#Returns True if ident update required, else False
	def __options_OnClick(self , pos):
		#If Cancel
		if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return False
		#If station select
		elif (76 <= pos[0] <= 124) and (189 <= pos[1] <= 237): return True
		#If shutdown
		elif (136 <= pos[0] <= 184) and (189 <= pos[1] <= 237): return self.__options_Shutdown()
		#If invert color
		elif (196 <= pos[0] <= 244) and (189 <= pos[1] <= 237):
			global invertBW , black , white
			invertBW *= -1
			black , white = white , black
			return False
		#If info
		elif (256 <= pos[0] <= 304) and (189 <= pos[1] <= 237): return self.__options_Info()
		return None
	
	#Display Shutdown/Exit option and touch button control
	#Returns False or exits program
	def __options_Shutdown(self):
		self.win.fill(white)
		if shutdownOnExit: self.win.blit(font32.render("Shutdown the Pi?" , 1 , black) , (22,70))
		else: self.win.blit(font32.render("Exit the program?" , 1 , black) , (18,70))
		pygame.draw.circle(self.win , green , (105,150) , 25)
		self.win.blit(font48.render(specialchar[2] , 1 , (0,0,0)) , (85,123))
		pygame.draw.circle(self.win , red , (215,150) , 25)
		self.win.blit(font48.render(specialchar[3] , 1 , (0,0,0)) , (195,123))
		pygame.display.flip()
		while True: #Input loop
			for event in pygame.event.get():
				if event.type == pygame.MOUSEBUTTONDOWN:
					pos = pygame.mouse.get_pos()
					#If select
					if (80 <= pos[0] <= 130) and (125 <= pos[1] <= 175):
						if shutdownOnExit: os.system('shutdown -h now')
						sys.exit()
					#If cancel
					elif (190 <= pos[0] <= 240) and (125 <= pos[1] <= 175):
						return False
	
	#Display info screen and cancel touch button control
	#Returns False
	def __options_Info(self):
		#Load
		self.win.fill(white)
		self.win.blit(font32.render('METAR-RasPi' , 1 , black) , (51,40))
		self.win.blit(font18.render('Michael duPont' , 1 , black) , (85,95))
		self.win.blit(font18.render('michael@mdupont.com' , 1 , black) , (50,120))
		self.win.blit(font12.render('github.com/flyinactor91/METAR-RasPi' , 1 , black) , (40,147))
		#Cancel Button
		pygame.draw.circle(self.win , gray , (40,213) , 24)
		self.win.blit(font48.render(specialchar[3] , 1 , white) , (20,185))
		pygame.display.flip()
		while True: #Input loop
			for event in pygame.event.get():
				if event.type == pygame.MOUSEBUTTONDOWN:
					pos = pygame.mouse.get_pos()
					if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return False
	
	#Run options bar display and options touch button control
	#Returns True if METAR update needed, False if not, None if no button pressed
	def options(self):
		self.__options_Load()
		while True:
			for event in pygame.event.get():
				if event.type == pygame.MOUSEBUTTONDOWN:
					ret = self.__options_OnClick(pygame.mouse.get_pos())
					if type(ret) == bool: return ret

#Program Main
#Returns 1 if error, else 0
def main():
	screen = METARScreen() #Init screen
	if logMETAR: print('\n' + timestamp('Program Boot'))
	firstRun , userSelected = True , True
	lastMETAR = ''
	screen.selectStation(firstRun) #Run firstRun station selection
	while True:
		METARtxt = getMETAR(getIdent(screen.screenIdent)) #Fetch current METAR
		while type(METARtxt) == int:                      #Fetch data until success
			if logMETAR: print(timestamp('Error METAR ' + str(METARtxt) + ' ' + getIdent(screen.screenIdent)))
			if METARtxt == 0: screen.error_timeout()      #Bad Connection
			elif METARtxt == 1:
				if not userSelected:
					if logMETAR: print(timestamp('Ignoring non-user generated selection'))
					METARtxt = copy(lastMETAR)
					break
				else: screen.error_badStation(firstRun) #Invalid Station
			else: return 1                              #Code error
			METARtxt = getMETAR(getIdent(screen.screenIdent))
		firstRun , userSelected = False , False
		lastMETAR = copy(METARtxt)
		if logMETAR: print(timestamp(METARtxt))
		while screen.displayMETAR(parseMETAR(METARtxt)): #Reload screen but don't get new data
			if screen.options():       #Load options. If ident update required
				screen.selectStation() #Run station selection
				userSelected = True
				break
	return 0

if __name__ == '__main__':
	if runOnPi:
		os.environ["SDL_FBDEV"] = "/dev/fb1"
		os.environ["SDL_MOUSEDEV"] = "/dev/input/touchscreen"
		os.environ["SDL_MOUSEDRV"] = "TSLIB"
		os.environ["SDL_VIDEODRIVER"] = "fbcon"
	main()
