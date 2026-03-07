"""Request/response examples for OpenAPI docs. Used by admin, wallet, and public routes."""

# ---- Admin: issue card body ----
ISSUE_CARD_EXAMPLES = {
    "by_user_id": {
        "summary": "By user ID",
        "value": {"user_id": "usr_abc123"},
    },
    "by_discord": {
        "summary": "By Discord sub",
        "value": {"discord_sub": "123456789012345678"},
    },
}

# ---- Admin: response examples ----
RESPONSE_AGENT_SETTINGS = {
    "admin_url": "http://localhost:8031",
    "admin_url_configured": True,
    "api_key_configured": True,
    "innkeeper_configured": True,
    "discord_bot_configured": True,
    "discord_bot_invite_url": "https://discord.com/api/oauth2/authorize?client_id=123&permissions=0&scope=bot%20applications.commands",
    "status": {"ready": True},
}

RESPONSE_STATS = {"total_users": 42, "total_sets": 5, "total_cards": 120}

RESPONSE_USERS = {
    "users": [
        {
            "user_id": "usr_abc",
            "discord_sub": "123456789",
            "username": "player1",
            "wallet_id": "wallet_xyz",
            "created_at": "2025-01-15T12:00:00Z",
        }
    ]
}

RESPONSE_SETS = {
    "sets": [
        {
            "id": "set_1",
            "name": "Season One",
            "slug": "season-one",
            "description": "First set",
            "set_type": "standard",
            "card_back_path": "sets/set_1/back.png",
        }
    ]
}

RESPONSE_SET = {
    "id": "set_1",
    "name": "Season One",
    "slug": "season-one",
    "description": "First set",
    "set_type": "standard",
    "card_back_path": "sets/set_1/back.png",
}

RESPONSE_CARDS = {
    "cards": [
        {
            "id": "card_1",
            "set_id": "set_1",
            "card_id": "a1b2c3d4e5f6",
            "name": "a1b2c3d4e5f6",
            "number": "1/57",
            "rarity": "rare",
            "set_name": "Season One",
            "image_path": "cards/set_1/card_1.png",
        }
    ]
}

RESPONSE_CARD = {
    "id": "card_1",
    "set_id": "set_1",
    "card_id": "a1b2c3d4e5f6",
    "name": "a1b2c3d4e5f6",
    "number": "1/57",
    "rarity": "rare",
    "set_name": "Season One",
    "quote": "",
    "artwork": "",
    "photograph": "",
    "artist": "",
    "band": "",
    "image_path": "cards/set_1/card_1.png",
    "types": ["TradingCard"],
    "subtypes": "trading-cards",
    "supertype": "trading-card",
}

RESPONSE_DELETED = {"deleted": True}

RESPONSE_ISSUE = {
    "issued": True,
    "issuance": {"card_id": "card_1", "user_id": "usr_abc", "credential_exchange_id": "v1-..."},
}

RESPONSE_DISCORD_REGISTER = {"registered": True}

RESPONSE_GUILDS = {
    "guilds": [
        {"id": "guild_123", "name": "My Server", "icon": "abc", "member_count": 50}
    ]
}

RESPONSE_GUILD = {"id": "guild_123", "name": "My Server", "icon": "abc", "member_count": 50}

RESPONSE_GUILD_MEMBERS = {
    "members": [
        {
            "user": {"id": "123456789", "username": "player1"},
            "is_registered": True,
        }
    ]
}

# ---- Wallet: response examples ----
RESPONSE_ME = {
    "user_id": "usr_abc",
    "sub": "discord|123456789",
    "provider": "discord",
    "username": "player1",
    "wallet_id": "wallet_xyz",
    "poser_username": "player1",
    "avatar_url": "https://cdn.discordapp.com/avatars/123456789/abc123.png?size=128",
    "is_admin": False,
    "has_passkey": True,
    "passkey_count": 1,
    "passkeys": [{"id": "abc123", "created_at": "2025-01-15 12:00:00Z", "credential_device_type": "multi_device", "credential_backed_up": True, "attestation_format": "none", "aaguid": "00000000-0000-0000-0000-000000000000", "registered_name": "red.radbit"}],
    "accounts": [{"provider": "discord", "username": "player1"}],
    "first_login_at": "2025-01-15 12:00:00Z",
    "is_first_login": False,
}

RESPONSE_WALLET_CARDS = {
    "cards": [
        {
            "id": "cred_1",
            "name": "Rare Card",
            "rarity": "rare",
            "set": "Season One",
            "number": "42",
            "quote": "",
            "artwork": "",
            "types": ["TradingCard"],
            "subtypes": "trading-cards",
            "supertype": "trading-card",
            "image_url": "",
        }
    ]
}

RESPONSE_SYNC = {"synced": 10, "message": "Collection synced. You will appear in search and card owners."}

# ---- Public: response examples (reuse admin set/card shapes) ----
RESPONSE_PUBLIC_OWNERS = {"card_id": "card_1", "owners": [{"user_id": "usr_1", "username": "player1"}]}

RESPONSE_PUBLIC_USERS = {
    "users": [{"user_id": "usr_1", "username": "player1", "poser_username": "player1", "discord_sub": "123", "collection_count": 5}]
}

RESPONSE_PUBLIC_USER = {"user_id": "usr_1", "username": "player1", "poser_username": "player1", "discord_sub": "123"}

RESPONSE_PUBLIC_USER_COLLECTION = {
    "user": {"user_id": "usr_1", "username": "player1", "poser_username": "player1"},
    "cards": [{"id": "card_1", "name": "Rare Card", "set_name": "Season One"}],
}


def response_example(example: dict) -> dict:
    """Build OpenAPI response content with example."""
    return {
        "description": "Success",
        "content": {"application/json": {"example": example}},
    }
