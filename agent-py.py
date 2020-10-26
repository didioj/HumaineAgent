# Imports
from flask import Flask
from flask import request
from functools import reduce
import requests
import importlib
import json
import sys
import time
import math
import random
app = Flask(__name__)

conversation = importlib.import_module('conversation')
extract_bid = importlib.import_module('extract-bid')

# Global variables / settings
appSettings = None
with open('./appSettings.json') as f:
    appSettings = json.load(f)
myPort = appSettings['defaultPort']
agentName = appSettings['name'] or "Agent007"
defaultRole = 'buyer'
defaultSpeaker = 'Jeff'
defaultEnvironmentUUID = 'abcdefg'
defaultAddressee = agentName
defaultRoundDuration = 600

# fetch the port number
for i in range(len(sys.argv)):
    if sys.argv[i] == "--port":
        myPort = sys.argv[i + 1]

# predefined responses
rejectionMessages = [
  "No thanks. Your offer is much too low for me to consider.",
  "Forget it. That's not a serious offer.",
  "Sorry. You're going to have to do a lot better than that!",
  "That is daylight ROBBERY!"
]
minOfferMessages = [
  "That's the best I can do. You won't find a better deal out there!"
]
acceptanceMessages = [
  "You've got a deal! I'll sell you",
  "You've got it! I'll let you have",
  "I accept your offer. Just to confirm, I'll give you"
]
confirmAcceptanceMessages = [
  "I confirm that I'm selling you ",
  "I'm so glad! This is to confirm that I'll give you ",
  "Perfect! Just to confirm, I'm giving you "
]
negotiationState = {
  "active": False,
  "startTime": None,
  "roundDuration": defaultRoundDuration
}

utilityInfo = None
bidHistory = {}

# ************************************************************************************************************ #
# REQUIRED APIs
# ************************************************************************************************************ #

# API route that receives utility information from the environment orchestrator. This also
# triggers the start of a round and the associated timer.
@app.route('/setUtility', methods=['POST'])
def setUtility():
    print("Entering setUtility")
    if request.json:
        global utilityInfo
        utilityInfo = request.json
        print("Info received:", utilityInfo)
        global agentName
        agentName = utilityInfo['name'] or agentName
        msg = {
            'status': 'Acknowledged',
            'utility': utilityInfo
        }
        print("Message sending:", msg)
        return msg
    else:
        msg = {
            'status': "Failed; no message body",
            'utility': None
        }
        print("Returning message:", msg)
        return msg


# API route that tells the agent that the round has started.
@app.route('/startRound', methods=['POST'])
def startRound():
    print("Entering startRound")
    bidHistory = {}
    if request.json:
        print("Info received:", request.json)
        negotiationState['roundDuration'] = request.json['roundDuration'] or negotiationState['roundDuration']
        negotiationState['roundNumber'] = request.json['roundNumber'] or negotiationState['roundNumber']
    negotiationState['active'] = True
    negotiationState['startTime'] = (time.time() * 1000)
    negotiationState['stopTime'] = negotiationState['startTime'] + (1000 * negotiationState['roundDuration'])
    msg = {
        'status': 'Acknowledged'
    }
    print("Returning message:", msg)
    return msg


# API route that tells the agent that the round has ended.
@app.route('/endRound', methods=['POST'])
def endRound():
    print("Entering endRound")
    negotiationState['active'] = False
    negotiationState['endTime'] = (time.time() * 1000)
    msg = {
        'status': 'Acknowledged'
    }
    print("Returning message:", msg)
    return msg


