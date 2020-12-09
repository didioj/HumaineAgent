# Imports
from flask import Flask
from flask import request
from functools import reduce
from sentiment import Event
import requests
import importlib
import json
import sys
import time
import math
import random
import traceback

from copy import deepcopy
import sentiment
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
sentimentModule = sentiment.Sentiment()

# fetch the port number
for i in range(len(sys.argv)):
    if sys.argv[i] == "--port":
        myPort = sys.argv[i + 1]

# Offer types
offerTypes = ["SellOffer", "MinOffer"]

# bundle types
bundleTypes = ['cake', 'pancake']

# bid types
bidTypes = ['NormalBid', 'BulkBid']

# predefined responses
offerMessages = [
  "How about if I sell you",
  "You look like a nice person. I can give you",
  "I can do",
  "Take",
  "I got you",
  "What do you think about",
  "I can sell you"
]

greedyOfferMessages = [
    "You're someone who appreciates a good deal, how about",
    "I know you like a fair price, what do you think about",
    "You seem like a person who likes a good price, I can sell you",
    "I know you like a fair price, take"
]

haggleOfferMessages = [
    "You drive a hard bargain, how about",
    "I see you're well versed in negotiation, I can do",
    "You drive a hard bargain, take"
]

rejectionMessages = [
  "No thanks. That offer is way too low for anyone. I have a family to feed.",
  "Forget it, I already gave you my best offer.",
  "Sorry. You're going to have to do a lot better than that!",
  "This is daylight ROBBERY!",
  "Come on, friend. I can't accept an offer like that."
]

# chance of fixing price and making an excuse when asked for better offer
minOfferExcuseMessages = [
  "All of our products are FRESH and ORGANIC!",
  "All of our products are NON-GMO!",
  "Destiny has brought you to me, so I'll give you a good deal.",
  "I have 5 cats at home to feed."
]

minOfferMessages = [
  "That's the best I can do. You won't find a better deal out there!",
  "This is the best deal I've offered to anyone.",
  "Incredible value on this deal.",
  "You won't find a deal like that anywhere else!",
  "I'm not even making any profit with that.",
  "I seriously can't go any lower than that.",
  "That price is unbeatable."
]

# if other seller proposed a price that will make us lose money
tauntMessages = [
  "Their products must be of low quality if they're so cheap!"
]

acceptanceMessages = [
  "Awesome! I'm glad we could do business. You got",
  "You've got a deal! I'll give you",
  "You've got it! I'll let you have",
  "I accept your offer. Just to confirm, I'm giving you"
]

confirmAcceptanceMessages = [
  "Just to confirm, I'm selling you ",
  "I'm so glad to do business with you. I'll give you the ",
  "Perfect! To confirm, I'm giving you ",
  "I'm so glad! This is to confirm that I'll give you ",
]

# Asking Human to clarify a message we didn't understand
clarifyMessages = [
  "Can you rephrase your request?",
  "I'm not sure what you're asking for."
]

negotiationState = {
  "active": False,
  "startTime": None,
  "roundDuration": defaultRoundDuration
}

utilityInfo = None
bidHistory = {}

def assembleBidResponse(bid, agentName, role, speaker, environmentUUID):
    response = {
        'text': translateBid(bid, False), # Translate the bid into English
        'speaker': agentName,
        'role': role,
        'addressee': speaker,
        'environmentUUID': environmentUUID,
        'timestamp': (time.time() * 1000),
        'bid': bid
    }
    return response

def reactOwnAgent(interpretation, speaker, addressee, role):
    print("- Received own message")
    if interpretation['type'] == 'AcceptOffer' or interpretation['type'] == 'RejectOffer':
        bidHistory[addressee] = None
        print("- We accepted/rejected offer. Clearing bidHistory")
    else:
        print("- Adding message to bidHistory")
        if bidHistory[addressee]:
            bidHistory[addressee].append(interpretation)
        print("- bidHistory:", bidHistory)

