##--Michael duPont
##--METAR-RasPi : mlogic
##--Shared METAR settings and functions
##--2015-03-27

import string , time , sys
if sys.version_info[0] == 2: import urllib2
elif sys.version_info[0] == 3: from urllib.request import urlopen
else: print("Cannot load urllib in mlogic.py")

##--User Vars
updateInterval = 600.0    #Seconds between server pings
timeoutInterval = 60.0    #Seconds between connection retries
ident = [10 , 9 , 5 , 10] #Default station ident, ex. [10,9,5,10] = KJFK
logMETAR = False          #Print METAR log. Use "file.py >> METARlog.txt"
shutdownOnExit = False    #Set true to shutdown the Pi when exiting the program

##--Logic Vars
cloudList = ['FEW','SCT','BKN','OVC']
charList = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','0','1','2','3','4','5','6','7','8','9']
wxReplacements = {
'RA':'Rain','TS':'Thunderstorm','SH':'Showers','DZ':'Drizzle','VC':'Vicinity','UP':'Unknown Precip',
'SN':'Snow','FZ':'Freezing','SG':'Snow Grains','IC':'Ice Crystals','PL':'Ice Pellets','GR':'Hail','GS':'Small Hail',
'FG':'Fog','BR':'Mist','HZ':'Haze','VA':'Volcanic Ash','DU':'Wide Dust','FU':'Smoke','SA':'Sand','SY':'Spray',
'SQ':'Squall','PO':'Dust Whirls','DS':'Duststorm','SS':'Sandstorm','FC':'Funnel Cloud',
'BL':'Blowing','MI':'Shallow','BC':'Patchy','PR':'Partial','UP':'Unknown'}

##--Station Location Identifiers
RegionsUsingUSParser = ['C', 'K', 'M', 'P', 'T']
RegionsUsingInternationalParser = ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'L', 'M', 'N', 'O', 'R', 'S', 'U', 'V', 'W', 'Y', 'Z']
#The Central American region is split. Therefore we need to use the first two letters
MStationsUsingUSParser = ['MB', 'MD', 'MK', 'MM', 'MT', 'MU', 'MW', 'MY']
MStationsUsingInternationalParser = ['MG', 'MH', 'MN', 'MP', 'MR', 'MS', 'MZ']

#Converts 'ident' values to chars
#Returns 4-char string
def getIdent(identList):
	ret = ''
	for num in identList: ret += charList[num]
	return ret

#Get METAR report for 'station' from www.aviationweather.gov
#Returns METAR report string
#Else returns error int
#0=Bad connection , 1=Station DNE/Server Error
def getMETAR(station):
	try:
		if sys.version_info[0] == 2:
			response = urllib2.urlopen('http://www.aviationweather.gov/metar/data?ids='+station+'&format=raw&date=0&hours=0')
			html = response.read()
		elif sys.version_info[0] == 3:
			response = urlopen('http://www.aviationweather.gov/metar/data?ids='+station+'&format=raw&date=0&hours=0')
			html = response.read().decode('utf-8')
		if html.find(station+'<') != -1: return 1   #Station does not exist/Database lookup error
		reportStart = html.find('<code>'+station+' ')+6      #Report begins with station iden
		reportEnd = html[reportStart:].find('<')        #Report ends with html bracket
		return html[reportStart:reportStart+reportEnd].replace('\n ','')
	except:
		return 0

#Remove remarks and split
#Remarks can include RMK and on, NOSIG and on, and BECMG and on
def __getRemarks(txt):
	txt = txt.replace('?' , ' ')
	if txt.find('BECMG') != -1: return txt[:txt.find('BECMG')-1].strip().split(' ') , txt[txt.find('BECMG'):]
	elif txt.find('TEMPO') != -1: return txt[:txt.find('TEMPO')-1].strip().split(' ') , txt[txt.find('TEMPO'):]
	elif txt.find('TEMP') != -1: return txt[:txt.find('TEMP')-1].strip().split(' ') , txt[txt.find('TEMP'):]
	elif txt.find('NOSIG') != -1: return txt[:txt.find('NOSIG')-1].strip().split(' ') , txt[txt.find('NOSIG'):]
	elif txt.find('RMK') != -1: return txt[:txt.find('RMK')-1].strip().split(' ') , txt[txt.find('RMK')+4:]
	return txt.strip().split(' ') , ''

