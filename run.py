import requests
import services


# web address base for request types
web_base = "https://skysmuggler.com/game/{action}"

# play flags
end_play = False
game_over = False

# number of games played
game_count = 0

# data file
data_file = open("data.txt", "a")

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
            bank_balance,
        ) = services.get_game_data(game)

        # check for low cargo event
        low_cargo = services.is_low_market_event(market)

        # sell all cargo
        sell_profit = services.sell_cargo(game_id, hold, market)
        cargo_bays_used = 0
        transactions.append(f"Cargo sale profit: {sell_profit}")
        game_credits += sell_profit

        # buy fuel cells
        if services.should_buy_fuel_cells(planet, turns_left, fuel_purchases):
            bought_cells, game_credits = services.try_buy_fuel_cells(
                game_id, game_credits
            )
            if bought_cells:
                transactions.append("Bought 5 more turns")
                turns_left += 5

        # repay loan
        if services.should_repay_loan(planet, loan, low_cargo):
            game_credits, loan = services.try_repay_loan(game_id, game_credits, loan)

        if loan:
            transactions.append(f"Loan balance: {loan}")

        # withdraw from bank
        bank_withdrawal = False

        if planet == "earth" and bank_balance:
            game_credits, bank_balance = services.try_bank_transaction(
                game_id, bank_balance, "withdraw"
            )
            bank_withdrawal = True

        # buy cargo
        cargo_to_buy = services.should_buy_cargo(market, game_credits)
        if cargo_to_buy:
            game_credits, hold, cargo_amount_bought = services.try_buy_cargo(
                game_id, cargo_to_buy, market, game_credits, cargo_bays_used, cargo_bays
            )

            # add notification
            if cargo_amount_bought:
                transactions.append(
                    f"Bought {cargo_amount_bought} {cargo_to_buy} at {market[cargo_to_buy]} each"
                )

        # deposit to bank
        if services.should_deposit(planet, bank_withdrawal, game_credits):
            deposit_amount = game_credits if bank_withdrawal else game_credits * 0.5
            game_credits, bank_balance = services.try_bank_transaction(
                game_id, deposit_amount, "deposit"
            )

        # add notification
        if bank_balance:
            transactions.append(f"Bank balance: {bank_balance}")

        # buy cargo bays
        if services.can_buy_bays(planet, cargo_bays) and services.should_buy_bays(
            turns_left, cargo_to_buy, game_credits
        ):
            game_credits, cargo_bays, cargo_bays_used, bays_bought = services.try_buy_bays(
                game_id, game_credits, cargo_bays
            )

            # add notification
            if bays_bought:
                transactions.append(f"Bought {bays_bought} bays")

            # bought more bays, try to buy cargo again
            cargo_to_buy = services.should_buy_cargo(market, game_credits)
            if cargo_to_buy:
                game_credits, hold, cargo_amount_bought = services.try_buy_cargo(
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
            travel_planet = services.choose_planet(
                planet, hold, loan, turns_left, cargo_bays
            )
            game = services.try_travel(game_id, travel_planet)
        else:
            # endgame
            sell_profit = services.sell_cargo(game_id, hold, market)

            # calculate score
            final_credits = game_credits + sell_profit
            final_score = final_credits - loan + bank_balance
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
    if game_count >= 1:
        end_play = True
    else:
        game_over = False

data_file.close()

# endregion
