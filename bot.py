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


def get_credits(current_id):
    """
    Pulls credit data from server
    :param current_id: a string holding the current game id
    :return: current game credits
    """

    return requests.get(
        web_base.format(action="game_state"), params={"gameId": current_id}
    ).json()["gameState"]["credits"]


def get_game_data(game_object):
    """
    Parses game state data into variables from json object
    :param game_object: a json object with game state data
    :return: tuple of (current planet, turns left, current market, current cargo hold)
    """
    current_planet = game_object["gameState"]["planet"]
    current_turns_left = game_object["gameState"]["turnsLeft"]
    current_market = game_object["currentMarket"]
    current_hold = game_object["gameState"]["currentHold"]
    current_fuel_purchases = game_object["gameState"]["fuelPurchases"]
    current_loan = game_object["gameState"]["loanBalance"]

    return (
        current_planet,
        current_turns_left,
        current_market,
        current_hold,
        current_fuel_purchases,
        current_loan,
    )


def is_low_market_event(current_market):
    """
    Determines if a low market event happened by looking at market prices and comparing to price limits
    :param game_market: dictionary of cargo:price keys and values
    :return: cargo type if low market event, else empty string
    """

    for cargo, amount in current_market.items():
        if amount and amount < MIN_CARGO_PRICES[cargo]:
            return cargo

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


def try_buy_fuel_cells(current_id):
    """
    Attempts to purchase fuel cells
    :param current_id: a string holding the current game id
    :return: string indicating result of transaction
    """
    status_code = requests.post(
        web_base.format(action="fueldepot"),
        data={"gameId": current_id, "transaction": {"side": "buy", "qty": 5}},
    ).status_code

    if status_code == 200:
        return "Purchased 5 more turns"
    else:
        return "Unable to purchase turns"


def try_repay_loan(current_id, current_credits):
    """
    Attempts to repay the loan shark with available credits
    :param current_id: a string holding the current game id
    :param current_credits: available credits
    :return: string indicating result of transaction
    """
    # TODO: consider a smarter way to repay loanshark
    status_code = requests.post(
        web_base.format(action="loanshark"),
        data={
            "gameId": current_id,
            "transaction": {"side": "borrow", "qty": current_credits},
        },
    ).status_code

    if status_code == 200:
        return ""


# endregion

# region play

while not end_play:
    # start new game and get json object
    game = requests.get(web_base.format(action="new_game")).json()
    # get game id
    game_id = game["gameId"]

    while not game_over:

        # parse game data
        planet, turns_left, market, hold, fuel_purchases, loan = get_game_data(game)

        # check for low cargo event
        low_cargo = is_low_market_event(market)

        # sell all cargo
        sell_cargo(game_id, game["gameState"]["currentHold"])

        # update credits
        game_credits = get_credits(game_id)

        # buy fuel cells
        if should_buy_fuel_cells(planet, turns_left, fuel_purchases):
            print(try_buy_fuel_cells(game_id))

        # repay loan
        if should_repay_loan(planet, loan, low_cargo):
            print(try_repay_loan(game_id, game_credits))

        print(planet)
        print(turns_left)
        print(market)
        print(hold)
        print(f"credits: {game_credits}")
        print(f"game: {game_count}")
        game_over = True
        game_count += 1

    # new game setup
    if game_count >= 3:
        end_play = True
    else:
        game_over = False

# endregion