#Sanitize wxData
#We can remove and identify "one-off" elements
#AUTO and COR indicate report was automated
#$ signifies station needs repair work
#NSC stands for No Significant Clouds. This is equiv to CLR, SKC, and NCD. Also interpretted as empty Cloud-List
#Remove the "Calm M" which is only observed following 00000KT
#Fixes the "Loose KT" after wind (03012 KT) or removes if fix fails
#We also return the runway visibility since it is very easy to recognize and its location in the report is non-standard
def __sanitize(wxData):
	runwayVisibility = ''
	for i in reversed(range(len(wxData))):
		if len(wxData[i]) > 4 and wxData[i][0] == 'R' and (wxData[i][3] == '/' or wxData[i][4] == '/') and wxData[i][1:3].isdigit():
			runwayVisibility = wxData.pop(i)
		elif len(wxData[i]) in [4,6] and wxData[i][:2] == 'RE':
			wxData.pop(i)
		# 10 SM -> 10SM  and  01012 KT -> 01012KT    This won't work for "030/15 KT" but KT will be removed below to prevent other errors
		elif i != 0 and (wxData[i] == 'SM' and wxData[i-1].isdigit()) or (wxData[i] == 'KT' and wxData[i-1][:5].isdigit()) or (wxData[i].isdigit() and wxData[i-1] in cloudList): ######
			wxData[i-1] += wxData.pop(i)
		elif wxData[i] in ['AUTO' , 'COR' , 'NSC' , 'CLR' , 'SKC' , 'NCD' , '$' , 'KT' , 'M']:
			wxData.pop(i)
	return wxData , runwayVisibility
	
#Altimeter
def __getAltimeterUS(wxData):
	altimeter = ''
	if wxData and (wxData[len(wxData)-1][0] == 'A'): altimeter = wxData.pop()[1:]
	elif wxData and len(wxData[len(wxData)-1]) == 4 and wxData[len(wxData)-1].isdigit(): altimeter = wxData.pop()
	return wxData , altimeter

def __getAltimeterInternational(wxData):
	altimeter = ''
	if wxData and (wxData[len(wxData)-1][0] == 'Q'): altimeter = wxData.pop()[1:]
	return wxData , altimeter

#Temp/Dewpoint
def __getTempAndDewpoint(wxData):
	if wxData and (wxData[len(wxData)-1].find('/') != -1):
		TD = wxData.pop().split('/')
		return wxData , TD[0] , TD[1]
	return wxData , '' , ''

#Station and Time
def __getStationAndTime(wxData):
	station = wxData.pop(0)
	if wxData and len(wxData[0]) == 7 and wxData[0][6] == 'Z' and wxData[0][:6].isdigit(): time = wxData.pop(0)
	else: time = ''
	return wxData , station , time

#Surface wind
#Occasionally KT is not included. Check len=5 and is not altimeter. Check len>=8 and contains G (gust)
def __getWindInfo(wxData):
	direction , speed , gust = '' , '' , ''
	variable = []
	if wxData and ((wxData[0][len(wxData[0])-2:] == 'KT') or (wxData[0][len(wxData[0])-3:] == 'KTS') or (len(wxData[0]) == 5 and wxData[0].isdigit()) or (len(wxData[0]) >= 8 and wxData[0].find('G') != -1 and wxData[0].find('/') == -1 and wxData[0].find('MPS') == -1)):
		direction = wxData[0][:3]
		if wxData[0].find('G') != -1:
			gust = wxData[0][wxData[0].find('G')+1:wxData[0].find('KT')]
			speed = wxData[0][3:wxData[0].find('G')]
		else: speed = wxData[0][3:wxData[0].find('KT')]
		wxData.pop(0)
	elif wxData and wxData[0][len(wxData[0])-3:] == 'MPS':
		direction = wxData[0][:3]
		if wxData[0].find('G') != -1:
			gust = wxData[0][wxData[0].find('G')+1:wxData[0].find('MPS')]
			speed = wxData[0][3:wxData[0].find('G')]
		else: speed = wxData[0][3:wxData[0].find('MPS')]
		wxData.pop(0)
	elif wxData and len(wxData[0]) > 5 and wxData[0][3] == '/' and  wxData[0][:3].isdigit() and  wxData[0][3:5].isdigit():
		direction = wxData[0][:3]
		if wxData[0].find('G') != -1:
			gIndex = wxData[0].find('G')
			gust = wxData[0][gIndex+1:gIndex+3]
			speed = wxData[0][4:wxData[0].find('G')]
		else:
			speed = wxData[0][4:]
		wxData.pop(0)
	#Separated Gust
	if wxData and 1 < len(wxData[0]) < 4 and wxData[0][0] == 'G' and wxData[0][1:].isdigit():
		gust = wxData.pop(0)[1:]
	#Variable Wind Direction
	if wxData and len(wxData[0]) == 7 and wxData[0][:3].isdigit() and wxData[0][3] == 'V' and wxData[0][4:].isdigit():
		variable = wxData.pop(0).split('V')
	return wxData , direction , speed , gust , variable

