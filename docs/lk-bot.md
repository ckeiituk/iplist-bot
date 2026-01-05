# Bot LK Plan

## Scope
- Provide a full LK experience inside the Telegram bot.
- Keep the bot as a thin UI and reuse the site API for data and business rules.

## Current State (Implemented)
- Main menu uses inline keyboard and edits a single primary message.
- LK sections: summary, balance, history (pagination), subscriptions, payments, loans.
- "Paid" action creates an admin request in the payment topic.
- Admin buttons call site API to confirm or decline payments.

## Data Model Notes
- Payment statuses: pending, paid, overdue, cancelled.
- Confirming a payment creates credit+debit transactions and sets status to paid.
- Declining keeps the payment due and sets status to pending/overdue based on due_date.

## Admin Flow
1. User taps "Paid" on a pending payment.
2. Bot sends a request to the admin topic with confirm/decline buttons.
3. Admin presses a button; bot calls site API with admin_telegram_id.
4. User receives a notification about the decision.

## API Endpoints Used by Bot
- POST /api/lk
- POST /api/lk/transactions
- POST /api/lk/payments/confirm
- POST /api/lk/payments/decline

## Env/Config Checklist
- bot/.env
  - SITE_API_BASE_URL
  - SITE_API_KEY
  - LK_ADMIN_CHANNEL_ID (example: -1003434221917:42)
- site/.env
  - API_KEY
  - ADMIN_TELEGRAM_IDS (comma-separated Telegram user IDs)

## Next Steps
- Add Remnawave integration as a separate service (keep LK format stable).
- Add LLM router + knowledge base for free-form requests.
- Add tests for history pagination and admin confirm flow.
