import logging
import os
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .client import AdventureLogClient
from .handlers import (
    start,
    handle_menu,
    handle_trips_list,
    handle_trip_itinerary,
    handle_location_detail,
    handle_location_docs,
    handle_search_go,
    handle_search_text,
    handle_date_go,
    handle_date_text,
    SEARCHING,
    DATING,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_app(token: str, al_url: str, al_username: str, al_password: str) -> Application:
    client = AdventureLogClient(base_url=al_url, username=al_username, password=al_password)

    app = Application.builder().token(token).build()
    app.bot_data["client"] = client

    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_search_go, pattern="^search:go$")],
        states={SEARCHING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text)]},
        fallbacks=[CallbackQueryHandler(handle_menu, pattern="^menu:main$")],
    )

    date_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_date_go, pattern="^date:go$")],
        states={DATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_text)]},
        fallbacks=[CallbackQueryHandler(handle_menu, pattern="^menu:main$")],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(search_conv)
    app.add_handler(date_conv)
    app.add_handler(CallbackQueryHandler(handle_menu, pattern="^menu:main$"))
    app.add_handler(CallbackQueryHandler(handle_trips_list, pattern="^trips:list$"))
    app.add_handler(CallbackQueryHandler(handle_trip_itinerary, pattern=r"^tl:"))
    app.add_handler(CallbackQueryHandler(handle_location_detail, pattern=r"^ld:[^o]"))
    app.add_handler(CallbackQueryHandler(handle_location_docs, pattern=r"^ldoc:"))

    return app


def main() -> None:
    load_dotenv()
    token = os.environ["TELEGRAM_TOKEN"]
    al_url = os.environ["AL_URL"]
    al_username = os.environ["AL_USERNAME"]
    al_password = os.environ["AL_PASSWORD"]

    app = build_app(token, al_url, al_username, al_password)
    logger.info("Starting Adventurebot…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