#Visibility
def __getVisibilityUS(wxData):
	visibility = ''
	if wxData and (wxData[0].find('SM') != -1):   #10SM
		if wxData[0].find('/') == -1: visibility = str(int(wxData[0][:wxData[0].find('SM')]))  #str(int()) fixes 01SM
		else: visibility = wxData[0][:wxData[0].find('SM')] #1/2SM
		wxData.pop(0)
	elif wxData and wxData[0] == '9999':
		wxData.pop(0)
		visibility = '10'
	elif (len(wxData) > 1) and wxData[1].find('SM') != -1 and wxData[0].isdigit():   #2 1/2SM
		vis1 = wxData.pop(0)  #2
		vis2 = wxData[0][:wxData[0].find('SM')]  #1/2
		wxData.pop(0)
		visibility = str(int(vis1)*int(vis2[2])+int(vis2[0]))+vis2[1:]  #5/2
	return wxData , visibility

def __getVisibilityInternational(wxData):
	visibility = ''
	if wxData and len(wxData[0]) == 4 and wxData[0].isdigit(): visibility = wxData.pop(0)
	#elif wxData and len(wxData[0]) == 5 and wxdata[0][:4].isdigit() and not wxData[0][4].isdigit(): visibility = wxData.pop(0)[:4]
	return wxData , visibility

#Fix rare cloud layer issues
def sanitizeCloud(cloud):
	if len(cloud) < 4: return cloud
	if not cloud[3].isdigit() and cloud[3] != '/':
		if cloud[3] == 'O': cloud[3] == '0'  #Bad "O": FEWO03 -> FEW003
		else:  #Move modifiers to end: BKNC015 -> BKN015C
			cloud = cloud[:3] + cloud[4:] + cloud[3]
	return cloud

#Transforms a cloud string into a list of strings: [Type , Height (, Optional Modifier)]
#Returns cloud string list
def splitCloud(cloud, beginsWithVV):
	splitCloud = []
	cloud = sanitizeCloud(cloud)
	if beginsWithVV:
		splitCloud.append(cloud[:2])
		cloud = cloud[2:]
	while len(cloud) >= 3:
		splitCloud.append(cloud[:3])
		cloud = cloud[3:]
	if cloud: splitCloud.append(cloud)
	return splitCloud

#Clouds
def __getClouds(wxData):
	clouds = []
	for i in reversed(range(len(wxData))):
		if wxData[i][:3] in cloudList:
			clouds.append(splitCloud(wxData.pop(i) , False))
		elif wxData[i][:2] == 'VV':
			clouds.append(splitCloud(wxData.pop(i) , True))
	clouds.reverse()
	return wxData , clouds

#Returns a dictionary of parsed METAR data
#Keys: Station, Time, Wind-Direction, Wind-Speed, Wind-Gust, Wind-Variable-Dir, Visibility, Runway-Visibility, Altimeter, Temperature, Dewpoint, Cloud-List, Other-List, Remarks
def parseMETAR(txt):
	if len(txt) < 2: return
	if txt[0] in RegionsUsingUSParser: return parseUSVariant(txt)
	elif txt[0] in RegionsUsingInternationalParser: return parseInternationalVariant(txt)
	elif txt[:2] in MStationsUsingUSParser: return parseUSVariant(txt)
	elif txt[:2] in MStationsUsingInternationalParser: return parseInternationalVariant(txt)

def parseUSVariant(txt):
	retWX = {}
	wxData , retWX['Remarks'] = __getRemarks(txt)
	wxData , retWX['Runway-Visibility'] = __sanitize(wxData)
	wxData , retWX['Altimeter'] = __getAltimeterUS(wxData)
	wxData , retWX['Temperature'] , retWX['Dewpoint'] = __getTempAndDewpoint(wxData)
	wxData , retWX['Station'] , retWX['Time'] = __getStationAndTime(wxData)
	wxData , retWX['Wind-Direction'] , retWX['Wind-Speed'] , retWX['Wind-Gust'] , retWX['Wind-Variable-Dir'] = __getWindInfo(wxData)
	wxData , retWX['Visibility'] = __getVisibilityUS(wxData)
	retWX['Other-List'] , retWX['Cloud-List'] = __getClouds(wxData)
	return retWX

