import random
import requests


# cargo price data
AVG_CARGO_PRICES = {
    "mining": 2_150,
    "medical": 3_650,
    "narcotics": 40_000,
    "weapons": 70_000,
    "water": 17_500,
    "metal": 700,
}

MIN_CARGO_PRICES = {
    "mining": 1_500,
    "medical": 1_800,
    "narcotics": 20_000,
    "weapons": 50_000,
    "water": 14_000,
    "metal": 300,
}

# web address base for request types
web_base = "https://skysmuggler.com/game/{action}"


def can_buy_bays(current_planet, current_cargo_bays):
    """
    Checks if actually possible to buy more cargo bays this turn
    :param current_planet: the name of the current planet
    :param current_cargo_bays: number of cargo bays acquired
    :return: True if correct planet and bays can still be purchased, else False
    """
    return current_planet == "taspra" and current_cargo_bays < 1_000


def choose_cargo_to_buy(
    current_market, current_credits, current_bays_used, current_cargo_bays
):
    """
    Checks against user-defined criteria to choose a cargo to buy (none if no good choice)
    :param current_market: dictionary of cargo:price keys and values
    :param current_credits: amount of available credits
    :param current_bays_used: number of cargo bays in use
    :param current_cargo_bays: number of cargo bays acquired
    :return: preferred type of cargo to buy if one is found, else empty string
    """
    chosen_cargo = ""
    chosen_cargo_profit = 0

    bays_available = current_cargo_bays - current_bays_used

    for cargo_type, current_price in current_market.items():
        if current_price:
            # find potential profit based on average prices
            potential_cargo_amount = current_credits // current_market[cargo_type]
            per_item_profit = AVG_CARGO_PRICES[cargo_type] - current_price
            cargo_amount = (
                potential_cargo_amount
                if potential_cargo_amount <= bays_available
                else bays_available
            )

            potential_cargo_profit = cargo_amount * per_item_profit

            # compare to previous highest profit, replace cargo if necessary
            if potential_cargo_profit > chosen_cargo_profit:
                chosen_cargo = cargo_type
                chosen_cargo_profit = potential_cargo_profit

    return chosen_cargo


def choose_planet(
    current_planet, current_hold, current_loan, current_turns_left, current_cargo_bays
):
    """
    Picks planet to travel to based on various game data
    :param current_planet: the name of the current planet
    :param current_hold: dictionary of cargo:quantity keys and values
    :param current_loan: number of credits owed to loan shark
    :param current_turns_left: the number of turns left in the game
    :param current_cargo_bays: number of cargo bays acquired
    :return: string containing chosen planet
    """
    planet_list = ["pertia", "earth", "taspra", "caliban", "umbriel", "setebos"]

    banned_cargo = {
        "metal": "pertia",
        "narcotics": "earth",
        "medical": "taspra",
        "mining": "caliban",
        "weapons": "umbriel",
        "water": "setebos",
    }

    # remove current planet
    planet_list.remove(current_planet)

    # remove planets that cargo can't be sold at
    for cargo_type, amount in current_hold.items():
        if amount > 0:
            try:
                planet_list.remove(banned_cargo[cargo_type])
            except KeyError:
                pass

    # choose preferred planet if still in list
    # top priority is paying off loanshark after making enough credits
    if current_loan and current_turns_left < 18 and "umbriel" in planet_list:
        chosen_planet = "umbriel"
    # travel to taspra to buy more bays
    elif "taspra" in planet_list and current_cargo_bays < 1_000:
        chosen_planet = "taspra"
    # earth should be traveled to (only) later in the game in order to make bank deposits
    elif "earth" in planet_list and 2 < current_turns_left < 16:
        chosen_planet = "earth"
    # pertia should be traveled to later in the game to buy more turns
    elif "pertia" in planet_list and current_turns_left < 15:
        chosen_planet = "pertia"
    else:
        # don't go to umbriel or earth accidentally (want to be able to buy weapons and narcotics)
        try:
            planet_list.remove("umbriel")
        except ValueError:
            pass

        try:
            planet_list.remove("earth")
        except ValueError:
            pass

        # choose a planet from those left in the list
        chosen_planet = random.choice(planet_list)

    # return chosen planet
    return chosen_planet


