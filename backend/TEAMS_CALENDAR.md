# Automatic Teams calendar joins

When `MOM@tcgdigital.com` is invited to a Teams meeting, the backend reads that mailbox's Microsoft 365 calendar through Microsoft Graph. It schedules an Attendee bot for the meeting start time, updates the scheduled bot if the invitation changes, and removes it if the invitation is cancelled. For an invitation received after the meeting starts, the bot joins immediately while the event is still active. The existing Attendee webhook stores transcript lines as they arrive. After the bot leaves, the backend generates the MOM and emails it to the organizer if the address is on an allowed domain, otherwise to `DEFAULT_MOM_EMAIL`.

The `tcg-meeting-bot` reference uses Graph only to find recipients for an existing Vexa bot. It has no calendar watcher or incoming Teams call handler.

## Microsoft 365 setup

1. Confirm `MOM@tcgdigital.com` is a Microsoft 365 mailbox in the tenant and that meeting invitations appear on its calendar. A mail alias or SMTP sender address alone is insufficient.
2. In [Microsoft Entra admin center](https://entra.microsoft.com/), open **Entra ID → App registrations → New registration**. Choose **Single tenant** for this organization's mailbox. Record the **Application (client) ID** and **Directory (tenant) ID**.
3. Open the app's **API permissions → Add a permission → Microsoft Graph → Application permissions**. Add `Calendars.Read`, then have an administrator click **Grant admin consent**. The delegated version of `Calendars.Read` is not enough for this backend's client credentials flow. An Exchange administrator can [scope the app to the MOM mailbox](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac).
4. Open **Certificates & secrets → New client secret**. Copy the **Value** immediately. Keep it in `backend/.env`, never in Git or chat.
5. Set these values in `backend/.env`:

   ```dotenv
   MICROSOFT_TENANT_ID=<Directory tenant ID>
   MICROSOFT_CLIENT_ID=<Application client ID>
   MICROSOFT_CLIENT_SECRET=<Client secret Value>
   TEAMS_CALENDAR_MAILBOX=MOM@tcgdigital.com
   TEAMS_CALENDAR_ENABLED=true
   ```

6. Apply `database/migrations/teams_calendar_meetings.sql` after approval and restart the backend. The watcher checks the mailbox every 60 seconds by default and looks up to 28 days ahead. The Attendee service and public `ATTENDEE_WEBHOOK_URL` must also be running.
7. Invite `MOM@tcgdigital.com` to a test Teams meeting starting in a few minutes. Check backend logs for `Scheduled bot for Teams calendar event`, then open `/calendar` in the frontend to see its title, join time, end time, and Teams source. Open the meeting for the live transcript. Admit the bot if the meeting lobby asks. Verify a second calendar check does not create a second bot, then reschedule or cancel a separate test meeting and check the calendar updates.

## Live call participant picker

Adding `MOM@tcgdigital.com` through **Participants → Invite someone** during an unscheduled call is a Teams calling invitation, not necessarily a calendar invitation. The calendar watcher cannot see it. Automatic acceptance of that invite requires a separately registered [Teams calling bot](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/registering-calling-bot) with a public incoming-call webhook and Graph call handling. The current Attendee bot is launched from a meeting URL and cannot act as that Teams identity. For a call already in progress, use **Copy meeting link** and create a meeting in the frontend to send the Attendee bot immediately.

Sources: [Graph calendarView](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview), [Teams calling bots](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/registering-calling-bot), [incoming call notifications](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/call-notifications).