def parseInternationalVariant(txt):
	retWX = {}
	wxData , retWX['Remarks'] = __getRemarks(txt)
	wxData , retWX['Runway-Visibility'] = __sanitize(wxData)
	wxData , retWX['Altimeter'] = __getAltimeterInternational(wxData)
	wxData , retWX['Temperature'] , retWX['Dewpoint'] = __getTempAndDewpoint(wxData)
	wxData , retWX['Station'] , retWX['Time'] = __getStationAndTime(wxData)
	wxData , retWX['Wind-Direction'] , retWX['Wind-Speed'] , retWX['Wind-Gust'] , retWX['Wind-Variable-Dir'] = __getWindInfo(wxData)
	if wxData and wxData[0] == 'CAVOK':
		retWX['Visibility'] = '9999'
		retWX['Cloud-List'] = []
		wxData.pop(0)
	else:
		wxData , retWX['Visibility'] = __getVisibilityInternational(wxData)
		wxData , retWX['Cloud-List'] = __getClouds(wxData)
	retWX['Other-List'] = wxData #Other weather
	return retWX

#Returns int based on current flight rules from parsed METAR data
#0=VFR , 1=MVFR , 2=IFR , 3=LIFR
#Note: Common practice is to report IFR if visibility unavailable
def getFlightRules(vis , splitCloud):
	#Parse visibility
	if (vis == ''): return 2
	elif vis.find('/') != -1:
		if vis[0] == 'M': vis = 0
		else: vis = int(vis.split('/')[0]) / int(vis.split('/')[1])
	elif len(vis) == 4 and vis.isdigit(): vis = int(vis) * 0.000621371  #Convert meters to miles
	else: vis = int(vis)
	#Parse ceiling
	if splitCloud: cld = int(splitCloud[1])
	else: cld = 99
	#Determine flight rules
	if (vis < 5) or (cld < 30):
		if (vis < 3) or (cld < 10):
			if (vis < 1) or (cld < 5):
				return 3 #LIFR
			return 2 #IFR
		return 1 #MVFR
	return 0 #VFR

#Returns list of ceiling layer from Cloud-List or None if none found
#Only 'Broken', 'Overcast', and 'Vertical Visibility' are considdered ceilings
#Prevents errors due to lack of cloud information (eg. '' or 'FEW///')
def getCeiling(clouds):
	for cloud in clouds:
		if len(cloud) > 1 and cloud[1].isdigit() and cloud[0] in ['OVC','BKN','VV']:
			return cloud
	return None

#Translates METAR weather codes into readable strings
#Returns translated string of variable length
def translateWX(wx):
	wxString = ''
	if wx[0] == '+':
		wxString = 'Heavy '
		wx = wx[1:]
	elif wx[0] == '-':
		wxString = 'Light '
		wx = wx[1:]
	if len(wx) not in [2,4,6]: return wx  #Return wx if wx is not a code, ex R03/03002V03
	for i in range(len(wx)//2):
		if wx[:2] in wxReplacements: wxString += wxReplacements[wx[:2]] + ' '
		else: wxString += wx[:2]
		wx = wx[2:]
	return wxString

#Adds timestamp to begining of print statement
#Returns string of time + logString
def timestamp(logString): return time.strftime('%d %H:%M:%S - ') + logString

#This test main provides example usage for all included public functions
if __name__ == '__main__':
	ret = timestamp(getIdent(ident) + '\n\n')
	fr = ['VFR','MVFR','IFR','LIFR']
	#txt = getMETAR(getIdent(ident))
	txt = 'KTOB 252234Z AUTO 29019G29KT 10SM OVC 01/M03 A3002 RMK AO2'
	if type(txt) == int: 
		if txt: ret += 'Station does not exist/Database lookup error'
		else: ret += 'http connection error'
	else:
		data = parseMETAR(txt)
		for key in data: ret += '{0}  --  {1}\n'.format(key , data[key])
		ret += '\nFlight rules for "{0}" and "{1}"  --  "{2}"'.format(data['Visibility'] , getCeiling(data['Cloud-List']) , fr[getFlightRules(data['Visibility'] , getCeiling(data['Cloud-List']))])
		if len(data['Other-List']) > 0:
			ret += '\nTranslated WX'
			for wx in data['Other-List']: ret += '  --  ' + translateWX(wx)
	print(ret)
