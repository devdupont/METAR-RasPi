##--Michael duPont
##--METAR-RasPi : mlogic
##--Shared METAR settings and functions
##--2015-01-06

import urllib2 , string , time

##--User Vars
updateInterval = 600.0    #Seconds between server pings
timeoutInterval = 60.0    #Seconds between connection retries
ident = [10 , 9 , 5 , 10] #Default station ident, ex. [10,9,5,10] = KJFK
logMETAR = False          #Print METAR log. Use "file.py >> METARlog.txt"
shutdownOnExit = False    #Set true to shutdown the Pi when exiting the program

##--Logic Vars
cloudList = ['CLR','SKC','FEW','SCT','BKN','OVC']
charList = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','0','1','2','3','4','5','6','7','8','9']
wxReplacements = {
'RA':'Rain','TS':'Thunderstorm','SH':'Showers','DZ':'Drizzle','VC':'Vicinity','UP':'Unknown Precip',
'SN':'Snow','FZ':'Freezing','SG':'Snow Grains','IC':'Ice Crystals','PL':'Ice Pellets','GR':'Hail','GS':'Small Hail',
'FG':'Fog','BR':'Mist','HZ':'Haze','VA':'Volcanic Ash','DU':'Wide Dust','FU':'Smoke','SA':'Sand','SY':'Spray',
'SQ':'Squall','PO':'Dust Whirls','DS':'Duststorm','SS':'Sandstorm','FC':'Funnel Cloud'}

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
		response = urllib2.urlopen('http://www.aviationweather.gov/metar/data?ids='+station+'&format=raw&date=0&hours=0')
		html = response.read()
		if html.find(station+'<') != -1: return 1   #Station does not exist/Database lookup error
		reportStart = html.find('<code>'+station+' ')+6      #Report begins with station iden
		reportEnd = html[reportStart:].find('<')        #Report ends with html bracket
		return html[reportStart:reportStart+reportEnd].replace('\n ','')
	except:
		return 0

#Returns a dictionary of parsed METAR data
#Keys: Station, Time, Wind-Direction, Wind-Speed, Wind-Gust, Visibility, Altimeter, Temperature, Dewpoint, Cloud-List, Other-List, Remarks
def parseMETAR(txt):
	retWX = {}
	#Remove remarks and split
	if txt.find('RMK') != -1:
		retWX['Remarks'] = txt[txt.find('RMK')+4:]
		wxData = txt[:txt.find('RMK')-1].split(' ')
	else:
		retWX['Remarks'] = ''
		wxData = txt.split(' ')
	#Sanitize wxData
	if wxData[2] == 'AUTO': wxData.pop(2)          #Indicates report was automated
	if wxData[2] == 'COR': wxData.pop(2)
	if wxData[len(wxData)-1] == '$': wxData.pop()  #Indicates station needs maintenance
	#Altimeter
	if wxData and (wxData[len(wxData)-1][0] == 'A'):
		retWX['Altimeter'] = wxData[len(wxData)-1][1:]
		wxData.pop()
	else: retWX['Altimeter'] = 'NONE'
	#Temp/Dewpoint
	if wxData and (wxData[len(wxData)-1].find('/') != -1):
		TD = wxData[len(wxData)-1].split('/')
		retWX['Temperature'] = TD[0]
		retWX['Dewpoint'] = TD[1]
	else:
		retWX['Temperature'] = ''
		retWX['Dewpoint'] = ''
	wxData.pop()
	#Station and Time
	retWX['Station'] = wxData.pop(0)
	retWX['Time'] = wxData.pop(0)
	#Surface wind
	#Occasionally KT is not included. Check len=5 and is not altimeter. Check len>=8 and contains G (gust)
	if wxData and ((wxData[0][len(wxData[0])-2:] == 'KT') or (len(wxData[0]) == 5 and wxData[0][0] != 'A') or (len(wxData[0]) >= 8 and wxData.find('G') != -1)):
		retWX['Wind-Direction'] = wxData[0][:3]
		if wxData[0].find('G') != -1:
			retWX['Wind-Gust'] = wxData[0][wxData[0].find('G')+1:wxData[0].find('KT')]
			retWX['Wind-Speed'] = wxData[0][3:wxData[0].find('G')]
		else:
			retWX['Wind-Gust'] = ''
			retWX['Wind-Speed'] = wxData[0][3:wxData[0].find('KT')]
		wxData.pop(0)
	else:
		retWX['Wind-Direction'] = ''
		retWX['Wind-Speed'] = ''
		retWX['Wind-Gust'] = ''
	#Visibility
	if wxData and (wxData[0].find('SM') != -1):   #10SM
		retWX['Visibility'] = wxData[0][:wxData[0].find('SM')]
		wxData.pop(0)
	elif (len(wxData) > 1) and wxData[1].find('SM') != -1:   #2 1/2SM
		vis1 = wxData.pop(0)  #2
		vis2 = wxData[0][:wxData[0].find('SM')]  #1/2
		wxData.pop(0)
		retWX['Visibility'] = str(int(vis1)*int(vis2[2])+int(vis2[0]))+vis2[1:]  #5/2
	else:
		retWX['Visibility'] = ''
	#Clouds
	clouds = []
	for i in reversed(range(len(wxData))):
		if (wxData[i][:3] in cloudList) or (wxData[i][:2] == 'VV'):
			clouds.append(wxData.pop(i))
	clouds.reverse()
	retWX['Cloud-List'] = clouds
	#Other weather
	retWX['Other-List'] = wxData
	return retWX

#Returns int based on current flight rules from parsed METAR data
#0=VFR , 1=MVFR , 2=IFR , 3=LIFR
#Note: Common practice is to report IFR if visibility unavailable
def getFlightRules(vis , cld):
	#Parse visibility
	if (vis == ''): return 2
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

#Returns string of ceiling layer from Cloud-List or '' if none found
#Only 'Broken', 'Overcast', and 'Vertical Visibility' are considdered ceilings
#Prevents errors due to lack of cloud information (eg. '' or 'FEW///')
def getCeiling(clouds):
	for cloud in clouds:
		if (cloud[len(cloud)-1] != '/') and ((cloud[:3] == 'BKN') or (cloud[:3] == 'OVC') or (cloud[:2] == 'VV')):
			return cloud
	return ''

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


#This test main provides example usage for all included functions
if __name__ == '__main__':
	ret = timestamp(getIdent(ident) + '\n\n')
	fr = ['VFR','MVFR','IFR','LIFR']
	txt = getMETAR(getIdent(ident))
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
