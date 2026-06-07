import sys

from ecos.common.common import INTEGRATE_AUTO_SCORE, INTEGRATE_CANDIDATE_SCORE


def classify_score(score: float) -> str:
    if score >= INTEGRATE_AUTO_SCORE:
        return "auto"
    if score >= INTEGRATE_CANDIDATE_SCORE:
        return "candidate"
    return "ignore"


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    print({"query": query, "status": classify_score(0.5)})


if __name__ == "__main__":
    main()
