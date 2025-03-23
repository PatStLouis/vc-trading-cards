from app.models.cards import CardEntry

SAMPLE_SET = {
    'label': '1st edition',
    'entries': [
        CardEntry(
            name='Jane Doe',
            quote='Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
            rarity='common',
            artwork='https://picsum.photos/id/237/200/300',
            photographer='Unknown',
        ).model_dump()
    ]
}
SAMPLE_DROP = {
    'quantity': 50,
    'setLabel': '1st edition'
}
SAMPLE_DRAW = {
    'quantity': 5,
    'setLabel': '1st edition',
    'username': 'CardCollector123'
}