# Ghislieri Services documentation

For maintainers. Describes the current system (v0.5.x, branch `main`) and the planned rework.

- [architecture.md](architecture.md): processes, RPC between services, data directory, logging.
- [bot/README.md](bot/README.md): how the Telegram bot works (live message, sessions, notifications, permissions).
- [bot/messages.md](bot/messages.md): reference for the JSON `.gsm` message format, with a message inventory.
- Services: [student_databaser](services/student_databaser.md), [calendar_manager](services/calendar_manager.md), [email_service](services/email_service.md), [printer_service](services/printer_service.md), [meals_management](services/meals_management.md), [content_submitter](services/content_submitter.md), [channels_manager](services/channels_manager.md).
- [development.md](development.md): local setup with uv, running in debug mode.
- Rework: [proposal](rework/proposal.md), [stack research](rework/research.md).
