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
    handle_trip_category,
    handle_calendar,
    handle_trip_itinerary,
    handle_transportation_list,
    handle_location_detail,
    handle_location_docs,
    handle_search_go,
    handle_search_text,
    handle_date_go,
    handle_date_text,
    handle_checklist_list,
    handle_checklist_detail,
    handle_checklist_toggle,
    handle_checklist_remove_item,
    handle_checklist_add_go,
    handle_checklist_add_text,
    SEARCHING,
    DATING,
    ADDING_CL_ITEM,
)
from .scheduler_handlers import (
    handle_schedulers_menu,
    handle_scheduler_detail,
    handle_scheduler_toggle,
    handle_scheduler_set_time_go,
    handle_scheduler_set_time_text,
    handle_scheduler_set_tz_go,
    handle_scheduler_set_tz_text,
    _reschedule,
    SETTING_SCHED_TIME,
    SETTING_SCHED_TZ,
)
from .recommendations_handlers import build_reco_conv

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _on_startup(app: Application) -> None:
    _reschedule(app, "checklist_reminder")
    _reschedule(app, "evening_digest")


def build_app(token: str, al_url: str, al_username: str, al_password: str) -> Application:
    client = AdventureLogClient(base_url=al_url, username=al_username, password=al_password)

    app = (
        Application.builder()
        .token(token)
        .post_init(_on_startup)
        .build()
    )
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

    cl_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_checklist_add_go, pattern=r"^cladd:")],
        states={ADDING_CL_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_checklist_add_text)]},
        fallbacks=[CommandHandler("start", start)],
    )

    sched_time_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_scheduler_set_time_go, pattern=r"^sched:settime:")],
        states={SETTING_SCHED_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scheduler_set_time_text)]},
        fallbacks=[CommandHandler("start", start)],
    )

    sched_tz_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_scheduler_set_tz_go, pattern=r"^sched:settz:")],
        states={SETTING_SCHED_TZ: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scheduler_set_tz_text)]},
        fallbacks=[CommandHandler("start", start)],
    )

    reco_conv = build_reco_conv()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedulers", handle_schedulers_menu))
    app.add_handler(search_conv)
    app.add_handler(date_conv)
    app.add_handler(cl_add_conv)
    app.add_handler(sched_time_conv)
    app.add_handler(sched_tz_conv)
    app.add_handler(reco_conv)
    app.add_handler(CallbackQueryHandler(handle_menu, pattern="^menu:main$"))
    app.add_handler(CallbackQueryHandler(handle_trips_list, pattern="^trips:list$"))
    app.add_handler(CallbackQueryHandler(handle_trip_category, pattern=r"^tc:"))
    app.add_handler(CallbackQueryHandler(handle_calendar, pattern=r"^cal:"))
    app.add_handler(CallbackQueryHandler(handle_trip_itinerary, pattern=r"^tl:"))
    app.add_handler(CallbackQueryHandler(handle_transportation_list, pattern=r"^tt:"))
    app.add_handler(CallbackQueryHandler(handle_location_detail, pattern=r"^ld:[^o]"))
    app.add_handler(CallbackQueryHandler(handle_location_docs, pattern=r"^ldoc:"))
    app.add_handler(CallbackQueryHandler(handle_checklist_list, pattern=r"^cllist:"))
    app.add_handler(CallbackQueryHandler(handle_checklist_detail, pattern=r"^cl:"))
    app.add_handler(CallbackQueryHandler(handle_checklist_toggle, pattern=r"^clc:"))
    app.add_handler(CallbackQueryHandler(handle_checklist_remove_item, pattern=r"^clr:"))
    app.add_handler(CallbackQueryHandler(handle_schedulers_menu, pattern=r"^sched:menu$"))
    app.add_handler(CallbackQueryHandler(handle_scheduler_detail, pattern=r"^sched:detail:"))
    app.add_handler(CallbackQueryHandler(handle_scheduler_toggle, pattern=r"^sched:toggle:"))

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