def reactToBuyer(interpretation, speaker, addressee, role):
    print("- Message from buyer to me")
    if speaker not in bidHistory or not bidHistory[speaker]:
        bidHistory[speaker] = []
    bidHistory[speaker].append(interpretation)
    print("- Added to bidHistory:", bidHistory)
    
    messageResponse = {
        'text': "",
        'speaker': agentName,
        'role': "seller",
        'addressee': speaker,
        'environmentUUID': interpretation['metadata']['environmentUUID'],
        'timestamp': (time.time() * 1000)
    }
    
    if interpretation['type'] in ["BuyRequest", "BuyOffer","BundleRequest"]:
        for good in interpretation['quantity']:
            if good not in utilityInfo['utility'] and good not in bundleTypes:
                print("- Unknown good in message. Setting intent as NotUnderstood")
                interpretation['type'] = "NotUnderstood"
                
    if interpretation['type'] == 'AcceptOffer': # Buyer accepted my offer! Deal with it.
        print("- Buyer accepted offer")
        print("- Checking bidHistory:", bidHistory)
        if speaker in bidHistory and bidHistory[speaker]: # I actually did make an offer to this buyer;
                                                             # fetch details and confirm acceptance
            bidHistoryIndividual = [bid for bid in bidHistory[speaker] 
                                        if (bid['metadata']['speaker'] == agentName and 
                                        (bid['type'] in offerTypes or bid['type'] == 'BulkOffer'))]
            print("- Our offers:", bidHistoryIndividual)
            if len(bidHistoryIndividual):
                acceptedBid = bidHistoryIndividual[-1]
                print("- acceptedBid:", acceptedBid)
                if acceptedBid['type'] == 'BulkOffer':
                    # return repeat of the BulkOffer and modify bidHistory
                    messageResponse = acceptedBulkOfferMessage(messageResponse, speaker)
                else:
                    bid = {
                        'price': acceptedBid['price'],
                        'quantity': acceptedBid['quantity'],
                        'type': "Accept"
                    }
                    bid['BundleIndicator'] = 0
                    if acceptedBid['type'] == 'BundleRequest' or len(acceptedBid['quantity']) >1:
                        bid['BundleIndicator'] = 1
                    print("- Sending bid to translate:", bid)
                    messageResponse['text'] = translateBid(bid, True)
                    messageResponse['bid'] = bid
                    print("- Clearing bidHistory")
                    bidHistory[speaker] = None
                if(len(bidHistoryIndividual) > 1):
                    haggleEvent = Event('buyer', 'seller', 'haggle')
                    sentimentModule.updateHistory(haggleEvent)
                else:
                    acceptEvent = Event('buyer', 'seller', 'dealAccept')
                    sentimentModule.updateHistory(acceptEvent)
            else: # Didn't have any outstanding offers with this buyer
                messageResponse['text'] = "I'm sorry, but I'm not aware of any outstanding offers."
        else: # Didn't have any outstanding offers with this buyer
            messageResponse['text'] = "I'm sorry, but I'm not aware of any outstanding offers."
        print("- Returning message:", messageResponse)
        return messageResponse
    elif interpretation['type'] == 'RejectOffer': # The buyer claims to be rejecting an offer I made; deal with it
        print("- Buyer rejected offer")
        if speaker in bidHistory and bidHistory[speaker]: # Check whether I made an offer to this buyer
            bidHistoryIndividual = [bid for bid in bidHistory[speaker] 
                                    if (bid['metadata']['speaker'] == agentName and 
                                    (bid['type'] in offerTypes or bid['type'] == 'BulkOffer'))]
            print("- Our SellOffers:", bidHistoryIndividual)

            if len(bidHistoryIndividual):
                rejectedBid = bidHistoryIndividual[-1]
                print("- rejectedBid:", rejectedBid)
                if rejectedBid['type'] == 'BulkOffer':
                    # return repeat of the BulkOffer and modify bidHistory
                    bidResponse = rejectedBulkOfferMessage(messageResponse, speaker)
                else:
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
                # print("- Buyer didn't like our offer. Need to make another offer!")
                print("- Returning bidResponse:", bidResponse)
                return bidResponse
            else:
                messageResponse['text'] = "There must be some confusion; I'm not aware of any outstanding offers."
        else:
            messageResponse['text'] = "OK, but I didn't think we had any outstanding offers."
        print("- Returning message:", messageResponse)
        return messageResponse
    elif interpretation['type'] == 'BundleRequest': # Buyer wants to make a specific good
        print("- Bundle request detected. Need to process interpretation for generateBid.")
        # processing calculating ingredients needed for bundle request
        ingredients  = {}
        for bundle in interpretation['quantity']:
            print("- Getting ingredients for:", bundle)
            scale = interpretation['quantity'][bundle]
            if bundle == 'cake':
                unit_ingredients = {'egg':2, 'flour':2, 'milk':1, 'sugar':1}
            elif bundle == 'pancake':
                unit_ingredients = {'egg':1, 'flour':2, 'milk':2}
            elif bundle in utilityInfo['utility']:
                unit_ingredients = {bundle:scale}
            print("- unit_ingredients:", unit_ingredients)
            scaled_ingredients = dict(unit_ingredients)
            for key in scaled_ingredients:
                if bundle not in utilityInfo['utility']:
                    scaled_ingredients[key] = scaled_ingredients[key] * scale
                if key not in ingredients:
                    ingredients[key] = scaled_ingredients[key]
                else:
                    ingredients[key] = ingredients[key] + scaled_ingredients[key]
        print("- Calculated ingredients needed:", ingredients)
        interpretation['quantity'] = ingredients
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
        return bidResponse
    elif interpretation['type'] == 'Information': # The buyer is just sending an informational message. Reply politely without attempting to understand.
        messageResponse = {
            'text': "OK. Thanks for letting me know.",
            'speaker': agentName,
            'role': "seller",
            'addressee': speaker,
            'environmentUUID': interpretation['metadata']['environmentUUID'],
            'timestamp': (time.time() * 1000)
        }
        print("- Returning message:", messageResponse)
        return messageResponse
    elif interpretation['type'] == 'NotUnderstood': # The buyer said something, but we can't figure out what
                                                    # they meant. Just ignore them and hope they'll try again if it's important.
        print("- Buyer message not understood. Going to ask to clarify.")
        bidResponse = {
            'text': selectMessage(clarifyMessages), 
            'speaker': agentName,
            'role': "seller",
            'addressee': speaker,
            'environmentUUID': interpretation['metadata']['environmentUUID'],
            'timestamp': (time.time() * 1000),
            'bid': None
        }
        return bidResponse
    elif ((interpretation['type'] == 'BuyOffer'
            or interpretation['type'] == 'BuyRequest')
            and mayIRespond(interpretation)): #The buyer evidently is making an offer or request; if permitted, generate a bid response
        # print("\n\n\n\n- Buyer is making an BuyRequest\n\n\n\n")
        # TODO: Offer bulk price if buying less than 5 items
        text = bulkPriceMessage(interpretation, speaker)
        
        # bid = generateBid(interpretation) # Generate bid based on message interpretation, utility,
                                          # and the current state of negotiation with the buyer
        bidResponse = {
            # 'text': translateBid(bid, False), # Translate the bid into English
            'text': text, # for bulkPrice
            'speaker': agentName,
            'role': "seller",
            'addressee': speaker,
            'environmentUUID': interpretation['metadata']['environmentUUID'],
            'timestamp': (time.time() * 1000),
            'bid': None
        }
        print("- Returning bidResponse:", bidResponse)
        return bidResponse
    else:
        print("- Message not processed. Edge case?")
        return None