def get_game_data(game_object):
    """
    Parses game state data into variables from json object
    :param game_object: a json object with game state data
    :return: tuple of current (planet, credits, turns left, market, hold,
    fuel purchases, loan, cargo bays, bank balance)
    """
    current_planet = game_object["gameState"]["planet"]
    current_credits = game_object["gameState"]["credits"]
    current_turns_left = game_object["gameState"]["turnsLeft"]
    current_market = game_object["currentMarket"]
    current_hold = game_object["gameState"]["currentHold"]
    current_fuel_purchases = game_object["gameState"]["fuelPurchases"]
    current_loan = game_object["gameState"]["loanBalance"]
    current_cargo_bays = game_object["gameState"]["totalBays"]
    current_bank_balance = game_object["gameState"]["bankBalance"]

    return (
        current_planet,
        current_credits,
        current_turns_left,
        current_market,
        current_hold,
        current_fuel_purchases,
        current_loan,
        current_cargo_bays,
        current_bank_balance,
    )


def is_low_market_event(current_market):
    """
    Determines if a low market event happened by looking at market prices and comparing to price limits
    :param current_market: dictionary of cargo:price keys and values
    :return: cargo type if low market event, else empty string
    """
    for cargo_type, amount in current_market.items():
        if amount and amount < MIN_CARGO_PRICES[cargo_type]:
            return cargo_type

    # low cargo wasn't found, so return empty string
    return ""


def sell_cargo(current_id, current_hold, current_market):
    """
    Sells all cargo in hold
    :param current_id: a string holding the current game id
    :param current_hold: dictionary of cargo:quantity keys and values
    :param current_market: dictionary of cargo:price keys and values
    :return: total profit from selling cargo
    """
    current_profit = 0

    for cargo_type, amount in current_hold.items():
        if amount:
            requests.post(
                web_base.format(action="trade"),
                json={
                    "gameId": current_id,
                    "transaction": {"side": "sell", cargo_type: amount},
                },
            )

            current_profit += amount * current_market[cargo_type]

    return current_profit


def should_buy_bays(current_turns_left, did_buy, current_credits):
    """
    Checks against defined criteria for if buying more cargo bays is a good choice
    right now (enough credits to buy bays and still have surplus, cargo should have
    been purchased on turn, and bays should not be purchased near end of game)
    :param current_turns_left: the number of turns left in the game
    :param did_buy: cargo chosen to buy (empty string if no cargo was chosen)
    :param current_credits: amount of available credits
    :return: True if criteria met, otherwise False
    """
    return current_turns_left > 2 and did_buy and current_credits > 1_600


def should_buy_fuel_cells(current_planet, current_turns_left, current_fuel_purchases):
    """
    Checks against user-defined criteria for if buying more fuel cells is a good choice
    :param current_planet: the name of the current planet
    :param current_turns_left: the number of turns left in the game
    :param current_fuel_purchases: total number of times fuel cells have been purchased
    :return: True if buying fuel cells is deemed correct action
    """
    # TODO: come up with better algorithm for deciding to buy fuel cells
    return (
        current_planet == "pertia"
        and current_turns_left < 5
        and current_fuel_purchases < 8
    )


def should_deposit(current_planet, did_withdraw, current_credits):
    """
    Checks against defined criteria for if a deposit should be made to the bank
    :param current_planet: the name of the current planet
    :param did_withdraw: True if a withdrawal was made on the same turn
    :param current_credits: amount of available credits
    :return: True if criteria met, otherwise false
    """
    return current_planet == "earth" and (current_credits > 500_000 or did_withdraw)


def should_repay_loan(current_planet, current_loan, current_low_cargo):
    """
    Checks against user-defined criteria for if buying more fuel cells is a good choice
    right now
    :param current_planet: string name of current planet
    :param current_loan: number of credits owed to loan shark
    :param current_low_cargo: string name of cargo if there is a low market event, empty string otherwise
    :return: True if repaying loan is deemed correct action
    """
    return current_planet == "umbriel" and current_loan > 0 and not current_low_cargo