# POST API that receives a message, interprets it, decides how to respond (e.g. Accept, Reject, or counteroffer),
# and if it desires sends a separate message to the /receiveMessage route of the environment orchestrator
@app.route('/receiveMessage', methods=['POST'])
def receiveMessage():
    print("Entering receiveMessage")
    timeRemaining = (negotiationState['stopTime'] - (time.time() * 1000)) / 1000
    if timeRemaining <= 0:
        negotiationState['active'] = False
    print("Remaining Time:", timeRemaining)
    print("Info received:", request.json)
    response = None
    if not request.json:
        response = {
            'status': "Failed; no message body"
        }
    elif negotiationState['active']: # We received a message and time remains in the round.
        message = request.json
        message['speaker'] = message['speaker'] or defaultSpeaker
        message['addressee'] = message['addressee']
        message['role'] = message['role'] or message['defaultRole']
        message['environmentUUID'] = message['environmentUUID'] or defaultEnvironmentUUID
        response = { # Acknowledge receipt of message from the environment orchestrator
            'status': "Acknowledged",
            'interpretation': message
        }
        if message['speaker'] == agentName:
            print("This message is from me!")
        #else:
        bidMessage = processMessage(message)
        print("Bid message from processMessage:", bidMessage)
        if bidMessage: # If warranted, proactively send a new negotiation message to the environment orchestrator
            print("Sending message:", bidMessage)
            sendMessage(bidMessage)
    else: # Either there's no body or the round is over.
        response = {
            'status': "Failed; round not active"
        }
    print("Returning response:", response)
    return response


# POST API that receives a rejection message, and decides how to respond to it. If the rejection is based upon
# insufficient funds on the part of the buyer, generate an informational message to send back to the human, as a courtesy
# (or rather to explain why we are not able to confirm acceptance of an offer).
@app.route('/receiveRejection', methods=['POST'])
def receiveRejection():
    print("Entering receiveRejection")
    timeRemaining = (negotiationState['stopTime'] - (time.time() * 1000)) / 1000
    if timeRemaining <= 0:
        negotiationState['active'] = False
    print("Remaining Time:", timeRemaining)
    print("Info received:", request.json)
    response = None
    if not request.json:
        response = {
            'status': 'Failed; no message body'
        }
    elif negotiationState['active']: # We received a message and time remains in the round.
        message = request.json
        print("Received message:", message)
        response = { # Acknowledge receipt of message from the environment orchestrator
            'status': 'Acknowledged',
            'message': message
        }
        if (message['rationale']
            and message['rationale'] == 'Insufficient budget'
            and message['bid']
            and message['bid']['type'] == "Accept"): # We tried to respond with an accept, but were rejected.
                                                     # So that the buyer will not interpret our apparent silence as rudeness, 
                                                     # explain to the Human that he/she were rejected due to insufficient budget.
            msg2 = json.loads(json.dumps(message))
            del msg2['rationale']
            del msg2['bid']
            msg2['timestamp'] = (time.time() * 1000)
            msg2['text'] = "I'm sorry, " + msg2['addressee'] + ". I was ready to make a deal, but apparently you don't have enough money left."
            print("Sending message:", msg2)
            sendMessage(msg2)
    else: # Either there's no body or the round is over.
        response = {
            'status': "Failed; round not active"
        }
    print("Returning response:", response)
    return response

# ************************************************************************************************************ #
# Non-required APIs (useful for unit testing)
# ************************************************************************************************************ #

# GET API route that simply calls Watson Assistant on the supplied text message to obtain intent and entities
@app.route('/classifyMessage', methods=['GET'])
def classifyMessageGet():
    print("Entering classifyMessageGet")
    data = request.json
    print("Info received:", data)
    if data['text']:
        text = data['text']
        message = { # Hard-code the speaker, role and envUUID
            'text': text,
            'speaker': defaultSpeaker,
            'addressee': defaultAddressee,
            'role': defaultRole,
            'environmentUUID': defaultEnvironmentUUID
        }
        waResponse = conversation.classifyMessage(message)
        print("Returning response:", waResponse)
        return waResponse


# POST API route that simply calls Watson Assistant on the supplied text message to obtain intents and entities
@app.route('/classifyMessage', methods=['POST'])
def classifyMessagePost():
    print("Entering classifyMessagePost")
    print("Info received:", data)
    if request.json:
        message = request.json
        message['speaker'] = message['speaker'] or defaultSpeaker
        message['addressee'] = message['addressee'] or None
        message['role'] = message['role'] or message['defaultRole']
        message['environmentUUID'] = message['environmentUUID'] or defaultEnvironmentUUID
        waResponse = conversation.classifyMessage(message, message['environmentUUID'])
        print("Returning response:", waResponse)
        if waResponse:
            return waResponse
        return "error classifying post"


