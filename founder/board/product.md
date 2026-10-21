# Product lens
Score: 6/10 | Vote: FUND IF

## What is strong
- The pain is concrete and the "no typing" promise is the right answer to why ledger apps go stale. The product starts from how the owner already behaves (WhatsApp text and voice) instead of asking for new behaviour.
- The capture loop is real and demonstrated end to end: message, understand, confirm card, tap, logged to the khata. Multi-item orders, voice and confirm-before-act all work.
- Confirm-before-act is a sound taste decision for a trust business: the owner stays in control of his own books.
- The core model ("every order has a direction", stock and khata computed from two streams) is simple. If it holds, it removes a whole product (inventory) from the build.
- The one-sentence pitch is clear.

## What would kill it (the top 3, most dangerous first)
1. **The experience has a hole where half the orders are.** The brief says about half of orders arrive by phone call, and call ingestion is not built. If calls never reach the books, the khata and stock are wrong from day one, and wrong books go stale just like the paper diary and the ledger apps. The promise of "never types" is only true if the capture is near complete. This is also the seam between the owner's world (calls) and the system (WhatsApp).
2. **The confirm tap may become the new typing.** With dozens of orders a day, one confirm card per order is a chore at the volume the customer describes. Nothing shows whether owners keep tapping after week two, or whether a card for a clear repeat order is needed at all. Rule 5 (never auto-execute) and "zero typing" are in tension, and the founder has not resolved it.
3. **The headline is not built, and the first five minutes are undefined.** "Ask your business anything in Hindi" is the reason an owner opens the app every morning, yet it does not exist, so the daily-habit goal rests on a feature nobody has seen. Meanwhile the live loop leans on dev-mode workarounds (owner taps do not route back, a 24-hour window for free-form messages, proactive summaries and reminders needing approved templates). No real shop has used it; the database was wiped.

## The questions I would ask the founder
- What is the one thing the product does brilliantly in version one: capture, khata, or answers? What are you willing to cut (collections, lending, network, call ingestion) to get it right?
- Walk me through the first five minutes of a real kirana owner: how does he get connected, does it really need no new number, and when does he first see value without typing anything?
- What happens to the orders that come by phone call before call ingestion exists? Does the owner log them by hand, and does that break the "never types" promise?
- How many confirm taps per day will an owner accept? What share of orders could be a one-tap batch, or pre-confirmed for known repeat customers?
- What accuracy do you get on Hindi/Hinglish voice, item names and quantities on real shop speech, not the 50-message test corpus? Who sees and fixes a wrong order, and how fast?
- When the owner is outside the 24-hour window or a template is missing, what does the owner see? Where else in the flow does a hand-off between WhatsApp, the AI and the database fail visibly?
- Do you own the whole experience, including onboarding, corrections, and the owner's first morning summary, or are those left to whoever deploys it?

## If FUND IF: the conditions
- Real-shop evidence before the money scales: a small pilot (the number of shops and the usage bar are for the founder to propose; I have no number) showing owners still use it in week four with books they trust. Retention data does not exist yet; /founder-consumer is the skill to design that test.
- Close the phone-call gap, or prove with pilot data that the call share is smaller than claimed, so the books are complete enough to trust.
- Ship the "ask in Hindi" answers on top of real captured data, even if narrow (today's sales, who owes me), before spending on lending, collections fees or the network.
- Show the confirm flow at real volume with a measured tap rate and error rate, and a lighter path for repeat orders.
- Unit economics, price and cost per shop are open questions for /founder-cfo; market size and cluster density for /founder-competitors. They are not judged here.
