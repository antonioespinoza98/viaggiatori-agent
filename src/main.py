import logging
import sys

from Config.Settings import PROFILES
from Data.SearchOrchestrator import run_all_profiles
from Intelligence.Analyzer import analyze
from Notifications.GmailNotifier import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Flight agent starting — %d profile(s) to process", len(PROFILES))

    results = run_all_profiles(PROFILES)

    for result in results:
        profile_name = result["profile"]
        flights = result["flights"]
        profile = next(p for p in PROFILES if p["name"] == profile_name)

        logger.info("[%s] Analysing %d flights", profile_name, len(flights))

        if not flights:
            logger.warning("[%s] No flights found — skipping analysis", profile_name)
            continue

        analysis = analyze(profile, flights)

        if analysis.get("alert") and analysis.get("best_flight"):
            logger.info("[%s] Alert triggered — sending notification", profile_name)
            send_alert(profile, analysis["best_flight"], analysis)
        else:
            logger.info(
                "[%s] No alert — %s",
                profile_name,
                analysis.get("reason", "no reason provided"),
            )

    logger.info("Flight agent completed")


if __name__ == "__main__":
    main()