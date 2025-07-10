import requests
import random
import time
import os
from faker import Faker
import json
import firebase_admin
from firebase_admin import auth, credentials
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Initialize Faker for realistic data
fake = Faker()

# Load environment variables
BASE_URL = os.getenv("BASE_URL", "http://host.docker.internal:10000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
MISTRAL_API_KEY = "eH1jwnate9tj2qnXFeySrkQnfBTdYAfW"
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY not set")

# Initialize Firebase
cred = credentials.Certificate("/app/call-of-adventure-firebase-adminsdk-fbsvc-a918936ac1.json")
firebase_admin.initialize_app(cred)

# Action sequence for the test scenario
ACTIONS = [
    "вийти з дому",
    "оглянути місцевість",
    "пошукати скарби",
    "взяти предмет",
    "відпочити",
    "пройти далі по місцевості",
    "поговорити з NPC, якщо зустрів",
    "використати предмет з інвентарю",
    "заявити, що ціль пригоди досягнута"
]

RACES = ["Людина", "Дварф", "Напіврослик", "Ельф", "Гном", "Напівельф", "Напіворк"]
CLASSES = ["Варвар", "Бард", "Клірик", "Друїд", "Боець", "Монах", "Паладин", "Рейнджер", "Розбійник", "Чаклун", "Чарівник", "Відьмак"]
ITEMS = ["зілля здоров’я", "еліксир сили", "меч", "щит"]

class HTTP429Error(Exception):
    pass

def check_status(response):
    if response.status_code == 429:
        raise HTTP429Error("Rate limit exceeded")
    response.raise_for_status()
    return response

@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(10),
    retry=retry_if_exception_type(HTTP429Error)
)
def make_request(url, data=None, headers=None):
    response = requests.post(url, json=data, headers=headers)
    return check_status(response)

def authenticate_user():
    """Authenticate with Firebase and return a user token."""
    try:
        email = f"test_{fake.user_name()}@coa.test"
        password = fake.password()
        user = auth.create_user(email=email, password=password)
        custom_token = auth.create_custom_token(user.uid)
        
        firebase_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
        api_key = "AIzaSyBChOBuQueBIdV3IxH1Klvge4pl4zwfx4Y"
        response = requests.post(
            f"{firebase_url}?key={api_key}",
            json={"token": custom_token.decode(), "returnSecureToken": True}
        )
        response.raise_for_status()
        token = response.json()["idToken"]
        print(f"Authentication successful: Bearer {token}")
        return token
    except Exception as e:
        print(f"Authentication failed: {e}")
        return None

def create_hero(token, heroname="Test", race="Напіврослик", character_class="Друїд"):
    """Create a hero with specified attributes."""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "heroname": heroname,
        "race": race,
        "characterClass": character_class
    }
    try:
        response = make_request(f"{BASE_URL}/start_prompt?language=uk", data=data, headers=headers)
        hero_data = response.json()
        hero_data["heroname"] = heroname
        hero_data["race"] = race
        hero_data["characterClass"] = character_class
        print(f"Create Hero: {response.status_code}, {hero_data}")
        return hero_data
    except HTTP429Error:
        print("Rate limit exceeded for create_hero, waiting to retry...")
        raise
    except Exception as e:
        print(f"Create Hero failed: {e}")
        return None

def start_adventure(hero, token):
    """Start the adventure using the hero data without new generation."""
    adventure_data = {
        "goal": hero.get("goal", "Досягти мети"),
        "intro": hero.get("intro", "Ти починаєш свою пригоду...")
    }
    print(f"Start Adventure: 200, {adventure_data}")
    return adventure_data

