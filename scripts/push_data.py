"""
FÁZIS 5b — Push.
A validált data.candidate.json-t data.json-ra másolja a repo checkoutban,
és a workflow commitolja/pusholja. Ha a candidate nincs meg (validáció bukott),
exit 1.
"""
import os, sys, shutil
from common import DATA_PATH

CANDIDATE = "data.candidate.json"


def main():
    if not os.path.exists(CANDIDATE):
        print("Nincs validált candidate — a push kihagyva.")
        return 1
    shutil.copyfile(CANDIDATE, DATA_PATH)
    print(f"data.json frissítve ({DATA_PATH}). A workflow commitolja.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