def reactToEnemyBuyer(interpretation, speaker, addressee, role):
    print("- Message from buyer not addressed to me. Need to wait for other agent to respond")
    if interpretation['type'] == 'AcceptOffer':
        bidHistory[speaker] = None
        print("- Other agent accepted/rejected offer. Clearing bidHistory")
        if speaker in bidHistory and bidHistory[speaker]: # Check whether I made an offer to this buyer
            bidHistoryIndividual = [bid for bid in bidHistory[speaker] 
                                if (bid['metadata']['speaker'] == agentName and  bid['type'] in offerTypes )]
        if len(bidHistoryIndividual):
            if(len(bidHistoryIndividual) > 1):
                haggleEvent = Event('buyer', 'seller', 'haggle')
                sentimentModule.updateHistory(haggleEvent)
            else:
                acceptEvent = Event('buyer', 'seller', 'dealAccept')
                sentimentModule.updateHistory(acceptEvent)
        else:
            acceptEvent = Event('buyer', 'seller', 'dealAccept')
            sentimentModule.updateHistory(acceptEvent)
    else: # Add to bidHistory and figure out how to respond
        if speaker not in bidHistory or not bidHistory[speaker]:
            bidHistory[speaker] = []
        bidHistory[speaker].append(interpretation)
        print("- Added to bidHistory:", bidHistory)
    
        # Ok, let's first wait and see if the other agent has responded
        time.sleep(3)
        
        """
        # This might prevent the NotUnderstood condition from running
        if speaker not in bidHistory:
            print("- Can't find speaker in bidHistory. Do nothing")
            return None"""
        
        if interpretation['type'] in ["BuyRequest", "BuyOffer","BundleRequest"]:
            for good in interpretation['quantity']:
                if good not in utilityInfo['utility'] and good not in bundleTypes:
                    interpretation['type'] = "NotUnderstood"
        
        humanHistory = [bidBlock for bidBlock in bidHistory[speaker]]
        print("- Human's history:", humanHistory)
        mostRecent = humanHistory[len(humanHistory) - 1]
        print("- Most recent human history:", mostRecent)
        print("- Most recent human history should be:", interpretation)
        # most recent human history is the same buyer request we just added
        if (mostRecent == interpretation and 
            (interpretation['type'] == 'BuyOffer' or interpretation['type'] == 'BuyRequest')) :
            # maybe call reactoToBuyer
            print("- No change to bidHistory. Going to make offer")
                      
            # bid = generateBid(interpretation)
            text = bulkPriceMessage(interpretation, speaker)
            
            bidResponse = {
                # 'text': translateBid(bid, False), # Translate the bid into English
                'text': text, # for bulkPrice
                'speaker': agentName,
                'role': "seller",
                'addressee': speaker,
                'environmentUUID': interpretation['metadata']['environmentUUID'],
                'timestamp': (time.time() * 1000),
                'bid': None
            }
            return bidResponse
        if (mostRecent == interpretation and interpretation['type'] == 'BundleRequest'): # Buyer wants to make a specific good
            print("- Bundle request detected. Need to process interpretation for generateBid.")
            # processing calculating ingredients needed for bundle request
            # maybe call reactoToBuyer
            ingredients  = {}
            for bundle in interpretation['quantity']:
                print("- Getting ingredients for:", bundle)
                scale = interpretation['quantity'][bundle]
                if bundle == 'cake':
                    unit_ingredients = {'egg':2, 'flour':2, 'milk':1, 'sugar':1}
                elif bundle == 'pancake':
                    unit_ingredients = {'egg':1, 'flour':2, 'milk':2}
                elif bundle in utilityInfo['utility']:
                    unit_ingredients = {bundle:scale}
                print("- unit_ingredients:", unit_ingredients)
                scaled_ingredients = dict(unit_ingredients)
                for key in scaled_ingredients:
                    if bundle not in utilityInfo['utility']:
                        scaled_ingredients[key] = scaled_ingredients[key] * scale
                    if key not in ingredients:
                        ingredients[key] = scaled_ingredients[key]
                    else:
                        ingredients[key] = ingredients[key] + scaled_ingredients[key]
            print("- Calculated ingredients needed:", ingredients)
            interpretation['quantity'] = ingredients
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
            return bidResponse
        if (mostRecent == interpretation and interpretation['type'] == 'NotUnderstood'):
            print("- No change to bidHistory and don't understand message.")
            # do nothing if addressing other seller, ask to clarify if no addressee
            if not addressee:
                # maybe call reactToBuyer
                print("- Message wasn't addressed to anyone. Going to ask to clarify")
                bidResponse = {
                    'text': selectMessage(clarifyMessages), 
                    'speaker': agentName,
                    'role': "seller",
                    'addressee': speaker,
                    'environmentUUID': interpretation['metadata']['environmentUUID'],
                    'timestamp': (time.time() * 1000),
                    'bid': None
                }
                return bidResponse
            else:
                print("- Message was addressed to other seller. Do nothing")
                return None
        else:
            print("- bidHistory changed, or last offer wasn't a BuyOffer or BuyRequest. Going to do nothing.")
            # if the bidHistory changed, then the new receiveMessage will deal with the new message. 
            # End the current action here
            return None

def reactToOtherSeller(interpretation, speaker, addressee, role):
    print("- Message from another seller. Need to make an offer!")
    print("- Message type:", interpretation['type'])
    time.sleep(2)
    # If other agent makes a sell offer, 
    
    if interpretation['type'] in ['SellOffer', 'MinOffer']:
         for good in interpretation['quantity']:
            if good not in utilityInfo['utility'] and good not in bundleTypes:
                interpretation['type'] = "NotUnderstood"

    if interpretation['type'] == 'SellOffer' or interpretation['type'] == 'MinOffer':
        print("- Other agent made a sell offer!")
        if addressee not in bidHistory:
            bidHistory[addressee] = []
        bidHistory[addressee].append(interpretation)
        bid = generateBid(interpretation) # Generate bid based on message interpretation, utility,
                                          # and the current state of negotiation with the buyer
        bidResponse = {
            'text': translateBid(bid, False), # Translate the bid into English
            'speaker': agentName,
            'role': "seller",
            'addressee': addressee,
            'environmentUUID': interpretation['metadata']['environmentUUID'],
            'timestamp': (time.time() * 1000),
            'bid': bid
        }
        
        print("- Returning bidResponse:", bidResponse)
        return bidResponse
    elif interpretation['type'] == 'AcceptOffer':
        bidHistory[addressee] = None
        print("- Other agent accepted/rejected offer. Clearing bidHistory")
    return None

# ************************************************************************************************************ #
# REQUIRED APIs
# ************************************************************************************************************ #

# API route that receives utility information from the environment orchestrator. This also
# triggers the start of a round and the associated timer.
@app.route('/setUtility', methods=['POST'])
def setUtility():
    print("- Entering setUtility")
    if request.json:
        global utilityInfo
        utilityInfo = request.json
        print("- Info received:", utilityInfo)
        global agentName
        agentName = utilityInfo['name'] or agentName
        msg = {
            'status': 'Acknowledged',
            'utility': utilityInfo
        }
        print("- Message sending:", msg)
        return msg
    else:
        msg = {
            'status': "Failed; no message body",
            'utility': None
        }
        print("- Returning message:", msg)
        return msg


# API route that tells the agent that the round has started.
@app.route('/startRound', methods=['POST'])
def startRound():
    global bidHistory
    print("- Entering startRound")
    bidHistory = {}
    if request.json:
        print("- Info received:", request.json)
        negotiationState['roundDuration'] = request.json['roundDuration'] or negotiationState['roundDuration']
        negotiationState['roundNumber'] = request.json['roundNumber'] or negotiationState['roundNumber']
    bidHistory = {}
    negotiationState['active'] = True
    negotiationState['startTime'] = (time.time() * 1000)
    negotiationState['stopTime'] = negotiationState['startTime'] + (1000 * negotiationState['roundDuration'])
    msg = {
        'status': 'Acknowledged'
    }
    print("- Returning message:", msg)
    return msg


