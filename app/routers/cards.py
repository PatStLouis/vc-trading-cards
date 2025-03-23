from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse

from app.models.web_requests import NewCardSet, NewCardBatch, CardDraw
from app.models.credentials import Credential
from app.models.cards import TradingCard, RARITY_VOLUMES
from app.plugins.askar import AskarStorage
from config import settings
from datetime import datetime
import random
import uuid


router = APIRouter(tags=["Cards"], prefix='/cards')
askar = AskarStorage()

@router.get("/")
async def get_user_cards(username: str):
    user_wallet = await askar.fetch('user', username)
    if not user_wallet:
        return HTTPException(status_code=404, details='No user found')
    
    user_cards = []
    for card_id in user_wallet:
        card = await askar.fetch('card', card_id)
        if not card:
            print(f'Missing card: {card_id}')
        else:
            user_cards.append(card)

    return JSONResponse(status_code=200, content={
        'userCards': user_cards
    })


@router.get("/{card_id}")
async def get_card(card_id: str):
    card = await askar.fetch('card', card_id)
    if not card:
        return HTTPException(status_code=404, details='No card found')

    return JSONResponse(status_code=200, content=card)


@router.post("/set")
async def new_card_set(request_body: NewCardSet):
    request_body = request_body.model_dump()
    await askar.store('cardSet', request_body['label'], request_body['entries'])
    return JSONResponse(
        status_code=201,
        content={},
    )


@router.post("/batch")
async def new_card_batch(request_body: NewCardBatch):
    request_body = request_body.model_dump()
    set_label = request_body['set']
    if await askar.fetch('cardBatch', set_label):
        return HTTPException(status_code=400, details='Batch already exists')
    
    card_set = await askar.fetch('cardSet', set_label)
    card_batch = []
    timestamp = str(datetime.now().isoformat('T', 'seconds'))
    for card_data in card_set:
        card_number = 0
        card_total = RARITY_VOLUMES[card_data.get('rarity')]
        for instance in range(card_total):
            card_number += 1
            card_id = str(uuid.uuid4())
            card_batch.append(card_id)
            vc_card = Credential(
                id=f'urn:uuid:{card_id}',
                validFrom=f'{timestamp}Z',
                credentialSubject=TradingCard(
                    **card_data,
                    set=set_label,
                    number=f'{card_number}/{card_total}'
                )
            ).model_dump()
            await askar.store('card', card_id, vc_card)
            
    random.shuffle(card_batch)
    await askar.store('cardBatch', set_label, card_batch)
    
    return JSONResponse(
        status_code=200,
        content={},
    )


@router.post("/draw")
async def draw_cards(request_body: CardDraw):
    request_body = request_body.model_dump()
    
    username = request_body.get('username')
    user_wallet = await askar.fetch('user', username)
    if not user_wallet:
        user_wallet = []
        await askar.store('user', username, user_wallet)
    
    sel_label = request_body.get('set')
    card_batch = await askar.fetch('cardBatch', sel_label)
    timestamp = str(datetime.now().isoformat('T', 'seconds'))
    
    cards = []
    for instance in range(request_body.get('quantity')):
        card_id = card_batch.pop()
        card = await askar.fetch('card', card_id)
        card['proof'] = {
            'type': 'DataIntegrity',
            'created': f'{timestamp}Z'
        }
        cards.append(card)
        await askar.update('card', card_id, card)
        user_wallet.append(card_id)
        
    await askar.update('user', username, user_wallet)
    await askar.update('cardBatch', sel_label, card_batch)
    
    return JSONResponse(
        status_code=200,
        content={
            'remainingCards': len(card_batch),
            'userCardsTotal': len(user_wallet),
            'pulledCards': cards
        },
    )