def try_bank_transaction(current_id, current_transaction_amount, bank_action):
    """
    Attempts to deposit all available credits to the bank
    :param current_id: a string holding the current game id
    :param current_transaction_amount: amount of credits to complete bank transaction with
    :param bank_action: string name of bank action. Must either be "withdraw" or "deposit
    :return: tuple of credits and bank balance
    """
    deposit_transaction = requests.post(
        web_base.format(action="bank"),
        json={
            "gameId": current_id,
            "transaction": {"side": bank_action, "qty": current_transaction_amount},
        },
    )

    if deposit_transaction.status_code == 200:
        return (
            deposit_transaction.json()["gameState"]["credits"],
            deposit_transaction.json()["gameState"]["bankBalance"],
        )
    else:
        error_state = requests.get(
            web_base.format(action="game_state"), params={"gameId": current_id}
        ).json()
        print(
            f"""
        **** Bank {bank_action} error! ****
        Tried to {bank_action} {current_transaction_amount} credits
        **** GAME ****
        planet: {error_state["gameState"]["planet"]}
        credits: {error_state["gameState"]["credits"]}
        bankBalance: {error_state["gameState"]["bankBalance"]}
        **** HOLD ****
        narcotics: {error_state["gameState"]["currentHold"]["narcotics"]}
        mining: {error_state["gameState"]["currentHold"]["mining"]}
        medical: {error_state["gameState"]["currentHold"]["medical"]}
        metal: {error_state["gameState"]["currentHold"]["metal"]}
        weapons: {error_state["gameState"]["currentHold"]["weapons"]}
        water: {error_state["gameState"]["currentHold"]["water"]}
        """
        )
        return (
            error_state["gameState"]["credits"],
            error_state["gameState"]["bankBalance"],
        )