# API route that tells the agent that the round has ended.
@app.route('/endRound', methods=['POST'])
def endRound():
    print("- Entering endRound")
    negotiationState['active'] = False
    negotiationState['endTime'] = (time.time() * 1000)
    msg = {
        'status': 'Acknowledged'
    }
    print("- Returning message:", msg)
    return msg


# POST API that receives a message, interprets it, decides how to respond (e.g. Accept, Reject, or counteroffer),
# and if it desires sends a separate message to the /receiveMessage route of the environment orchestrator
@app.route('/receiveMessage', methods=['POST'])
def receiveMessage():
    print("- Entering receiveMessage")
    timeRemaining = (negotiationState['stopTime'] - (time.time() * 1000)) / 1000
    if timeRemaining <= 0:
        negotiationState['active'] = False
    print("- Remaining Time:", timeRemaining)
    print("- Info received:", request.json)
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
            print("- This message is from me!")
        #else:
        try:
            bidMessage = processMessage(message)
            print("- Bid message from processMessage:", bidMessage)
        except:
            traceback.print_exc()
            print("- ERROR: caught an error. Going to ask to clarify")
            bidMessage = bidResponse = {
                'text': selectMessage(clarifyMessages), 
                'speaker': agentName,
                'role': "seller",
                'addressee': "Human",
                'environmentUUID': message['environmentUUID'],
                'timestamp': (time.time() * 1000),
                'bid': None
            }
            
        if bidMessage: # If warranted, proactively send a new negotiation message to the environment orchestrator        
            print("- Sending message:", bidMessage)
            sendMessage(bidMessage)
    else: # Either there's no body or the round is over.
        response = {
            'status': "Failed; round not active"
        }
    print("- Returning response:", response)
    return response


# POST API that receives a rejection message, and decides how to respond to it. If the rejection is based upon
# insufficient funds on the part of the buyer, generate an informational message to send back to the human, as a courtesy
# (or rather to explain why we are not able to confirm acceptance of an offer).
@app.route('/receiveRejection', methods=['POST'])
def receiveRejection():
    print("- Entering receiveRejection")
    timeRemaining = (negotiationState['stopTime'] - (time.time() * 1000)) / 1000
    if timeRemaining <= 0:
        negotiationState['active'] = False
    print("- Remaining Time:", timeRemaining)
    print("- Info received:", request.json)
    response = None
    if not request.json:
        response = {
            'status': 'Failed; no message body'
        }
    elif negotiationState['active']: # We received a message and time remains in the round.
        message = request.json
        print("- Received message:", message)
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
            print("- Sending message:", msg2)
            sendMessage(msg2)
    else: # Either there's no body or the round is over.
        response = {
            'status': "Failed; round not active"
        }
    print("- Returning response:", response)
    return response

# ************************************************************************************************************ #
# Non-required APIs (useful for unit testing)
# ************************************************************************************************************ #

# GET API route that simply calls Watson Assistant on the supplied text message to obtain intent and entities
@app.route('/classifyMessage', methods=['GET'])
def classifyMessageGet():
    print("- Entering classifyMessageGet")
    data = request.json
    print("- Info received:", data)
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
        print("- Returning response:", waResponse)
        return waResponse


# POST API route that simply calls Watson Assistant on the supplied text message to obtain intents and entities
@app.route('/classifyMessage', methods=['POST'])
def classifyMessagePost():
    print("- Entering classifyMessagePost")
    print("- Info received:", data)
    if request.json:
        message = request.json
        message['speaker'] = message['speaker'] or defaultSpeaker
        message['addressee'] = message['addressee'] or None
        message['role'] = message['role'] or message['defaultRole']
        message['environmentUUID'] = message['environmentUUID'] or defaultEnvironmentUUID
        waResponse = conversation.classifyMessage(message, message['environmentUUID'])
        print("- Returning response:", waResponse)
        if waResponse:
            return waResponse
        return "error classifying post"


# POST API route that is similar to /classify Message, but takes the further
# step of determining the type and parameters of the message (if it is a negotiation act),
# and formatting this information in the form of a structured bid.
@app.route('/extractBid', methods=['POST'])
def extractBid():
    print("- Entering extractBid")
    print("- Info received:", data)
    if request.json:
        message = request.json
        message['speaker'] = message['speaker'] or defaultSpeaker
        message['addressee'] = message['addressee'] or None
        message['role'] = message['role'] or message['defaultRole']
        message['environmentUUID'] = message['environmentUUID'] or defaultEnvironmentUUID
        extractedBid = extract_bid.extractBidFromMessage(message)
        print("- Returning bid:", extractedBid)
        if extractedBid:
            return extractedBid
        return "error extracting bid"


# API route that reports the current utility information.
@app.route('/reportUtility', methods=['GET'])
def reportUtility():
    print("- Entering reportUtility")
    print("- Returning utilityInfo:", utilityInfo)
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
    print("- Entering mayIRespond")
    print("- Need to make it so can't respond if just responded and human hasn't responded. Check history to see if human responded?")
    print("- Returning reponse:", (interpretation and interpretation['metadata']['role'] and
            (interpretation['metadata']['addressee'] == agentName or not interpretation['metadata']['addressee']) ))
    return (interpretation and interpretation['metadata']['role'] and
            (interpretation['metadata']['addressee'] == agentName or not interpretation['metadata']['addressee']) )


# *** calculateUtilitySeller() 
# Calculate utility for a given bundle of goods and price, given the utility function
def calculateUtilityAgent(utilityInfo, bundle):
    print("- Entering calculateUtilityAgent")
    print("- Received utilityInfo:", utilityInfo)
    print("- Received bundle:", bundle)
    
    utilityParams = utilityInfo['utility']
    util = 0
    if 'price' not in bundle or bundle['type'] in offerTypes :
        price = 0
    else:
        price = bundle['price']['value'] 

    if bundle['quantity']:
        # this is to handle the case of indefinite quantity, note that
        # we are producing a random quantity in the range 1-4
        for good in bundle['quantity'].keys():
            goodVal = bundle['quantity'][good]
            if goodVal == 'indef':
                bundle['quantity'][good] = (int(random.random() * 100)%3)+1
        util = price
        if 'price' in bundle:
            unit = bundle['price']['unit']
        else:
            unit = None
        if not unit: # Check units -- not really used, but a good practice in case we want
                     # to support currency conversion some day
            print("- no currency units provided")
        elif unit == utilityInfo['currencyUnit']:
            print("- Currency units match")
        else:
            print("- Currency units do not match")
    
    for good in bundle['quantity'].keys():
        util -= utilityParams[good]['parameters']['unitcost'] * bundle['quantity'][good]
    
    print("- Returning utility:",util)
    return util


