import pytest
import json
import os
from agent import authenticate_user, create_hero, start_adventure, perform_action

BASE_URL = os.getenv("BASE_URL", "http://localhost:10000")

@pytest.fixture
def token():
    return authenticate_user()

def test_authentication():
    token = authenticate_user()
    assert token is not None
    assert len(token) > 0

def test_create_hero(token):
    hero = create_hero(token)
    assert hero is not None
    assert "intro" in hero
    assert "goal" in hero
    assert "[GOAL:" in hero["goal"]

def test_perform_action(token):
    hero = create_hero(token)
    action = "оглянути місцевість"
    history = [{"type": "reply", "text": hero.get("intro", "")}]
    inventory = []
    npc = None
    result = perform_action(hero, action, history, inventory, npc, token)
    assert result is not None
    assert "reply" in result
    assert isinstance(result.get("newItems", []), list)
    assert isinstance(result.get("removedItems", []), list)

def test_goal_achievement(token):
    hero = create_hero(token)
    action = "заявити, що ціль пригоди досягнута"
    history = [{"type": "reply", "text": hero.get("intro", "")}]
    inventory = []
    npc = None
    result = perform_action(hero, action, history, inventory, npc, token)
    assert result.get("isGoalAchieved", False)
    assert result.get("finalDescription", "")