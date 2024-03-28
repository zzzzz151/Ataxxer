from sprt_math import SPRT
from worker import worker
import argparse
import signal
import os
import multiprocessing
import random

def split_list(input_list, n):
    sublist_size = len(input_list) // n
    remainder = len(input_list) % n
    start = 0
    result = []

    for i in range(n):
        end = start + sublist_size + (1 if i < remainder else 0)
        result.append(input_list[start:end])
        start = end

    return result

if __name__ == "__main__":

    # Parse args
    parser = argparse.ArgumentParser(description="Ataxxer - run matches and sprt between 2 Ataxx engines")
    parser.add_argument("--engine1", help="Engine 1 exe", type=str, required=True)
    parser.add_argument("--engine2", help="Engine 2 exe", type=str, required=True) 
    parser.add_argument("--concurrency", help="Threads to use", type=int, required=True) 
    parser.add_argument("--tc", help="Time control", type=str, required=True) 
    parser.add_argument("--openings", help="Openings book .txt file", type=str, required=True)
    parser.add_argument("--elo0", help="elo0", type=float, required=True) 
    parser.add_argument("--elo1", help="elo1", type=float, required=True)
    parser.add_argument("--alpha", help="alpha", type=float, required=True)
    parser.add_argument("--beta", help="beta", type=float, required=True)
    parser.add_argument("--cutechess_llr", help="Use Cutechess LLR formula", action="store_true")
    parser.add_argument("--ratinginterval", help="Print current SPRT results every x games", type=int, required=True)
    args = parser.parse_args()

    print()
    print(args.engine1, "vs", args.engine2)
    print("Time control", args.tc, "seconds")
    print("Concurrency", args.concurrency)
    print("Openings book", args.openings)
    print("elo0 {} elo1 {} alpha {} beta {} cutechess_llr {}".format(
        args.elo0, args.elo1, args.alpha, args.beta, args.cutechess_llr))
    print("Rating interval", args.ratinginterval)
    print()

    # Parse time control
    tc_split = args.tc.split("+")
    assert(len(tc_split) <= 2 and len(tc_split) > 0)
    milliseconds = int(float(tc_split[0]) * 1000)
    increment_ms = int(float(tc_split[1]) * 1000) if len(tc_split) == 2 else 0

    # Load openings
    openings_file = open(args.openings, "r")
    openings = openings_file.readlines()
    openings_file.close()
    assert len(openings) >= args.concurrency
    random.shuffle(openings)
    openings_split = split_list(openings, args.concurrency)

    # Create folder 'debug'
    if not os.path.exists("debug"):
        os.makedirs("debug")
    # Delete all files in 'debug' folder
    else:
        for filename in os.listdir("debug"):
            file_path = os.path.join("debug", filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)

    sprt = SPRT(args.elo0, args.elo1, args.alpha, args.beta, args.cutechess_llr)

    # Launch <concurrency> processes/workers
    # Each will launch 2 subprocesses (1 for each engine)
    processes = []
    with multiprocessing.Manager() as manager:
        shared = {
            'games': manager.Value('i', 0),  # Total games finished
            'w': manager.Value('i', 0),      # Engine1 wins
            'l': manager.Value('i', 0),      # Engine1 losses
            'd': manager.Value('i', 0),      # Draws
            'w_red': manager.Value('i', 0),  # Red wins
            'l_red': manager.Value('i', 0),  # Red losses
        }

        for i in range(args.concurrency):
            worker_args = (i+1, args.engine1, args.engine2, shared, milliseconds, increment_ms, 
                          openings_split[i], sprt, args.ratinginterval)
            process = multiprocessing.Process(target=worker, args=worker_args)
            processes.append(process)
            process.start()

        # Wait for the workers to end
        for p in processes:
            p.join()