# *** generateBid()
# Given a received offer and some very recent prior bidding history, generate a bid
# including the type (Accept, Reject, and the terms (bundle and price).
def generateBid(offer):
    print("- Entering generateBid")
    print("- Received offer:", offer)
    minDicker = 0.10
    speaker = offer['metadata']['speaker']
    humanName = None 
    if offer['metadata']['role'] == 'buyer':
        humanName = speaker
    else:
        humanName = offer['metadata']['addressee']
    
    for bidBlock in bidHistory[humanName]:
        print("- BidBlock:", bidBlock)
        print("- BidBlock['type']:", bidBlock['type'])
    
    # all the offers made to the human
    recentOffers = [bidBlock for bidBlock in bidHistory[humanName] if bidBlock['type'] in offerTypes]
    print("- Recent offers:", recentOffers)
    
    # need to add offer quantities to RejectOffer to calculate utility
    if offer['type'] == 'RejectOffer':
        print('- RejectOffer detected. Need to find our last offer')
        # find our last offer
        for bidBlock in recentOffers:
            if bidBlock['metadata']['speaker'] == agentName:
                offer['quantity'] = bidBlock['quantity']
                print('- our last offer:', offer['quantity'])
    utility = calculateUtilityAgent(utilityInfo, offer)
    totalItems = dict(offer) # make a copy of the offer for calculating utility
    totalItems.pop('price', None)
    totalCosts = calculateUtilityAgent(utilityInfo, totalItems)
    print("- Total items:", totalItems)
    print("- Total cost of items (should be negative):", totalCosts)
    print("- Utility received:",utility)
    
    # find all offers relevant to the current one
    relevantOffers = [bidBlock for bidBlock in bidHistory[humanName] 
                if (bidBlock['type'] in offerTypes and bidBlock['quantity'] == offer['quantity'])]
    print("Relevant Offers:", relevantOffers)

    lastPrice = None # last price made to human 
    lastOffer = None # last offer made to human
    if len(relevantOffers):
        lastPrice = relevantOffers[len(relevantOffers) - 1]['price']['value']
        lastOffer = relevantOffers[len(relevantOffers) - 1]
    print("- Last price:", lastPrice)
    print("- Last offer:", lastOffer)
    
    timeRemaining = (negotiationState['stopTime'] - (time.time() * 1000)) / 1000
    print("- Remaining time:",timeRemaining)
    

    # Note that we are making no effort to upsell the buyer on a different package of goods than what they requested.
    # It would be legal to do so, and perhaps profitable in some situations -- consider doing that!

    bid = {
        'quantity': deepcopy(offer['quantity'])
    }
    
    bid['markupRatio'] = 0
    bid['BundleIndicator'] = 0
    #for bundle, the type is changing from bundlerequest to minoffer, to reject offer, etc 
    print(offer['type'])
    if offer['type'] == 'BundleRequest' or len(offer['quantity']) >1:
        bid['BundleIndicator'] = 1
    
    # check that offer is a BuyOffer before deciding 
    if offer['type'] == 'BuyOffer' and 'price' in offer and 'value' in offer['price']: # The buyer included a proposed price, which we must take into account
        print("- Buyer proposed price! Going to consider it based on bundleCost (profit)")
        bundleCost = offer['price']['value'] - utility
        print("- Calculated bundleCost:",bundleCost)
        markupRatio = utility / bundleCost
        print("- Calculated markupRatio:", markupRatio)
        bid['markupRatio'] = markupRatio
        if (markupRatio > 2.0
            or (lastPrice != None
            and abs(offer['price']['value'] - lastPrice) < minDicker)): # If our markup is large, accept the offer
            print("- Proposed price is good. Going to make an accept bid")
            bid['type'] = 'Accept'
            bid['price'] = offer['price']
        elif markupRatio < -0.5: # If buyer's offer is substantially below our cost, reject their offer
            print("- Proposed price is too low. Going to reject")
            bid['type'] = 'Reject'
            bid['price'] = None
        else: # If buyer's offer is in a range where an agreement seems possible, generate a counteroffer
            print("- Buyer's offer is workable. Going to generate a SellOffer")
            bid['type'] = 'SellOffer'
            bid['price'] = generateSellPrice(bundleCost, offer['price'], lastPrice, timeRemaining)
            if bid['price']['value'] < offer['price']['value'] + minDicker:
                bid['type'] = 'Accept'
                bid['price'] = offer['price']
    else: # The buyer didn't include a proposed price, leaving us free to consider how much to charge.
    # Set markup between 2 and 3 times the cost of the bundle and generate price accordingly.
    # make price based on the last offer price if exists
    # handles other agent's SellOffer
        print("- Buyer did not propose price or other agent made an offer. Going to generate price")
        # if lowering last offer, then reduce last markupRatio
        
        """ print("\n\n\n\n\n\n\n\n", lastOffer, "\n", lastPrice, "\n")
        if lastOffer!=None:
            print(lastOffer['quantity']==bid['quantity'])
        print("\n\n\n\n\n\n\n\n", bid, "\n\n\n\n\n\n\n\n")
        """
        
        if lastPrice: #and lastOffer['quantity']==bid['quantity'] and lastOffer['metadata']['speaker']==agentName:
            print("- A SellOffer has been made before")
            # if not making enough profit, set type to MinMarkup
            minMarkupRatio = 0.3
            
            # find my last offer 
            myRecentOffers = [bidBlock for bidBlock in relevantOffers
                                if bidBlock['metadata']['speaker'] == agentName]
            print("- My recent offers:",  myRecentOffers)
            myLastPrice = None
            if len(myRecentOffers):
                print("- We've made a SellOffer before!")
                myLastPrice = myRecentOffers[len(myRecentOffers) - 1]['price']['value']
                print("- myLastPrice:", myLastPrice)
            
            # price can still be reduced
            if lastPrice/totalCosts*-1 > minMarkupRatio+1:
                print("- lastPrice can still be reduced")
                if myLastPrice and myLastPrice < lastPrice:
                    print("- Our last offer was better than lastPrice. Reiterate our better offer")
                    bid['price'] = myRecentOffers[len(myRecentOffers) - 1]['price']
                    bid['type'] = "MinMarkup"
                    bid['speaker'] = agentName
                else:
                    print("- This is the lowest offer so far. Going to reduce")
                    # reversed the calculation to find the previous random.random() value
                    lastMarkupRatio = 1 - (lastPrice/totalCosts) - 2
                    print("- Calcuated last markupRatio:", lastMarkupRatio) # i.e., 1.3
                    # reduce by 10%-25% -> ratio = 75-90%
                    markupRatio = 2.0 + (lastMarkupRatio * (random.random() * 0.15 + 0.75))
                    print("- Going to markup price by", markupRatio)
                    bid['type'] = 'SellOffer'
                    
                    # if low markupRatio, 20% chance of fixing price and making an excuse
                    if (offer['type'] == 'RejectOffer' and offer['metadata']['addressee'] == agentName and
                        markupRatio < 2.5 and random.random() < 0.2):
                        bid['type'] = 'MinMarkupExcuse'
                        markupRatio = 2.0 + lastMarkupRatio
                    
                    bid['price'] = {
                        'unit': utilityInfo['currencyUnit'],
                        'value': quantize((1.0 - markupRatio) * totalCosts, 2)
                    }
            else: # price can't be reduced
                print("- Reached minMarkupRatio:", lastPrice/utility*-1)
                bid['type'] = 'MinMarkup'
                # if we made a SellOffer, 
                #   if we proposed lastPrice, reiterate it's the best we can do
                #   if other agent proposed lastPrice, taunt them
                # if no SellOffer history, generate price
                if humanName not in bidHistory:
                    print("- ERROR: edge case other agent made an offer but human not in bidHistory")        
                    return None
                    
                if myLastPrice and myLastPrice < lastPrice:
                    print("- Our last offer was better than lastPrice. Reiterate our better offer")
                    bid['price'] = myRecentOffers[len(myRecentOffers) - 1]['price']
                    bid['type'] = "MinMarkup"
                    bid['speaker'] = agentName
                else:
                    bid['price'] = lastOffer['price']
                    bid['type'] = "MinMarkupExcuse"
                    bid['speaker'] = agentName
                    if lastOffer['type'] == 'NormalBulkOffer' and (lastPrice+0.02 > totalCosts*-1):
                        print("- detected a NormalBulkOffer. going to reduce bulk price")
                        # lastOffer was the normal bulk price. need to make better offer
                        profit = lastPrice + totalCosts # totalcost is negative
                        # bulk price reduce profit by up to 50%, at least 1 cent off
                        bulk_price = (-1*totalCosts) + (random.random() * 0.5 * profit) - 0.01
                    elif lastOffer['metadata']['speaker'] == agentName:
                        print("- We made the last offer. Say it's the lowest")
                        bid['type'] = "MinMarkup"
                    elif (lastPrice-0.01) > (totalCosts*-1):
                    # offer 1 cent cheaper if possible
                        print("- Going to offer 1 cent cheaper")
                        bid['price']['value'] = quantize(lastPrice-0.01,2)
                    else:
                        print("- Can't reduce price anymore. Going negative")
                        bid['speaker'] = speaker
                        bid['type'] = "MinMarkup"
                        bid['action'] = 'reject' # negative profit. Going to taunt
                        # propose the minMarkupPrice
                        markupRatio = 2.0 + minMarkupRatio
                        minMarkupPrice = quantize((1.0 - markupRatio) * totalCosts, 2)
                        if not myLastPrice or myLastPrice > minMarkupPrice:
                            print("- minMarkupPrice is lower")
                            bid['price']['value'] = minMarkupPrice
                        else:
                            print("- myLastPrice is lower")
                            bid['price']['value'] = myLastPrice
        else:
            print("- No history of any SellOffers. Going to propose price")
            markupRatio = 2.0 + random.random()
            print("Original markup ratio:", markupRatio)
            if sentimentModule.getStrategy() == 'haggle':
                print("We have determined the buyer is haggling.")
                markupRatio += 0.3
            elif sentimentModule.getStrategy() == 'greedy':
                print("We have determined the buyer is greedy.")
                markupRatio = 2.3
            print("- Going to markup price by", markupRatio)
            bid['type'] = 'SellOffer'
            bid['price'] = {
                'unit': utilityInfo['currencyUnit'],
                'value': quantize((1.0 - markupRatio) * utility, 2)
            }
    print("- Returning bid:", bid)
    return bid

