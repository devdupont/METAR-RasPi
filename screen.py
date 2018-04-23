"""
Michael duPont - michael@mdupont.com
screen.py - Display ICAO METAR weather data with a Raspberry Pi and Adafruit 320x240 Touch PiTFT
"""

# pylint: disable=E1101

# stdlib
import math
import os
import sys
import time
from copy import copy, deepcopy
# library
import avwx
import pygame
# module
import common
import config as cfg
from common import IDENT_CHARS, logger

SPECIAL_CHAR = [
    '\u25b2', # Up triangle
    '\u2713', # Checkmark
    '\u25bc', # Down triangle
    '\u2715', # Cancel X
    '\u2699', # Settings gear
    '\u00B0', # Degree sign
    '\u2600', # Sun
    '\u263E', # Moon
    '\u2139'  # Info i
]

class Color():
    WHITE = 255,255,255
    BLACK = 0,0,0
    RED = 255,0,0
    GREEN = 0,255,0
    BLUE = 0,0,255
    PURPLE = 150,0,255
    GRAY = 60,60,60

# Init pygame and fonts
pygame.init()
path = os.path.abspath(os.path.dirname(__file__))
FONT12 = pygame.font.Font(path+'/icons/DejaVuSans.ttf', 12)
FONT16 = pygame.font.Font(path+'/icons/DejaVuSans.ttf', 16)
FONT18 = pygame.font.Font(path+'/icons/DejaVuSans.ttf', 18)
FONT26 = pygame.font.Font(path+'/icons/DejaVuSans.ttf', 26)
FONT32 = pygame.font.Font(path+'/icons/DejaVuSans.ttf', 32)
FONT48 = pygame.font.Font(path+'/icons/DejaVuSans.ttf', 48)

fr_display = {
    'VFR': (Color.GREEN, (263,5)),
    'MVFR': (Color.BLUE, (241,5)),
    'IFR': (Color.RED, (273,5)),
    'LIFR': (Color.PURPLE, (258,5)),
    'N/A': (Color.BLACK, (269,5))
}

