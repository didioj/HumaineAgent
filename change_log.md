## 10/21/2020
* Added print statements to the beginning and end of every function
* Set `price = {'value':0, 'unit':'USD'}` if buyer did not offer a price [extract-bid.py - extractPrice]
* Set `addressee  = None` if no addressee specified [extract-bid.py - extractAddressee]
* Fixed intent to `cmd = {'type': "AcceptOffer"}` [extract-bid.py - interpretMessage]
* Fixed receiveMessage to allow this agent's message to be processed [agent-py.py - receiveMessage]