# *** generateSellPrice()
# Generate a bid price that is sensitive to cost, negotiation history with this buyer, and time remaining in round
def generateSellPrice(bundleCost, offerPrice, myLastPrice, timeRemaining):
    print("- Entering generateSellPrice")
    print("- Received bundleCost:", bundleCost)
    print("- Received offerPrice:", offerPrice)
    print("- Received myLastPrice:", myLastPrice)
    print("- Received timeRemaining:", timeRemaining)
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
    print("- Returning offering price:", price)
    return price


# *** processMessage() 
# Orchestrate a sequence of
# * classifying the message to obtain and intent and entities
# * interpreting the intents and entities into a structured representation of the message
# * determining (through self-policing) whether rules permit a response to the message
# * generating a bid (or other negotiation act) in response to the offer
def processMessage(message):
    print("- Entering processMessage")
    print("- Received message:", message)
    
    classification = conversation.classifyMessage(message)
    print("- Received message classification:", classification)
    
    classification['environmentUUID'] = message['environmentUUID']
    interpretation = extract_bid.interpretMessage(classification)
    print("- Received interpretation:", interpretation)

    speaker = interpretation['metadata']['speaker']
    addressee = interpretation['metadata']['addressee']
    role = interpretation['metadata']['role']

    if speaker == agentName: # The message was from me; this means that the system allowed it to go through.
        # If the message from me was an accept or reject, wipe out the bidHistory with this particular negotiation partner
        # Otherwise, add the message to the bid history with this negotiation partner
        return reactOwnAgent(interpretation, speaker, addressee, role)
    elif addressee == agentName and role == 'buyer': # Message was addressed to me by a buyer; continue to process
        return reactToBuyer(interpretation, speaker, addressee, role)
    elif role == 'buyer' and addressee != agentName:  # Message was not addressed to me, but is a buyer.
                                                      # A more clever agent might try to steal the deal.
        return reactToEnemyBuyer(interpretation, speaker, addressee, role)
    elif role == 'seller': # Message was from another seller. A more clever agent might be able to exploit this info somehow!
        # TODO: Make an offer
        return reactToOtherSeller(interpretation, speaker, addressee, role)
    return None



# ******************************************************************************************************* #
#                                                     Simple Utilities                                    #
# ******************************************************************************************************* #