class METARScreen:
    """
    Controls and draws UI elements
    """

    def __init__(self, station: str, size: (int, int), inverted: bool):
        logger.debug('Running init')
        self.ident = common.station_to_ident(station)
        self.old_ident = copy(self.ident)
        self.width, self.height = size
        self.win = pygame.display.set_mode(size)
        self.c = Color()
        self.inverted = inverted
        if inverted:
            self.c.BLACK, self.c.WHITE = self.c.WHITE, self.c.BLACK
        # Hide mouse for touchscreen input/Disable if test non touchscreen
        if cfg.on_pi:
            pygame.mouse.set_visible(False)
        logger.debug('Finished running init')

    @property
    def station(self) -> str:
        """
        The current station
        """
        return common.ident_to_station(self.ident)

    @classmethod
    def from_session(cls, session: dict, size: (int, int)):
        """
        """
        station = session.get('station', 'KJFK')
        inverted = session.get('inverted', True)
        return cls(station, size, inverted)

    def export_session(self, save: bool = True):
        """
        Saves or returns a dictionary representing the session's state
        """
        session = {
            'station': self.station,
            'inverted': self.inverted
        }
        if save:
            common.save_session(session)
        return session

    def __selection_OnClick(self, pos: (int, int)) -> bool:
        """
        Selection touch button control

        Returns True if selection has been made, else False
        """
        if 25 <= pos[0] <= 60:  #Column 1
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
                self.old_ident = copy(self.ident)
                return True
            elif 135 <= pos[1] <= 185: #Cancel
                self.ident = copy(self.old_ident)
                return True
        return False

    @staticmethod
    def __selection_getx(col: int) -> int:
        """
        Returns the top left x pixel for a desired column
        """
        return 25 + col * 55

    def __selection_Load(self):
        """
        Load selection screen elements
        """
        self.win.fill(self.c.WHITE)
        # Draw Selection Grid
        # Left-most column y values [up, char, down]
        y = (10, 90, 160)
        for row in range(3):
            for col in range(4):
                if row == 1:
                    element = FONT48.render(IDENT_CHARS[self.ident[col]], 1, self.c.BLACK)
                else:
                    element = FONT48.render(SPECIAL_CHAR[row], 1, self.c.BLACK)
                self.win.blit(element, (self.__selection_getx(col), y[row]))
        # Draw Select Button
        pygame.draw.circle(self.win, self.c.GREEN, (275,80), 25)
        self.win.blit(FONT48.render(SPECIAL_CHAR[1], 1, (0,0,0)), (255,53))
        # Draw Cancel Button
        pygame.draw.circle(self.win, self.c.RED, (275,160), 25)
        self.win.blit(FONT48.render(SPECIAL_CHAR[3], 1, (0,0,0)), (255,133))
        pygame.display.flip()

    def __selection_UpdateIdent(self, pos: int, direc: bool):
        """
        Updates ident and replaces ident char on display
        
        pos: 0-3 column
        direc: True down/False up
        """
        # Update ident
        if direc:
            self.ident[pos] += 1
            if self.ident[pos] == len(IDENT_CHARS): self.ident[pos] = 0
        else:
            if self.ident[pos] == 0: self.ident[pos] = len(IDENT_CHARS)
            self.ident[pos] -= 1
        # Update display
        x = self.__selection_getx(pos)
        pygame.draw.rect(self.win, self.c.WHITE, (x,90,55,55))
        element = FONT48.render(IDENT_CHARS[self.ident[pos]], 1, self.c.BLACK)
        self.win.blit(element, [x,90])
        pygame.display.flip()

    def selectStation(self):
        """
        Runs station selection screen, updates ident, and
        displays load screen once selection made or cancelled
        """
        logger.debug('Select Loaded')
        self.__selection_Load() #Load selection display
        while True: #Input loop
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    #Run input control and continue if selection made
                    if self.__selection_OnClick(pygame.mouse.get_pos()):
                        #Display load screen
                        self.win.fill(self.c.WHITE)
                        self.win.blit(FONT32.render('Fetching weather', 1, self.c.BLACK), (25,70))
                        self.win.blit(FONT32.render('data for ' + self.station, 1, self.c.BLACK), (25,120))
                        pygame.display.flip()
                        return None

    def error_badStation(self):
        """
        Display invalid station message and sleep
        """
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render("No weather data", 1, self.c.BLACK), (25,70))
        self.win.blit(FONT32.render("for " + self.station, 1, self.c.BLACK), (25,120))
        pygame.display.flip()
        print('Sleeping bad station')
        pygame.time.wait(3000)
        self.selectStation()

    def error_timeout(self):
        """
        Display timeout message and sleep
        """
        logger.warning('Connection Timeout')
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render("No connection", 1, self.c.BLACK), (25,70))
        self.win.blit(FONT32.render("Check back soon", 1, self.c.BLACK), (25,120))
        pygame.display.flip()
        pygame.time.wait(cfg.timeout_interval * 1000)

    def __display_LoadStatic(self):
        """
        Load Main static background elements
        """
        self.win.fill(self.c.WHITE)
        #Cloud Axis
        self.win.blit(FONT18.render('Clouds AGL', 1, self.c.BLACK), (205,35))
        pygame.draw.lines(self.win, self.c.BLACK, False, ((200,60),(200,230),(310,230)), 3)
        #Settings
        pygame.draw.circle(self.win, self.c.GRAY, (40,213), 24)
        self.win.blit(FONT48.render(SPECIAL_CHAR[4], 1, self.c.WHITE), (19,185))
        #Wind Compass
        pygame.draw.circle(self.win, self.c.GRAY, (40,80), 35, 3)
        pygame.display.flip()

    def __display_LoadDynamic(self, data: dict) -> bool:
        """
        Load Main dynamic foreground elements

        Returns True if "Other-WX" or "Remarks" is not empty, else False
        """
        #Station and Time
        self.win.blit(FONT26.render(data['Station']+'  '+data['Time'][:2]+'-'+data['Time'][2:4]+':'+data['Time'][4:], 1, self.c.BLACK), (5,5))
        #Current Flight Rules
        fr = data['Flight-Rules'] or 'N/A'
        fr_color, fr_loc = fr_display[fr]
        self.win.blit(FONT26.render(fr, 1, fr_color), fr_loc)
        #Wind
        windDir = data['Wind-Direction']
        if data['Wind-Speed'] == '00': 1
        elif windDir == 'VRB': self.win.blit(FONT26.render('VRB', 1, self.c.BLACK), (15,66))
        elif windDir != '' and windDir[0] != '/':
            pygame.draw.line(self.win, self.c.RED, (40,80), (40+35*math.cos((int(windDir)-90)*math.pi/180),80+35*math.sin((int(windDir)-90)*math.pi/180)), 2)
            if len(data['Wind-Variable-Dir']) == 2:
                pygame.draw.line(self.win, self.c.BLUE, (40,80), (40+35*math.cos((int(data['Wind-Variable-Dir'][0])-90)*math.pi/180),80+35*math.sin((int(data['Wind-Variable-Dir'][0])-90)*math.pi/180)), 2)
                pygame.draw.line(self.win, self.c.BLUE, (40,80), (40+35*math.cos((int(data['Wind-Variable-Dir'][1])-90)*math.pi/180),80+35*math.sin((int(data['Wind-Variable-Dir'][1])-90)*math.pi/180)), 2)
            self.win.blit(FONT26.render(windDir, 1, self.c.BLACK), (15,66))
        else: self.win.blit(FONT48.render(SPECIAL_CHAR[3], 1, self.c.RED), (20,54))
        if data['Wind-Speed'] == '00': self.win.blit(FONT18.render('Calm', 1, self.c.BLACK), (17,126))
        elif data['Wind-Speed'].find('-') != -1: self.win.blit(FONT18.render(data['Wind-Speed']+' kt', 1, self.c.BLACK), (5,116))
        else: self.win.blit(FONT18.render(data['Wind-Speed']+' kt', 1, self.c.BLACK), (17,116))
        if data['Wind-Speed'] == '00': 1
        elif data['Wind-Gust'].find('-') != -1: self.win.blit(FONT18.render('G: '+data['Wind-Gust'], 1, self.c.BLACK), (5,137))
        elif data['Wind-Gust'] != '': self.win.blit(FONT18.render('G: '+data['Wind-Gust'], 1, self.c.BLACK), (17,137))
        else: self.win.blit(FONT18.render('No Gust', 1, self.c.BLACK), (5,137))
        #Temperature / Dewpoint / Humidity
        temp = data['Temperature']
        dew = data['Dewpoint']
        if dew != '' and dew[0] != '/':
            if dew[0] == 'M': dew = -1 * int(dew[1:])
            else: dew = int(dew)
            self.win.blit(FONT18.render('DEW: '+str(dew)+SPECIAL_CHAR[5], 1, self.c.BLACK), (105,114))
        else: self.win.blit(FONT18.render('DEW: --', 1, self.c.BLACK), (105,114))
        if temp != '' and temp[0] != '/':
            if temp[0] == 'M': temp = -1 * int(temp[1:])
            else: temp = int(temp)
            fileNum = temp//12+2
            if fileNum < 0: fileNum = 0
            if self.inverted:
                self.win.blit(pygame.image.load(path+'/icons/Therm'+str(fileNum)+'I.png'), (60,50))
            else:
                self.win.blit(pygame.image.load(path+'/icons/Therm'+str(fileNum)+'.png'), (60,50))
            self.win.blit(FONT18.render('TMP: '+str(temp)+SPECIAL_CHAR[5], 1, self.c.BLACK), (110,50))
            tempDiff = temp - 15
            if tempDiff < 0: self.win.blit(FONT18.render('STD: -'+str(abs(tempDiff))+SPECIAL_CHAR[5], 1, self.c.BLACK), (110,82))
            else: self.win.blit(FONT18.render('STD:+'+str(tempDiff)+SPECIAL_CHAR[5], 1, self.c.BLACK), (110,82))
        else:
            if self.inverted:
                self.win.blit(pygame.image.load(path+'/icons/Therm0I.png'), (60,50))
            else:
                self.win.blit(pygame.image.load(path+'/icons/Therm0.png'), (60,50))
            self.win.blit(FONT18.render('TMP: --', 1, self.c.BLACK), (110,50))
            self.win.blit(FONT18.render('STD: --', 1, self.c.BLACK), (110,82))
        if type(temp) == int and type(dew) == int:
            relHum = str((6.11*10.0**(7.5*dew/(237.7+dew)))/(6.11*10.0**(7.5*temp/(237.7+temp)))*100)
            self.win.blit(FONT18.render('HMD: '+relHum[:relHum.find('.')]+'%', 1, self.c.BLACK), (90,146))
        else: self.win.blit(FONT18.render('HMD: --', 1, self.c.BLACK), (90,146))
        #Altimeter
        altm = data['Altimeter']
        if altm != '' and altm[0] != '/':
            altm = altm[:2] + '.' + altm[2:]
            self.win.blit(FONT18.render('ALT:  '+altm, 1, self.c.BLACK), (90,178))
        else:
            self.win.blit(FONT18.render('ALT: --', 1, self.c.BLACK), (90,178))
        #Visibility
        vis = data['Visibility']
        if vis != '' and vis[0] != '/':
            if len(vis) == 4 and vis.isdigit(): self.win.blit(FONT18.render('VIS: '+vis+'M', 1, self.c.BLACK), (90,210))
            else: self.win.blit(FONT18.render('VIS: '+vis+'SM', 1, self.c.BLACK), (90,210))
        else: self.win.blit(FONT18.render('VIS: --', 1, self.c.BLACK), (90,210))
        #Cloud Layers
        clouds = copy(data['Cloud-List'])
        clouds.reverse()
        if len(clouds) == 0 or clouds[0] in ['CLR','SKC']:
            self.win.blit(FONT32.render('CLR', 1, self.c.BLUE), (226,120))
        else:
            top = 80
            LRBool = 1
            for cloud in clouds:
                if cloud[1][0] != '/':
                    if int(cloud[1]) > top: top = int(cloud[1])
                    drawHeight = 220-160*int(cloud[1])/top
                    if LRBool > 0:
                        self.win.blit(FONT12.render(cloud[0]+cloud[1], 1, self.c.BLUE), (210,drawHeight))
                        pygame.draw.line(self.win, self.c.BLUE, (262,drawHeight+7), (308,drawHeight+7))
                    else:
                        self.win.blit(FONT12.render(cloud[0]+cloud[1], 1, self.c.BLUE), (260,drawHeight))
                        pygame.draw.line(self.win, self.c.BLUE, (210,drawHeight+7), (255,drawHeight+7))
                    LRBool *= -1
        #Other Weather data
        moreData = True
        if data['Remarks'] != '' and data['Other-List'] != []:
            pygame.draw.rect(self.win, self.c.PURPLE, ((3,159),(80,27)), 2)
            self.win.blit(FONT18.render('WX/RMK', 1, self.c.PURPLE), (4,162))
        else:
            if data['Remarks'] != '':
                pygame.draw.rect(self.win, self.c.BLUE, ((3,159),(80,27)), 2)
                self.win.blit(FONT18.render('RMK', 1, self.c.BLUE), (21,162))
            elif data['Other-List'] != []:
                pygame.draw.rect(self.win, self.c.RED, ((3,159),(80,27)), 2)
                self.win.blit(FONT18.render('WX', 1, self.c.RED), (26,162))
            else: moreData = False
        pygame.display.flip()
        return moreData

    def __display_OtherData(self, wxList, rmk):
        """
        Display available Other Weather / Remarks and cancel button control
        
        wxList : List of raw other weather, rmk : Remarks string

        Note: This function is designed to easily add more display data
        """
        def getY(numHead: int, numLine: int) -> int:
            return 5+26*numHead+23*numLine
        #Load
        self.win.fill(self.c.WHITE)
        numHead, numLine = 0, 0
        #Weather
        if wxList:
            self.win.blit(FONT18.render('Other Weather', 1, self.c.BLACK), (8,getY(numHead,numLine)))
            numHead += 1
            offset = -75
            for wx in wxList:
                wx = avwx.translate.other_list(wx).strip() #Translate raw WX
                #Column overflow control
                if len(wx) > 17:
                    if offset > 0: numLine += 1
                    offset = -75
                self.win.blit(FONT16.render(wx, 1, self.c.BLACK), (85+offset,getY(numHead,numLine)))
                if len(wx) > 17: numLine += 1
                else:
                    if offset > 0: numLine += 1
                    offset *= -1
            if offset > 0: numLine += 1
        #Remarks
        if rmk != '':
            self.win.blit(FONT18.render('Remarks', 1, self.c.BLACK), (8,getY(numHead,numLine)))
            numHead += 1
            #Line overflow control
            while len(rmk) > 28:
                cutPoint = rmk[:28].rfind(' ')
                self.win.blit(FONT16.render(rmk[:cutPoint], 1, self.c.BLACK), (10,getY(numHead,numLine)))
                numLine += 1
                rmk = rmk[cutPoint+1:]
            self.win.blit(FONT16.render(rmk, 1, self.c.BLACK), (10,getY(numHead,numLine)))
            numLine += 1
        #Cancel Button
        pygame.draw.circle(self.win, self.c.GRAY, (40,213), 24)
        self.win.blit(FONT48.render(SPECIAL_CHAR[3], 1, self.c.WHITE), (20,185))
        pygame.display.flip()
        while True: #Input loop
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return None

    def displayMETAR(self, data: dict) -> bool:
        """
        Run main data display and options touch button control

        Returns True if options button pressed, False when elapsed time > update time
        """
        self.__display_LoadStatic()
        moreData = self.__display_LoadDynamic(data)
        updateTime = time.time() + cfg.update_interval
        while time.time() <= updateTime: #Input loop, exit if elapsed time > update time
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    #If settings button
                    if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return True
                    #If other wx/rmk button
                    elif moreData and (3 <= pos[0] <= 83) and (159 <= pos[1] <= 186):
                        otherList = data['Other-List']
                        if data['Runway-Vis-List']:
                            otherList += data['Runway-Vis-List']
                        self.__display_OtherData(otherList, data['Remarks'])
                        self.__display_LoadStatic()
                        moreData = self.__display_LoadDynamic(data)
        return False

    def __options_Load(self):
        """
        Load options bar elements
        """
        #Clear Option background
        pygame.draw.rect(self.win, self.c.WHITE, ((0,190),(85,50)))
        pygame.draw.rect(self.win, self.c.WHITE, ((85,180),(335,60)))
        #Cancel Button
        pygame.draw.circle(self.win, self.c.GRAY, (40,213), 24)
        self.win.blit(FONT48.render(SPECIAL_CHAR[3], 1, self.c.WHITE), (20,185))
        #Selection Button
        pygame.draw.circle(self.win, self.c.GREEN, (100,213), 24)
        self.win.blit(FONT26.render(SPECIAL_CHAR[0], 1, self.c.WHITE), (90,183))
        self.win.blit(FONT26.render(SPECIAL_CHAR[2], 1, self.c.WHITE), (90,207))
        #Shutdown Button
        pygame.draw.circle(self.win, self.c.RED, (160,213), 24)
        pygame.draw.circle(self.win, self.c.WHITE, (160,213), 18)
        pygame.draw.circle(self.win, self.c.RED, (160,213), 15)
        pygame.draw.rect(self.win, self.c.WHITE, ((158,203),(4,20)))
        #Invert Button
        pygame.draw.circle(self.win, self.c.BLACK, (220,213), 24)
        if self.inverted:
            self.win.blit(FONT48.render(SPECIAL_CHAR[6], 1, self.c.WHITE), (198,185))
        else:
            self.win.blit(FONT48.render(SPECIAL_CHAR[7], 1, self.c.WHITE), (202,185))
        #Info Button
        pygame.draw.circle(self.win, self.c.PURPLE, (280,213), 24)
        self.win.blit(FONT48.render(SPECIAL_CHAR[8], 1, self.c.WHITE), (271,185))
        pygame.display.flip()

    def __options_OnClick(self, pos: (int, int)) -> bool:
        """
        Options touch button control

        Returns True if ident update requiself.c.RED, else False
        """
        #If Cancel
        if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237): return False
        #If station select
        elif (76 <= pos[0] <= 124) and (189 <= pos[1] <= 237): return True
        #If shutdown
        elif (136 <= pos[0] <= 184) and (189 <= pos[1] <= 237): return self.__options_Shutdown()
        #If invert color
        elif (196 <= pos[0] <= 244) and (189 <= pos[1] <= 237):
            self.inverted = not self.inverted
            self.c.BLACK, self.c.WHITE = self.c.WHITE, self.c.BLACK
            self.export_session()
            return False
        #If info
        elif (256 <= pos[0] <= 304) and (189 <= pos[1] <= 237): return self.__options_Info()
        return None

    def __options_Shutdown(self) -> False:
        """
        Display Shutdown/Exit option and touch button control

        Returns False or exits program
        """
        self.win.fill(self.c.WHITE)
        if cfg.shutdown_on_exit: self.win.blit(FONT32.render("Shutdown the Pi?", 1, self.c.BLACK), (22,70))
        else: self.win.blit(FONT32.render("Exit the program?", 1, self.c.BLACK), (18,70))
        pygame.draw.circle(self.win, self.c.GREEN, (105,150), 25)
        self.win.blit(FONT48.render(SPECIAL_CHAR[1], 1, (0,0,0)), (85,123))
        pygame.draw.circle(self.win, self.c.RED, (215,150), 25)
        self.win.blit(FONT48.render(SPECIAL_CHAR[3], 1, (0,0,0)), (195,123))
        pygame.display.flip()
        while True: #Input loop
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    #If select
                    if (80 <= pos[0] <= 130) and (125 <= pos[1] <= 175):
                        if cfg.shutdown_on_exit: os.system('shutdown -h now')
                        sys.exit()
                    #If cancel
                    elif (190 <= pos[0] <= 240) and (125 <= pos[1] <= 175):
                        return False

    def __options_Info(self) -> False:
        """
        Display info screen and cancel touch button control

        Always returns False
        """
        #Load
        self.win.fill(self.c.WHITE)
        self.win.blit(FONT32.render('METAR-RasPi', 1, self.c.BLACK), (51,40))
        self.win.blit(FONT18.render('Michael duPont', 1, self.c.BLACK), (85,95))
        self.win.blit(FONT18.render('michael@mdupont.com', 1, self.c.BLACK), (50,120))
        self.win.blit(FONT12.render('github.com/flyinactor91/METAR-RasPi', 1, self.c.BLACK), (40,147))
        #Cancel Button
        pygame.draw.circle(self.win, self.c.GRAY, (40,213), 24)
        self.win.blit(FONT48.render(SPECIAL_CHAR[3], 1, self.c.WHITE), (20,185))
        pygame.display.flip()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if (16 <= pos[0] <= 64) and (189 <= pos[1] <= 237):
                        return False

    def options(self) -> bool:
        """
        Run options bar display and options touch button control

        Returns True if METAR update needed, False if not, None if no button pressed
        """
        self.__options_Load()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    ret = self.__options_OnClick(pygame.mouse.get_pos())
                    if type(ret) == bool:
                        return ret

