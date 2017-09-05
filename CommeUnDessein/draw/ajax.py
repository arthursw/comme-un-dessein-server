from threading import Timer
import datetime
import logging
import os
import shutil
import os.path
import errno
import json

# from django.utils import json
# from dajaxice.decorators import dajaxice_register
from django.core import serializers
# from dajaxice.core import dajaxice_functions
from django.contrib.auth.models import User
from django.db.models import F
from models import *
import ast
from pprint import pprint
from django.contrib.auth import authenticate, login, logout
from paypal.standard.ipn.signals import payment_was_successful, payment_was_flagged, payment_was_refunded, payment_was_reversed
from math import *
import random
import re
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
import django.dispatch

from mongoengine import ValidationError
from mongoengine.queryset import Q
import time

# from PIL import Image
import cStringIO
import StringIO
import traceback
import requests
from CommeUnDessein import settings
from allauth.socialaccount.models import SocialToken
# import collaboration

import base64


# from github3 import authorize

# from wand.image import Image

import functools

debugMode = False
positiveVoteThreshold = 50
negativeVoteThreshold = 5
voteValidationDelay = datetime.timedelta(minutes=1) 		# once the drawing gets positiveVoteThreshold votes, the duration before the drawing gets validated (the drawing is not immediately validated in case the user wants to cancel its vote)
voteMinDuration = datetime.timedelta(hours=6)				# the minimum duration the vote will last (to make sure a good moderation happens)

drawingModes = ['free', 'ortho', 'orthoDiag', 'pixel', 'image']

def userAllowed(request, owner):
	return request.user.username == owner or isAdmin(request.user)