# POST API route that is similar to /classify Message, but takes the further
# step of determining the type and parameters of the message (if it is a negotiation act),
# and formatting this information in the form of a structured bid.
@app.route('/extractBid', methods=['POST'])
def extractBid():
    print("Entering extractBid")
    print("Info received:", data)
    if request.json:
        message = request.json
        message['speaker'] = message['speaker'] or defaultSpeaker
        message['addressee'] = message['addressee'] or None
        message['role'] = message['role'] or message['defaultRole']
        message['environmentUUID'] = message['environmentUUID'] or defaultEnvironmentUUID
        extractedBid = extract_bid.extractBidFromMessage(message)
        print("Returning bid:", extractedBid)
        if extractedBid:
            return extractedBid
        return "error extracting bid"


# API route that reports the current utility information.
@app.route('/reportUtility', methods=['GET'])
def reportUtility():
    print("Entering reportUtility")
    print("Returning utilityInfo:", utilityInfo)
    if utilityInfo:
        return utilityInfo
    else:
        return {'error': 'utilityInfo not initialized'}


# ******************************************************************************************************* #
# ******************************************************************************************************* #
#                                               Functions
# ******************************************************************************************************* #
# ******************************************************************************************************* #


# ******************************************************************************************************* #
#                                         Bidding Algorithm Functions                                     #
# ******************************************************************************************************* #

# *** mayIRespond()                 
# Choose not to respond to certain messages, either because the received offer has the wrong role
# or because a different agent is being addressed. Note that this self-censoring is stricter than that required
# by competition rules, i.e. this agent is not trying to steal a deal despite this being permitted under the
# right circumstances. You can do better than this!
def mayIRespond(interpretation):
    print("Entering mayIRespond")
    print("Returning reponse:", (interpretation and interpretation['metadata']['role'] and
            (interpretation['metadata']['addressee'] == agentName or not interpretation['metadata']['addressee']) ))
    return (interpretation and interpretation['metadata']['role'] and
            (interpretation['metadata']['addressee'] == agentName or not interpretation['metadata']['addressee']) )


# *** calculateUtilitySeller() 
# Calculate utility for a given bundle of goods and price, given the utility function
def calculateUtilityAgent(utilityInfo, bundle):
    print("Entering calculateUtilityAgent")
    print("Received utilityInfo:", utilityInfo)
    print("Received bundle:", bundle)
    
    utilityParams = utilityInfo['utility']
    util = 0
    # check added here in case no price given
    if 'price' in bundle:
        price = bundle['price']['value']
    else:
        price = 0

    if bundle['quantity']:
        util = price
        if 'price' in bundle:
            unit = bundle['price']['value']
        else:
            unit = None
        if not unit: # Check units -- not really used, but a good practice in case we want
                     # to support currency conversion some day
            print("no currency units provided")
        elif unit == utilityInfo['currencyUnit']:
            print("Currency units match")
        else:
            print("Currency units do not match")
    
    for good in bundle['quantity'].keys():
        util -= utilityParams[good]['parameters']['unitcost'] * bundle['quantity'][good]
    
    print("Returning utility:",util)
    return util


