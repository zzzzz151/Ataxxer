from engine import Engine
from sprt_math import SPRT
import ataxx
import time
import random

GAME_RESULT_NORMAL = 0
GAME_RESULT_OUT_OF_TIME = 1
GAME_RESULT_ILLEGAL_MOVE = 2

def worker(process_id: int, 
           exe1: str, 
           exe2: str, 
           shared_data: dict, 
           tc_milliseconds: int, 
           tc_increment_milliseconds: int, 
           openings: list[str], 
           sprt: SPRT,
           rating_interval: int):

    print("Starting worker", process_id)

    assert len(openings) >= 1
    assert len(shared_data.keys()) == 6

    # Debug file to log messages between this worker and its 2 engines
    # Each worker creates his own debug file (debug/1.txt, debug/2.txt, debug/3.txt, ...)
    debug_file = open("debug/" + str(process_id) + ".txt", "w")

    board = None # Our ataxx board, using the python ataxx library
    eng1 = Engine(exe1, debug_file) # Engine 1, passed in program args
    eng2 = Engine(exe2, debug_file) # Engine 2, passed in program args
    eng_red = None     # Engine playing red
    eng_blue = None    # Engine playing blue
    eng_to_play = None # Engine to move

    opening_index = -1
    must_repeat_opening = False

    # Send "go btime <btime> wtime <wtime> binc <binc> winc <winc>" to engine to move
    def send_go():
        nonlocal board, eng1, eng2, eng_red, eng_blue, eng_to_play
        assert board != None
        assert eng1 != None and eng2 != None
        assert eng_red != None and eng_blue != None
        assert eng_to_play != None

        command = "go"
        command += " btime " + str(eng_red.milliseconds)
        command += " wtime " + str(eng_blue.milliseconds)
        command += " binc " + str(tc_increment_milliseconds)
        command += " winc " + str(tc_increment_milliseconds)
        eng_to_play.send(command)

    # Setup a game and play it until its over, returning the result (see constants)
    def play_game():
        nonlocal board, eng1, eng2, eng_red, eng_blue, eng_to_play
        nonlocal opening_index, must_repeat_opening
        assert eng1 != None and eng2 != None

        eng1.send("uainewgame")
        eng2.send("uainewgame")

        # Get opening
        repeating = must_repeat_opening
        if must_repeat_opening:
            opening = openings[opening_index].strip()
            must_repeat_opening = False
        else:
            opening_index += 1
            if opening_index >= len(openings):
                opening_index = 0
            opening = openings[opening_index].strip()
            must_repeat_opening = True

        # Initialize ataxx board, eng_red, eng_blue, eng_to_play
        board = ataxx.Board(opening)
        if repeating:
            eng_red = eng2
            eng_blue = eng1
        else:
            eng_red = eng1
            eng_blue = eng2
        assert opening[-5] == "x" or opening[-5] == "o"
        eng_to_play = eng_red if opening[-5] == "x" else eng_blue

        # Reset each engine's time
        eng1.milliseconds = eng2.milliseconds = tc_milliseconds

        assert board != None
        assert eng_red != None and eng_blue != None and eng_to_play != None
        assert eng_red != eng_blue
        assert eng_to_play == eng_red or eng_to_play == eng_blue
        assert eng_to_play == eng1 or eng_to_play == eng2

        # Play out game until its over
        while True:
            # Send "position fen <fen>" to both engines
            fen = board.get_fen()
            eng1.send("position fen " + fen)
            eng2.send("position fen " + fen)

            # Send go command and initialize time this turn started
            send_go()
            start_time = time.time()

            # Wait for "bestmove <move>" from the engine
            while True:
                line = eng_to_play.read_line()
                if line.startswith("bestmove"):
                    break

            # Subtract the time the engine took this turn
            eng_to_play.milliseconds -= int((time.time() - start_time) * 1000)

            if eng_to_play.milliseconds <= 0:
                return GAME_RESULT_OUT_OF_TIME

            # Get the move from the "bestmove <move>" command the engine sent
            str_move = line.split(" ")[-1].strip()
            move = ataxx.Move.from_san(str_move)

            if not board.is_legal(move):
                return GAME_RESULT_ILLEGAL_MOVE

            board.makemove(move)

            if board.gameover():
                return GAME_RESULT_NORMAL

            # Add increment to engine that just played this turn
            eng_to_play.milliseconds += tc_increment_milliseconds

            # Switch sides: the other engine will play the next turn
            eng_to_play = eng_red if eng_to_play == eng_blue else eng_blue

    # Main loop, play games over and over
    while True:
        # Play a full game and get the result (see constants)
        game_result_type = play_game()

        # Update shared_data variables between the processes: wins, losses, draws, etc
        shared_data["games"].value += 1
        # If game over due to out of time or illegal move
        if game_result_type != GAME_RESULT_NORMAL:
            # if red lost
            if eng_to_play == eng_red: 
                shared_data["l_red"].value += 1
            # else blue lost
            else: 
                assert eng_to_play == eng_blue
                shared_data["w_red"].value += 1
            # if eng1 lost
            if eng_to_play == eng1: 
                shared_data["l"].value += 1
            # else eng1 won
            else:
                assert eng_to_play == eng2
                shared_data["w"].value += 1
        # Else game is over naturally
        else:
            str_result = board.result().strip()
            # if red won
            if str_result == "1-0": 
                shared_data["w_red"].value += 1
                # if eng1 won as red
                if eng1 == eng_red:
                    shared_data["w"].value += 1
                # else eng1 lost as blue
                else: 
                    assert eng1 == eng_blue and eng2 == eng_red
                    shared_data["l"].value += 1
            # else if blue won
            elif str_result == "0-1":
                shared_data["l_red"].value += 1
                # if eng1 won as blue
                if eng1 == eng_blue: 
                    shared_data["w"].value += 1
                # else eng1 lost as red
                else: 
                    assert eng1 == eng_red and eng2 == eng_blue
                    shared_data["l"].value += 1
            # else its a draw
            else: 
                shared_data["d"].value += 1

        # Grab info from the shared data
        games = shared_data["games"].value
        w = shared_data["w"].value
        l = shared_data["l"].value
        d = shared_data["d"].value
        w_red = shared_data["w_red"].value
        l_red = shared_data["l_red"].value

        # Print new WDL
        print("({} vs {}, worker {})".format(eng1.name, eng2.name, process_id), end="")
        print(" Total w-l-d {}-{}-{} ({})".format(w, l, d, games), end="")
        if game_result_type == GAME_RESULT_OUT_OF_TIME:
            print("", eng_to_play.name, "out of time", end="")
        elif game_result_type == GAME_RESULT_ILLEGAL_MOVE:
            print("", eng_to_play.name, "illegal move", end="")
        print()

        # Every rating_interval games, print current sprt results
        if games % rating_interval == 0:
            print("Red w-l {}-{} | Blue w-l {}-{}".format(w_red, l_red, l_red, w_red))
            e1, e2, e3 = sprt.elo_wld(w, l, d)
            print(f"ELO: {round(e2, 1)} +- {round((e3 - e1) / 2, 1)} ({round(e1, 1)}, {round(e3, 1)})")
            llr = sprt.get_llr(w, l, d)
            print(f"LLR: {llr:.3} ({sprt.lower:.3}, {sprt.upper:.3})")
            sprt.print_result(llr)