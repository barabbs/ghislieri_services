# Features

Who sees what depends on the user's groups (`users.KNOWN_GROUPS`): `student`, `alumnus`, `master` (admins), `tester` (developers), `representative`, `socials_rep`, `calendar.*` (who may add events of a class), and the four academic areas (`sci_tech`, `biomed`, `social_sci`, `human_sci`).

## Signup and accounts

- A new user types `/start`, then surname, name and gender (needed for the canteen lists), checks a recap and confirms. Only then is the account created, with status `pending` and the current academic year as enrollment year. Names are validated, so incomplete accounts cannot exist.
- Admins get a notification with a button to **Admin → Registrazioni**: one entry per pending user, where they can adjust year and gender and approve as student or alumnus, or reject. The user is told the outcome. Admins can keep using the bot while registrations wait.
- On **August 15** students whose enrollment year is 6 or more academic years ago are moved from `student` to `alumnus` (a freshman of September 2019 becomes an alumnus on 2025-08-15). Admins get a silent summary.
- A user who blocks the bot becomes `blocked` and is skipped by notifications; writing to the bot again reactivates them. Admins can `disable` a user, who is then ignored.

## Canteen (Mensa) — students

- **Bookings**: the open days, each with lunch and dinner marked 🟢 booked, 🔴 not booked or ❔ not answered. The first tap books, later taps toggle.
- A day opens for booking at 07:00 on the Monday of the week containing (day − 2 days) — weekends on their own Monday — and closes at 07:00 on the day itself.
- **Reminders** at 12:00 and 19:00 for tomorrow, only to students who have not answered every meal of that day. The 19:00 one replaces the 12:00 one; the reminder disappears as soon as the student has answered, and in any case at 07:00 of the day.
- **Segnalazione**: a complaint with optional photos, sent by email to `master` and `representative` and notified to them.

## Canteen — admins (⚙️ Gestione)

- Upcoming days with booking counts; add a day from a calendar; remove a day (shows how many bookings will be deleted).
- For a day: get the recap PDF in the chat, or send the recap email again.
- **Genera anno accademico**: creates the meal days of the current academic year that are missing (also runs automatically on August 15 for the new year):
  - every Saturday and Sunday from September 8 to July 31;
  - November 1, April 25, June 2, plus the *ponte* day when the holiday is on a Tuesday (the Monday before) or a Thursday (the Friday after);
  - nothing between December 23 and January 6.
  The rules are constants at the top of `meals.py`.
- Every day at 07:00 the recap PDF of today's bookings (by gender, with totals) is emailed to `GS_MEALS_RECAP_TO` and to the admins.

## Calendar

- Day view with previous/next day and a date picker; event details with a link when there is one.
- Users with a `calendar.<class>` group can add events of that class; admins and the event's creator can edit (including marking it cancelled) and delete.
- Every night at 03:00 events are imported from the college website (the feed gives the posts; dates come from each event page). Events created or edited in the bot are never overwritten. Admins can trigger the sync from Admin → Calendario.
- The calendar is exported to `calendar.ics` in the data directory after every change, ready to be published.

## Other menus

- **Stampa**: send a PDF, choose copies, pages, sides and pages per sheet, confirm; printed on the college printer through CUPS.
- **Canali e Gruppi**: links to the college's Telegram channels and groups.
- **Invia Contenuti**: eduroam problem reports (stored, admins notified) and photos for the college's social media (emailed to `master` and `socials_rep`).
- **Impostazioni**: profile (name, surname, email), feedback to the admins, about, changelog.
- **Admin**: registrations, students (filters, search, groups, year, gender, disable, delete), notifications composer (text, target groups, silent or not, expiry, optional button), update announcement, canteen and calendar management.
- **Sviluppo** (`tester` only): recent errors with tracebacks, runtime info, and the unreleased "Prenota servizi" menus and the old Supersega text kept for reference.

## Removed in v1

- Today's canteen menu (the canteen no longer emails it).
- The Facebook → Telegram channel bridge (Facebook removed the API it depended on).
- Log browsing and service statistics in the bot (logs are in journald; errors are alerted and listed in Sviluppo).