# *** generateBid()
# Given a received offer and some very recent prior bidding history, generate a bid
# including the type (Accept, Reject, and the terms (bundle and price).
def generateBid(offer):
    print("Entering generateBid")
    print("Received offer:", offer)
    minDicker = 0.10
    buyerName = offer['metadata']['speaker']
    
    for bidBlock in bidHistory[buyerName]:
        print("BidBlock:", bidBlock)
        print("BidBlock['type']:", bidBlock['type'])
    
    myRecentOffers = [bidBlock for bidBlock in bidHistory[buyerName] if bidBlock['type'] == "SellOffer"]
    print("My recent offers:",myRecentOffers)
    myLastPrice = None
    if len(myRecentOffers):
        myLastPrice = myRecentOffers[len(myRecentOffers) - 1]['price']['value']
    print("My last price:",myLastPrice)
    
    timeRemaining = (negotiationState['stopTime'] - (time.time() * 1000)) / 1000
    print("Remaining time:",timeRemaining)
    
    # need to add quantities to RejectOffer to calculate utility
    if offer['type'] == 'RejectOffer':
        offer['quantity'] = myRecentOffers[0]['quantity']
    utility = calculateUtilityAgent(utilityInfo, offer)
    print("Utility received:",utility)

    # Note that we are making no effort to upsell the buyer on a different package of goods than what they requested.
    # It would be legal to do so, and perhaps profitable in some situations -- consider doing that!

    bid = {
        'quantity': offer['quantity']
    }

    if 'price' in offer and 'value' in offer['price']: # The buyer included a proposed price, which we must take into account
        print("Buyer proposed price! Going to consider it based on profit")
        bundleCost = offer['price']['value'] - utility
        print("Calculated bundleCost:",bundleCost)
        markupRatio = utility / bundleCost
        print("Calculated markupRatio::", markupRatio)

        if (markupRatio > 2.0
            or (myLastPrice != None
            and abs(offer['price']['value'] - myLastPrice) < minDicker)): # If our markup is large, accept the offer

            bid['type'] = 'Accept'
            bid['price'] = offer['price']

        elif markupRatio < -0.5: # If buyer's offer is substantially below our cost, reject their offer
            bid['type'] = 'Reject'
            bid['price'] = None
        else: # If buyer's offer is in a range where an agreement seems possible, generate a counteroffer
            bid['type'] = 'SellOffer'
            bid['price'] = generateSellPrice(bundleCost, offer['price'], myLastPrice, timeRemaining)
            if bid['price']['value'] < offer['price']['value'] + minDicker:
                bid['type'] = 'Accept'
                bid['price'] = offer['price']
    else: # The buyer didn't include a proposed price, leaving us free to consider how much to charge.
    # Set markup between 2 and 3 times the cost of the bundle and generate price accordingly.
        print("Buyer did not propose price. Going to generate price")
        # if lowering last offer, then reduce last markupRatio
        if myLastPrice:
            # if not making enough profit, set type to MinMarkup
            minMarkupRatio = 0.5
            if myLastPrice/utility*-1 <= minMarkupRatio+1:
                print("Reached minMarkupRatio:", myLastPrice/utility*-1)
                bid['type'] = 'MinMarkup'
                bid['price'] = None
                return bid
            
            # reversed the calculation to find the previous random.random() value
            lastMarkupRatio = 1 - myLastPrice/utility - 2
            print("Calcuated last markupRatio:", lastMarkupRatio)
            markupRatio = 2.0 + (lastMarkupRatio * random.random())
        else: 
            markupRatio = 2.0 + random.random()
        print("Going to markup price by", markupRatio)
        bid['type'] = 'SellOffer'
        bid['price'] = {
            'unit': utilityInfo['currencyUnit'],
            'value': quantize((1.0 - markupRatio) * utility, 2)
        }
    print("Returning bid:", bid)
    return bid


# *** generateSellPrice()
# Generate a bid price that is sensitive to cost, negotiation history with this buyer, and time remaining in round
def generateSellPrice(bundleCost, offerPrice, myLastPrice, timeRemaining):
    print("Entering generateSellPrice")
    print("Received bundleCost:", bundleCost)
    print("Received offerPrice:", offerPrice)
    print("Received myLastPrice:", myLastPrice)
    print("Received timeRemaining:", timeRemaining)
    minMarkupRatio = 0
    maxMarkupRatio = 0
    markupRatio = offerPrice['value']/bundleCost - 1.0
    if myLastPrice != None:
        maxMarkupRatio = myLastPrice/bundleCost - 1.0
    else:
        maxMarkupRatio = 2.0 - 1.5 * (1.0 - timeRemaining/negotiationState['roundDuration']) # Linearly decrease max markup ratio towards 
                                                                                             # just 0.5 at the conclusion of the round
    minMarkupRatio = max(markupRatio, 0.20)
    
    minProposedMarkup = max(minMarkupRatio, markupRatio)
    newMarkupRatio = minProposedMarkup + random.random() * (maxMarkupRatio - minProposedMarkup)
    
    price = {
        'unit': offerPrice['unit'],
        'value': (1.0 + newMarkupRatio) * bundleCost
    }

    price['value'] = quantize(price['value'], 2)
    print("Returning offering price:", price)
    return price


