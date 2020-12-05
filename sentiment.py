import math

class Event:
	def __init__(self, newSender=None, newRecipient=None, newType=None):
		self.sender = newSender
		self.recipient = newRecipient
		self.type = newType

	def getSender(self):
		return self.sender

	def getRecipient(self):
		return self.recipient

	def getType(self):
		return self.Type

class Sentiment:
	def __init__(self):
		self.history = []
		self.validTypes = ['haggle', 'dealAccept']

	def updateHistory(self, newEvent):
		if newEvent.type not in validTypes:
			raise KeyError('invalid type')
		else:
			self.history.append(newEvent)

	def computeStrategy(self):
		# this is just a simple concept for now
		haggleCount = 0
		accepts = 0
		for event in self.history:
			if event.type == 'haggle':
				haggleCount += 1
			elif event.type == 'dealAccept':
				accepts += 1
		totalEvents = haggleCount + accepts
		# make sure this sorting works properly
		threshold = 0.15
		hagglePercent = haggleCount/totalEvents
		acceptPercent = accepts/totalEvents

		percentDifference = math.abs(hagglePercent - acceptPercent)

		if percentDifference > threshold:
			if hagglePercent > acceptPercent:
				return 'haggle'
			else:
				return 'greedy'
		else:
			return 'indeterminate'

	def getStrategy(self):
		return self.computeStrategy()