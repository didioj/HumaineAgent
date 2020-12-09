Features:
* NotUnderstood intent for human errors
* BundleReqest to form best deal
* Bulk deal
* Better personality
* Improved haggling intent
* Greedy and 
* Be careful of what the other agent is offering

To do:
* Bugs: Modify other agent's sellOffer price with ours
* Store old bulk deals so don't keep offering. reset at new buyrequest? 
* Add bulk deal to reactToEnemy
* Rejection offer with no addressee should be directed to us. Talking to me?
* Clear bidHistory at StartRound

## 12/6/2020
To do:
* Bugs:
	* If accept/reject other seller on BulkOffer, then don't clear bidHistory
* Bulk deal sometimes not better
* Prioritize accepting bulk deals
	* Save context of original offer to list so don't ask again for this context
* Reminder that we can sell ingredients based on bundle
* When responding, ignore BidHistory change by other agent unless it's an offer
	* When addressing human message and other agent sends a message
		check the type of message. 
		If it's an offer, then check context and cancel current response if match
		If it's not an offer, then continue with current response

Completed:
* Clear out bidHistory at startRound [agent-py.py - startRound]
* Added acceptedBulkOfferMessage for when Buyer reacted with `AcceptOffer` 
	right after we proposed a `BulkOffer` [agent-py.py - acceptedBulkOfferMessage, reactToBuyer]
* Finish rejectedBulkOfferMessage [agent-py.py - rejectedBulkOfferMessage, reactToBuyer]
* Tested accepting bulk offer with single agent
* Tested rejecting bulk offer with single agent
* Prioritize accepting bulk deals
	* Are you interested in deal?
	* Classify response as acceptOffer and rejectOffer
	* Save both regular offer and bulk offer in BidHistory.
		* If detect bulk offer,
			* Determine whether the human accepted bulk offer
			* Reiterate the offer the buyer chose

## 12/3/2020
* Pull from personality branch 
* Return in assembleBidResponse - [agent-py.py - assembleBidResponse]

## 12/2/2020
* Classify unknown goods and messages as `NotUnderstood` [agent-py.py - processMessage]
	* Filter out `cake` and `pancake`
* Rejection: I want better offer, is there better offer, too expensive [Watson Assistant - rejectOffer]

## 12/1/2020
* bidHistory switch context and reject properly **** 
	* Testing:
		* If rejection, need to find our last offer
		* If quantity given, pull up all offers for that quantity
		* relevant offers is correct (use our last offer)
		* my recent offers is correct
		* rejection refers to the correct offer
		* context switch works (use new given quantity)
		* rejection fails if no offer
* If buyer doesn't specify quantity of cake/pancakes, default to 1 [extract-bid.py - extractOfferFromEntities]
* Buyer can specify bundle request and individual goods [agent-py.py - processMessage]
	* Classify `BundleRequest` correctly [extract-bid.py - interpretMessage]
* Make sure bulk price is lower than original price 
	* Add normal price for bulk to bidHistory as NormalBulkOffer [agent-py.py - bulkPriceMessage]
	* Reduce bulk price in generateBid [agent-py.py - generateBid]
	* Say how much the buyer is saving [agent-py.py - bulkPriceMessage]
* Fixed bug reject most recent offer instead of first offer [agent-py.py - generateBid]
 
## 11/29/2020
* bulkPriceMessage - returns agent message with regular offer and bulk price offer [agent-py.py - bulkPriceMessage]
* Added `keyword` entity to Watson Assistant so we can check which offer the buyer wants
* Include a list of keywords in interpretation [extract-bid.py - interpretMessage]
* Pass needed variables from `processMessage` to `reactTo...` [agent-py.py - processMessage]
* Return `reactTo...` in processMessage [agent-py.py - processMessage]

## 11/24/2020
* Check that `intents` isn't empty [extract-bid.py - interpretMessage]
* Ask Human to clarify if we can't classify the intent and messages not addressed to other agent
	(empty intent or uncertain) [agent-py.py - processMessage]
* Added new clarifyMessages (Can you rephrase your request?, 
	I'm not sure what you're asking for.) [agent-py.py]
* Changed `if len(bidHistory[speaker])` to `if bidHistory[speaker]` 
	in case bidHistory[speaker] is None [agent-py.py - processMessage]
* Added `bundle` entity and `BundleRequest` intent to Watson Assistant
* Extract `bundle` entity from entityList [extract-bid.py - extractOfferFromEntities]
* Detect `BundleRequest` [agent-py.py - processMessage]
* Convert `bundle` entity to ingredients [agent-py.py - processMessage]
To do:
* Context change!!!!!
* Test: only allow accept request when addresssed to us
* Add greeting intent?
Note: 
* BundleRequest response for both addressed to us and not addressed to us

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