# *** processMessage() 
# Orchestrate a sequence of
# * classifying the message to obtain and intent and entities
# * interpreting the intents and entities into a structured representation of the message
# * determining (through self-policing) whether rules permit a response to the message
# * generating a bid (or other negotiation act) in response to the offer
def processMessage(message):
    print("Entering processMessage")
    print("Received message:", message)
    
    classification = conversation.classifyMessage(message)
    print("Received message classification:", classification)
    
    classification['environmentUUID'] = message['environmentUUID']
    interpretation = extract_bid.interpretMessage(classification)
    print("Received interpretation:", interpretation)

    speaker = interpretation['metadata']['speaker']
    addressee = interpretation['metadata']['addressee']
    role = interpretation['metadata']['role']

    if speaker == agentName: # The message was from me; this means that the system allowed it to go through.
        # If the message from me was an accept or reject, wipe out the bidHistory with this particular negotiation partner
        # Otherwise, add the message to the bid history with this negotiation partner
        print("Received own message")
        if interpretation['type'] == 'AcceptOffer' or interpretation['type'] == 'RejectOffer':
            bidHistory[addressee] = [] # originally was none, but that created lots of problems and doesn't make sense
            print("Offer complete. Clearing history")
        else:
            print("Adding message to bidHistory")
            if bidHistory[addressee]:
                bidHistory[addressee].append(interpretation)
            print("bidHistory:", bidHistory)
    elif addressee == agentName and role == 'buyer': # Message was addressed to me by a buyer; continue to process
        print("Message from buyer to me")
        messageResponse = {
            'text': "",
            'speaker': agentName,
            'role': "seller",
            'addressee': speaker,
            'environmentUUID': interpretation['metadata']['environmentUUID'],
            'timestamp': (time.time() * 1000)
        }
        if interpretation['type'] == 'AcceptOffer': # Buyer accepted my offer! Deal with it.
            print("Buyer accepted offer")
            print("Checking bidHistory:", bidHistory)
            if bidHistory[speaker] and len(bidHistory[speaker]): # I actually did make an offer to this buyer;
                                                                 # fetch details and confirm acceptance
                bidHistoryIndividual = [bid for bid in bidHistory[speaker] if bid['metadata']['speaker'] == agentName and bid['type'] == "SellOffer"]
                if len(bidHistoryIndividual):
                    acceptedBid = bidHistoryIndividual[-1]
                    bid = {
                        'price': acceptedBid['price'],
                        'quantity': acceptedBid['quantity'],
                        'type': "Accept"
                    }
                    messageResponse['text'] = translateBid(bid, True)
                    messageResponse['bid'] = bid
                    bidHistory[speaker] = [] # originally was none, but that created lots of problems and doesn't make sense
                else: # Didn't have any outstanding offers with this buyer
                    messageResponse['text'] = "I'm sorry, but I'm not aware of any outstanding offers."
            else: # Didn't have any outstanding offers with this buyer
                messageResponse['text'] = "I'm sorry, but I'm not aware of any outstanding offers."
            print("Returning message:", messageResponse)
            return messageResponse
        elif interpretation['type'] == 'RejectOffer': # The buyer claims to be rejecting an offer I made; deal with it
            print("Buyer rejected offer")
            if bidHistory[speaker] and len(bidHistory[speaker]): # Check whether I made an offer to this buyer
                bidHistoryIndividual = [bid for bid in bidHistory[speaker] if bid['metadata']['speaker'] == agentName and bid['type'] == "SellOffer"]
                if len(bidHistoryIndividual):
                    if speaker not in bidHistory:
                        bidHistory[speaker] = []
                    bidHistory[speaker].append(interpretation)
                    bid = generateBid(interpretation) # Generate bid based on message interpretation, utility,
                                                      # and the current state of negotiation with the buyer
                    bidResponse = {
                        'text': translateBid(bid, False), # Translate the bid into English
                        'speaker': agentName,
                        'role': "seller",
                        'addressee': speaker,
                        'environmentUUID': interpretation['metadata']['environmentUUID'],
                        'timestamp': (time.time() * 1000),
                        'bid': bid
                    }
                    # messageResponse['text'] = "I'm sorry you rejected my bid. I hope we can do business in the near future."
                    # TODO: make another offer
                    # print("Buyer didn't like our offer. Need to make another offer!")
                    # bidHistory[speaker] = None
                    return bidResponse
                else:
                    messageResponse['text'] = "There must be some confusion; I'm not aware of any outstanding offers."
            else:
                messageResponse['text'] = "OK, but I didn't think we had any outstanding offers."
            print("Returning message:", messageResponse)
            return messageResponse
        elif interpretation['type'] == 'Information': # The buyer is just sending an informational message. Reply politely without attempting to understand.
            messageResponse = {
                'text': "OK. Thanks for letting me know.",
                'speaker': agentName,
                'role': "seller",
                'addressee': speaker,
                'evnironmentUUID': interpretation['metadata']['environmentUUID'],
                'timestamp': (time.time() * 1000)
            }
            print("Returning message:", messageResponse)
            return messageResponse
        elif interpretation['type'] == 'NotUnderstood': # The buyer said something, but we can't figure out what
                                                        # they meant. Just ignore them and hope they'll try again if it's important.
            print("Buyer message not understood. Ignoring message.")
            return None
        elif ((interpretation['type'] == 'BuyOffer'
                or interpretation['type'] == 'BuyRequest')
                and mayIRespond(interpretation)): #The buyer evidently is making an offer or request; if permitted, generate a bid response
            print("Buyer is making an BuyRequest")
            if speaker not in bidHistory:
                bidHistory[speaker] = []
            bidHistory[speaker].append(interpretation)

            bid = generateBid(interpretation) # Generate bid based on message interpretation, utility,
                                              # and the current state of negotiation with the buyer
            bidResponse = {
                'text': translateBid(bid, False), # Translate the bid into English
                'speaker': agentName,
                'role': "seller",
                'addressee': speaker,
                'environmentUUID': interpretation['metadata']['environmentUUID'],
                'timestamp': (time.time() * 1000),
                'bid': bid
            }
            print("Returning bidResponse:", bidResponse)
            return bidResponse
        else:
            print("Message not processed. Edge case?")
            return None
    elif role == 'buyer' and addressee != agentName:  # Message was not addressed to me, but is a buyer. A more clever agent might try to steal the deal.
        # Ok, let's first wait and see if the other agent has responded
        time.sleep(3)
        # if the entry for the other speaker is not empty
        if agentName == 'Watson':
            opponentName = 'Celia'
        else:
            opponentName = 'Watson'
        if opponentName in bidHistory: # this might cause problems if the history is not properly cleared for other seller
                                       # solution could be to just check the last bid?
            print("\nFOUND OPPONENT NAME\n")
            return None
        else:
            print("\nNOT FOUND OPPONENT NAME", opponentName, agentName, "\n")
            print("\n\nBIDHISTORY IS CURRENTLY", bidHistory, "\n\n")
            if speaker not in bidHistory:
                bidHistory[speaker] = []
            bidHistory[speaker].append(interpretation)
            bid = generateBid(interpretation)
            bidResponse = {
                    'text': translateBid(bid, False), # Translate the bid into English
                    'speaker': agentName,
                    'role': "seller",
                    'addressee': speaker,
                    'environmentUUID': interpretation['metadata']['environmentUUID'],
                    'timestamp': (time.time() * 1000),
                    'bid': bid
                }
            print("Message from buyer not addressed to me. Need to make an offer!")
            return bidResponse
    elif role == 'seller': # Message was from another seller. A more clever agent might be able to exploit this info somehow!
        print("\n\nRECEIVED MESSAGE FROM OTHER SELLER\n\n")
        # TODO: Make an offer
        # below block adds history of seller responses for use by the program
        if speaker not in bidHistory:
            bidHistory[speaker] = []
        bidHistory[speaker].append(interpretation)
        if not 'Human' in bidHistory:
            bidHistory['Human'] = [interpretation]
        else:
            bidHistory['Human'].append(interpretation)# this change is experimental and may cause problems.
        time.sleep(2)
        print("\n\nBIDHISTORY IS NOW", bidHistory, "\n\n")
        offeredPrice = interpretation['price']['value']
        print("The other seller offered this price", offeredPrice)
        counterPrice = offeredPrice - 0.10# this calculation will need to be adjusted
        bidResponse = {
                    'text': "I will give you a counteroffer of " + str(quantize(counterPrice, 2)) + " USD.", # Translate the bid into English
                    'speaker': agentName,
                    'role': "seller",
                    'addressee': speaker,
                    'environmentUUID': interpretation['metadata']['environmentUUID'],
                    'timestamp': (time.time() * 1000),
                    'bid': quantize(counterPrice, 2)
                }
        #print("Message from another seller. Need to make an offer!")
        return bidResponse
    return None


