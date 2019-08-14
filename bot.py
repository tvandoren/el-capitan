import random
import requests

# region setup

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

# play flags
end_play = False
game_over = False

# number of games played
game_count = 0

# endregion

# region game functions


def can_buy_bays(current_planet, current_cargo_bays):
    """
    Checks if actually possible to buy more cargo bays this turn
    :param current_planet: the name of the current planet
    :param current_cargo_bays: number of cargo bays acquired
    :return: True if correct planet and bays can still be purchased, else False
    """

    return current_planet == "taspra" and current_cargo_bays < 1_000


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
    if current_loan and current_turns_left < 18 and "umbriel" in planet_list:
        # top priority is paying off loanshark after making enough credits
        chosen_planet = "umbriel"
    elif "taspra" in planet_list and current_cargo_bays < 1_000:
        # travel to taspra to buy more bays
        chosen_planet = "taspra"
    elif "pertia" in planet_list and current_turns_left < 15:
        # pertia is a fairly safe planet to travel to later game, since metal is not as helpful
        chosen_planet = "pertia"
    else:
        # don't go to umbriel or earth accidentally (want to be able to buy weapons and narcotics)
        try:
            planet_list.remove("umbriel")
            planet_list.remove("earth")
        except KeyError:
            pass

        # choose a planet from those left in the list
        chosen_planet = random.choice(planet_list)

    # return chosen planet
    return chosen_planet


def get_game_variable(current_id, requested_variable):
    """
    Pulls credit data from server
    :param current_id: a string holding the current game id
    :param requested_variable: a string holding the gamestate variable desired
    :return: current game credits
    """
    return requests.get(
        web_base.format(action="game_state"), params={"gameId": current_id}
    ).json()["gameState"][requested_variable]


def get_game_data(game_object):
    """
    Parses game state data into variables from json object
    :param game_object: a json object with game state data
    :return: tuple of current (planet, turns left, market, hold, fuel purchases, loan, cargo bays)
    """
    current_planet = game_object["gameState"]["planet"]
    current_turns_left = game_object["gameState"]["turnsLeft"]
    current_market = game_object["currentMarket"]
    current_hold = game_object["gameState"]["currentHold"]
    current_fuel_purchases = game_object["gameState"]["fuelPurchases"]
    current_loan = game_object["gameState"]["loanBalance"]
    current_cargo_bays = game_object["gameState"]["totalBays"]

    return (
        current_planet,
        current_turns_left,
        current_market,
        current_hold,
        current_fuel_purchases,
        current_loan,
        current_cargo_bays,
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


def sell_cargo(current_id, current_hold):
    """
    Sells all cargo in hold
    :param current_id: a string holding the current game id
    :param current_hold: dictionary of cargo:quantity keys and values
    :return: dictionary of cargo:total_profit keys and values
    """

    for cargo_type, amount in current_hold.items():
        if amount:
            requests.post(
                web_base.format(action="trade"),
                data={
                    "gameId": current_id,
                    "transaction": {"side": "sell", cargo_type: amount},
                },
            )


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


def should_buy_cargo(current_market, current_credits):
    """
    Checks against user-define criteria for if buying any cargo type is a good choice
    :param current_market: dictionary of cargo:price keys and values
    :param current_credits: amount of available credits
    :return: preferred type of cargo to buy if one is found, else empty string
    """

    chosen_cargo = ""
    chosen_cargo_percentage = 0

    # expense percentage rate
    acceptable_percentage = 0.09

    # cargo weight used to determine preferred cargo
    cargo_weight = {
        "mining": 0.90,
        "medical": 0.95,
        "narcotics": 0.95,
        "weapons": 1.0,
        "water": 0.75,
        "metal": 0.35,
        "": 1.0,
    }

    # keep track of cheapest cargo by percentage
    for cargo_type, current_price in current_market.items():
        try:
            # find percentage that cargo is over/under average
            percentage_under = (
                AVG_CARGO_PRICES[cargo_type] - current_price
            ) / AVG_CARGO_PRICES[cargo_type]

            # cargo is cheap enough, is affordable, and more preferable than previous cargo
            if (
                percentage_under > acceptable_percentage
                and current_price < current_credits
                and percentage_under * cargo_weight[cargo_type]
                > chosen_cargo_percentage * cargo_weight[chosen_cargo]
            ):
                chosen_cargo = cargo_type
                chosen_cargo_percentage = percentage_under
        except TypeError:
            # cargo not available on planet
            pass

    return chosen_cargo


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
        and current_fuel_purchases < 5
    )


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


