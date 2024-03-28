# Adapted from https://github.com/jw1912/SPRT
# Big thanks to jw for the original script

from math import pow, sqrt, log, log10, copysign, pi
from dataclasses import dataclass

class SPRT:
    def __init__(self, elo0: float, elo1: float, alpha: float, beta: float, cutechess_llr: bool):
        self.elo0 = elo0
        self.elo1 = elo1
        self.lower = log(beta / (1 - alpha))
        self.upper = log((1 - beta) / alpha)
        self.cutechess_llr = cutechess_llr

    def expected_score(self, x: float) -> float:
        return 1.0 / (1.0 + pow(10, -x / 400.0))

    def adj_probs(self, elo: float, draw_elo: float) -> tuple[float, float, float]:
        win = self.expected_score(-draw_elo + elo)
        loss = self.expected_score(-draw_elo - elo)
        return win, loss, 1 - win - loss # return w, l, d

    def erf_inv(self, x):
        a = 8 * (pi - 3) / (3 * pi * (4 - pi))
        y = log(1 - x * x)
        z = 2 / (pi * a) + y / 2
        return copysign(sqrt(sqrt(z * z - y / a) - z), x)

    def phi_inv(self, p):
        return sqrt(2) * self.erf_inv(2*p-1)

    def elo(self, score: float) -> float:
        if score <= 0 or score >= 1:
            return 0.0
        return -400 * log10(1 / score - 1)

    def elo_wld(self, wins: float, losses: float, draws: float):
        # win/loss/draw ratio
        N = int(wins + losses + draws)
        if N == 0:
            return (0, 0, 0)

        p_w = wins / N
        p_l = losses / N
        p_d = draws / N

        mu = p_w + p_d/2
        stdev = sqrt(p_w*(1-mu)**2 + p_l*(0-mu)**2 + p_d*(0.5-mu)**2) / sqrt(N)

        # 95% confidence interval for mu
        mu_min = mu + self.phi_inv(0.025) * stdev
        mu_max = mu + self.phi_inv(0.975) * stdev

        return (self.elo(mu_min), self.elo(mu), self.elo(mu_max))

    def scale(self, draw_elo: float) -> float:
        x = pow(10, -draw_elo / 400)
        return 4 * x / pow(1 + x, 2)

    def get_llr(self, wins: float, losses: float, draws: float) -> float:
        if wins == 0 or losses == 0:
            return 0.0

        # Draws are rare in Ataxx
        # so always assume at least 1 draw
        # so we can calculate llr
        if draws == 0:
            draws = 1

        total = wins + draws + losses
        prob_win = wins / total
        prob_loss = losses / total
        prob_draw = draws / total
        draw_elo = 200 * log10((1 - 1 / prob_win) * (1 - 1 / prob_loss))

        # cutechess applies a draw elo based scaling
        s = self.scale(draw_elo) if self.cutechess_llr else 1

        p0 = self.adj_probs(self.elo0 / s, draw_elo)
        p1 = self.adj_probs(self.elo1 / s, draw_elo)

        WIN = 0
        LOSS = 1
        DRAW = 2

        return wins * log(p1[WIN] / p0[WIN]) \
            + losses * log(p1[LOSS] / p0[LOSS]) \
            + draws * log(p1[DRAW] / p0[DRAW])

    def print_result(self, llr):
        if llr >= self.upper:
            print("H1 Accepted")
        elif llr <= self.lower:
            print("H0 Accepted")
        else:
            print("Continue Playing")

