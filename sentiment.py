# potential idea, think about having a sentiment to return with abnormal number of
# rejections, such that the return may be used to ascertain if we need to ask the
# buyer about what is wrong, or perform some other service

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
		self.validTypes = ['haggle', 'dealReject', 'dealAccept']

	def updateHistory(self, newEvent):
		if newEvent.type not in validTypes:
			raise KeyError('invalid type')
		else:
			self.history.append(newEvent)

	def computeStrategy(self):
		# this is just a simple concept for now
		haggleCount = 0
		accepts = 0
		rejects = 0
		for event in self.history:
			if event.type == 'haggle':
				haggleCount += 1
			elif event.type == 'dealAccept':
				accepts += 1
			elif event.type == 'dealReject':
				rejects += 1
		# make sure this sorting works properly
		counts = [(haggleCount, 'haggle'), (accepts, 'accept'), (rejects, 'reject')]
		counts.sort()
		prevMax = 0
		strategy = counts[0][1]
		for i in range(0, len(self.validTypes)):
			if counts[i][0] == prevMax:
				return 'indeterminate'
			elif counts[i][0] > prevMax:
				prevMax = counts[i][0]

		return strategy

	def getStrategy(self):
		return self.computeStrategy()