def try_buy_bays(current_id, current_credits, current_cargo_bays):
    """
    Attempts to purchase half the amount of bays affordable
    :param current_id: a string holding the current game id
    :param current_credits: amount of available credits
    :param current_cargo_bays: number of cargo bays acquired
    :return: string indicating result of transaction
    """
    cargo_bay_cost = 800

    potential_bays = (current_credits // cargo_bay_cost) // 2

    bays_to_buy = (
        potential_bays
        if (current_cargo_bays + potential_bays) <= 1000
        else 1000 - current_cargo_bays
    )

    transaction_status_code = requests.post(
        web_base.format(action="shipyard"),
        data={"gameId": current_id, "transaction": {"side": "buy", "qty": bays_to_buy}},
    ).status_code

    if transaction_status_code == 200:
        return f"Purchased {bays_to_buy} bays"
    else:
        return "Shipyard transaction error"


def try_buy_cargo(current_id, chosen_cargo, current_market, current_credits):
    """
    Attempts to purchase given cargo
    :param current_id: a string holding the current game id
    :param chosen_cargo: cargo to buy
    :param current_market: dictionary of cargo:price keys and values
    :param current_credits: amount of available credits
    :return: string indicating result of transaction
    """
    cargo_amount = current_credits // current_market[chosen_cargo]
    print(f"buying {chosen_cargo}. Credits: {current_credits}")

    transaction_status_code = requests.post(
        web_base.format(action="trade"),
        data={
            "gameId": current_id,
            "transaction": {"side": "buy", chosen_cargo: cargo_amount},
        },
    )

    print(f"json: {transaction_status_code.json()}")

    if transaction_status_code.status_code == 200:
        return f"Purchased {cargo_amount} {chosen_cargo} at {current_market[chosen_cargo]} credits each"
    else:
        return f"Buy cargo error"


def try_buy_fuel_cells(current_id):
    """
    Attempts to purchase fuel cells
    :param current_id: a string holding the current game id
    :return: string indicating result of transaction
    """
    transaction_status_code = requests.post(
        web_base.format(action="fueldepot"),
        data={"gameId": current_id, "transaction": {"side": "buy", "qty": 5}},
    ).status_code

    if transaction_status_code == 200:
        return "Purchased 5 more turns"
    else:
        return "Unable to purchase turns"


def try_repay_loan(current_id, current_credits, current_loan):
    """
    Attempts to repay the loan shark with available credits
    :param current_id: a string holding the current game id
    :param current_credits: amount of available credits
    :param current_loan: number of credits owed to the loanshark
    :return: string indicating result of transaction
    """
    # TODO: consider a smarter way to repay loanshark
    repay_amount = current_credits if current_loan > current_credits else current_loan

    transaction_status_code = requests.post(
        web_base.format(action="loanshark"),
        data={
            "gameId": current_id,
            "transaction": {"side": "borrow", "qty": repay_amount},
        },
    ).status_code

    if transaction_status_code == 200:
        return f"Paid {repay_amount} to the loanshark"
    else:
        return "Loanshark error"


def try_travel(current_id, chosen_planet):
    """
    Attempt to travel to planet passed in
    :param current_id: a string holding the current game id
    :param chosen_planet: planet to travel to
    :return: string indicating result of request
    """
    transaction_status_code = requests.post(
        web_base.format(action="travel"),
        data={"gameId": current_id, "toPlanet": chosen_planet},
    ).status_code

    print(f"code: {transaction_status_code}")

    if transaction_status_code == 200:
        return f"**** Traveled to {chosen_planet} ****"
    else:
        return "Travel error!"


# endregion

# region play
while not end_play:
    print("Starting game")
    # start new game and get json object
    game = requests.get(web_base.format(action="new_game")).json()
    # get game id
    game_id = game["gameId"]
    while not game_over:
        print("Starting turn")
        transactions = []

        # parse game data
        planet, turns_left, market, hold, fuel_purchases, loan, cargo_bays = get_game_data(
            game
        )

        # check for low cargo event
        low_cargo = is_low_market_event(market)

        # sell all cargo
        sell_cargo(game_id, game["gameState"]["currentHold"])

        # update credits
        game_credits = get_game_variable(game_id, "credits")

        # buy fuel cells
        if should_buy_fuel_cells(planet, turns_left, fuel_purchases):
            transactions.append(try_buy_fuel_cells(game_id))
            turns_left = get_game_variable(game_id, "turnsLeft")

        # repay loan
        if should_repay_loan(planet, loan, low_cargo):
            transactions.append(try_repay_loan(game_id, game_credits, loan))

        # update credits
        game_credits = get_game_variable(game_id, "credits")

        # buy cargo
        cargo_to_buy = should_buy_cargo(market, game_credits)
        if cargo_to_buy:
            transactions.append(
                try_buy_cargo(game_id, cargo_to_buy, market, game_credits)
            )
            hold = get_game_variable(game_id, "currentHold")

        # update credits
        game_credits = get_game_variable(game_id, "credits")

        # buy cargo bays
        if can_buy_bays(planet, cargo_bays) and should_buy_bays(
            turns_left, cargo_to_buy, game_credits
        ):
            transactions.append(try_buy_bays(game_id, game_credits, cargo_bays))
            cargo_bays = get_game_variable(game_id, "totalBays")

        # print data
        print("\nPlanet: ", planet)
        print("Turns: ", turns_left, "\tCredits: ", game_credits)

        for item in transactions:
            print(item)

        print("\nCargo:".ljust(15), "Market price:".ljust(15), "In hold:")
        for cargo, price in market.items():
            in_hold = "-" if hold[cargo] == "0" else hold[cargo]
            print(f"{cargo}:".ljust(15), f"{price}".ljust(15), in_hold)

        print("\n")

        # endgame/travel
        if turns_left > 1:
            # travel
            travel_planet = choose_planet(planet, hold, loan, turns_left, cargo_bays)
            print(try_travel(game_id, travel_planet))
        else:
            # endgame
            sell_cargo(game_id, game["gameState"]["currentHold"])

            high_score_code = requests.post(
                "https://skysmuggler.com/scores/submit", data={"gameId": game_id}
            ).status_code

            if high_score_code == 200:
                requests.post(
                    "https://skysmuggler.com/scores/update_name",
                    data={"newName": "El Capitan", "gameId": game_id},
                )
                print("***** High score achieved *****")
            else:
                print("***** End of game *****")

            game_over = True
            game_count += 1

    # new game setup
    if game_count >= 1:
        end_play = True
    else:
        game_over = False

# endregion
