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

# data file
data_file = open("data.txt", "a")

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
    fuel purchases, loan, cargo bays, cargo bays used)
    """
    current_planet = game_object["gameState"]["planet"]
    current_credits = game_object["gameState"]["credits"]
    current_turns_left = game_object["gameState"]["turnsLeft"]
    current_market = game_object["currentMarket"]
    current_hold = game_object["gameState"]["currentHold"]
    current_fuel_purchases = game_object["gameState"]["fuelPurchases"]
    current_loan = game_object["gameState"]["loanBalance"]
    current_cargo_bays = game_object["gameState"]["totalBays"]
    current_cargo_bays_used = game_object["gameState"]["usedBays"]

    return (
        current_planet,
        current_credits,
        current_turns_left,
        current_market,
        current_hold,
        current_fuel_purchases,
        current_loan,
        current_cargo_bays,
        current_cargo_bays_used,
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
            f"""**** Buy bays error! ****
            Tried to buy {bays_to_buy} bays
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
            f"""**** Buy cargo error! ****
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
            f"""**** Travel error! ****
        Tried to travel to {chosen_planet}
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
        return None


# endregion

# region play
while not end_play:
    print(f"Starting game {game_count + 1}")
    # start new game and get json object
    game = requests.get(web_base.format(action="new_game")).json()
    # get game id
    game_id = game["gameId"]
    while not game_over:
        transactions = []

        # parse game data
        (
            planet,
            game_credits,
            turns_left,
            market,
            hold,
            fuel_purchases,
            loan,
            cargo_bays,
            cargo_bays_used,
        ) = get_game_data(game)

        # check for low cargo event
        low_cargo = is_low_market_event(market)

        # sell all cargo
        sell_profit = sell_cargo(game_id, hold, market)
        transactions.append(f"Cargo sale profit: {sell_profit}")
        game_credits += sell_profit

        # buy fuel cells
        # if should_buy_fuel_cells(planet, turns_left, fuel_purchases):
        #     bought_cells, game_credits = try_buy_fuel_cells(game_id, game_credits)
        #     if bought_cells:
        #         transactions.append("Bought 5 more turns")
        #         turns_left += 5

        # repay loan
        if should_repay_loan(planet, loan, low_cargo):
            game_credits, loan = try_repay_loan(game_id, game_credits, loan)

        if loan:
            transactions.append(f"Loan balance: {loan}")

        # buy cargo
        cargo_to_buy = should_buy_cargo(market, game_credits)
        if cargo_to_buy:
            game_credits, hold, cargo_amount_bought = try_buy_cargo(
                game_id, cargo_to_buy, market, game_credits, cargo_bays_used, cargo_bays
            )

            # add notification
            if cargo_amount_bought:
                transactions.append(
                    f"Bought {cargo_amount_bought} {cargo_to_buy} at {market[cargo_to_buy]} each"
                )

        # buy cargo bays
        if can_buy_bays(planet, cargo_bays) and should_buy_bays(
            turns_left, cargo_to_buy, game_credits
        ):
            game_credits, cargo_bays, cargo_bays_used, bays_bought = try_buy_bays(
                game_id, game_credits, cargo_bays
            )

            # add notification
            if bays_bought:
                transactions.append(f"Bought {bays_bought} bays")

            # bought more bays, try to buy cargo again
            cargo_to_buy = should_buy_cargo(market, game_credits)
            if cargo_to_buy:
                game_credits, hold, cargo_amount_bought = try_buy_cargo(
                    game_id,
                    cargo_to_buy,
                    market,
                    game_credits,
                    cargo_bays_used,
                    cargo_bays,
                )

                # add notification
                if cargo_amount_bought:
                    transactions.append(
                        f"Bought {cargo_amount_bought} {cargo_to_buy} at {market[cargo_to_buy]} each"
                    )

        # print data
        print("\nPlanet: ", planet)
        print("Turns: ", turns_left, "\tCredits: ", game_credits)

        for item in transactions:
            print(item)

        # uncomment for market and hold data
        # print("\nCargo:".ljust(15), "Market price:".ljust(15), "In hold:")
        # for cargo, price in market.items():
        #     in_hold = "-" if hold[cargo] == "0" else hold[cargo]
        #     print(f"{cargo}:".ljust(15), f"{price}".ljust(15), in_hold)

        print("\n")

        # endgame/travel
        if turns_left > 1:
            # travel
            travel_planet = choose_planet(planet, hold, loan, turns_left, cargo_bays)
            game = try_travel(game_id, travel_planet)
        else:
            # endgame
            sell_profit = sell_cargo(game_id, hold, market)

            # calculate score
            final_credits = game_credits + sell_profit
            final_loan = loan
            final_score = final_credits - final_loan
            print(
                f"Sold cargo for a total of {sell_profit}\nFinal score: {final_score}"
            )

            data_file.write(f"{final_score}\n")

            score = requests.post(
                "https://skysmuggler.com/scores/submit", json={"gameId": game_id}
            )

            if score.status_code == 200 and "New" in score.json()["message"]:
                requests.post(
                    "https://skysmuggler.com/scores/update_name",
                    json={"newName": "El Capitan", "gameId": game_id},
                )
                print("***** High score achieved *****")
            else:
                print("***** End of game *****")

            game_over = True
            game_count += 1

    # new game setup
    if game_count >= 10:
        end_play = True
    else:
        game_over = False

data_file.close()

# endregion