# *** quantize()
# Quantize numeric quantity to desired number of decimal digits
# Useful for making sure that bid prices don't get more fine-grained than cents
def quantize(quantity, decimals):
    print("- Entering quantize")
    print("- Received quantity:", quantity)
    print("- Received decimals:", decimals)
    multiplicator = math.pow(10, decimals)
    q = float("%.2f" % (quantity * multiplicator))
    print("- Returning value:", round(q) / multiplicator)
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

bulkOffers = [] # track when we proposed bulk price

# *** bulkPriceMessage()
# Generate message for bulk price
def bulkPriceMessage(interpretation, speaker):
    print("- Entering bulkPriceMessage")
    print("- received interpretation:", interpretation)
    # regular bid for requested items
    basic_bid = generateBid(interpretation)
    
    # temporarily removing bulk pricing
    return translateBid(basic_bid, False)
    bid_quantity = interpretation['quantity']
    
    if bid_quantity in bulkOffers:
        return translateBid(basic_bid, False)
    
    # return bulk message if any quantity <= 2
    return_bulk = False
    for good in bid_quantity:
        if bid_quantity[good] <= 2:
            return_bulk = True
            break;
    
    if not return_bulk: # return regular message
        bulkOffers.append(deepcopy(bid_quantity))
        return translateBid(basic_bid, False)

    # add bid for the normal quantity of items the buyer wants to bidHistory
    normal_bid = deepcopy(interpretation)
    normal_bid['type'] = 'NormalBid'
    normal_bid['price'] = deepcopy(basic_bid['price'])
    print('- NormalBid:', normal_bid)
    bidHistory[speaker].append(normal_bid)
    print('- Added NormalBid to bidHistory:', bidHistory)
    
    # bulk bid for requested items
    bulk_interpretation = deepcopy(interpretation)
    bulk_interpretation['type'] = 'GoodPrice'
    # scale up to 5 times the quantity of goods
    scale = int((random.random() * 4) + 2)
    print("- scale:", scale)
    for good in bulk_interpretation['quantity']:
        bulk_interpretation['quantity'][good] = bulk_interpretation['quantity'][good] * scale
        
    # Add normal price for bulk to bidHistory so discounted bulk price will be cheaper
    normal_bulk_bid = deepcopy(bulk_interpretation)
    normal_bulk_bid['type'] = 'NormalBulkBid'
    normal_bulk_bid['price'] = deepcopy(basic_bid['price'])
    normal_bulk_bid['price']['value'] = normal_bulk_bid['price']['value'] * scale
    normal_bulk_bid['metadata'] = {'speaker':agentName, 'addressee':speaker, 'text':"Placeholder for NormalBulkBid", 'role':'seller'}
    bidHistory['Human'].append(normal_bulk_bid)
    bulk_bid = generateBid(bulk_interpretation)
    bulk_bid['type'] = "GoodPrice"
    
    # to be added to bidHistory for accepting
    bulk_bid_copy = deepcopy(bulk_bid)
    bulk_bid_copy['type'] = 'BulkBid'
    bulk_bid_copy['metadata'] = {'speaker':agentName, 'addressee':speaker, 'text':"Placeholder for BulkBid", 'role':'seller'}
    bidHistory[speaker].append(bulk_bid_copy)
    
    print("- interpretation:", interpretation)
    print("- bulk_interpretation:", bulk_interpretation)
    print("- basic_bid:", basic_bid)
    print("- normal_bulk_bid:", normal_bulk_bid)
    print("- bulk_bid:", bulk_bid)
    savings = quantize((scale * basic_bid['price']['value']) - bulk_bid['price']['value'], 2)
    unit = bulk_bid['price']['unit']
    message = translateBid(basic_bid, False)
    message += " I can also offer you a special discounted bulk deal of"
    message += translateBid(bulk_bid, False)
    message += " That is "
    message += str(savings) + " " + unit
    message += " off the normal price! "
    message += "Are you interested in the bulk deal?"
    return message 

# *** acceptedBulkOfferMessage()
# Generate message after buyer accepts BulkOffer
def acceptedBulkOfferMessage(messageResponse, speaker):
    print("- Entering acceptedBulkOfferMessage")
    print("- Received messageResponse:", messageResponse)
    # return repeat of the BulkBid
    bulk_bid = None
    for bidBlock in bidHistory[speaker]:
        if bidBlock['type'] == 'BulkBid':
            bulk_bid = bidBlock
    
    if bulk_bid:
        print("- Found the bulk_bid:", bulk_bid)
        bulk_bid = deepcopy(bulk_bid)
        bulk_bid['type'] = 'GoodPrice'
        message = "I'm glad you are interested in the bulk deal! "
        message += "I can sell you"
        message += translateBid(bulk_bid, False)
        bid = {
            'price': bulk_bid['price'],
            'quantity': bulk_bid['quantity']
        }
        messageResponse['text'] = message
        messageResponse['bid'] = bid
        return messageResponse
    print("- ERROR: Can't find bulk deal")

# *** rejectedBulkOfferMessage()
# Generate message after buyer rejects BulkOffer
def rejectedBulkOfferMessage(messageResponse, speaker):
    print("- Entering rejectedBulkOfferMessage")
    print("- Received messageResponse:", messageResponse)
    # return repeat of the NormalBid
    normal_bid = None
    for bidBlock in bidHistory[speaker]:
        if bidBlock['type'] == 'NormalBid':
            normal_bid = bidBlock
    
    if normal_bid:
        normal_bid = deepcopy(normal_bid)
        print("- Found the normal_bid:", normal_bid)
        normal_bid['type'] = 'GoodPrice'
        message = "It sounds like you're not interested in the bulk deal. "
        message += "Then the normal price is"
        message += translateBid(normal_bid, False)
        bid = {
            'price': normal_bid['price'],
            'quantity': normal_bid['quantity']
        }
        messageResponse['text'] = message
        messageResponse['bid'] = bid
        return messageResponse
    print("- ERROR: Can't find normal deal")
            

def UnitsBid(good,good_quantity):
    if good == 'egg' and good_quantity > 1:
        return "eggs"
    elif good == 'egg' and good_quantity == 1:
        return "egg"
    elif good == 'chocolate' and good_quantity >1:
        return "chocolates"
    elif good == 'chocolate' and good_quantity == 1:
        return "chocolate"
    elif good =='flour' and good_quantity > 1:
        return "cups of flour"
    elif good =='flour' and good_quantity == 1:
        return "cup of flour"
    elif good == 'milk' and good_quantity > 1:
        return "cups of milk"
    elif good == 'milk' and good_quantity == 1:
        return "cup of milk"
    elif good == 'sugar' and good_quantity > 1:
        return "cups of sugar"
    elif good == 'sugar' and good_quantity == 1:
        return "cup of sugar"
    elif good == 'vanilla' and good_quantity >1:
        return "teaspoons of vanilla extract"
    elif good == 'vanilla' and good_quantity ==1:
        return "teaspoon of vanilla extract"
    elif good == 'blueberry' and good_quantity > 1:
        return 'cups of blueberries'
    elif good == 'blueberry' and good_quantity == 1:
        return 'cup of blueberries'
    else:
        return ""