def generate_action(history, inventory, npc=None):
    """Generate a context-aware action using Mistral API."""
    prompt = f"""
    You are a game tester for a Dungeons & Dragons text RPG. Based on the game history and inventory, suggest a realistic action for the player.
    History: {json.dumps(history[-5:], indent=2)}
    Inventory: {inventory}
    NPC (if present): {npc}
    Available action types: exploration, combat, dialogue, item usage, goal completion.
    Return a single action string in Ukrainian, e.g., "оглянути місцевість" or "напасти на гобліна".
    """
    try:
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-large-latest",
            "prompt": prompt,
            "max_tokens": 50,
            "temperature": 0.7
        }
        response = requests.post("https://api.mixtral.ai/v1/completions", json=data, headers=headers)
        response.raise_for_status()
        action = response.json()["choices"][0]["text"].strip()
        if not action:
            action = random.choice(ACTIONS)
        return action
    except Exception as e:
        print(f"Action generation failed: {e}")
        return random.choice(ACTIONS)

def perform_action(hero, action, history, inventory, npc, token):
    """Perform an action and process the response."""
    headers = {"Authorization": f"Bearer {token}"}
    dice_roll = random.randint(1, 20)
    difficulty = random.randint(2, 15)
    data = {
        "action": action,
        "dice_result": dice_roll,
        "difficulty": difficulty,
        "heroname": hero.get("heroname", "Герой"),
        "race": hero.get("race", "Людина"),
        "characterClass": hero.get("characterClass", "Чарівник"),
        "intro": history[0].get("text", "") if history else "",
        "goal": hero.get("goal", "Досягти мети"),
        "history": [{"action": h.get("action", ""), "reply": h.get("text", "")} for h in history],
        "weapon": hero.get("weapon", "Посох"),
        "inventory": inventory,
        "NPCName": npc.get("name", "Невідомий NPC") if npc else "Невідомий NPC"
    }
    try:
        response = make_request(f"{BASE_URL}/gpt?language=uk", data=data, headers=headers)
        result = response.json()
        print(f"Perform Action: {response.status_code}, {result}")
        return result
    except HTTP429Error:
        print("Rate limit exceeded for perform_action, waiting to retry...")
        raise
    except Exception as e:
        print(f"Perform Action failed: {e}")
        return {"error": str(e)}

def run_test_scenario(heroname="Test", race="Напіврослик", character_class="Друїд"):
    """Run a single test scenario with predefined actions."""
    print("Running test scenario")
    token = authenticate_user()
    if not token:
        print("Authentication failed, exiting.")
        return

    hero = create_hero(token, heroname, race, character_class)
    if not hero:
        print("Hero creation failed, exiting.")
        return

    print(f"Created hero: {hero}")

    adventure = start_adventure(hero, token)
    if not adventure:
        print("Adventure start failed, exiting.")
        return

    history = [{"type": "reply", "text": adventure.get("intro", "")}]
    inventory = hero.get("inventory", [])
    npc = None

    for action in ACTIONS:
        time.sleep(5)  # Повернуто затримку до 5 секунд
        print(f"Performing action: {action}")
        if "поговорити з NPC" in action and not npc:
            continue

        if "використати предмет" in action and inventory:
            action = action.replace("використати предмет", f"використати {random.choice(inventory)}")
        elif "використати предмет" in action and not inventory:
            action = "оглянути місцевість"
        if "поговорити з NPC" in action and npc:
            action = action.replace("поговорити з NPC, якщо зустрів", f"поговорити з {npc.get('name', 'Невідомий NPC')}")

        result = perform_action(hero, action, history, inventory, npc, token)
        
        if "error" in result:
            print(f"Action {action} failed: {result['error']}")
            break

        history.append({"type": "action", "text": action})
        history.append({"type": "reply", "text": result.get("reply", "")})

        if result.get("newItems"):
            inventory.extend(result["newItems"])
        if result.get("removedItems"):
            inventory = [item for item in inventory if item not in result["removedItems"]]

        if result.get("npc"):
            npc = result["npc"]

        if result.get("isGoalAchieved"):
            print("Goal achieved! Final description:", result.get("finalDescription"))
            break

if __name__ == "__main__":
    print("Starting test scenario")
    run_test_scenario(heroname="TestDynamic", race="Ельф", character_class="Чарівник")