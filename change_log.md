## 11/24/2020
* Check that `intents` isn't empty [extract-bid.py - interpretMessage]
* Ask Human to clarify if we can't classify the intent and messages not addressed to other agent
	(empty intent or uncertain) [agent-py.py - processMessage]
* Added new clarifyMessages (Can you rephrase your request?, I'm not sure what you're asking for.) [agent-py.py]
* Changed `if len(bidHistory[speaker])` to `if bidHistory[speaker]` in case bidHistory[speaker] is None [agent-py.py - processMessage]
To do:
* Add greeting intent

## 11/19/2020
* Merged Ling to master
* Added instructions

======================================================================================

## To do:
* remove from bidHistory if wasn't accepted
* Test rejectoffer

## Considerations:
* Fix bidHistory on messageRejections
* Make more human
* Detect more general intent. Deal with unknown intent.
	* Filter out price and quantity goods
	* Add default intents from 
* Detect context change
* Better reply (units, commas, 'and')
* Ask "how can I negotiate with you"/ ask how to use
	* At start round, list things we can do
* Inquire about inventory
* Ask what do you sell
	* "Do you have"
* Ask about quality and pricing
* Ask about sales/ special deals
* Ask about origins
* Automatic discount when over a certain price
* Proper rejection to clear history
* Sentient classifier for intent 
* Haggle intent
* Sell bundle for cake/pancake
	* reject bundle and only buy item
	* Scale up for bundle pancake/cake, additives
* "I accept"

* Response to different messages:
	* General
	* No quantity
* Reject and increase price if buyer offer is too low
* Track what the user bought to make better deals with? 
* If other agent makes a SellOffer
	* Counter it or
	* The lowest I can go is $ because ... 
	* Make a different deal

## 10/27/2020
* Changed bidBlock['type'] == 'Offer' to bidBlock['type'] in offerTypes

## 10/26/2020
* When reducing price, always reduce markupRatio by 10% to 25%
* Add price details to MinOffer in interpretMessage
* Address human when other agent talks
* Recognize confirmations then clear bidHistory
* Wait 2 seconds after receiving message from other agent
* Added changes from sneaky branch
	* Wait 3 seconds after receiving general message from human. Then check if history changed. 
	* If yes, do nothing.
	* If no, make an offer

## 10/25/2020
* Note: Formatting for bidHistory, interpretation, offer
``` bidHistory: {'Human': [{'quantity': {'milk': 1}, 'type': 'BuyRequest', 'metadata': {'speaker': 'Human', 'addressee': 'Watson', 'text': 'Watson I want 1 cup of milk', 'role': 'buyer', 'environmentUUID': 'abcdefg', 'timestamp': 1603411644692, 'timeStamp': 1603411646.5213463}}]},
	interpretation: {'type': 'RejectOffer', 'metadata': {'speaker': 'Human', 'addressee': 'Watson', 'text': "Watson I don't like the offer", 'role': 'buyer', 'environmentUUID': 'abcdefg', 'timestamp': 1603411677110, 'timeStamp': 1603411677.8419251}}
	offer: {'quantity': {'milk': 1}, 'price': {'value': 0.48, 'unit': 'USD'}, 'type': 'SellOffer', 'metadata': {'text': 'How about if I sell you 1 milk for 0.48 USD.', 'speaker': 'Watson', 'role': 'seller', 'addressee': 'Human', 'environmentUUID': 'abcdefg', 'timestamp': 1603411677799.0557, 'timeStamp': 1603411678.442418}}
```
* Fixed naming for myRecentOffer and myLastPrice
* Chance of trying to convince buyer to accept price if buyer rejects it

## 10/22/2020
* If other agent makes an offer:
	* Offer a lower price
	* Match their offer if it's lower than our minMarkupRatio
	* Taunt that their products are bad if they're losing money with their offer

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