# *** translateBid()
# Translate structured bid to text, with some randomization
def translateBid(bid, confirm):
    print("- Entering translateBid")
    print("- Received bid:", bid)
    print("- Received confirm:", confirm)
    text = ""
    if bid['type'] == 'SellOffer':
        print("- bid is a SellOffer")
        randEvent = ['special'] * 99 + ['normal'] * 1
        eventChoice = random.choice(randEvent) 
        if(sentimentModule.computeStrategy() == 'haggle' and eventChoice == 'special') :
            text = selectMessage(haggleOfferMessages)
        elif(sentimentModule.computeStrategy() == 'greedy' and eventChoice == 'special') :
            text = selectMessage(greedyOfferMessages)
        else :
            text = selectMessage(offerMessages)
        overall_goods = len(bid['quantity'].keys())
        good_index = 0
        for good in bid['quantity'].keys():
            good_quantity = bid['quantity'][good]
            if bid['BundleIndicator'] == 0: #if this is not a bundle
                text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
            else:# if it is a bundle add commas + and if its the last good  
                if good_index == (overall_goods-1):
                    text += " and " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                else:
                    text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity) +","
            good_index+=1
        text += " for " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + "."
        if bid['markupRatio'] < 0: #so if we would lose money by making this deal
            text += " Sorry for not accepting your offer as it stands, but we would have lost money."
        elif bid['markupRatio'] > 0 and bid['markupRatio'] < 0.5: #if we are approaching the break-even point
            text += " We're getting close to the best I can do here."
    elif bid['type'] == 'Reject':
        print("- bid is a Reject")
        text = selectMessage(rejectionMessages)
    elif bid['type'] == 'MinMarkupExcuse':
        print("- bid is a minMarkupExcuse")
        text += selectMessage(minOfferExcuseMessages) + ' '
        text += str(bid['price']['value']) + " " + str(bid['price']['unit']) + " for "
        overall_goods = len(bid['quantity'].keys())
        good_index = 0
        for good in bid['quantity'].keys():
            good_quantity = bid['quantity'][good]
            if bid['BundleIndicator'] == 0: #if this is not a bundle
                text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
            else:# if it is a bundle add commas + and if its the last good  
                if good_index == (overall_goods-1):
                    text += " and " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                else:
                    text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity) +","
            good_index+=1
        text += "."
        text += " This is such a good deal for you!"
        
    elif bid['type'] == 'MinMarkup':
        print("- bid is a minMarkup")
        # identify who made the min offer and respond accordingly
        if bid['speaker'] == agentName:
            print("- min offer was made by us!")
            text += "My offer for " 
            overall_goods = len(bid['quantity'].keys())
            good_index = 0
            for good in bid['quantity'].keys():
                good_quantity = bid['quantity'][good]
                if bid['BundleIndicator'] == 0: #if this is not a bundle
                    text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                else:# if it is a bundle add commas + and if its the last good  
                    if good_index == (overall_goods-1):
                        text += " and " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                    else:
                        text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity) +","
                good_index+=1
            text += " stands at " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + ". "
            text += selectMessage(minOfferMessages)
        else:
            print("- min offer was made by other agent")
            # match the other agent's deal (lower than our min markupRatio so can't do better)
            if bid['action'] == 'match':
                print("- Going to match other agent's offer")
                text += 'I will also offer you '
                overall_goods = len(bid['quantity'].keys())
                good_index = 0
                for good in bid['quantity'].keys():
                    good_quantity = bid['quantity'][good]
                    if bid['BundleIndicator'] == 0: #if this is not a bundle
                        text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                    else:# if it is a bundle add commas + and if its the last good  
                        if good_index == (overall_goods-1):
                            text += " and " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                        else:
                            text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity) +","
                    good_index+=1
                text += "for " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + ". "
                text += "Our products are organic and Non-GMO."
            elif bid['action'] == 'reject': # other agent is losing money so don't match
                # state our best offer and taunt other agent
                text += str(bid['price']['value']) + " " + str(bid['price']['unit']) + " for "
                for good in bid['quantity'].keys():
                    good_quantity = bid['quantity'][good]
                    text += str(bid['quantity'][good]) + " " +  UnitsBid(good,good_quantity) + " "
                text += "is my best offer. "
                text += selectMessage(tauntMessages)

    elif bid['type'] == 'Accept':
        print("- bid is a Accept")
        if confirm:
            text = selectMessage(confirmAcceptanceMessages)
        else:
            text = selectMessage(acceptanceMessages)
        overall_goods = len(bid['quantity'].keys())
        good_index = 0     
        for good in bid['quantity'].keys():
            good_quantity = bid['quantity'][good]
            if bid['BundleIndicator'] == 0: #if this is not a bundle
                text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
            else:# if it is a bundle add commas + and if its the last good  
                if good_index == (overall_goods-1):
                    text += " and " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                else:
                    text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity) +","
            good_index+=1
        text += " for " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + "."
        text += " This is such a good deal for you!"
    elif bid['type'] == 'GoodPrice': # just the goods and the price
        overall_goods = len(bid['quantity'].keys())
        good_index = 0
        for good in bid['quantity'].keys():
            good_quantity = bid['quantity'][good]
            if bid['BundleIndicator'] == 0: #if this is not a bundle
                text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
            else:# if it is a bundle add commas + and if its the last good  
                if good_index == (overall_goods-1):
                    text += " and " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity)
                else:
                    text += " " + str(bid['quantity'][good]) + " " + UnitsBid(good,good_quantity) +","
            good_index+=1
        text += " for " + str(bid['price']['value']) + " " + str(bid['price']['unit']) + "."
      
    print("- Returning response:", text)
    return text


# *** selectMessage()
# Randomly select a message or phrase from a specified set
def selectMessage(messageSet):
    msgSetSize = len(messageSet)
    indx = int(random.random() * msgSetSize)
    print("- Returning random messge:", messageSet[indx])
    return messageSet[indx]


# *** sendMessage()
# Send specified message to the /receiveMessage route of the environment orchestrator
def sendMessage(message):
    print("- Sending message to orchestrator:", message)
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