if settings.DEBUG:
	import pdb

	def checkDebug(func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			if debugMode:
				import pdb; pdb.Pdb(skip=['django.*', 'gevent.*']).set_trace()
			return func(*args, **kwargs)
		return wrapper
else:
	def checkDebug(func):
	    return func

def isAdmin(user):
	try:
		profile = UserProfile.objects.get(username=user.username)
		return profile.admin
	except UserProfile.DoesNotExist:
		return False
	return False

logger = logging.getLogger(__name__)

try:
	commeUnDesseinCity = City.objects.get(name='CommeUnDessein', owner='CommeUnDesseinOrg', public=True)
except City.DoesNotExist:
	commeUnDesseinCity = City(name='CommeUnDessein', owner='CommeUnDesseinOrg', public=True)
	commeUnDesseinCity.save()


logger = logging.getLogger(__name__)

with open('/data/secret_github.txt') as f:
	PASSWORD = base64.b64decode(f.read().strip())

with open('/data/secret_tipibot.txt') as f:
	TIPIBOT_PASSWORD = f.read().strip()

with open('/data/client_secret_github.txt') as f:
	CLIENT_SECRET = f.read().strip()

with open('/data/accesstoken_github.txt') as f:
	ACCESS_TOKEN = f.read().strip()

with open('/data/openaccesstoken_github.txt') as f:
	OPEN_ACCESS_TOKEN = f.read().strip()

# pprint(vars(object))
# import pdb; pdb.set_trace()
# import pudb; pu.db

import datetime

def unix_time(dt):
	epoch = datetime.datetime.utcfromtimestamp(0)
	delta = dt - epoch
	return delta.total_seconds()

def unix_time_millis(dt):
	return unix_time(dt) * 1000.0

def makeBox(tlX, tlY, brX, brY):
	return { "type": "Polygon", "coordinates": [ [ [tlX, tlY], [brX, tlY], [brX, brY], [tlX, brY], [tlX, tlY] ] ] }

userID = 0
isUpdatingRasters = False
# dummyArea = None
# defaultPathTools = ["Checkpoint", "EllipseShape", "FaceShape", "GeometricLines", "GridPath", "Meander", "PrecisePath", "RectangleShape", "ShapePath", "SpiralShape", "StarShape", "ThicknessPath"]
defaultPathTools = ["Precise path", "Thickness path", "Meander", "Grid path", "Geometric lines", "Shape path", "Rectangle", "Ellipse", "Star", "Spiral", "Face generator", "Checkpoint"]

# @dajaxice_register
def setDebugMode(request, debug):
	if not isAdmin(request.user):
		return json.dumps({"status": "error", "message": "not_admin"})
	global debugMode
	debugMode = debug
	return json.dumps({"message": "success"})

def setDrawingMode(request, mode):
	if not isAdmin(request.user):
		return json.dumps({"status": "error", "message": "not_admin"})
	global drawingMode
	drawingMode = mode
	return json.dumps({"message": "success"})

def getPositiveVoteThreshold():
	return positiveVoteThreshold

def getNegativeVoteThreshold():
	return negativeVoteThreshold

def getVoteMinDuration():
	return voteMinDuration

def setPositiveVoteThreshold(request, voteThreshold):
	if not isAdmin(request.user):
		return json.dumps({"status": "error", "message": "not_admin"})
	global positiveVoteThreshold
	positiveVoteThreshold = voteThreshold
	return json.dumps({"message": "success"})

def setNegativeVoteThreshold(request, voteThreshold):
	if not isAdmin(request.user):
		return json.dumps({"status": "error", "message": "not_admin"})
	global negativeVoteThreshold
	negativeVoteThreshold = voteThreshold
	return json.dumps({"message": "success"})

def setVoteValidationDelay(request, hours, minutes, seconds):
	if not isAdmin(request.user):
		return json.dumps({"status": "error", "message": "not_admin"})
	global voteValidationDelay
	voteValidationDelay = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
	return json.dumps({"message": "success"})

def setVoteMinDuration(request, hours, minutes, seconds):
	if not isAdmin(request.user):
		return json.dumps({"status": "error", "message": "not_admin"})
	global voteMinDuration
	voteMinDuration = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
	return json.dumps({"message": "success"})

# @dajaxice_register
@checkDebug
def multipleCalls(request, functionsAndArguments):
	results = []
	for fa in functionsAndArguments:
		results.append(json.loads(globals()[fa['function']](request=request, **fa['arguments'])))
	return json.dumps(results)


## debug
@checkDebug
def debugDatabase(request):
	models = ['Path', 'Div', 'Box', 'Drawing']

	# for model in models:
	# 	objects = globals()[model].objects()
	# 	for obj in objects:
	# 		obj.clientId = obj.clientID
	# 		obj.save()
	return


@checkDebug
def deleteItems(request, itemsToDelete, confirm):
	if not isAdmin(request.user):
		return json.dumps( {'state': 'error', 'message': 'not admin' } )

	if confirm != 'confirm':
		return json.dumps( {'state': 'error', 'message': 'please confirm' } )
	
	for itemToDelete in itemsToDelete:
		itemType = itemToDelete['itemType']
		pks = itemToDelete['pks']
		
		if itemType not in ['Path', 'Div', 'Box', 'AreaToUpdate', 'Drawing']:
			return json.dumps({'state': 'error', 'message': 'Can only delete Paths, Divs, Boxs, AreaToUpdates or Drawings.'})

		itemsQuerySet = globals()[itemType].objects(pk__in=pks)
	
		itemsQuerySet.delete()

	return json.dumps( {'state': 'success', 'message': 'items successfully deleted' } )

@checkDebug
def deleteAllItems(request, confirm):
	if not isAdmin(request.user):
		return json.dumps( {'state': 'error', 'message': 'not admin' } )

	if confirm != 'confirm':
		return json.dumps( {'state': 'error', 'message': 'please confirm' } )

	for itemType in ['Path', 'Div', 'Box', 'AreaToUpdate', 'Drawing']:
		
		itemsQuerySet = globals()[itemType].objects()
	
		itemsQuerySet.delete()

	return json.dumps( {'state': 'success', 'message': 'items successfully deleted' } )

# @dajaxice_register
@checkDebug
def githubRequest(request, githubRequest, method='get', data=None, params=None, headers=None):
	token = ACCESS_TOKEN

	try:
		socialAccount = SocialAccount.objects.get(user_id=request.user.id, provider='github')
		userToken = SocialToken.objects.get(account_id=socialAccount.id, account__provider='github')
		if userToken:
			token = userToken
	except:
		pass
	if data:
		data = json.dumps(data)
	if not headers:
		headers = {}
	headers['Authorization'] = 'token ' + str(token)
	r = getattr(requests, method)(githubRequest, data=data, params=params, headers=headers)
	response = { 'content': r.json(), 'status': r.status_code }
	if 'link' in r.headers:
		response['headers'] = { 'link': r.headers['link'] }
	return json.dumps(response)

# r = requests.post(githubRequest, headers={'Authorization': 'token ' + ACCESS_TOKEN})

# @dajaxice_register
@checkDebug
def getGithubAuthToken(request):
	client_id = None
	try:
		socialAccount = SocialAccount.objects.get(user_id=request.user.id, provider='github')
		token = SocialToken.objects.get(account__user=socialAccount.id, account__provider='github')
		r = requests.put('https://api.github.com/authorizations/clients/'+str(client_id), params={'client_secret': CLIENT_SECRET})
	except:
		return json.dumps({"state": "error", "message": "success"})
	return


# @dajaxice_register
@checkDebug
def benchmarkLoad(request, areasToLoad):

	start = time.time()

	items = {}

	for b in areasToLoad:
		try:
			area = Area.objects.get(x=b['x'], y=b['y'])
		except:
			continue

		for item in area.items:
			if hasattr(item, 'pk') and not item.pk in items:
				items[item.pk] = item.to_json()

	end = time.time()
	print "Time elapsed area load: " + str(end - start)
	print 'retrieved' + str(len(items)) + 'items'

	start = time.time()

	items = {}
	n = 0
	for area in areasToLoad:

		tlX = area['pos']['x']
		tlY = area['pos']['y']

		planetX = area['planet']['x']
		planetY = area['planet']['y']

		geometry = makeBox(tlX, tlY, tlX+1, tlY+1)

		# load items
		paths = Path.objects(planetX=planetX, planetY=planetY, points__geo_intersects=geometry)

		for item in paths:
			if hasattr(item, 'pk') and not item.pk in items:
				items[item.pk] = item.to_json()
			n = n + 1


	end = time.time()
	print "Time elapsed geo json load path only: " + str(end - start)
	print 'retrieved ' + str(len(items)) + ' items out of ' + str(n)

	return json.dumps({"message": "success"})

# # @dajaxice_register
# @checkDebug
# def quick_load(request, box, boxes, zoom):

# 	items = {}

# 	left = box['left']
# 	top = box['top']
# 	right = box['right']
# 	bottom = box['bottom']

# 	if zoom > 0.04:
# 		for b in boxes:
# 			try:
# 				area = Area.objects.get(x=b['x'], y=b['y'])
# 			except:
# 				continue

# 			for item in area.items:
# 				if hasattr(item, 'pk') and not items.has_key(item.pk):
# 					items[item.pk] = item.to_json()
# 	else:
# 		areas = Area.objects(x__gte=left, x__lte=right, y__gte=top, y__lte=bottom)


# 		for area in areas:
# 			for item in area.items:
# 				if hasattr(item, 'pk') and not items.has_key(item.pk):
# 					items[item.pk] = item.to_json()

# 	# load rasters
# 	rasters = []

# 	step = 1

# 	if zoom > 0.2:
# 		step = 1
# 	elif zoom > 0.04:
# 		step = 5
# 	else:
# 		step = 25

# 	for x1 in range(left,right+step,step):
# 		for y1 in range(top,bottom+step,step):

# 			x5 = floorToMultiple(x1, 5)
# 			y5 = floorToMultiple(y1, 5)

# 			x25 = floorToMultiple(x1, 25)
# 			y25 = floorToMultiple(y1, 25)

# 			if zoom > 0.2:
# 				position = { 'x': x1, 'y': y1 }
# 				rasterPath = 'media/rasters/zoom100/' + str(x25) + ',' + str(y25) + '/' + str(x5) + ',' + str(y5) + '/'
# 			elif zoom > 0.04:
# 				position = { 'x': x5, 'y': y5 }
# 				rasterPath = 'media/rasters/zoom20/' + str(x25) + ',' + str(y25) + '/'
# 			else:
# 				position = { 'x': x25, 'y': y25 }
# 				rasterPath = 'media/rasters/zoom4/'

# 			rasterName = rasterPath + str(position['x']) + "," + str(position['y']) + ".png"

# 			if os.path.isfile(os.getcwd() + '/' + rasterName):
# 				rasters.append( { 'url': rasterName, 'position': position } )

# 	global userID
# 	user = request.user.username
# 	if not user:
# 		user = userID
# 	userID += 1

# 	# global dummyArea
# 	# if not dummyArea:
# 	# 	try:
# 	# 		dummyArea = Area.objects.get(x=-180000.5, y=-900000.5)
# 	# 	except Area.DoesNotExist:
# 	# 		dummyArea = Area(x=-180000.5, y=-900000.5)
# 	# 	dummyArea.save()

# 	return json.dumps( { 'items': items.values(), 'rasters': rasters, 'zoom': zoom, 'user': user } )

# @dajaxice_register
@checkDebug
def createCity(request, name, public=None):
	try:
		city = City.objects.get(name=name, owner=request.user.username)
		return json.dumps( { 'state': 'error', 'message': 'The city named ' + name + ' already exists.' } )
	except Exception:
		pass

	city = City(name=name, owner=request.user.username, public=public)
	city.save()

	return json.dumps( { 'state': 'succes', 'city': city.to_json() } )

# @dajaxice_register
@checkDebug
def deleteCity(request, name):
	try:
		city = City.objects.get(name=name, owner=request.user.username)
	except City.DoesNotExist:
		return json.dumps( { 'state': 'error', 'message': 'The city ' + name + ' for user ' + request.user.username + ' does not exist.' } )

	city.delete()

	models = ['Path', 'Div', 'Box', 'AreaToUpdate']

	for model in models:
		globals()[model].objects(city=city.pk).delete()

	try:
		shutil.rmtree('media/rasters/' + str(city.pk))
	except Exception:
		pass

	return json.dumps( { 'state': 'succes', 'cityPk': str(city.pk) } )

# @dajaxice_register
@checkDebug
def updateCity(request, pk, name, public=None):
	try:
		city = City.objects.get(name=name, owner=request.user.username)
		return json.dumps( { 'state': 'error', 'message': 'The city named ' + name + ' already exists.' } )
	except Exception:
		pass

	try:
		city = City.objects.get(pk=pk, owner=request.user.username)
		city.name = name
		if public:
			city.public = public
		city.save()
	except City.DoesNotExist:
		return json.dumps( { 'state': 'error', 'message': 'The city with id ' + pk + ' for user ' + request.user.username + ' does not exist.' } )

	return json.dumps( { 'state': 'succes', 'city': city.to_json() } )

# @dajaxice_register
@checkDebug
def loadCities(request):
	userCities = City.objects(owner=request.user.username)
	publicCities = City.objects(public=True)
	return json.dumps( { 'userCities': userCities.to_json(), 'publicCities': publicCities.to_json() } )

# @dajaxice_register
@checkDebug
def loadUserCities(request):
	userCities = City.objects(owner=request.user.username)
	return json.dumps( { 'userCities': userCities.to_json() } )

# @dajaxice_register
@checkDebug
def loadPublicCities(request):
	publicCities = City.objects(public=True)
	return json.dumps( { 'publicCities': publicCities.to_json() } )

# @dajaxice_register
@checkDebug
def loadCity(request, pk):
	try:
		city = City.objects.get(pk=pk, owner=request.user.username)
	except City.DoesNotExist:
		return json.dumps( { 'state': 'error', 'message': 'The city with id ' + pk + ' for user ' + request.user.username + ' does not exist.' } )
	return json.dumps( { 'state': 'succes', 'city': city.to_json() } )

def getCity(request, cityObject=None):
	if not cityObject or not ('name' in cityObject) or (cityObject['name'] == ''):
		city = commeUnDesseinCity
	else:
		try:
			city = City.objects.get(name=cityObject['name'])
			if not city.public:
				return None
		except City.DoesNotExist:
			return None
	return str(city.pk)

def checkAddItem(item, items, itemsDates=None, ignoreDrafts=False):
	if not item.pk in items:
		if ignoreDrafts:
			itemIsDraft = type(item) is Path and item.drawing is None
			if not itemIsDraft:
				items[item.pk] = item.to_json()
		else:
			items[item.pk] = item.to_json()
	return

def checkAddItemRasterizer(item, items, itemsDates, ignoreDrafts=False):
	pk = item.pk
	itemLastUpdate = unix_time_millis(item.lastUpdate)
	if not pk in items and (not pk in itemsDates or itemsDates[pk]<itemLastUpdate):
		items[pk] = item.to_json()
		if pk in itemsDates:
			del itemsDates[pk]
	return

def getItems(models, areasToLoad, qZoom, city, checkAddItemFunction, itemDates=None, owner=None, loadDrafts=True):
	items = {}
	for area in areasToLoad:

		tlX = area['pos']['x']
		tlY = area['pos']['y']

		planetX = area['planet']['x']
		planetY = area['planet']['y']

		geometry = makeBox(tlX, tlY, tlX+qZoom, tlY+qZoom)

		for model in models:

			itemsQuerySet = globals()[model].objects(city=city, planetX=planetX, planetY=planetY, box__geo_intersects=geometry)

			for item in itemsQuerySet:
				checkAddItemFunction(item, items, itemDates, loadDrafts)

	if loadDrafts:
		# add drafts
		if owner is not None:
			drafts = Path.objects(city=city, drawing=None, owner=owner)
			for draft in drafts:
				if not draft.pk in items:
					items[draft.pk] = draft.to_json()

	return items

def getAllItems(models, city, checkAddItemFunction, itemDates=None, owner=None, loadDrafts=True):
	items = {}

	for model in models:

		itemsQuerySet = globals()[model].objects(city=city)

		for item in itemsQuerySet:
			checkAddItemFunction(item, items, itemDates, loadDrafts)

	if loadDrafts:
		# add drafts
		if owner is not None:
			drafts = Path.objects(city=city, drawing=None, owner=owner)
			for draft in drafts:
				if not draft.pk in items:
					items[draft.pk] = draft.to_json()

	return items

# @dajaxice_register
@checkDebug
def load(request, rectangle, areasToLoad, qZoom, city=None):

	start = time.time()

	cityPk = getCity(request, city)
	if not cityPk:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.', 'code': 'CITY_DOES_NOT_EXIST' } )

	models = ['Path', 'Div', 'Box', 'AreaToUpdate', 'Drawing']
	items = getItems(models, areasToLoad, qZoom, cityPk, checkAddItem, None, request.user.username)

	# load rasters
	rasters = []

	step = qZoom

	left = int(rectangle['left'])
	top = int(rectangle['top'])
	right = int(rectangle['right'])
	bottom = int(rectangle['bottom'])

	for x1 in range(left,right+step,step):
		for y1 in range(top,bottom+step,step):

			x5 = floorToMultiple(x1, 5)
			y5 = floorToMultiple(y1, 5)

			x25 = floorToMultiple(x1, 25)
			y25 = floorToMultiple(y1, 25)

			if qZoom < 5:
				position = { 'x': x1, 'y': y1 }
				rasterPath = 'media/rasters/' + cityPk + '/zoom100/' + str(x25) + ',' + str(y25) + '/' + str(x5) + ',' + str(y5) + '/'
			elif qZoom < 25:
				position = { 'x': x5, 'y': y5 }
				rasterPath = 'media/rasters/' + cityPk + '/zoom20/' + str(x25) + ',' + str(y25) + '/'
			else:
				position = { 'x': x25, 'y': y25 }
				rasterPath = 'media/rasters/' + cityPk + '/zoom4/'

			rasterName = rasterPath + str(position['x']) + "," + str(position['y']) + ".png"

			filePath = os.getcwd() + '/' + rasterName
			if os.path.isfile(filePath):
				# rasters.append( { 'url': rasterName, 'position': position, 'lastUpdate': time.ctime(os.path.getmtime(filePath)) } )
				rasters.append( { 'url': rasterName, 'position': position } )

	end = time.time()
	print "Time elapsed: " + str(end - start)

	global userID
	user = request.user.username
	if not user:
		user = userID
	userID += 1

	# return json.dumps( { 'paths': paths, 'boxes': boxes, 'divs': divs, 'user': user, 'rasters': rasters, 'areasToUpdate': areas, 'zoom': zoom } )
	return json.dumps( { 'items': items.values(), 'user': user, 'rasters': rasters, 'qZoom': qZoom } )

@checkDebug
def loadAll(request, city=None):

	cityPk = getCity(request, city)
	if not cityPk:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.', 'code': 'CITY_DOES_NOT_EXIST' } )

	models = ['Path', 'AreaToUpdate', 'Drawing']
	items = getAllItems(models, cityPk, checkAddItem, None, request.user.username)

	global userID
	user = request.user.username
	if not user:
		user = userID
	userID += 1

	# return json.dumps( { 'paths': paths, 'boxes': boxes, 'divs': divs, 'user': user, 'rasters': rasters, 'areasToUpdate': areas, 'zoom': zoom } )
	return json.dumps( { 'items': items.values(), 'user': user } )


# @dajaxice_register
@checkDebug
def loadRasterizer(request, areasToLoad, itemsDates, city):

	start = time.time()

	city = getCity(request, city)
	if not city:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.' } )

	models = ['Path', 'Box']
	items = getItems(models, areasToLoad, 1, city, checkAddItemRasterizer, itemsDates)

	# add items to update which are not on the loading area (to update items which have been moved out of the area to load)
	for model in models:
		itemsQuerySet = globals()[model].objects(pk__in=itemsDates.keys())
		for item in itemsQuerySet:
			pk = str(item.pk)
			itemLastUpdate = unix_time_millis(item.lastUpdate)
			if not pk in items and itemsDates[pk]<itemLastUpdate:
				items[pk] = item.to_json()
			del itemsDates[pk]


	end = time.time()
	print "Time elapsed: " + str(end - start)

	return json.dumps( { 'items': items.values(), 'deletedItems': itemsDates } )

# @return [Array<{x: x, y: y}>] the list of areas on which the bounds lie
def getAreas(bounds):
	areas = {}
	scale = 1000
	l = int(floor(bounds['x'] / scale))
	t = int(floor(bounds['y'] / scale))
	r = int(floor((bounds['x']+bounds['width']) / scale))
	b = int(floor((bounds['y']+bounds['height']) / scale))

	areas = {}
	for x in range(l, r+1):
		for y in range(t, b+1):
			if not x in areas:
				areas[x] = {}
			areas[x][y] = True
	return areas

# # add areas with item
# def addAreas(bounds, item):
# 	print "<<<"
# 	print "add areas of item: " + str(item.pk)

# 	areas = getAreas(bounds)

# 	areasToAdd = []
# 	for x, column in areas.iteritems():
# 		for y in column:
# 			area = Area.objects(x=x, y=y).modify(upsert=True, new=True, push__items=item)
# 			print 'area: ' + str(x) + ', ' + str(y) + ': ' + str(area.pk)
# 			# Area.objects(x=a['x'], y=a['y']).update_one(push__paths=p, upsert=True) # good but how to get id?
# 			# try:
# 			# 	area = Area.objects.get(x=x, y=y)
# 			# except Area.DoesNotExist:
# 			# 	area = Area(x=x, y=y)
# 			# area.items.append(item)
# 			# area.save()
# 			areasToAdd.append(area)
# 			# item.areas.append(area)

# 	# item.save()
# 	document = type(item)
# 	print "update areas to item.areas"
# 	document.objects(pk=item.pk).update_one(push_all__areas=areasToAdd)
# 	print "end addAreas"
# 	print ">>>"

# 	# check that DB is ok
# 	try:
# 		i = document.objects.get(pk=item.pk)
# 	except document.DoesNotExist:
# 		print 'item was deleted before add check.'
# 		return

# 	for a in areasToAdd:
# 		try:
# 			aa = Area.objects.get(pk=a.pk)
# 		except Area.DoesNotExist:
# 			print 'Area.DoesNotExist'
# 			import pdb; pdb.set_trace()
# 		if aa not in i.areas:
# 			print 'aa not in items.areas'
# 			import pdb; pdb.set_trace()

# 	for x, column in areas.iteritems():
# 		for y in column:
# 			try:
# 				aa = Area.objects.get(x=x, y=y)
# 			except Area.DoesNotExist:
# 				print 'Area.DoesNotExist'
# 				import pdb; pdb.set_trace()
# 			if i not in aa.items:
# 				print 'Area not updated!'
# 				import pdb; pdb.set_trace()
# 			if aa not in i.areas:
# 				print 'aa not in items.areas'
# 				import pdb; pdb.set_trace()
# 	return

# # update areas with item
# # areas: the list of areas which now intersect with item
# def updateAreas(bounds, item):
# 	print "<<<"
# 	print "update areas of item: " + str(item.pk)
# 	areas = getAreas(bounds)

# 	document = type(item)

# 	areasToRemove = []
# 	areasToRemovePks = []

# 	# remove areas which do not intersect with item anymore
# 	for area in item.areas:
# 		if areas.has_key(area.x) and areas[area.x].has_key(area.y): 	# if the area still intersects: do not remove it
# 			del areas[area.x][area.y]
# 		else: 															# otherwise: remove it
# 			areasToRemove.append(area)
# 			if not hasattr(area, 'pk'):
# 				print 'WARNING: area in item.areas was deleted'
# 				continue
# 			areasToRemovePks.append(area.pk)
# 			# print 'remove item: ' + str(area.x) + ', ' + str(area.y) + ': ' + str(area.pk) + ' from area.items...'
# 			# try:
# 			# 	area.items.remove(item)
# 			# except ValueError:
# 			# 	print 'WARNING: item is not in area.items'
# 			# 	continue
# 			# print 'removed'
# 			# if len(area.items)==0:
# 			# 	print 'delete area: ' + str(area.pk)
# 			# 	area.delete()
# 			# 	print 'deleted'
# 			# else:
# 			# 	print 'save area: ' + str(area.pk)
# 			# 	area.save()
# 			# 	print 'saved'
# 			# Area.objects(pk=area.pk).update_one(pull__items=item)

# 	Area.objects(pk__in=areasToRemovePks).update(pull__items=item)
# 	Area.objects(pk__in=areasToRemovePks, items__size=0).delete()

# 	print "remove old areas from item.areas..."
# 	document.objects(pk=item.pk).update_one(pull_all__areas=areasToRemove)
# 	print "...removed old areas from item.areas"

# 	areasToAdd = []
# 	# for all areas which now intersect with item: create or update them, and
# 	for x, column in areas.iteritems():
# 		for y in column:
# 			area = Area.objects(x=x, y=y).modify(upsert=True, new=True, push__items=item)
# 			print 'add item: ' + str(item.pk) + ' to area.items: ' + str(area.x) + ', ' + str(area.y) + ': ' + str(area.pk)
# 			areasToAdd.append(area)
# 			# try:
# 			# 	area = Area.objects.get(x=x, y=y)
# 			# except Area.DoesNotExist:
# 			# 	area = Area(x=x, y=y)
# 			# area.items.append(item)
# 			# area.save()
# 			# item.areas.append(area)

# 	print 'add areas in item.areas...'
# 	document.objects(pk=item.pk).update_one(push_all__areas=areasToAdd)
# 	print '...areas added'

# 	print "end updateAreas"
# 	print ">>>"

# 	# check that DB is ok
# 	# item.save()

# 	try:
# 		i = document.objects.get(pk=item.pk)
# 	except document.DoesNotExist:
# 		print 'item was deleted before update check.'
# 		return

# 	for x, column in areas.iteritems():
# 		for y in column:
# 			try:
# 				a = Area.objects.get(x=x, y=y)
# 			except Area.DoesNotExist:
# 				print 'Area.DoesNotExist'
# 				import pdb; pdb.set_trace()
# 			if a not in i.areas:
# 				print 'area not in items.areas'
# 				import pdb; pdb.set_trace()
# 			if i not in a.items:
# 				print 'item not in area.items'
# 				import pdb; pdb.set_trace()

# 	for a in areasToRemove:
# 		try:
# 			aa = Area.objects.get(pk=a.pk)
# 		except Area.DoesNotExist:
# 			if a in i.areas:
# 				print 'area not deleted from item.areas'
# 				import pdb; pdb.set_trace()
# 			continue
# 		if i in aa.items:
# 			print 'item not deleted from area.items'
# 			import pdb; pdb.set_trace()
# 		if len(aa.items)==0:
# 			print 'area not deleted'
# 			import pdb; pdb.set_trace()
# 	return

# # update areas with item
# def deleteAreas(item):

# 	print "<<<"
# 	print "delete areas of item: " + str(item.pk)

# 	areaPks = []
# 	for a in item.areas:
# 		if hasattr(a, 'pk'):
# 			areaPks.append(a.pk)

# 	print 'remove areas: ' + str(areaPks)
# 	Area.objects(pk__in=areaPks).update(pull__items=item)

# 	print 'delete empty areas...'
# 	Area.objects(pk__in=areaPks, items__size=0).delete()

# 	# for area in item.areas:
# 	# 	# a = Area.objects.get(pk=area.pk) # should not be necessary
# 	# 	# risk of having error with area.items
# 	# 	if not hasattr(area, 'items'):
# 	# 		print 'WARNING: area in item.areas was deleted'
# 	# 		continue
# 	# 	try:
# 	# 		print 'remove item: ' + str(item.pk) + ' from area: ' + str(area.pk) + ' ...'
# 	# 		area.items.remove(item)
# 	# 	except ValueError:
# 	# 		print 'WARNING: item is not in area.items'
# 	# 		continue
# 	# 	if len(area.items)==0:
# 	# 		print 'delete area ' + str(area.pk) + '...'
# 	# 		area.delete()
# 	# 		print '...area deleted'
# 	# 	else:
# 	# 		print 'save area ' + str(area.pk) + '...'
# 	# 		area.save()
# 	# 		print '...area saved'

# 	print "end deleteAreas"
# 	print ">>>"

# 	# check that DB is ok
# 	document = type(item)

# 	try:
# 		i = document.objects.get(pk=item.pk)
# 	except document.DoesNotExist:
# 		print 'item was deleted before delete check.'
# 		return
# 	for a in i.areas:
# 		try:
# 			if not hasattr(a, 'pk'):
# 				continue
# 			aa = Area.objects.get(pk=a.pk)
# 		except Area.DoesNotExist:
# 			continue
# 		if i in aa.items:
# 			print 'item not deleted from area.items'
# 			import pdb; pdb.set_trace()

# 	return

def boxContainsPoint(boxX, boxY, boxWidth, boxHeight, pointX, pointY):
	return pointX > boxX and pointX < boxX + boxWidth and pointY > boxY and pointY < boxY + boxHeight

def boxContainsPoints(boxX, boxY, boxWidth, boxHeight, points):
	for point in points:
		if not boxContainsPoint(boxX, boxY, boxWidth, boxHeight, point[0], point[1]):
			return False
	return True

# @dajaxice_register
@checkDebug
def savePath(request, clientId, points, object_type, box, date, data=None, city=None):
# def savePath(request, points, pID, planet, object_type, data=None, rasterData=None, rasterPosition=None, areasNotRasterized=None):

	if not request.user.is_authenticated():
		return json.dumps( { 'state': 'not_logged_in', 'message': 'The user does not exist.' } )

	city = getCity(request, city)
	if not city:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.' } )

	if not boxContainsPoints(-2, -1.5, 4, 3, points):
		return json.dumps( { 'state': 'error', 'message': 'The path is not in the drawing area.' } )

	boxPoints = box['points']
	planetX = box['planet']['x']
	planetY = box['planet']['y']

	lockedAreas = Box.objects(city=city, planetX=planetX, planetY=planetY, box__geo_intersects={"type": "LineString", "coordinates": points }) # , owner__ne=request.user.username )
	lock = None
	for area in lockedAreas:
		if area.owner == request.user.username:
			lock = str(area.pk)
		else:
			return json.dumps( {'state': 'error', 'message': 'Your path intersects with a locked area which you do not own'} )

	try:
		tool = Tool.objects.get(name=object_type, accepted=True)
	except Tool.DoesNotExist:
		global defaultPathTools
		if not object_type in defaultPathTools:
			return json.dumps( { 'state': 'error', 'message': 'The path "' + object_type + '" does not exist.' } )

	boxGeometry = makeBox(boxPoints[0][0], boxPoints[0][1], boxPoints[2][0], boxPoints[2][1])
	
	p = Path(clientId=clientId, city=city, planetX=planetX, planetY=planetY, box=boxGeometry, points=points, owner=request.user.username, object_type=object_type, data=data, date=datetime.datetime.fromtimestamp(date/1000.0), lock=lock )
	p.save()

	addAreaToUpdate( boxPoints, planetX, planetY, city )

	# addAreas(bounds, p)

	# rasterResult = updateRastersJson(rasterData, rasterPosition, areasNotRasterized)

	# return json.dumps( {'state': rasterResult['state'], 'pID': pID, 'pk': str(p.pk), 'message': rasterResult['message'] if 'message' in rasterResult else '' } )
	return json.dumps( {'state': 'success', 'pk': str(p.pk), 'owner': request.user.username } )

# @dajaxice_register
@checkDebug
def updatePath(request, pk, points=None, box=None, data=None, date=None):

	try:
		p = Path.objects.get(pk=pk)
	except Path.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Update impossible: element does not exist for this user'})

	if not userAllowed(request, p.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of path'})

	if p.drawing:
		return json.dumps({'state': 'error', 'message': 'Path is in drawing'})

	if box and not points or points and not box:
		return json.dumps( { 'state': 'error', 'message': 'Modifying points without box or box without points' } )

	if points and box:

		boxPoints = box['points']
		planetX = box['planet']['x']
		planetY = box['planet']['y']

		lockedAreas = Box.objects(city=p.city, planetX=planetX, planetY=planetY, box__geo_intersects={"type": "LineString", "coordinates": points }) #, owner__ne=request.user.username )

		p.lock = None
		# p.owner = None

		for area in lockedAreas:
			if userAllowed(request, area.owner):
				p.lock = str(area.pk)
				p.owner = area.owner
			else:
				return json.dumps( {'state': 'error', 'message': 'Your path intersects with a locked area which you do not own'} )

		addAreaToUpdate( p.box['coordinates'][0], p.planetX, p.planetY, p.city )

		p.box = [boxPoints]
		p.planetX = planetX
		p.planetY = planetY
		p.points = points

		addAreaToUpdate( boxPoints, planetX, planetY, p.city )
	if data:
		p.data = data
	if date:
		p.date = datetime.datetime.fromtimestamp(date/1000.0)
	p.lastUpdate = datetime.datetime.now()
	# updateAreas(bounds, p)

	p.save()

	return json.dumps( {'state': 'success'} )

# @dajaxice_register
@checkDebug
def deletePath(request, pk):

	try:
		p = Path.objects.get(pk=pk)
	except Path.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Delete impossible: element does not exist for this user'})

	if not userAllowed(request, p.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of path'})

	if p.drawing:
		return json.dumps({'state': 'error', 'message': 'Path is in drawing'})

	if p.lock and not userAllowed(request, p.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of path'})

	addAreaToUpdate( p.box['coordinates'][0], p.planetX, p.planetY, p.city )

	p.delete()

	return json.dumps( { 'state': 'success', 'pk': pk } )

# @dajaxice_register
@checkDebug
def saveBox(request, clientId, box, object_type, data=None, siteData=None, siteName=None, city=None):
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	city = getCity(request, city)
	if not city:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.' } )

	points = box['points']
	planetX = box['planet']['x']
	planetY = box['planet']['y']

	# check if the box intersects with another one
	geometry = makeBox(points[0][0], points[0][1], points[2][0], points[2][1])
	lockedAreas = Box.objects(city=city, planetX=planetX, planetY=planetY, box__geo_intersects=geometry, owner__ne=request.user.username )
	if lockedAreas.count()>0:
		return json.dumps( {'state': 'error', 'message': 'This area intersects with another locked area'} )

	# todo: warning: website is not defined in Box model...
	try:
		data = json.dumps( { 'loadEntireArea': loadEntireArea } )
		b = Box(clientId=clientId, city=city, planetX=planetX, planetY=planetY, box=[points], owner=request.user.username, object_type=object_type, siteName=siteName, data=data)
		b.save()
		addAreaToUpdate( points, planetX, planetY, city )
	except ValidationError:
		return json.dumps({'state': 'error', 'message': 'invalid_url'})

	# addAreas(bounds, b)

	if name and len(name)>0 and siteData:
		site = Site(box=b, name=name, data=siteData)
		site.save()

	# pathsToLock = Path.objects(planetX=planetX, planetY=planetY, box__geo_within=geometry)
	# for path in pathsToLock:
	# 	path.locked = True
	# 	path.save()

	Path.objects(city=city, planetX=planetX, planetY=planetY, points__geo_within=geometry).update(set__lock=str(b.pk), set__owner=request.user.username)
	Div.objects(city=city, planetX=planetX, planetY=planetY, box__geo_within=geometry).update(set__lock=str(b.pk), set__owner=request.user.username)

	return json.dumps( {'state': 'success', 'object_type':object_type, 'owner': request.user.username, 'pk':str(b.pk), 'box':box } )

# @dajaxice_register
@checkDebug
def updateBox(request, pk, box=None, data=None, name=None, updateType=None, modulePk=None):
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	try:
		b = Box.objects.get(pk=pk, owner=request.user.username)
	except Box.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist for this user'})

	if box:

		points = box['points']
		planetX = box['planet']['x']
		planetY = box['planet']['y']

		geometry = makeBox(points[0][0], points[0][1], points[2][0], points[2][1])

		# check if new box intersects with another one
		lockedAreas = Box.objects(city=b.city, planetX=planetX, planetY=planetY, box__geo_intersects=geometry, owner__ne=request.user.username )
		if lockedAreas.count()>0:
			return json.dumps( {'state': 'error', 'message': 'This area intersects with a locked area'} )


	# if box and updateType=='position':
	# 	newPoints = box['points']
	# 	# retrieve the old paths and divs to unlock them if they are not in the new box:
	# 	oldPoints = b.box['coordinates'][0]

	# 	planetX = b.planetX
	# 	planetY = b.planetY

	# 	geometry = makeBox(oldPoints[0][0], oldPoints[0][1], oldPoints[2][0], oldPoints[2][1])

	# 	paths = Path.objects(planetX=planetX, planetY=planetY, points__geo_within=geometry)

	# 	oldCenterX = points[0][0] + points[2][0]
	# 	oldCenterY = points[0][1] + points[2][1]
	# 	newCenterX = newPoints[0][0] + newPoints[2][0]
	# 	newCenterY = newPoints[0][1] + newPoints[2][1]

	# 	deltaX = newCenterX - oldCenterX
	# 	deltaY = newCenterY - oldCenterY

	# 	for path in paths:
	# 		for point in path.points['coordinates']:
	# 			point[0] = point[0] + deltaX
	# 			point[1] = point[1] + deltaY
	# 		path.save()

	# 	divs = Div.objects(planetX=planetX, planetY=planetY, box__geo_within=geometry)

	# 	import pdb; pdb.set_trace()

	# 	for div in divs:
	# 		for geometry in div.box:
	# 			points = geometry['coordinates'][0]
	# 			for i in range(0, 4):
	# 				points[i][0] = points[i][0] + deltaX
	# 				points[i][1] = points[i][1] + deltaY
	# 		div.save()

	# update the box:
	if box:
		addAreaToUpdate( b.box['coordinates'][0], b.planetX, b.planetY, b.city )
		b.box = [points]
		b.planetX = planetX
		b.planetY = planetY
		addAreaToUpdate( points, planetX, planetY, b.city )
	if data:
		b.data = data
	if modulePk:
		try:
			module = Module.objects.get(pk=modulePk)
		except Module.DoesNotExist:
			return json.dumps({'state': 'error', 'message': 'The module does not exist.'})
		b.module = module
		# module.lock = b
		# module.save()
	b.lastUpdate = datetime.datetime.now()

	try:
		b.save()
	except ValidationError:
		return json.dumps({'state': 'error', 'message': 'The URL is invalid.'})

	# if box:
	# 	# retrieve the new paths and divs to lock them if they were not in the old box:
	# 	points = box['points']
	# 	planetX = box['planet']['x']
	# 	planetY = box['planet']['y']
	# 	geometry = makeBox(points[0][0], points[0][1], points[2][0], points[2][1])

	# 	newPaths = Path.objects(planetX=b.planetX, planetY=b.planetY, points__geo_within=geometry)
	# 	newDivs = Div.objects(planetX=b.planetX, planetY=b.planetY, box__geo_within=geometry)

	# 	# update old and new paths and divs
	# 	newPaths.update(set__lock=str(b.pk), set__owner=request.user.username)
	# 	newDivs.update(set__lock=str(b.pk), set__owner=request.user.username)

	# 	oldPaths.filter(pk__nin=newPaths.scalar("id")).update(set__lock=None, set__owner=None)
	# 	oldDivs.filter(pk__nin=newDivs.scalar("id")).update(set__lock=None, set__owner=None)

	# 	# for oldPath in oldPaths:
	# 	# 	if oldPath not in newPaths:
	# 	# 		oldPath.locked = False
	# 	# 		oldPath.save()

	# 	# for oldDiv in oldDivs:
	# 	# 	if oldDiv not in newDivs:
	# 	# 		oldDiv.locked = False
	# 	# 		oldDiv.save()

	return json.dumps( {'state': 'success' } )

# @dajaxice_register
@checkDebug
def deleteBox(request, pk):
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	try:
		b = Box.objects.get(pk=pk, owner=request.user.username)
	except Box.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist for this user'})

	points = b.box['coordinates'][0]
	planetX = b.planetX
	planetY = b.planetY
	oldGeometry = makeBox(points[0][0], points[0][1], points[2][0], points[2][1])

	Path.objects(city=b.city, planetX=planetX, planetY=planetY, points__geo_within=oldGeometry).update(set__lock=None)
	Div.objects(city=b.city, planetX=planetX, planetY=planetY, box__geo_within=oldGeometry).update(set__lock=None)

	if not userAllowed(request, b.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of div'})

	# deleteAreas(b)
	addAreaToUpdate( points, planetX, planetY, b.city )
	b.delete()

	return json.dumps( { 'state': 'success', 'pk': pk } )

# @dajaxice_register
@checkDebug
def saveDiv(request, clientId, box, object_type, date=None, data=None, lock=None, city=None):

	points = box['points']
	planetX = box['planet']['x']
	planetY = box['planet']['y']

	city = getCity(request, city)
	if not city:
		return json.dumps( { 'status': 'error', 'message': 'The city does not exist.' } )

	lockedAreas = Box.objects(city=city, planetX=planetX, planetY=planetY, box__geo_intersects=makeBox(points[0][0], points[0][1], points[2][0], points[2][1]) ) # , owner__ne=request.user.username )
	lock = None
	for area in lockedAreas:
		if userAllowed(request, area.owner):
			lock = str(area.pk)
		else:
			return json.dumps( {'state': 'error', 'message': 'Your div intersects with a locked area which you do not own'} )

	# if lockedAreas.count()>0:
	# 	return json.dumps( {'state': 'error', 'message': 'Your div intersects with a locked area'} )

	d = Div(clientId=clientId, city=city, planetX=planetX, planetY=planetY, box=[points], owner=request.user.username, object_type=object_type, data=data, lock=lock, date=datetime.datetime.fromtimestamp(date/1000.0))
	# addAreaToUpdate( points, planetX, planetY )
	d.save()

	return json.dumps( {'state': 'success', 'object_type':object_type, 'owner': request.user.username, 'pk':str(d.pk), 'box': box } )

# @dajaxice_register
@checkDebug
def updateDiv(request, pk, object_type=None, box=None, date=None, data=None, lock=None):

	try:
		d = Div.objects.get(pk=pk)
	except Div.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist'})

	if d.lock and not userAllowed(request, d.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of div'})

	if box:
		points = box['points']
		planetX = box['planet']['x']
		planetY = box['planet']['y']

		lockedAreas = Box.objects(city=d.city, planetX=planetX, planetY=planetY, box__geo_intersects=makeBox(points[0][0], points[0][1], points[2][0], points[2][1]) ) # , owner__ne=request.user.username )
		d.lock = None
		d.owner = None
		for area in lockedAreas:
			if userAllowed(request, area.owner):
				# try:
				# 	lock = Box.objects(planetX=planetX, planetY=planetY, point__geo_within_box=makeBox(points[0][0], points[0][1], points[2][0], points[2][1]) )
				# except Box.DoesNotExist:
				# 	return json.dumps( {'state': 'error', 'message': 'Your div intersects with a locked area that you own.'} )
				d.lock = str(area.pk)
				d.owner = area.owner
			else:
				return json.dumps( {'state': 'error', 'message': 'Your div intersects with a locked area which you do not own'} )

		# addAreaToUpdate( d.box['coordinates'][0], d.planetX, d.planetY )
		d.box = [points]
		d.planetX = planetX
		d.planetY = planetY
		# addAreaToUpdate( d.box[0], d.planetX, d.planetY )
	if date:
		d.date = datetime.datetime.fromtimestamp(date/1000.0)
	if data:
		d.data = data
	d.lastUpdate = datetime.datetime.now()

	d.save()

	return json.dumps( {'state': 'success' } )

# @dajaxice_register
@checkDebug
def deleteDiv(request, pk):

	try:
		d = Div.objects.get(pk=pk)
	except Div.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist for this user.'})

	if d.lock and not userAllowed(request, d.owner):
		return json.dumps({'state': 'error', 'message': 'You are not the owner of this div.'})

	# addAreaToUpdate( d.box['coordinates'][0], d.planetX, d.planetY )

	d.delete()


	return json.dumps( { 'state': 'success', 'pk': pk } )


# --- Drawings --- #

# @dajaxice_register
@checkDebug
def saveDrawing(request, clientId, date, pathPks, title, description):
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	paths = []

	xMin = None
	xMax = None
	yMin = None
	yMax = None

	city = None
	planetX = None
	planetY = None

	for pathPk in pathPks:
		try:
			path = Path.objects.get(pk=pathPk)

			if path.drawing:
				return json.dumps({'state': 'error', 'message': 'One path is already part of a drawing.'})

			if not userAllowed(request, path.owner):
				return json.dumps({'state': 'error', 'message': 'One path is not property of user.'})

			if city != None and path.city != city or planetX != None and path.planetX != planetX or planetY != None and path.planetY != planetY:
				return json.dumps({'state': 'error', 'message': 'One path is from a different city or planet.'})

			city = path.city
			planetX = path.planetX
			planetY = path.planetY

			cbox = path.box['coordinates'][0]
			cleft = cbox[0][0]
			ctop = cbox[0][1]
			cright = cbox[2][0]
			cbottom = cbox[2][1]

			if not xMin or cleft < xMin:
				xMin = cleft
			if not xMax or cright > xMax:
				xMax = cright
			if not yMin or ctop < yMin:
				yMin = ctop
			if not yMax or cbottom > yMax:
				yMax = cbottom

			paths.append(path)
		except Path.DoesNotExist:
			return json.dumps({'state': 'error', 'message': 'Element does not exist for this user.'})

	points = [ [xMin, yMin], [xMax, yMin], [xMax, yMax], [xMin, yMax], [xMin, yMin] ]

	try:
		d = Drawing(clientId=clientId, city=city, planetX=planetX, planetY=planetY, box=[points], owner=request.user.username, paths=paths, date=datetime.datetime.fromtimestamp(date/1000.0), title=title, description=description)
		d.save()
	except NotUniqueError:
		return json.dumps({'state': 'error', 'message': 'A drawing with this name already exists.'})

	pathPks = []
	for path in paths:
		path.drawing = d
		path.save()
		pathPks.append(str(path.pk))

	return json.dumps( {'state': 'success', 'owner': request.user.username, 'pk':str(d.pk), 'pathPks': pathPks, 'negativeVoteThreshold': negativeVoteThreshold, 'positiveVoteThreshold': positiveVoteThreshold, 'voteMinDuration': voteMinDuration.total_seconds() } )

# @dajaxice_register
@checkDebug
def loadDrawing(request, pk):
	try:
		d = Drawing.objects.get(pk=pk)
	except Drawing.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist'})
	
	votes = []
	for vote in d.votes:
		if isinstance(vote, Vote):
			votes.append( { 'vote': vote.to_json(), 'author': vote.author.username, 'authorPk': str(vote.author.pk) } )

	paths = []
	for path in d.paths:
		if isinstance(path, Path):
			paths.append(path.to_json())

	return json.dumps( {'state': 'success', 'votes': votes, 'paths': paths, 'drawing': d.to_json() } )

# @dajaxice_register
@checkDebug
def updateDrawing(request, pk, title, description):
	
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	try:
		d = Drawing.objects.get(pk=pk)
	except Drawing.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist'})

	if not userAllowed(request, d.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of drawing'})

	if d.status != 'pending':
		return json.dumps({'state': 'error', 'message': 'The drawing is already validated, it cannot be modified anymore.'})

	d.title = title
	d.description = description

	d.save()

	return json.dumps( {'state': 'success' } )

# @dajaxice_register
@checkDebug
def deleteDrawing(request, pk):
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	try:
		d = Drawing.objects.get(pk=pk)
	except Drawing.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Element does not exist for this user.'})

	if not userAllowed(request, d.owner):
		return json.dumps({'state': 'error', 'message': 'Not owner of drawing'})

	if d.status != 'pending':
		return json.dumps({'state': 'error', 'message': 'The drawing is already validated, it cannot be cancelled anymore.'})

	d.delete()

	return json.dumps( { 'state': 'success', 'pk': pk } )

# --- get drafts --- #
@checkDebug
def getDrafts(request, city=None):

	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	cityPk = getCity(request, city)
	if not cityPk:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.', 'code': 'CITY_DOES_NOT_EXIST' } )

	paths = Path.objects(owner=request.user.username, drawing=None, city=cityPk)
	items = []

	for path in paths:
		items.append(path.to_json())

	return  json.dumps( {'state': 'success', 'items': items } )

# --- votes --- #

def computeVotes(drawing):
	nPositiveVotes = 0
	nNegativeVotes = 0
	for vote in drawing.votes:
		if vote.positive:
			nPositiveVotes += 1
		else:
			nNegativeVotes += 1
	return (nPositiveVotes, nNegativeVotes)

def isDrawingValidated(nPositiveVotes, nNegativeVotes):
	return nPositiveVotes >= positiveVoteThreshold and nNegativeVotes < negativeVoteThreshold

def isDrawingRejected(nNegativeVotes):
	return nNegativeVotes >= negativeVoteThreshold

drawingValidated = django.dispatch.Signal(providing_args=["drawingId", "status"])

@checkDebug
def vote(request, pk, date, positive):
	if not request.user.is_authenticated():
		return json.dumps({'state': 'not_logged_in'})

	drawing = None
	try:
		drawing = Drawing.objects.get(pk=pk)
	except Drawing.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Drawing does not exist.', 'pk': pk})

	if drawing.owner == request.user.username:
		return json.dumps({'state': 'error', 'message': 'Cannot vote for own drawing.'})

	if drawing.status != 'pending':
		return json.dumps({'state': 'error', 'message': 'The drawing is already validated.'})

	for vote in drawing.votes:
		if vote.author.username == request.user.username:
			if vote.positive == positive:
				if datetime.datetime.now() - vote.date < voteValidationDelay:
					return json.dumps({'state': 'error', 'message': 'You must wait before cancelling your vote', 'cancelled': False, 'voteValidationDelay': voteValidationDelay.total_seconds(), 'messageOptions': ['voteValidationDelay'] })
				# cancel vote: delete vote and return:
				vote.author.votes.remove(vote)
				drawing.votes.remove(vote)
				vote.delete()
				return json.dumps({'state': 'success', 'message': 'Your vote was cancelled', 'cancelled': True })
			else:
				# votes are different: delete vote and break (create a new one):
				vote.author.votes.remove(vote)
				drawing.votes.remove(vote)
				vote.delete()
				break

	user = None

	try:
		user = UserProfile.objects.get(username=request.user.username)
	except UserProfile.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Username does not exist.'})

	vote = Vote(author=user, drawing=drawing, positive=positive, date=datetime.datetime.fromtimestamp(date/1000.0))
	vote.save()

	drawing.votes.append(vote)
	drawing.save()

	user.votes.append(vote)
	user.save()

	(nPositiveVotes, nNegativeVotes) = computeVotes(drawing)

	validates = isDrawingValidated(nPositiveVotes, nNegativeVotes)
	rejects = isDrawingRejected(nNegativeVotes)

	delay = voteValidationDelay.total_seconds()

	if validates or rejects:

		def timeout(drawingPk):
			try:
				drawing = Drawing.objects.get(pk=pk)
			except Drawing.DoesNotExist:
				return

			(nPositiveVotes, nNegativeVotes) = computeVotes(drawing)

			if isDrawingValidated(nPositiveVotes, nNegativeVotes):
				drawing.status = 'drawing'
				drawing.save()
			elif isDrawingRejected(nNegativeVotes):
				drawing.status = 'rejected'
				drawing.save()

			drawingValidated.send(sender=None, drawingId=drawing.clientId, status=drawing.status)

			return

		if datetime.datetime.now() - drawing.date < voteMinDuration:
			delay = (drawing.date + voteMinDuration - datetime.datetime.now()).total_seconds()
		
		t = Timer(delay, timeout, args=[pk])
		t.start()
	
	votes = []
	for vote in drawing.votes:
		if isinstance(vote, Vote):
			votes.append( { 'vote': vote.to_json(), 'author': vote.author.username, 'authorPk': str(vote.author.pk) } )

	return json.dumps( {'state': 'success', 'owner': request.user.username, 'drawingPk':str(drawing.pk), 'votePk':str(vote.pk), 'validates': validates, 'rejects': rejects, 'votes': votes, 'delay': delay } )

# --- Get Next Drawing To Be Drawn / Set Drawing Drawn --- #

# @checkDebug
# def loadItems(request, itemType, pks):

# 	if itemType not in ['Path', 'Div', 'Box', 'AreaToUpdate', 'Drawing']:
# 		return json.dumps({'state': 'error', 'message': 'Can only load Paths, Divs, Boxs, AreaToUpdates or Drawings.'})

# 	itemsQuerySet = globals()[itemType].objects(pk__in=pks)

# 	items = []
# 	for item in itemsQuerySet:
# 		items.append(item.to_json())

# 	return json.dumps( {'state': 'success', 'items': items } )

@checkDebug
def loadItems(request, itemsToLoad):
	items = []

	for itemToLoad in itemsToLoad:
		itemType = itemToLoad['itemType']
		pks = itemToLoad['pks']
		
		if itemType not in ['Path', 'Div', 'Box', 'AreaToUpdate', 'Drawing']:
			return json.dumps({'state': 'error', 'message': 'Can only load Paths, Divs, Boxs, AreaToUpdates or Drawings.'})

		itemsQuerySet = globals()[itemType].objects(pk__in=pks)
	
		for item in itemsQuerySet:
			items.append(item.to_json())

	return json.dumps( {'state': 'success', 'items': items } )

@checkDebug
def getNextValidatedDrawing(request, city=None):
	
	cityPk = getCity(request, city)
	if not cityPk:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.', 'code': 'CITY_DOES_NOT_EXIST' } )
	
	drawings = Drawing.objects(status='drawing', city=cityPk)

	drawing = drawings.first()
	if drawing is not None:
		# get all path of the first drawing
		paths = []
		for path in drawing.paths:
			paths.append(path.to_json())

		return  json.dumps( {'state': 'success', 'pk': str(drawing.pk), 'items': paths } )
	else:
		return  json.dumps( {'state': 'success', 'message': 'no path' } )

@checkDebug
def setDrawingStatusDrawn(request, pk, secret):
	if secret != TIPIBOT_PASSWORD:
		return json.dumps({'state': 'error', 'message': 'Secret invalid.'})

	try:
		drawing = Drawing.objects.get(pk=pk)
	except Drawing.DoesNotExist:
		return json.dumps({'state': 'error', 'message': 'Drawing does not exist.', 'pk': pk})
	
	drawing.status = 'drawn'
	drawing.save()

	drawingValidated.send(sender=None, drawingId=drawing.clientId, status=drawing.status)

	return json.dumps( {'state': 'success', 'message': 'Drawing status successfully updated.', 'pk': pk } )

# --- rasters --- #

def addAreaToUpdate(points, planetX, planetY, city):

	# merge all overlapping areas into one (and delete them)
	print '<<<'
	print 'start merging all regions overlapping with the new area to update: '
	print 'points: ' + str(points)

	overlappingAreas = AreaToUpdate.objects(city=city, planetX=planetX, planetY=planetY, box__geo_intersects=[points])

	xMin = points[0][0]
	xMax = points[2][0]
	yMin = points[0][1]
	yMax = points[2][1]

	while len(overlappingAreas)>0:

		for overlappingArea in overlappingAreas:

			cbox = overlappingArea.box['coordinates'][0]
			cleft = cbox[0][0]
			ctop = cbox[0][1]
			cright = cbox[2][0]
			cbottom = cbox[2][1]

			# # if the areas just share an edge: continue
			# # check if intersection has a positive area
			# ileft = max(left, cleft)
			# itop = max(top, ctop)
			# iright = min(right, cright)
			# ibottom = min(bottom, cbottom)

			# if (iright-ileft) <= 0 or (ibottom-itop) <= 0 or (iright-ileft) * (ibottom-itop) <= 0.001:
			# 	continue

			print '!!! OVERLAPPING !!!'

			if not xMin or cleft < xMin:
				xMin = cleft
			if not xMax or cright > xMax:
				xMax = cright
			if not yMin or ctop < yMin:
				yMin = ctop
			if not yMax or cbottom > yMax:
				yMax = cbottom


			print 'start deleting areas of overlapping area: ' + str(overlappingArea.pk)
			print 'start deleting overlapping area: ' + str(overlappingArea.pk) + '...'
			try:
				overlappingArea.delete()
			except Area.DoesNotExist:
				print "Impossible to delete area: " + str(overlappingArea.pk) + ", skipping area merging"
				xMin = points[0][0]
				xMax = points[2][0]
				yMin = points[0][1]
				yMax = points[2][1]
				break
			print '...finished deleting overlapping area: ' + str(overlappingArea.pk)

		points = [ [xMin, yMin], [xMax, yMin], [xMax, yMax], [xMin, yMax], [xMin, yMin] ]
		overlappingAreas = AreaToUpdate.objects(city=city, planetX=planetX, planetY=planetY, box__geo_intersects=[points])

	areaToUpdate = AreaToUpdate(city=city, planetX=planetX, planetY=planetY, box=[points])
	areaToUpdate.save()

	return

# Get the position in project coordinate system of *point* on *planet*
# This is the opposite of projectToPlanetJson
def posOnPlanetToProject(xp, yp, planetX, planetY):
	scale = 1000.0
	x = planetX*360.0+xp
	y = planetY*180.0+yp
	x *= scale
	y *= scale
	return (x,y)

# @dajaxice_register
@checkDebug
def batchUpdateRasters(request, args):
	results = []
	for arg in args:
		results.append(updateRastersJson(arg['data'], arg['position'], arg['areasNotRasterized'], arg['areaToDeletePk']))
	return json.dumps(results)

# # @dajaxice_register
# @checkDebug
# def updateRasters(request, data=None, position=None, areasNotRasterized=None, areaToDeletePk=None):
# 	result = updateRastersJson(data, position, areasNotRasterized, areaToDeletePk)
# 	return json.dumps(result)

def floorToMultiple(x, m):
	return int(floor(x/float(m))*m)

# warning: difference between ceil(x/m)*m and floor(x/m)*(m+1)
def ceilToMultiple(x, m):
	return int(ceil(x/float(m))*m)

# # # @dajaxice_register
# @checkDebug
# def updateRastersJson(data=None, position=None, areasNotRasterized=None, areaToDeletePk=None):
# 	print "updateRastersJson"

# 	# for line in traceback.format_stack():
# 	# 	print line.strip()

# 	# global isUpdatingRasters

# 	# if isUpdatingRasters:
# 	# 	print 'Error: isUpdatingRasters!'
# 	# 	import pdb; pdb.set_trace()

# 	# isUpdatingRasters = True

# 	if areaToDeletePk:
# 		try:
# 			areaToDelete = AreaToUpdate.objects.get(pk=areaToDeletePk)
# 		except AreaToUpdate.DoesNotExist:
# 			return json.dumps({'state': 'log', 'message': 'Delete impossible: area does not exist'})
# 		print '<<<'
# 		print "1. attempt to delete areas from area to delete " + str(areaToDelete.pk) + "..."
# 		# deleteAreas(areaToDelete)
# 		print "2. attempt to delete areas to delete " + str(areaToDelete.pk) + "..."
# 		areaToDelete.delete()

# 		try:
# 			a = AreaToUpdate.objects.get(pk=areaToDeletePk)
# 			print 'WHAT?'
# 			import pdb; pdb.set_trace()
# 		except AreaToUpdate.DoesNotExist:
# 			print 'ok'
# 		print '3. finished deleting area to delete'
# 		print '>>>'

# 	areasDeleted = []
# 	areasToUpdate = []

# 	if areasNotRasterized:
# 		for area in areasNotRasterized:

# 			points = area['points']
# 			planetX = area['planet']['x']
# 			planetY = area['planet']['y']

# 			# merge all overlapping areas into one (and delete them)
# 			print '<<<'
# 			print 'start merging all regions overlapping with the new area to update: '
# 			print 'points: ' + str(points)
# 			overlappingAreas = AreaToUpdate.objects(planetX=planetX, planetY=planetY, box__geo_intersects=[points])
# 			left = xMin = points[0][0]
# 			right = xMax = points[2][0]
# 			top = yMin = points[0][1]
# 			bottom = yMax = points[2][1]
# 			for overlappingArea in overlappingAreas:

# 				cbox = overlappingArea.box['coordinates'][0]
# 				cleft = cbox[0][0]
# 				ctop = cbox[0][1]
# 				cright = cbox[2][0]
# 				cbottom = cbox[2][1]

# 				# if the areas just share an edge: continue
# 				# check if intersection has a positive area
# 				ileft = max(left, cleft)
# 				itop = max(top, ctop)
# 				iright = min(right, cright)
# 				ibottom = min(bottom, cbottom)

# 				if (iright-ileft) <= 0 or (ibottom-itop) <= 0 or (iright-ileft) * (ibottom-itop) <= 0.001:
# 					continue

# 				print '!!! OVERLAPPING !!!'
# 				print '!!! OVERLAPPING !!!'
# 				print '!!! OVERLAPPING !!!'

# 				if not xMin or cleft < xMin:
# 					xMin = cleft
# 				if not xMax or cright > xMax:
# 					xMax = cright
# 				if not yMin or ctop < yMin:
# 					yMin = ctop
# 				if not yMax or cbottom > yMax:
# 					yMax = cbottom

# 				areasDeleted.append(str(overlappingArea.pk))
# 				print 'start deleting areas of overlapping area: ' + str(overlappingArea.pk)
# 				# deleteAreas(overlappingArea)
# 				print 'start deleting overlapping area: ' + str(overlappingArea.pk) + '...'
# 				try:
# 					overlappingArea.delete()
# 				except Area.DoesNotExist:
# 					print "Impossible to delete area: " + str(overlappingArea.pk) + ", skipping area merging"
# 					xMin = points[0][0]
# 					xMax = points[2][0]
# 					yMin = points[0][1]
# 					yMax = points[2][1]
# 					break
# 				print '...finished deleting overlapping area: ' + str(overlappingArea.pk)

# 			print 'creating new area to update...'
# 			areaToUpdate = AreaToUpdate(planetX=planetX, planetY=planetY, box=[[ [xMin, yMin], [xMax, yMin], [xMax, yMax], [xMin, yMax], [xMin, yMin] ]])
# 			areaToUpdate.save()
# 			# print '...created new area to update'

# 			# topLeft = posOnPlanetToProject(xMin, yMin, planetX, planetY)
# 			# bottomRight = posOnPlanetToProject(xMax, yMax, planetX, planetY)
# 			# print "planet"
# 			# print planetX
# 			# print planetY
# 			# print "rectangle"
# 			# print xMin
# 			# print yMin
# 			# print xMax
# 			# print yMax
# 			# print "rectangle in project coordinates"
# 			# print topLeft
# 			# print bottomRight
# 			# bounds = {'x': topLeft[0], 'y': topLeft[1], 'width': bottomRight[0]-topLeft[0], 'height': bottomRight[1]-topLeft[1]}

# 			# print 'adding new area to area to update...'
# 			# addAreas(bounds, areaToUpdate)
# 			# print '...added new area to area to update'

# 			areasToUpdate.append( areaToUpdate.to_json() )
# 			print '>>>'

# 	if (not data) or (data == "data:,"):
# 		return { 'state': 'success', 'areasToUpdate': areasToUpdate, 'areasDeleted': areasDeleted }

# 	imageData = re.search(r'base64,(.*)', data).group(1)

# 	try:
# 		image = Image.open(StringIO.StringIO(imageData.decode('base64')))				# Pillow version
# 	except IOError:
# 		return { 'state': 'error', 'message': 'impossible to read image.'}

# 	# with Image(file=cStringIO.StringIO(imageData.decode('base64'))) as image: 		# Wand version

# 	# # find top, left, bottom and right positions of the area in the quantized space

# 	start = time.time()

# 	x = int(position['x'])
# 	y = int(position['y'])
# 	width = int(image.size[0])
# 	height = int(image.size[1])

# 	l = floorToMultiple(x, 1000)
# 	t = floorToMultiple(y, 1000)
# 	r = floorToMultiple(x+width, 1000)+1000
# 	b = floorToMultiple(y+height, 1000)+1000

# 	imageOnGrid25x = floorToMultiple(x, 25)
# 	imageOnGrid25y = floorToMultiple(y, 25)
# 	imageOnGrid25width = ceilToMultiple(x+width, 25)-imageOnGrid25x
# 	imageOnGrid25height = ceilToMultiple(y+height, 25)-imageOnGrid25y

# 	# debug

# 	# image.save('media/rasters/image.png')

# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print 'original rect'
# 	# print x
# 	# print y
# 	# print width
# 	# print height
# 	# print 'rounded rect'
# 	# print l
# 	# print t
# 	# print r
# 	# print b

# 	# print 'image size:'
# 	# print image.size[0]
# 	# print image.size[1]

# 	# print 'big image:'
# 	# print imageOnGrid25x
# 	# print imageOnGrid25y
# 	# print imageOnGrid25width
# 	# print imageOnGrid25height

# 	# try:
# 	imageOnGrid25 = Image.new("RGBA", (1000, 1000))

# 	for xi in range(l,r,1000):
# 		for yi in range(t,b,1000):

# 			x1 = int(xi/1000)
# 			y1 = int(yi/1000)

# 			x5 = floorToMultiple(x1, 5)
# 			y5 = floorToMultiple(y1, 5)

# 			x25 = floorToMultiple(x1, 25)
# 			y25 = floorToMultiple(y1, 25)

# 			rasterPath = 'media/rasters/zoom100/' + str(x25) + ',' + str(y25) + '/' + str(x5) + ',' + str(y5) + '/'

# 			try:
# 				os.makedirs(rasterPath)
# 			except OSError as exception:
# 				if exception.errno != errno.EEXIST:
# 					raise

# 			rasterName = rasterPath + str(x1) + "," + str(y1) + ".png"

# 			try:
# 				# raster = Image(filename=rasterName)  		# Wand version
# 				raster = Image.open(rasterName)				# Pillow version
# 			except IOError:
# 				# raster = Image(width=1000, height=1000) 	# Wand version
# 				raster = Image.new("RGBA", (1000, 1000)) 	# Pillow version

# 			left = max(xi,x)
# 			right = min(xi+1000,x+width)
# 			top = max(yi,y)
# 			bottom = min(yi+1000,y+height)

# 			# print '-----'
# 			# print '-----'
# 			# print 'raster pos:'
# 			# print xi
# 			# print yi

# 			# print 'rectangle cutted:'
# 			# print left
# 			# print top
# 			# print right
# 			# print bottom

# 			# print 'width, height:'
# 			# print right-left
# 			# print bottom-top

# 			# print 'sub image rect:'
# 			# print left-x
# 			# print top-y
# 			# print right-x
# 			# print bottom-y

# 			# import pdb; pdb.set_trace()
# 			subImage = image.crop((left-x, top-y, right-x, bottom-y))

# 			# subImage = image.clone().crop(left=subImageLeft,top=subImageTop,width=subImageWidth,height=subImageHeight) # unefficient: clone the whole image instead of the sub image

# 			# print 'posInRaster:'
# 			# print left-xi
# 			# print top-yi

# 			# print 'sub image size:'
# 			# print subImage.size[0]
# 			# print subImage.size[1]

# 			# import pdb; pdb.set_trace()

# 			# raster.composite(image=subImage, left=posInRasterX, top=posInRasterY) 	# problem: we want to totally replace current raster with new one
# 			# raster100.composite_channel(channel='all_channels', image=subImage, operator='replace', left=posInRasterX, top=posInRasterY) 		# Wand version
# 			raster.paste(subImage, (left-xi, top-yi))
# 			raster.save(rasterName)

# 			left = max(xi,imageOnGrid25x)
# 			right = min(xi+1000,imageOnGrid25x+imageOnGrid25width)
# 			top = max(yi,imageOnGrid25y)
# 			bottom = min(yi+1000,imageOnGrid25y+imageOnGrid25height)

# 			# subImage.save('media/rasters/subimage_' + str(x1) + ',' + str(y1) + '.png')
# 			# print 'sub imageOnGrid25 in global coordinates:'
# 			# print left
# 			# print top
# 			# print right
# 			# print bottom
# 			# print 'in raster100 coordinates:'
# 			# print left-xi
# 			# print top-yi
# 			# print 'in imageOnGrid25 coordinates:'
# 			# print left-imageOnGrid25x
# 			# print top-imageOnGrid25y

# 			subRaster = raster.crop((left-xi, top-yi, right-xi, bottom-yi))
# 			imageOnGrid25.paste(subRaster, (left-imageOnGrid25x, top-imageOnGrid25y))

# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print 'raster20:'

# 	l = floorToMultiple(x, 5000)
# 	t = floorToMultiple(y, 5000)
# 	r = floorToMultiple(x+width, 5000)+5000
# 	b = floorToMultiple(y+height, 5000)+5000

# 	for xi in range(l,r,5000):
# 		for yi in range(t,b,5000):

# 			x1 = int(xi/1000)
# 			y1 = int(yi/1000)

# 			x5 = floorToMultiple(x1, 5)
# 			y5 = floorToMultiple(y1, 5)

# 			x25 = floorToMultiple(x1, 25)
# 			y25 = floorToMultiple(y1, 25)

# 			rasterPath = 'media/rasters/zoom20/' + str(x25) + ',' + str(y25) + '/'

# 			try:
# 				os.makedirs(rasterPath)
# 			except OSError as exception:
# 				if exception.errno != errno.EEXIST:
# 					raise

# 			rasterName = rasterPath + str(x5) + "," + str(y5) + ".png"

# 			try:
# 				raster = Image.open(rasterName)
# 			except IOError:
# 				raster = Image.new("RGBA", (1000, 1000))

# 			left = max(xi,imageOnGrid25x)
# 			right = min(xi+5000,imageOnGrid25x+imageOnGrid25width)
# 			top = max(yi,imageOnGrid25y)
# 			bottom = min(yi+5000,imageOnGrid25y+imageOnGrid25height)

# 			# print '-----'
# 			# print '-----'
# 			# print 'raster pos:'
# 			# print xi
# 			# print yi
# 			# print 'sub imageOnGrid25 in global coordinates:'
# 			# print left
# 			# print top
# 			# print right
# 			# print bottom
# 			# print 'in raster20 coordinates:'
# 			# print (left-xi)/5
# 			# print (top-yi)/5
# 			# print 'in imageOnGrid25 coordinates:'
# 			# print left-imageOnGrid25x
# 			# print top-imageOnGrid25y

# 			subImage = imageOnGrid25.crop((left-imageOnGrid25x, top-imageOnGrid25y, right-imageOnGrid25x, bottom-imageOnGrid25y))
# 			subImageSmall = subImage.resize((subImage.size[0]/5, subImage.size[1]/5), Image.LANCZOS)
# 			raster.paste(subImageSmall, ((left-xi)/5, (top-yi)/5))
# 			raster.save(rasterName)

# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print '-----'
# 	# print 'raster4:'

# 	l = floorToMultiple(x, 25000)
# 	t = floorToMultiple(y, 25000)
# 	r = floorToMultiple(x+width, 25000)+25000
# 	b = floorToMultiple(y+height, 25000)+25000

# 	for xi in range(l,r,25000):
# 		for yi in range(t,b,25000):

# 			x1 = int(xi/1000)
# 			y1 = int(yi/1000)

# 			x25 = floorToMultiple(x1, 25)
# 			y25 = floorToMultiple(y1, 25)

# 			rasterPath = 'media/rasters/zoom4/'

# 			try:
# 				os.makedirs(rasterPath)
# 			except OSError as exception:
# 				if exception.errno != errno.EEXIST:
# 					raise

# 			rasterName = rasterPath + str(x25) + "," + str(y25) + ".png"

# 			try:
# 				raster = Image.open(rasterName)
# 			except IOError:
# 				raster = Image.new("RGBA", (1000, 1000))

# 			left = max(xi,imageOnGrid25x)
# 			right = min(xi+25000,imageOnGrid25x+imageOnGrid25width)
# 			top = max(yi,imageOnGrid25y)
# 			bottom = min(yi+25000,imageOnGrid25y+imageOnGrid25height)

# 			# print '-----'
# 			# print '-----'
# 			# print 'raster pos:'
# 			# print xi
# 			# print yi
# 			# print 'sub imageOnGrid25 in global coordinates:'
# 			# print left
# 			# print top
# 			# print right
# 			# print bottom
# 			# print 'in raster4 coordinates:'
# 			# print (left-xi)/25
# 			# print (top-yi)/25
# 			# print 'in imageOnGrid25 coordinates:'
# 			# print left-imageOnGrid25x
# 			# print top-imageOnGrid25y

# 			subImage = imageOnGrid25.crop((left-imageOnGrid25x, top-imageOnGrid25y, right-imageOnGrid25x, bottom-imageOnGrid25y))
# 			subImageSmall = subImage.resize((subImage.size[0]/25, subImage.size[1]/25), Image.LANCZOS)
# 			raster.paste(subImageSmall, ((left-xi)/25, (top-yi)/25))
# 			raster.save(rasterName)

# 	# except:
# 	# 	import pdb; pdb.set_trace()
# 	# 	return { 'state': 'error', 'message': 'Failed to open, create or save an image.' }

# 	# another solution, slower since open and close many images

# 	# for xi in range(l,r,1000):
# 	# 	for yi in range(t,b,1000):

# 	# 		xm = int(xi/1000)
# 	# 		ym = int(yi/1000)

# 	# 		x5 = floorToMultiple(xm, 5)
# 	# 		y5 = floorToMultiple(ym, 5)

# 	# 		x25 = floorToMultiple(xm, 25)
# 	# 		y25 = floorToMultiple(ym, 25)

# 	# 		rasterPath100 = 'media/rasters/zoom100/' + str(x25) + ',' + str(y25) + '/' + str(x5) + ',' + str(y5) + '/'
# 	# 		rasterPath20 = 'media/rasters/zoom20/' + str(x25) + ',' + str(y25) + '/'
# 	# 		rasterPath4 = 'media/rasters/zoom4/'

# 	# 		try:
# 	# 			os.makedirs(rasterPath100)
# 	# 		except OSError as exception:
# 	# 			if exception.errno != errno.EEXIST:
# 	# 				raise

# 	# 		try:
# 	# 			os.makedirs(rasterPath20)
# 	# 		except OSError as exception:
# 	# 			if exception.errno != errno.EEXIST:
# 	# 				raise

# 	# 		try:
# 	# 			os.makedirs(rasterPath4)
# 	# 		except OSError as exception:
# 	# 			if exception.errno != errno.EEXIST:
# 	# 				raise

# 	# 		rasterName100 = rasterPath100 + str(xm) + "," + str(ym) + ".png"
# 	# 		rasterName20 = rasterPath20 + str(x5) + "," + str(y5) + ".png"
# 	# 		rasterName4 = rasterPath4 + str(x25) + "," + str(y25) + ".png"

# 	# 		try:
# 	# 			# raster100 = Image(filename=rasterName100)  		# Wand version
# 	# 			raster100 = Image.open(rasterName100)				# Pillow version
# 	# 		except IOError:
# 	# 			try:
# 	# 				# raster100 = Image(width=1000, height=1000) 	# Wand version
# 	# 				raster100 = Image.new("RGBA", (1000, 1000)) 	# Pillow version
# 	# 			except:
# 	# 				return { 'state': 'error', 'message': 'Failed to create the image.' }

# 	# 		try:
# 	# 			raster20 = Image.open(rasterName20)
# 	# 		except IOError:
# 	# 			try:
# 	# 				raster20 = Image.new("RGBA", (1000, 1000))
# 	# 			except:
# 	# 				return { 'state': 'error', 'message': 'Failed to create the image.' }

# 	# 		try:
# 	# 			raster4 = Image.open(rasterName4)
# 	# 		except IOError:
# 	# 			try:
# 	# 				raster4 = Image.new("RGBA", (1000, 1000))
# 	# 			except:
# 	# 				return { 'state': 'error', 'message': 'Failed to create the image.' }

# 	# 		left = max(xi,x)
# 	# 		right = min(xi+1000,x+width)
# 	# 		top = max(yi,y)
# 	# 		bottom = min(yi+1000,y+height)

# 	# 		print '-----'
# 	# 		print '-----'
# 	# 		print '-----'
# 	# 		print '-----'
# 	# 		print '-----'
# 	# 		print '-----'
# 	# 		print 'raster pos:'
# 	# 		print xi
# 	# 		print yi

# 	# 		print 'rectangle:'
# 	# 		print x
# 	# 		print y
# 	# 		print width
# 	# 		print height

# 	# 		print 'rectangle cutted:'
# 	# 		print left
# 	# 		print top
# 	# 		print right
# 	# 		print bottom
# 	# 		print 'width, height:'
# 	# 		print right-left
# 	# 		print bottom-top

# 	# 		subImageLeft = left-x
# 	# 		subImageTop = top-y
# 	# 		subImageRight = right-x
# 	# 		subImageBottom = bottom-y
# 	# 		subImageWidth = subImageRight-subImageLeft
# 	# 		subImageHeight = subImageBottom-subImageTop

# 	# 		print 'sub image rect:'
# 	# 		print subImageLeft
# 	# 		print subImageTop
# 	# 		print subImageRight
# 	# 		print subImageBottom
# 	# 		print 'width, height:'
# 	# 		print subImageWidth
# 	# 		print subImageHeight

# 	# 		print 'image size:'
# 	# 		print image.size[0]
# 	# 		print image.size[1]

# 	# 		print 'raster size:'
# 	# 		print raster100.size[0]
# 	# 		print raster100.size[1]

# 	# 		# import pdb; pdb.set_trace()
# 	# 		subImage = image.crop((subImageLeft, subImageTop, subImageWidth, subImageHeight))

# 	# 		# subImage = image.clone().crop(left=subImageLeft,top=subImageTop,width=subImageWidth,height=subImageHeight) # unefficient: clone the whole image instead of the sub image
# 	# 		posInRasterX = left-xi
# 	# 		posInRasterY = top-yi

# 	# 		print 'posInRaster:'
# 	# 		print posInRasterX
# 	# 		print posInRasterY

# 	# 		# import pdb; pdb.set_trace()

# 	# 		# raster.composite(image=subImage, left=posInRasterX, top=posInRasterY) 	# problem: we want to totally replace current raster with new one
# 	# 		# raster100.composite_channel(channel='all_channels', image=subImage, operator='replace', left=posInRasterX, top=posInRasterY) 		# Wand version
# 	# 		raster100.paste(subImage, (posInRasterX, posInRasterY))
# 	# 		raster100.save(rasterName100)

# 	# 		raster100cropX = floorToMultiple(posInRasterX, 5)
# 	# 		raster100cropY = floorToMultiple(posInRasterY, 5)
# 	# 		raster100cropWidth = ceilToMultiple(posInRasterX+subImageWidth, 5)-raster100cropX
# 	# 		raster100cropHeight = ceilToMultiple(posInRasterY+subImageHeight, 5)-raster100cropY

# 	# 		print 'raster100crop:'
# 	# 		print raster100cropX
# 	# 		print raster100cropY
# 	# 		print raster100cropWidth
# 	# 		print raster100cropHeight
# 	# 		raster100crop = raster100.crop((raster100cropX, raster100cropY, raster100cropWidth, raster100cropHeight))
# 	# 		raster100crop.resize((raster100cropWidth/5, raster100cropHeight/5), Image.LANCZOS)

# 	# 		print 'raster100crop final size:'
# 	# 		print raster100cropWidth/5
# 	# 		print raster100cropHeight/5

# 	# 		print 'xm & ym:'
# 	# 		print xm
# 	# 		print ym
# 	# 		print 'x5 & y5:'
# 	# 		print x5
# 	# 		print y5
# 	# 		print '(xm-x5)*1000:'
# 	# 		print (xm-x5)*1000
# 	# 		print (ym-y5)*1000

# 	# 		posInRasterX = ((xm-x5)*1000+raster100cropX)/5
# 	# 		posInRasterY = ((ym-y5)*1000+raster100cropY)/5
# 	# 		print 'posInRaster:'
# 	# 		print posInRasterX
# 	# 		print posInRasterY
# 	# 		raster20.paste(raster100crop, (posInRasterX, posInRasterY))
# 	# 		raster20.save(rasterName20)

# 	# 		raster20cropX = floorToMultiple(posInRasterX,5)
# 	# 		raster20cropY = floorToMultiple(posInRasterY,5)
# 	# 		raster20cropWidth = ceilToMultiple(posInRasterX+raster100cropWidth/5, 5)-raster20cropX
# 	# 		raster20cropHeight = ceilToMultiple(posInRasterY+raster100cropHeight/5, 5)-raster20cropY

# 	# 		print 'x25 & y25:'
# 	# 		print x25
# 	# 		print y25
# 	# 		print 'raster20crop:'
# 	# 		print raster20cropX
# 	# 		print raster20cropY
# 	# 		print raster20cropWidth
# 	# 		print raster20cropHeight
# 	# 		raster20crop = raster20.crop((raster20cropX, raster20cropY, raster20cropWidth, raster20cropHeight))
# 	# 		raster20crop.resize((raster20cropWidth/5, raster20cropHeight/5), Image.LANCZOS)

# 	# 		posInRasterX = ((x5-x25)*1000/5+raster20cropX)/5
# 	# 		posInRasterY = ((y5-y25)*1000/5+raster20cropY)/5
# 	# 		print 'posInRaster:'
# 	# 		print posInRasterX
# 	# 		print posInRasterY
# 	# 		raster4.paste(raster20crop, (posInRasterX, posInRasterY))
# 	# 		raster20.save(rasterName4)

# 	# 		# Wand version
# 	# 		# with image[subImageLeft:subImageRight, subImageTop:subImageBottom] as subImage:

# 	# 		# subImage.resize(filter='triangle', width=subImage.width/5, height=subImage.height/5)
# 	# 		# raster20.composite_channel(channel='all_channels', image=subImage, operator='replace', left=posInRasterX, top=posInRasterY)
# 	# 		# raster20.save(filename=rasterName)

# 	# 		# posInRasterX = int((left-x25*1000)/25)
# 	# 		# posInRasterY = int((top-y25*1000)/25)
# 	# 		# subImage.resize(filter='triangle', width=subImage.width/5, height=subImage.height/5)
# 	# 		# raster4.composite_channel(channel='all_channels', image=subImage, operator='replace', left=posInRasterX, top=posInRasterY)
# 	# 		# raster4.save(filename=rasterName)


# 	# 		raster100.close()
# 	# 		raster20.close()
# 	# 		raster4.close()

# 	image.close()

# 	end = time.time()

# 	print "Time elapsed: " + str(end - start)
# 	# isUpdatingRasters = False

# 	return { 'state': 'success', 'areasToUpdate': areasToUpdate, 'areasDeleted': areasDeleted }

# # @dajaxice_register
# @checkDebug
# def loadRasters(request, areasToLoad):

# 	images = []
# 	start = time.time()
# 	for area in areasToLoad:

# 		x = area['x']
# 		y = area['y']

# 		rasterPath = 'media/rasters/' + str(floor(x/10)*10) + ',' + str(floor(y/10)*10) + '/'
# 		rasterName = rasterPath + str(x) + "," + str(y) + ".png"

# 		with open(rasterName, 'rb') as inputFile:
# 			imageData = inputfile.read().encode('base64')
# 			inputfile.close()
# 			images.append(imageData)

# 	end = time.time()
# 	print "Time elapsed: " + str(end - start)

# 	return json.dumps( { 'images': images } )

# @dajaxice_register
@checkDebug
def getAreasToUpdate(request):
	areas = AreaToUpdate.objects()
	return areas.to_json()

@checkDebug
def getPathsToUpdate(request, city):

	cityPk = getCity(request, city)
	if not cityPk:
		return json.dumps( { 'state': 'error', 'message': 'The city does not exist.', 'code': 'CITY_DOES_NOT_EXIST' } )


	paths = Paths.objects(city=city, needUpdate=True)

	items = []
	for path in paths:
		if path.drawing is not None:
			items.append( { 'path': path.to_json(), 'status': path.drawing.status })

	return json.dumps( { 'paths': items } )

# @dajaxice_register
@checkDebug
def deleteAreaToUpdate(request, pk):
	try:
		area = AreaToUpdate.objects.get(pk=pk)
	except AreaToUpdate.DoesNotExist:
		return json.dumps( { 'state': 'error', 'message': 'area does not exist.' } )
	area.delete()
	return

# # @dajaxice_register
# @checkDebug
# def updateAreasToUpdate(request, pk, newAreas):

# 	try:
# 		areaToUpdate = AreaToUpdate.objects.get(pk=pk)
# 	except AreaToUpdate.DoesNotExist:
# 		return json.dumps({'state': 'log', 'message': 'Delete impossible: area does not exist'})

# 	areaToUpdate.delete()

# 	areasToUpdate = []
# 	for area in newAreas:
# 		points = area['points']
# 		planetX = area['planet']['x']
# 		planetY = area['planet']['y']

# 		areaToUpdate = AreaToUpdate(planetX=planetX, planetY=planetY, box=[points])
# 		areaToUpdate.save()

# 		areasToUpdate.append( areasToUpdate.to_json() )

# 	return json.dumps( { 'state': 'success', 'areasToUpdate': areasToUpdate } )

# --- images --- #

# @dajaxice_register
@checkDebug
def saveImage(request, image):

	imageData = re.search(r'base64,(.*)', image).group(1)

	imagePath = 'media/images/' + request.user.username + '/'

	try:
		os.mkdir(imagePath)
	except OSError as exception:
		if exception.errno != errno.EEXIST:
			raise

	date = str(datetime.datetime.now()).replace (" ", "_").replace(":", ".")
	imageName = imagePath + date + ".png"

	output = open(imageName, 'wb')
	output.write(imageData.decode('base64'))
	output.close()

	# to read the image
	# inputfile = open(imageName, 'rb')
	# imageData = inputfile.read().encode('base64')
	# inputfile.close()
	# return json.dumps( { 'image': imageData, 'url': imageName } )

	return json.dumps( { 'url': imageName } )

# --- modules --- #


'''
# requires github3 to work
# from github3 import authorize

def createCommitAndPush(repoName, source, localRepository, commitDescription):

	sourcePath = 'modules/' + repoName + '/main.coffee'
	moduleFile = open(sourcePath, 'wb')
	moduleFile.write(source.encode('utf-8'))
	moduleFile.close()

	origin = localRepository.remote(name='origin')
	localRepository.index.add(['main.coffee'])
	localRepository.index.commit(commitDescription)
	origin.fetch()
	origin.push()

	return

def addModule(user, name, source, compiledSource, description, type=None, commitDescription=None, iconURL=None, category=None):

	if 'CommeUnDessein module' not in description:
		description = 'CommeUnDessein module - ' + description

	try:
		githubRepository = commeUnDesseinOrg.create_repo(name, description=description, auto_init=True)
	except Exception as githubException:
		errorMessage = 'unknown error'
		if 'errors' in githubException.data and len(githubException.data['errors'])>=1 and 'message' in githubException.data['errors'][0]:
			errorMessage = githubException.data['errors'][0]['message']
		return json.dumps( { 'state': 'error', 'message': 'An error occured while creating the github repository: ' + errorMessage })

	repoName = githubRepository.name

	# lock = None
	# if lockPk:
	# 	try:
	# 		lock = Box.objects.get(pk=lockPk)
	# 	except:
	# 		return json.dumps( { 'state': 'error', 'message': 'The lock could not be found.'})

	try:
		module = Module(owner=user, name=name, repoName=repoName, description=description, source=source, compiledSource=compiledSource, iconURL=iconURL, local=True, category=category, githubURL=githubRepository.html_url, moduleType=type)
		module.save()
	except Exception as e:
		return json.dumps( { 'state': 'error', 'message': 'An error occured while creating the module.'})

	localRepository = Repo.clone_from(githubRepository.clone_url, 'modules/' + repoName, branch='master')

	createCommitAndPush(repoName, source, localRepository, commitDescription or "initial commit")

	return json.dumps( { 'state': 'success', 'message': 'Request for adding ' + name + ' successfully sent.', 'githubURL': githubRepository.html_url, 'modulePk': str(module.pk) } )

def updateModule(user, module, name, repoName, source, compiledSource, commitDescription, githubURL=None, iconURL=None, category=None):
	if module.local:
		# update (commit) local repo

		localRepository = Repo('modules/' + repoName)
		createCommitAndPush(repoName, source, localRepository, commitDescription)

		if iconURL:
			module.iconURL = iconURL
		if category:
			module.category = category

		module.save()
		githubURL = module.githubURL
	else:
		# push request

		githubRepository = github.get_repo(githubURL)
		fork = commeUnDesseinOrg.create_fork(githubRepository)

		localRepository = Repo.clone_from(fork.clone_url, 'modules/' + repoName, branch='master')
		createCommitAndPush(repoName, source, localRepository, commitDescription)

		fork.create_pull('Pull request created by ' + str(user), description, 'master', 'master')
		githubURL = fork.html_url

	return json.dumps( { 'state': 'success', 'message': 'Request for updating ' + name + ' successfully sent.', 'githubURL': githubURL, 'modulePk': str(module.pk) } )

# @dajaxice_register
@checkDebug
def addOrUpdateModule(request, name, source, compiledSource, type=None, description=None, commitDescription=None, githubURL=None, iconURL=None, category=None):
	try:
		module = Module.objects.get(name=name)
		result = updateModule(request.user.username, module, name, module.repoName, source, compiledSource, commitDescription, githubURL, iconURL, category)
	except Module.DoesNotExist:
		result = addModule(request.user.username, name, source, compiledSource, type, description, commitDescription, iconURL, category)

	return result

'''

# # @dajaxice_register
# @checkDebug
# def addModule(request, name, className, source, compiledSource, isTool, description, iconURL=None):

# 	try:
# 		module = Module(owner=request.user.username, name=name, className=className, source=source, compiledSource=compiledSource, iconURL=iconURL, isTool=isTool)
# 	except OperationError:
# 		return json.dumps( { 'state': 'error', 'message': 'A module with the name ' + name + ' or the className ' + className + ' already exists.' } )

# 	githubRepository = commeUnDesseinOrg.create_repo(name, description=description, auto_init=True)

# 	localRepository = Repo.clone_from(path_to='modules/' + name, url=githubRepository.clone_url, branch='master')
# 	origin = localRepository.remote(name='origin')

# 	moduleName = name + '.coffee'
# 	sourcePath = 'modules/' + moduleName
# 	moduleFile = open(sourcePath, 'wb')
# 	moduleFile.write(source)
# 	moduleFile.close()

# 	localRepository.index.add([moduleName])
# 	localRepository.index.commit("initial commit")
# 	origin.fetch()
# 	origin.push()

# 	module.githubURL = githubRepository.clone_url
# 	module.save()

# 	return json.dumps( { 'state': 'success', 'message': 'Request for adding ' + name + ' successfully sent.', 'cloneURL': githubRepository.clone_url } )

# # @dajaxice_register
# @checkDebug
# def updateModule(request, name, source):
# 	try:
# 		module = Module.objects.get(name=name)
# 	except Module.DoesNotExist:
# 		return json.dumps( { 'state': 'error', 'message': 'The module with the name ' + name + ' does not exist.' } )

# 	sourcePath = name + '.coffee'
# 	output = open(sourcePath, 'wb')
# 	output.write(source)
# 	output.close()

# 	localRepository = Repo.init('modules/' + name)
# 	origin = localRepository.remote(name='origin')
# 	localRepository.index.add([sourcePath])
# 	localRepository.index.commit(commitDescription)
# 	origin.fetch()
# 	origin.push()

# 	return json.dumps( { 'state': 'success', 'message': 'Request for updating ' + name + ' successfully sent.' } )

# @dajaxice_register
@checkDebug
def getModules(request):
	modules = Module.objects(accepted=True).only('name', 'iconURL', 'githubURL', 'category', 'pk')
	return json.dumps( { 'state': 'success', 'modules': modules.to_json() } )

# @dajaxice_register
@checkDebug
def getModuleList(request):
	modules = Module.objects().only('name', 'iconURL', 'githubURL', 'thumbnailURL', 'description', 'owner', 'accepted', 'category', 'lastUpdate', 'pk')
	return json.dumps( { 'state': 'success', 'modules': modules.to_json() } )

# @dajaxice_register
@checkDebug
def getModuleSource(request, name=None, pk=None, accepted=None):
	if name:
		try:
			module = Module.objects.get(name=name)
		except Module.DoesNotExist:
			return json.dumps( { 'state': 'error', 'type': 'DoesNotExist', 'message': 'Module ' + name + ' does not exist.' } )
	elif pk:
		try:
			module = Module.objects.get(pk=pk)
		except Module.DoesNotExist:
			return json.dumps( { 'state': 'error', 'type': 'DoesNotExist', 'message': 'Module ' + pk + ' does not exist.' } )
	else:
		return json.dumps( { 'state': 'error', 'message': 'Module name and pk are null.' } )

	if accepted is not None:
		if accepted and not module.accepted:
			return json.dumps( { 'state': 'error', 'message': 'Module ' + module.name + ' is not accepted.' } )
		elif not accepted and module.accepted:
			return json.dumps( { 'state': 'error', 'message': 'Module ' + module.name + ' is accepted.' } )

	return json.dumps( { 'state': 'success', 'module': module.to_json() } )

# @dajaxice_register
@checkDebug
def getWaitingModules(request):
	if not isAdmin(request.user):
		return json.dumps( { 'state': 'error', 'message': 'You must be administrator to get the waiting modules.' } )

	latestModules = []

	acceptedModules = Module.objects(accepted=True)
	acceptedModulesNames = acceptedModules.scalar('repoName', 'name', 'lastUpdate')
	namesToLastUpdate = {}
	for module in acceptedModulesNames:
		namesToLastUpdate[module[0]] = { 'name': module[1], 'lastUpdate': module[2] }

	# search on github for repositories with 'commeUnDessein module' in the description
	repos = github.legacy_search_repos('commeUnDessein module')
	for githubRepository in repos:
		if githubRepository.name in namesToLastUpdate:
			if githubRepository.updated_at <= namesToLastUpdate[githubRepository.name]['lastUpdate']:
				continue
			name = namesToLastUpdate[githubRepository.name]['name']
		else:
			name = githubRepository.name
		try:
			source = base64.b64decode(githubRepository.get_file_contents('main.coffee').content)
		except:
			source = 'Impossible to open main.coffee'

		latestModules.append( {'name': name, 'repoName': githubRepository.name, 'source': source, 'owner': githubRepository.owner.url, 'githubURL': githubRepository.html_url } )

	# for module in modules:
	# 	githubRepository = commeUnDesseinOrg.get_repo(module.name)

	# 	if githubRepository.updated_at > module.lastUpdate:

	# 	# localRepository = Repo.clone_from(path_to='modules/', url=githubRepository.clone_url, branch='master')
	# 	# origin = localRepository.remote(name='origin')

	# 		modulePath = 'modules/' + module.name
	# 		localRepository = Repo.init(modulePath)

	# 		origin = localRepository.remote(name='origin')
	# 		origin.fetch()
	# 		origin.pull()

	# 		moduleFile = open(modulePath + '/' + module.name, 'rb')
	# 		module.source = moduleFile.read()
	# 		inputfile.close()

			# module.source = compileModule(modulePath)


	return json.dumps( { 'state': 'success', 'modules': latestModules } )

# @dajaxice_register
@checkDebug
def acceptModule(request, name, repoName, source, compiledSource, description=None, owner=None, githubURL=None, iconURL=None):
	if not isAdmin(request.user):
		return json.dumps( { 'state': 'error', 'message': 'You must be administrator to get the waiting modules.' } )

	try:
		module = Module.objects.get(name=name)
		module.lastUpdate = datetime.datetime.now()
		module.source = source
		module.compiledSource = compiledSource
		module.accepted = True
		module.save()
	except Module.DoesNotExist:
		if not owner:
			return json.dumps( { 'state': 'error', 'message': 'Module does not exist and owner was not provided.' } )
		module = Module(owner=owner, name=name, repoName=repoName, description=description, source=source, compiledSource=compiledSource, githubURL=githubURL, iconURL=iconURL, accepted=True)
		module.save()

	return json.dumps( { 'state': 'success', 'message': 'The module ' + module.name + ' was accepted.' } )

# @dajaxice_register
@checkDebug
def deleteModule(request, name=None, pk=None, repoName=None):

	try:
		module = Module.objects.get(name=name)
		githubRepository = commeUnDesseinOrg.get_repo(repoName or module.repoName)
		githubRepository.delete()
		module.delete()
	except Module.DoesNotExist:
		if pk:
			try:
				module = Module.objects.get(pk=pk)
				module.delete()
			except Module.DoesNotExist:
				return json.dumps( { 'state': 'Warning', 'message': 'Module ' + name + ' does not exist.' } )
		githubRepository = commeUnDesseinOrg.get_repo(repoName or name)
		githubRepository.delete()

	return json.dumps( { 'state': 'success', 'message': 'Module deleted.' } )


# --- tools --- #

# @dajaxice_register
@checkDebug
def addTool(request, name, className, source, compiledSource, isTool):

	try:
		tool = Tool(owner=request.user.username, name=name, className=className, source=source, compiledSource=compiledSource, isTool=isTool)
	except OperationError:
		return json.dumps( { 'state': 'error', 'message': 'A tool with the name ' + name + ' or the className ' + className + ' already exists.' } )
	tool.save()
	return json.dumps( { 'state': 'success', 'message': 'Request for adding ' + name + ' successfully sent.' } )

# @dajaxice_register
@checkDebug
def updateTool(request, name, className, source, compiledSource):

	try:
		tool = Tool.objects.get(name=name)
	except Tool.DoesNotExist:
		return json.dumps( { 'state': 'error', 'message': 'The tool with the name ' + name + ' does not exist.' } )

	tool.nRequests += 1
	tool.save()
	newName = name + str(tool.nRequests)
	newClassName = className + str(tool.nRequests)
	newTool = Tool(owner=request.user.username, name=newName, originalName=name, originalClassName=className, className=newClassName, source=source, compiledSource=compiledSource, isTool=tool.isTool)
	newTool.save()

	return json.dumps( { 'state': 'success', 'message': 'Request for updating ' + name + ' successfully sent.' } )

# @dajaxice_register
@checkDebug
def getTools(request):
	tools = Tool.objects(accepted=True)
	return json.dumps( { 'state': 'success', 'tools': tools.to_json() } )

# --- admin --- #

# @dajaxice_register
@checkDebug
def getWaitingTools(request):
	if not isAdmin(request.user):
		return json.dumps( { 'state': 'error', 'message': 'You must be administrator to get the waiting tools.' } )
	tools = Tool.objects(accepted=False)
	return json.dumps( { 'state': 'success', 'tools': tools.to_json() } )

# @dajaxice_register
@checkDebug
def acceptTool(request, name):
	if not isAdmin(request.user):
		return json.dumps( { 'state': 'error', 'message': 'You must be administrator to accept tools.' } )
	try:
		tool = Tool.objects.get(name=name)
	except Tool.DoesNotExist:
		return json.dumps( { 'state': 'success', 'message': 'New tool does not exist.' } )
	if tool.originalName:
		try:
			originalTool = Tool.objects.get(name=tool.originalName)
		except Tool.DoesNotExist:
			return json.dumps( { 'state': 'success', 'message': 'Original tool does not exist.' } )
		originalTool.source = tool.source
		originalTool.compiledSource = tool.compiledSource
		originalTool.save()
		tool.delete()
	else:
		tool.accepted = True
		tool.save()
	return json.dumps( { 'state': 'success' } )

# --- loadSite --- #

# @dajaxice_register
@checkDebug
def loadSite(request, siteName):
	try:
		site = Site.objects.get(name=siteName)
	except:
		return { 'state': 'error', 'message': 'Site ' + siteName + ' does not exist.' }
	return { 'state': 'success', 'box': site.box.to_json(), 'site': site.to_json() }

# --- payment signal --- #

def updateUserCommeUnDesseinCoins(sender, **kwargs):
	ipn_obj = sender

	print "updateUserCommeUnDesseinCoins"

	if ipn_obj.payment_status == "Completed":

		data = json.loads(ipn_obj.custom)

		import pdb; pdb.set_trace()

		# profile = User.objects.get(username=data['user']).profile
		# profile.commeUnDesseinCoins += ipn_obj.num_cart_items

		# Fails with: OperationalError: no such column: user_profile.commeUnDesseinCoins:
		# UserProfile.objects.filter(user__username=data['user']).update(commeUnDesseinCoins=F('commeUnDesseinCoins')+1000*ipn_obj.num_cart_items)
		# so instead:

		try:
			userProfile = User.objects.get(username=data['user']).profile
			userProfile.commeUnDesseinCoins += 1000*ipn_obj.num_cart_items
			userProfile.save()
		except UserProfile.DoesNotExist:
			pass

	else:
		print "payment was not successful: "
		print ipn_obj.payment_status

payment_was_successful.connect(updateUserCommeUnDesseinCoins)

def paymentWasFlagged(sender, **kwargs):
	ipn_obj = sender
	print "paymentWasFlagged"

payment_was_flagged.connect(paymentWasFlagged)

def paymentWasRefunded(sender, **kwargs):
	ipn_obj = sender
	print "paymentWasRefunded"

payment_was_refunded.connect(paymentWasRefunded)

def paymentWasReversed(sender, **kwargs):
	ipn_obj = sender
	print "paymentWasReversed"

payment_was_reversed.connect(paymentWasReversed)