def main() -> int:
    """
    Program main handles METAR data handling and user interaction flow
    """
    screen = METARScreen.from_session(common.load_session(), cfg.size)
    logger.debug('Program Boot')
    user_selected = True
    last_station = None
    try:
        station = avwx.Metar(screen.station)
    except avwx.exceptions.BadStation:
        station = avwx.Metar('KJFK')
    while True:
        try:
            station.update()
            screen.export_session()
            user_selected = False
            last_station = deepcopy(station)
            logger.info(station.raw)
            # Reload the main data display without calling update
            # - True means user pressed a UI button
            # - False triggers a data refresh
            while screen.displayMETAR(station.data):
                # Load options menu. True triggers ident selection screen
                if screen.options():
                    screen.selectStation()
                    user_selected = True
                    station = avwx.Metar(screen.station)
                    break
        except (avwx.exceptions.InvalidRequest, avwx.exceptions.BadStation) as exc:
            logger.warning('Error on ' + screen.station + ' ' + str(exc))
            if not user_selected:
                logger.info('Ignoring non-user generated selection')
                station = deepcopy(last_station)
                break
            # Invalid Station
            else:
                screen.error_badStation()
        except TimeoutError:
            screen.error_timeout()
    return 0

if __name__ == '__main__':
    if cfg.on_pi:
        os.environ["SDL_FBDEV"] = "/dev/fb1"
        os.environ["SDL_MOUSEDEV"] = "/dev/input/touchscreen"
        os.environ["SDL_MOUSEDRV"] = "TSLIB"
        os.environ["SDL_VIDEODRIVER"] = "fbcon"
    main()