def try_buy_bays(current_id, current_credits, current_cargo_bays):
    """
    Attempts to purchase half the amount of bays affordable
    :param current_id: a string holding the current game id
    :param current_credits: amount of available credits
    :param current_cargo_bays: number of cargo bays acquired
    :return: tuple of credits, cargo bays, used bays, and bays bought
    """
    cargo_bay_cost = 800

    potential_bays = (current_credits // cargo_bay_cost) // 2

    bays_to_buy = (
        potential_bays
        if (current_cargo_bays + potential_bays) <= 1000
        else 1000 - current_cargo_bays
    )

    buy_transaction = requests.post(
        web_base.format(action="shipyard"),
        json={"gameId": current_id, "transaction": {"side": "buy", "qty": bays_to_buy}},
    )

    if buy_transaction.status_code == 200:
        return (
            buy_transaction.json()["gameState"]["credits"],
            buy_transaction.json()["gameState"]["totalBays"],
            buy_transaction.json()["gameState"]["usedBays"],
            bays_to_buy,
        )
    else:
        error_state = requests.get(
            web_base.format(action="game_state"), params={"gameId": current_id}
        ).json()
        print(
            f"""
        **** Buy bays error! ****
        Tried to buy {bays_to_buy} bays
        **** GAME ****
        planet: {error_state["gameState"]["planet"]}
        credits: {error_state["gameState"]["credits"]}
        usedBays: {error_state["gameState"]["usedBays"]}
        totalBays: {error_state["gameState"]["totalBays"]}
        """
        )
        return (
            error_state["gameState"]["credits"],
            error_state["gameState"]["totalBays"],
            error_state["gameState"]["usedBays"],
            0,
        )


def try_buy_cargo(
    current_id,
    chosen_cargo,
    current_market,
    current_credits,
    current_bays_used,
    current_cargo_bays,
):
    """
    Attempts to purchase given cargo
    :param current_id: a string holding the current game id
    :param chosen_cargo: cargo to buy
    :param current_market: dictionary of cargo:price keys and values
    :param current_credits: amount of available credits
    :param current_bays_used: number of cargo bays in use
    :param current_cargo_bays: number of cargo bays acquired
    :return: tuple of game credits, hold, and amount of cargo bought
    """
    potential_cargo_amount = current_credits // current_market[chosen_cargo]
    bays_available = current_cargo_bays - current_bays_used

    cargo_amount = (
        potential_cargo_amount
        if potential_cargo_amount <= bays_available
        else bays_available
    )

    buy_transaction = requests.post(
        web_base.format(action="trade"),
        json={
            "gameId": current_id,
            "transaction": {"side": "buy", chosen_cargo: cargo_amount},
        },
    )

    if buy_transaction.status_code == 200:
        return (
            buy_transaction.json()["gameState"]["credits"],
            buy_transaction.json()["gameState"]["currentHold"],
            cargo_amount,
        )
    else:
        error_state = requests.get(
            web_base.format(action="game_state"), params={"gameId": current_id}
        ).json()
        print(
            f"""
        **** Buy cargo error! ****
        Tried to buy {cargo_amount} {chosen_cargo} at {current_market[chosen_cargo]}
        **** GAME ****
        planet: {error_state["gameState"]["planet"]}
        credits: {error_state["gameState"]["credits"]}
        usedBays: {error_state["gameState"]["usedBays"]}
        totalBays: {error_state["gameState"]["totalBays"]}
        **** HOLD ****
        narcotics: {error_state["gameState"]["currentHold"]["narcotics"]}
        mining: {error_state["gameState"]["currentHold"]["mining"]}
        medical: {error_state["gameState"]["currentHold"]["medical"]}
        metal: {error_state["gameState"]["currentHold"]["metal"]}
        weapons: {error_state["gameState"]["currentHold"]["weapons"]}
        water: {error_state["gameState"]["currentHold"]["water"]}
        """
        )
        return (
            error_state["gameState"]["credits"],
            error_state["gameState"]["currentHold"],
            0,
        )


def try_buy_fuel_cells(current_id, current_credits):
    """
    Attempts to purchase fuel cells
    :param current_id: a string holding the current game id
    :param current_credits: amount of available credits
    :return: tuple of transaction success and game credits
    """
    buy_transaction = requests.post(
        web_base.format(action="fueldepot"),
        json={"gameId": current_id, "transaction": {"side": "buy", "qty": 5}},
    )

    if buy_transaction.status_code == 200:
        return True, buy_transaction.json()["gameState"]["credits"]
    else:
        print("Not enough credits for fuel cells")
        return False, current_credits


def try_repay_loan(current_id, current_credits, current_loan):
    """
    Attempts to repay the loan shark with available credits
    :param current_id: a string holding the current game id
    :param current_credits: amount of available credits
    :param current_loan: number of credits owed to the loanshark
    :return: tuple of game credits and outstanding loan amount
    """
    # TODO: consider a smarter way to repay loanshark
    repay_amount = current_credits if current_loan > current_credits else current_loan

    loan_transaction = requests.post(
        web_base.format(action="loanshark"),
        json={
            "gameId": current_id,
            "transaction": {"side": "repay", "qty": repay_amount},
        },
    )

    return (
        loan_transaction.json()["gameState"]["credits"],
        loan_transaction.json()["gameState"]["loanBalance"],
    )


def try_travel(current_id, chosen_planet):
    """
    Attempt to travel to planet passed in
    :param current_id: a string holding the current game id
    :param chosen_planet: planet to travel to
    :return: json object of game data if transaction was a success, else print
    error message and return None
    """
    travel_transaction = requests.post(
        web_base.format(action="travel"),
        json={"gameId": current_id, "toPlanet": chosen_planet},
    )

    if travel_transaction.status_code == 200:
        return travel_transaction.json()
    else:
        error_state = requests.get(
            web_base.format(action="game_state"), params={"gameId": current_id}
        ).json()
        print(
            f"""
        **** Travel error! ****
        Tried to travel to {chosen_planet}
        **** GAME ****
        planet: {error_state["gameState"]["planet"]}
        credits: {error_state["gameState"]["credits"]}
        **** HOLD ****
        narcotics: {error_state["gameState"]["currentHold"]["narcotics"]}
        mining: {error_state["gameState"]["currentHold"]["mining"]}
        medical: {error_state["gameState"]["currentHold"]["medical"]}
        metal: {error_state["gameState"]["currentHold"]["metal"]}
        weapons: {error_state["gameState"]["currentHold"]["weapons"]}
        water: {error_state["gameState"]["currentHold"]["water"]}
        """
        )
        return None
