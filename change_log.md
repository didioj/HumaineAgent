## 10/21/2020
### Changes
* Added print statements to the beginning and end of every function
* Check for `'price' in bundle` [extract-bid.py - calculateUtilityAgent]
* Set `addressee  = None` if no addressee specified [extract-bid.py - extractAddressee]
* Fixed typo to `cmd = {'type': "AcceptOffer"}` [extract-bid.py - interpretMessage]
* Fixed receiveMessage to allow this agent's message to be processed [agent-py.py - receiveMessage]
* Fixed `speaker not in bidHistory` [agent-py.py - procesMessage]
* Add `quantity` from recent offer to RejectOffer to calculate utility [agent-py.py - generateBid]
* Fixed typo to `rationale` [agent-py.py - receiveMessage]
* If buyer rejects offer, reduce markup and make another offer
* When reach a minimum markup, return a "minOfferMessage"
* Buyer can still accept offer after seeing the "minOfferMessage"

### To do:
* Respond when buyer not addressing anyone
* Respond when buyer is addressing other agent