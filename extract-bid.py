# imports
import time
import json
import importlib
conversation = importlib.import_module('conversation')

# Methods
# From the intents and entities obtained from Watson Assistant, extract a structured representation
# of the message
def interpretMessage(watsonResponse):
    print("entered interpretMessage")
    print("Received watsonResponse:", watsonResponse)

    intents = watsonResponse['intents']
    entities = watsonResponse['entities']
    print("intents: ", intents)
    print("entities: ", entities)
    cmd = {}

    if intents[0]['intent'] == "Offer" and intents[0]['confidence'] > 0.2:
        extractedOffer = extractOfferFromEntities(entities)
        cmd = {
            'quantity': extractedOffer['quantity']
        }
        if extractedOffer['price']:
            cmd['price'] = extractedOffer['price']
            if watsonResponse['input']['role'] == 'buyer':
                cmd['type'] = "BuyOffer"
            elif watsonResponse['input']['role'] == 'seller':
                cmd['type'] = "SellOffer"
        else:
            if watsonResponse['input']['role'] == 'buyer':
                cmd['type'] = "BuyRequest"
            elif watsonResponse['input']['role'] == 'seller':
                cmd['type'] = "SellRequest"
    elif intents[0]['intent'] == "AcceptOffer" and intents[0]['confidence'] > 0.2:
        cmd = {'type': "AcceptOffer"}
    elif intents[0]['intent'] == "RejectOffer" and intents[0]['confidence'] > 0.2:
        cmd = {'type': "RejectOffer"}
    elif intents[0]['intent'] == "MinOffer" and intents[0]['confidence'] > 0.2:
        extractedOffer = extractOfferFromEntities(entities)
        cmd = {
            'quantity': extractedOffer['quantity']
        }
        if extractedOffer['price']:
            cmd['price'] = extractedOffer['price']
        cmd['type'] = "MinOffer"
    elif intents[0]['intent'] == 'Information' and intents[0]['confidence'] > 0.2:
        cmd = {'type': "Information"}
    else:
        cmd = {'type': "NotUnderstood"}
    
    if cmd:
        cmd['metadata'] = watsonResponse['input']
        cmd['metadata']['addressee'] = watsonResponse['input']['addressee'] or extractAddressee(entities) # Expect the addressee to be provided, but extract it if necessary
        cmd['metadata']['timeStamp'] = time.time()
    print("cmd leaving interpretMessage:", cmd)
    return cmd


# Extract the addressee from entities (in case addressee is not already supplied with the input message)
def extractAddressee(entities):
    print("entered extractAddressee")
    print("Received entities:", entities)
    addressees = []
    addressee = None
    for eBlock in entities:
        if eBlock['entity'] == "avatarName":
            addressees.append(eBlock['value'])
    
    if 'agentName' in addressees:
        addressee = addressees['agentName']
    else:
        addressee = None
    print("Returning addressee:", addressee)
    return addressee


# Extract goods and their amounts from the entities extracted by Watson Assistant
def extractOfferFromEntities(entityList):
    print("entered extractOfferFromEntities")
    print("Received entityList:", entityList)
    entities = json.loads(json.dumps(entityList))
    removedIndices = []
    quantity = {}
    state = None
    amount = None

    for i, eBlock in enumerate(entities):
        entities[i]['index'] = i
        if eBlock['entity'] == 'sys-number':
            amount = float(eBlock['value'])
            state = 'amount'
        elif eBlock['entity'] == 'good' and state == 'amount':
            if(amount % 1 == 0):
                quantity[eBlock['value']] = int(amount)
            else:
                quantity[eBlock['value']] = amount
            state = None
            removedIndices.append(i - 1)
            removedIndices.append(i)
    
    entities = [entity for entity in entities if entity['index'] not in removedIndices]
    print("Found entities:", entities)
    price = extractPrice(entities)
    print("Received price:", price)
    print("Returning offer:", {'quantity': quantity, 'price': price})
    return {'quantity': quantity, 'price': price}


# Extract price from entities extracted by Watson Assistant
def extractPrice(entities):
    print("entered extractPrice")
    print("entities given:", entities)
    price = None

    for eBlock in entities:
        if eBlock['entity'] == 'sys-currency':
            price = {
                'value': eBlock['metadata']['numeric_value'],
                'unit': eBlock['metadata']['unit']
            }
        elif eBlock['entity'] == 'sys-number' and not price:
            price = {
                'value': eBlock['metadata']['numeric_value'],
                'unit': 'USD'
            }
    print("Returning price:", price)
    return price


# Extract bid from message sent by another agent, a human, or myself
def extractBidFromMessage(message):
    print("entered extractBidFromMessage")
    print("Received message:", message)
    response = conversation.classifyMessage(message)
    print("Received response:", response)
    response['environmentUUID'] = message['environmentUUID']

    receivedOffer = interpretMessage(response)
    print("Received offer:", receivedOffer)
    extractedBid = {
        'type': receivedOffer['type'],
        'price': receivedOffer['price'],
        'quantity': receivedOffer['quantity']
    }
    print("Returning extractedBid:", extractedBid)
    return extractedBid