# ******************************************************************************************************* #
#                                                     Simple Utilities                                    #
# ******************************************************************************************************* #

# *** quantize()
# Quantize numeric quantity to desired number of decimal digits
# Useful for making sure that bid prices don't get more fine-grained than cents
def quantize(quantity, decimals):
    print("Entering quantize")
    print("Received quantity:", quantity)
    print("Received decimals:", decimals)
    multiplicator = math.pow(10, decimals)
    q = float("%.2f" % (quantity * multiplicator))
    print("Returning value:", round(q) / multiplicator)
    return round(q) / multiplicator


# *** getSafe() 
# Utility that retrieves a specified piece of a JSON structure safely.
# o: the JSON structure from which a piece needs to be extracted, e.g. bundle
# p: list specifying the desired part of the JSON structure, e.g.['price', 'value'] to retrieve bundle.price.value
# d: default value, in case the desired part does not exist.
def getSafe(p, o, d):
    return reduce((lambda xs, x: xs[x] if (xs and xs[x] != None) else d), p)

# ******************************************************************************************************* #
#                                                    Messaging                                            #
# ******************************************************************************************************* #

# *** translateBid()
# Translate structured bid to text, with some randomization
def translateBid(bid, confirm):
    print("Entering translateBid")
    print("Received bid:", bid)
    print("Received confirm:", confirm)
    text = ""
    if bid['type'] == 'SellOffer':
        print("bid is a SellOffer")
        text = "How about if I sell you"
        for good in bid['quantity'].keys():
            text += " " + str(bid['quantity'][good]) + " " + good
        text += " for " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + "."
    elif bid['type'] == 'Reject':
        print("bid is a Reject")
        text = selectMessage(rejectionMessages)
    elif bid['type'] == 'MinMarkup':
        print("bid is a minMarkup")
        text = selectMessage(minOfferMessages)
    elif bid['type'] == 'Accept':
        print("bid is a Accept")
        if confirm:
            text = selectMessage(confirmAcceptanceMessages)
        else:
            text = selectMessage(acceptanceMessages)
        for good in bid['quantity'].keys():
            text += " " + str(bid['quantity'][good]) + " " + good
        text += " for " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + "."
    print("Returning response:", text)
    return text


# *** selectMessage()
# Randomly select a message or phrase from a specified set
def selectMessage(messageSet):
    msgSetSize = len(messageSet)
    indx = int(random.random() * msgSetSize)
    print("Returning random messge:", messageSet[indx])
    return messageSet[indx]


# *** sendMessage()
# Send specified message to the /receiveMessage route of the environment orchestrator
def sendMessage(message):
    print("Sending message to orchestrator:", message)
    return postDataToServiceType(message, 'environment-orchestrator', '/relayMessage')


# *** postDataToServiceType()
# POST a given json to a service type; mappings to host:port are externalized in the appSettings.json file
def postDataToServiceType(json, serviceType, path):
    serviceMap = appSettings['serviceMap']
    if serviceMap[serviceType]:
        options = serviceMap[serviceType]
        options['path'] = path
        url = options2URL(options)
        
        response = requests.post(url, json=json)
        return response


# *** options2URL() 
# Convert host, port, path to URL
def options2URL(options):
    protocol = options['protocol'] or 'http'
    url = protocol + '://' + options['host']
    if options['port']:
        url += ':' + str(options['port'])
    if options['path']:
        url += options['path']
    return url


# Start the API
if __name__ == "__main__":
    app.run(host='http://localhost', port=myPort)
